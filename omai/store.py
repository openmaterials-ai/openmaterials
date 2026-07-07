"""The log-first versioned map store (kernel P3).

The map's source of truth is data, not Python: an append-only change log
(`log.jsonl`) plus a materialized current view (`current/nodes.json`,
`current/edges.json`) regenerated on every push, and a frozen genesis hash
(`GENESIS`). This module is the record / log / materialize / verify machinery
over a store directory.

Determinism is the load-bearing property. Every version hash is a pure
function of the record's content and the previous version hash (see
`omai.operator.identity.version_hash`); nothing here reads the clock or any
source of randomness. Dates always arrive from the caller.

The store is rebuildable from `log.jsonl` alone, without importing any omai
domain module: a record's payload carries the full identity dict and (for
edges) the formula srepr and display latex inline. `read()` replays the log;
`current/` is only a convenience mirror that `verify()` checks against the
replay.

Record shape (one canonical-JSON line per record in `log.jsonl`):

    {"seq", "op", "payload", "author", "date", "reason", "prev", "version"}

with `version = version_hash(prev, {every field except version})` and
`prev` = the previous record's version (genesis prev = 64 zeros).
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.operator.identity import canonical_json, version_hash

__all__ = ["CHANGE_OPS", "GENESIS_PREV", "Store", "make_record"]

CHANGE_OPS = ("add_node", "add_edge", "edit_meta", "deprecate", "supersede",
              "equate")

# The prev of the genesis record: 64 hex zeros.
GENESIS_PREV = "0" * 64


def make_record(*, seq, op, payload, author, date, reason, prev) -> dict:
    """Build one change record with its chained version hash.

    The version is `version_hash(prev, record-without-version)`: a sha256 over
    prev concatenated with the canonical JSON of every other field. Because the
    JSON is canonical and no field is a clock read, the hash is reproducible
    across processes and runs.
    """
    if op not in CHANGE_OPS:
        raise ValueError(f"unknown op {op!r}; must be one of {CHANGE_OPS}")
    record = {
        "seq": seq,
        "op": op,
        "payload": payload,
        "author": author,
        "date": date,
        "reason": reason,
        "prev": prev,
    }
    record["version"] = version_hash(prev, record)
    return record


def _apply(record: dict, nodes: dict, edges: dict, problems: list[str] | None) -> None:
    """Apply one record to the (nodes, edges) accumulator in place.

    A non-add op that references an unknown uid is a no-op for materialization
    (the mutation simply has nothing to touch): validation gates on push are
    out of scope until P4, so push never rejects such a record. When `problems`
    is not None the replay is in verify mode, and the same condition also
    appends a human-readable problem so verify() reports the dangling reference.
    """
    op = record["op"]
    payload = record["payload"]

    if op == "add_node":
        nodes[payload["uid"]] = {"uid": payload["uid"],
                                 "identity": payload["identity"],
                                 "meta": dict(payload["meta"])}
        return
    if op == "add_edge":
        edges[payload["uid"]] = {"uid": payload["uid"],
                                 "identity": payload["identity"],
                                 "meta": dict(payload["meta"])}
        return

    # Every remaining op targets existing entries by uid.
    def _entries_for(uid: str):
        if uid in nodes:
            return nodes[uid]
        if uid in edges:
            return edges[uid]
        return None

    def _missing(uid: str, what: str) -> bool:
        if _entries_for(uid) is None:
            if problems is not None:
                problems.append(
                    f"seq {record['seq']} {op}: unknown uid {uid[:12]} "
                    f"({what})")
            return True
        return False

    if op == "edit_meta":
        uid = payload["uid"]
        if _missing(uid, "edit_meta target"):
            return
        _entries_for(uid)["meta"].update(payload["meta"])
        return

    if op == "deprecate":
        uid = payload["uid"]
        if _missing(uid, "deprecate target"):
            return
        entry = _entries_for(uid)
        entry["deprecated"] = True
        entry["deprecation_note"] = payload.get("note")
        return

    if op == "supersede":
        new_uids = payload["new_uids"]
        for uid in payload["old_uids"]:
            if _missing(uid, "supersede old_uid"):
                continue
            _entries_for(uid)["superseded_by"] = list(new_uids)
        return

    if op == "equate":
        uids = payload["uids"]
        for uid in uids:
            if _missing(uid, "equate uid"):
                continue
            _entries_for(uid)["equivalent_to"] = list(uids)
        return

    # make_record / push already guard op membership; this is defensive.
    raise ValueError(f"unknown op {op!r}")


class Store:
    """An append-only change log with a materialized current view.

    ``root/log.jsonl`` is the log (one canonical-JSON record per line);
    ``root/current/{nodes,edges}.json`` is the materialized view, rewritten
    on every push and never hand-edited; ``root/GENESIS`` holds the frozen
    genesis version hash (written by the genesis migration, not by this class).
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.log_path = self.root / "log.jsonl"
        self.current_dir = self.root / "current"
        self.genesis_path = self.root / "GENESIS"

    # -- log access -------------------------------------------------------

    def _records(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(line)
                for line in self.log_path.read_text().splitlines() if line]

    @property
    def head(self) -> str:
        """The last version hash, or 64 zeros when the log is empty."""
        recs = self._records()
        return recs[-1]["version"] if recs else GENESIS_PREV

    # -- push -------------------------------------------------------------

    def push(self, op, payload, author, date, reason) -> str:
        """Append one record, rematerialize current/, return the new version."""
        if op not in CHANGE_OPS:
            raise ValueError(f"unknown op {op!r}; must be one of {CHANGE_OPS}")
        recs = self._records()
        seq = (recs[-1]["seq"] + 1) if recs else 1
        prev = recs[-1]["version"] if recs else GENESIS_PREV
        record = make_record(seq=seq, op=op, payload=payload, author=author,
                             date=date, reason=reason, prev=prev)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as fh:
            fh.write(canonical_json(record) + "\n")
        self._materialize(recs + [record])
        return record["version"]

    def _materialize(self, records: list[dict]) -> None:
        nodes, edges = self._replay(records, problems=None)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        (self.current_dir / "nodes.json").write_text(
            json.dumps(nodes, sort_keys=True, indent=1))
        (self.current_dir / "edges.json").write_text(
            json.dumps(edges, sort_keys=True, indent=1))

    # -- replay / read ----------------------------------------------------

    def _replay(self, records: list[dict], *, problems: list[str] | None
                ) -> tuple[dict, dict]:
        nodes: dict = {}
        edges: dict = {}
        for record in records:
            _apply(record, nodes, edges, problems)
        return nodes, edges

    def read(self, version: str | None = None) -> dict:
        """Return {"nodes": {uid: entry}, "edges": {uid: entry}}.

        With ``version`` given, replay up to and including the record whose
        version matches (unknown version raises ValueError). Without it, replay
        the whole log.
        """
        recs = self._records()
        if version is not None:
            idx = next((i for i, r in enumerate(recs)
                        if r["version"] == version), None)
            if idx is None:
                raise ValueError(f"unknown version {version}")
            recs = recs[: idx + 1]
        nodes, edges = self._replay(recs, problems=None)
        return {"nodes": nodes, "edges": edges}

    # -- diff -------------------------------------------------------------

    def diff(self, a: str, b: str) -> list[dict]:
        """Records strictly after version ``a``, up to and including ``b``.

        ``a`` may be the genesis prev (64 zeros) to mean "from the start".
        """
        recs = self._records()
        if a == GENESIS_PREV:
            start = 0
        else:
            ai = next((i for i, r in enumerate(recs) if r["version"] == a), None)
            if ai is None:
                raise ValueError(f"unknown version {a}")
            start = ai + 1
        bi = next((i for i, r in enumerate(recs) if r["version"] == b), None)
        if bi is None:
            raise ValueError(f"unknown version {b}")
        return recs[start: bi + 1]

    # -- verify -----------------------------------------------------------

    def verify(self) -> list[str]:
        """Return a list of human-readable problems; empty when clean.

        Checks, in order: every record's version recomputes from its fields and
        prev; the chain links (record N's prev == record N-1's version, genesis
        prev == 64 zeros); seq is dense 1..N; every non-add op references a
        known uid; and the replayed view equals current/ on disk (structural,
        parsed-JSON equality, not textual).
        """
        problems: list[str] = []
        recs = self._records()

        # Hash chain + recomputed versions + dense seq.
        expected_prev = GENESIS_PREV
        for i, rec in enumerate(recs):
            unversioned = {k: v for k, v in rec.items() if k != "version"}
            recomputed = version_hash(rec["prev"], unversioned)
            if recomputed != rec.get("version"):
                problems.append(
                    f"seq {rec.get('seq')}: version hash mismatch "
                    f"(stored {str(rec.get('version'))[:12]}, "
                    f"recomputed {recomputed[:12]}), tampered record")
            if rec.get("prev") != expected_prev:
                problems.append(
                    f"seq {rec.get('seq')}: broken chain "
                    f"(prev {str(rec.get('prev'))[:12]}, "
                    f"expected {expected_prev[:12]})")
            if rec.get("seq") != i + 1:
                problems.append(
                    f"record {i}: seq {rec.get('seq')} is not dense "
                    f"(expected {i + 1})")
            expected_prev = rec.get("version")

        # Non-add ops reference known uids; capture replay problems.
        replay_nodes, replay_edges = self._replay(recs, problems=problems)

        # Materialized view matches the replay (structural equality).
        for fname, replayed in (("nodes.json", replay_nodes),
                                ("edges.json", replay_edges)):
            path = self.current_dir / fname
            if not path.exists():
                problems.append(f"current/{fname} is missing")
                continue
            try:
                on_disk = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                problems.append(f"current/{fname} is not valid JSON: {exc}")
                continue
            if on_disk != replayed:
                problems.append(
                    f"current/{fname} does not match the replayed materialized "
                    f"view (stale or truncated)")

        return problems
