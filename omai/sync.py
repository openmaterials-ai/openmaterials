"""The sync tool (kernel P4): propose store change records from the Python layer.

The Python operator modules stay the authoring surface for the existing domains.
``compute_sync`` diffs the live ``DOMAINS`` (through the exact payload builder
the genesis migration uses) against the materialized store view and proposes
change records; the CLI prints them by default and can apply the safe ones
behind ``--apply``. It is the bidirectional drift alarm between the code and the
frozen store: on the pristine repo the two agree exactly and every bucket is
empty.

Diff semantics:

* **add**       a Python-side element whose uid is absent from the store.
* **edit_meta** the same uid with differing metadata (name / symbol /
  description / tier for nodes; name / description / formula_srepr /
  formula_latex / schemes for edges), carrying only the changed keys. Because
  the formula fingerprint is part of the edge identity, two elements sharing a
  uid necessarily share a formula, so a formula change never surfaces here.
* **re_mint**   a store element whose uid no longer exists Python-side that
  pairs with a new (added) Python-side element of the same kind and anchor
  (a node's quantity tag; an edge's primary output node). Identity content
  changed: this is reported, never auto-applied, because a re-mint must be a
  deliberate ``supersede`` record.
* **deprecate** a store element whose uid no longer exists Python-side and has
  no re-mint pair.

Determinism: no clock or randomness. ``--apply`` takes the date from the caller.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from omai.genesis import genesis_records
from omai.store import Store

__all__ = ["compute_sync", "main"]

# The committed store root. Tests monkeypatch this to run the CLI against a
# throwaway store; compute_sync itself takes the materialized view as an
# argument and never reads a path.
_STORE_ROOT = Path("map")

# Meta keys that participate in the edit_meta diff, per element kind.
_NODE_META_KEYS = ("name", "symbol", "description", "tier")
_EDGE_META_KEYS = ("name", "description", "formula_srepr", "formula_latex",
                   "schemes")


def _python_side() -> tuple[dict[str, dict], dict[str, dict]]:
    """The live Python-side view as ``(nodes, edges)`` uid -> payload maps.

    Built from ``genesis_records()``, the single deterministic payload builder
    that walks ``DOMAINS``; this is exactly what the store was born from, so the
    diff against the committed store is precise.
    """
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for op, payload, _reason in genesis_records():
        if op == "add_node":
            nodes.setdefault(payload["uid"], payload)
        elif op == "add_edge":
            edges.setdefault(payload["uid"], payload)
    return nodes, edges


def _node_anchor(entry: dict) -> tuple:
    """Re-mint pairing anchor for a node: its quantity tag."""
    return ("node", entry.get("identity", {}).get("quantity"))


def _edge_anchor(entry: dict) -> tuple:
    """Re-mint pairing anchor for an edge: its primary output node uid.

    Stable across a formula change (the formula fingerprint changes, so the
    edge uid changes, but the output node it produces is the same), which is
    what makes the old / new edge pair recognisable as a re-mint.
    """
    return ("edge", entry.get("identity", {}).get("output"))


def _meta_diff(py_meta: dict, store_meta: dict, keys) -> dict:
    """The subset of ``keys`` whose Python value differs from the store value."""
    changed: dict = {}
    for k in keys:
        if py_meta.get(k) != store_meta.get(k):
            changed[k] = py_meta.get(k)
    return changed


def compute_sync(current: dict) -> dict:
    """Diff the live Python operator layer against ``current`` (a store view).

    Returns ``{"add": [...], "edit_meta": [...], "deprecate": [...],
    "re_mint": [...]}``. ``add`` / ``edit_meta`` / ``deprecate`` entries are
    ``{"op", "payload"}`` change records; ``re_mint`` entries are
    ``{"old_uid", "new_uid", "name", "why"}`` reports.
    """
    py_nodes, py_edges = _python_side()
    store_nodes = current.get("nodes", {})
    store_edges = current.get("edges", {})

    edit_meta: list[dict] = []
    deprecate: list[dict] = []
    re_mint: list[dict] = []

    # First pass: new (unmatched) Python-side uids and metadata edits, keeping a
    # by-anchor index of the new uids so unmatched store elements can pair.
    new_py: dict[str, tuple[str, dict]] = {}  # uid -> (op, payload)
    new_by_anchor: dict[tuple, list[str]] = {}
    for kind, py, store, meta_keys, anchor_of in (
            ("add_node", py_nodes, store_nodes, _NODE_META_KEYS, _node_anchor),
            ("add_edge", py_edges, store_edges, _EDGE_META_KEYS, _edge_anchor)):
        for uid, payload in py.items():
            if uid not in store:
                new_py[uid] = (kind, payload)
                new_by_anchor.setdefault(anchor_of(payload), []).append(uid)
            else:
                changed = _meta_diff(payload["meta"], store[uid].get("meta", {}),
                                     meta_keys)
                if changed:
                    edit_meta.append({"op": "edit_meta",
                                      "payload": {"uid": uid, "meta": changed}})

    # Second pass: unmatched store elements pair with a new Python-side element
    # of the same kind + anchor as a re_mint (identity content changed: report,
    # never auto-apply), else deprecate. A new uid consumed by a re_mint is
    # claimed so it is NOT also emitted as a bare add: landing it is the job of
    # the human-written supersede, not of --apply.
    #
    # A store entry already carrying ``superseded_by`` (or ``deprecated``) is
    # skipped: it is an intentionally-retired identity whose successor already
    # landed, so the live Python layer legitimately no longer produces it. Without
    # this skip a completed supersede would forever re-surface the retired old edge
    # as a re_mint / deprecate and the store could never return to "in sync". This
    # is what makes the map's supersede flow converge: propose the new edge, write
    # the supersede tying old -> new, and thereafter sync sees the old edge as
    # retired and stays clean.
    claimed_new: set[str] = set()
    for store, py, anchor_of in ((store_nodes, py_nodes, _node_anchor),
                                 (store_edges, py_edges, _edge_anchor)):
        for uid, entry in store.items():
            if uid in py:
                continue
            if entry.get("superseded_by") or entry.get("deprecated"):
                continue
            candidates = [u for u in new_by_anchor.get(anchor_of(entry), [])
                          if u not in claimed_new]
            if candidates:
                new_uid = candidates[0]
                claimed_new.add(new_uid)
                re_mint.append({
                    "old_uid": uid,
                    "new_uid": new_uid,
                    "name": (entry.get("meta", {}).get("name")
                             or new_py[new_uid][1]["meta"].get("name")),
                    "why": "identity content changed",
                })
            else:
                deprecate.append({
                    "op": "deprecate",
                    "payload": {"uid": uid,
                                "note": "no longer produced by the Python layer"},
                })

    # Remaining new Python-side uids (not claimed by a re_mint) are adds.
    add = [{"op": op, "payload": payload}
           for uid, (op, payload) in new_py.items() if uid not in claimed_new]

    return {"add": add, "edit_meta": edit_meta, "deprecate": deprecate,
            "re_mint": re_mint}


def _summarize(proposal: dict) -> list[str]:
    """One-liner per proposed record, grouped by bucket."""
    lines: list[str] = []
    for r in proposal["add"]:
        p = r["payload"]
        lines.append(f"add        {r['op']:9s} {p['uid'][:12]} "
                     f"{p['meta'].get('name', '')}")
    for r in proposal["edit_meta"]:
        p = r["payload"]
        lines.append(f"edit_meta  {p['uid'][:12]} keys={sorted(p['meta'])}")
    for r in proposal["deprecate"]:
        p = r["payload"]
        lines.append(f"deprecate  {p['uid'][:12]}")
    for r in proposal["re_mint"]:
        lines.append(f"re_mint    {r['old_uid'][:12]} -> {r['new_uid'][:12]} "
                     f"{r['name']} ({r['why']})")
    return lines


def main(argv=None) -> int:
    """CLI: ``python -m omai.sync [--apply --author A --date D --reason R]``.

    Default (dry run): print the proposal summary (counts plus one line per
    record); exit 0 if there are no proposals, 2 if there are.

    ``--apply``: push the additions and metadata edits through
    ``Store.propose`` (the gates run). Re-mints are never applied: if any exist,
    print instructions to write an explicit ``supersede`` record and exit 3
    without applying anything.
    """
    parser = argparse.ArgumentParser(prog="omai.sync")
    parser.add_argument("--apply", action="store_true",
                        help="apply additions and metadata edits (gated)")
    parser.add_argument("--author")
    parser.add_argument("--date")
    parser.add_argument("--reason", default="sync from the Python operator layer")
    args = parser.parse_args(argv)

    store = Store(_STORE_ROOT)
    proposal = compute_sync(store.read())
    counts = {k: len(v) for k, v in proposal.items()}
    total = sum(counts.values())

    if total == 0:
        print("in sync: the Python operator layer and the store agree "
              "(0 add, 0 edit_meta, 0 deprecate, 0 re_mint)")
        return 0

    print(f"proposals: {counts['add']} add, {counts['edit_meta']} edit_meta, "
          f"{counts['deprecate']} deprecate, {counts['re_mint']} re_mint")
    for line in _summarize(proposal):
        print("  " + line)

    if not args.apply:
        return 2

    if proposal["re_mint"]:
        print("\nrefusing to apply: this proposal contains re-mints (identity "
              "content changed). A re-mint must be a deliberate supersede "
              "record. Write an explicit supersede tying each old_uid to its "
              "new_uid, then re-run --apply on the remaining add / edit_meta:")
        for r in proposal["re_mint"]:
            print(f"  supersede old_uid={r['old_uid'][:12]} "
                  f"new_uid={r['new_uid'][:12]} ({r['name']})")
        return 3

    if not (args.author and args.date):
        print("--apply requires --author and --date")
        return 2

    records = proposal["add"] + proposal["edit_meta"]
    store.propose(records, author=args.author, date=args.date,
                  reason_prefix=args.reason)
    print(f"applied {len(records)} records; head is now {store.head[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
