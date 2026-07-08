"""Tests for the genesis migration (kernel P3).

The genesis migration walks the Python DOMAINS in a fixed order and pushes one
add_node record per node (51) and one add_edge per operator (49) into a fresh
store, with a FIXED genesis date, then freezes the resulting version hash into
map/GENESIS. Determinism is the acceptance property: running the migration into
two separate directories must produce byte-identical log.jsonl and the same
genesis hash, and the replayed materialized view must equal the graph the
Python layer generates today.
"""
from __future__ import annotations

from pathlib import Path

from omai.genesis import (
    GENESIS_AUTHOR,
    GENESIS_DATE,
    genesis_records,
    run_genesis,
)
from omai.store import Store


def _live_uid_sets():
    """The node and edge uid sets computed live from DOMAINS via identity,
    deduped by uid exactly as the migration dedupes (first occurrence wins)."""
    from omai.map_data import DOMAINS
    from omai.operator.identity import edge_id, node_id, parameter_node_id

    node_uids: set[str] = set()
    for d in DOMAINS:
        for s in d.nodes:
            node_uids.add(node_id(s))
    for d in DOMAINS:
        for pid, _sym, _obj, *rest in d.param_promotions:
            node_uids.add(parameter_node_id(pid, rest[0] if rest else None))

    edge_uids: set[str] = set()
    for d in DOMAINS:
        for op in d.edges:
            edge_uids.add(edge_id(op, node_id))
    return node_uids, edge_uids


def test_genesis_date_is_the_frozen_constant():
    assert GENESIS_DATE == "2026-07-07"
    assert GENESIS_AUTHOR == "genesis"


def test_run_genesis_materializes_every_live_domain_node_and_edge(tmp_path):
    """run_genesis is now a historical migration TOOL, not a genesis-era
    snapshot: it replays the live DOMAINS. The store it builds must hold one
    node/edge per deduped live element (55 nodes + 52 edges once the DFT
    ground-state domain joined thermal + materials; 51 + 49 at genesis). The
    frozen-prefix invariant lives in test_committed_genesis_is_the_frozen_prefix;
    the Python-vs-committed-store drift alarm lives in test_sync.py."""
    # Counts derive from the live domain set, so the next domain does not
    # re-break this test.
    ops = [op for op, _payload, _reason in genesis_records()]
    run_genesis(tmp_path)
    m = Store(tmp_path).read()
    assert len(m["nodes"]) == ops.count("add_node")
    assert len(m["edges"]) == ops.count("add_edge")


def test_genesis_uid_sets_equal_live_identity(tmp_path):
    run_genesis(tmp_path)
    m = Store(tmp_path).read()
    node_uids, edge_uids = _live_uid_sets()
    assert set(m["nodes"]) == node_uids
    assert set(m["edges"]) == edge_uids


def test_genesis_store_verifies_clean(tmp_path):
    run_genesis(tmp_path)
    assert Store(tmp_path).verify() == []


def test_genesis_is_byte_identical_across_two_dirs(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    ha = run_genesis(a)
    hb = run_genesis(b)
    assert ha == hb, "genesis hash must be reproducible"
    assert (a / "log.jsonl").read_bytes() == (b / "log.jsonl").read_bytes()
    assert (a / "GENESIS").read_text().strip() == ha
    assert (b / "GENESIS").read_text().strip() == hb


def test_genesis_hash_is_head_and_64_hex(tmp_path):
    h = run_genesis(tmp_path)
    s = Store(tmp_path)
    assert h == s.head
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_genesis_records_deterministic_order_and_count():
    recs = genesis_records()
    ops = [op for op, _payload, _reason in recs]
    # Counts derive from the live domain set (51 + 49 at genesis; 55 + 52 with
    # the DFT ground-state domain), so the next domain does not re-break this
    # test; the invariant is one add_node per deduped live node, one add_edge
    # per deduped live edge, nodes emitted before edges.
    node_uids, edge_uids = _live_uid_sets()
    assert ops.count("add_node") == len(node_uids)
    assert ops.count("add_edge") == len(edge_uids)
    assert ops == sorted(ops, key=lambda o: 0 if o == "add_node" else 1)
    # Deterministic: two calls produce identical structure.
    recs2 = genesis_records()
    assert [(op, p["uid"]) for op, p, _ in recs] == \
           [(op, p["uid"]) for op, p, _ in recs2]


def test_every_node_entry_carries_full_meta(tmp_path):
    run_genesis(tmp_path)
    nodes = Store(tmp_path).read()["nodes"]
    for uid, entry in nodes.items():
        meta = entry["meta"]
        for key in ("name", "symbol", "description", "tier"):
            assert key in meta, f"node {uid[:12]} missing meta.{key}"
        assert meta["name"], f"node {uid[:12]} has empty name"
        assert meta["symbol"], f"node {uid[:12]} has empty symbol"


def test_every_edge_entry_carries_formula_srepr(tmp_path):
    run_genesis(tmp_path)
    edges = Store(tmp_path).read()["edges"]
    for uid, entry in edges.items():
        assert "formula_srepr" in entry["meta"], f"edge {uid[:12]} missing srepr"
        assert "formula_latex" in entry["meta"], f"edge {uid[:12]} missing latex"
        assert "schemes" in entry["meta"]


def test_heat_capacity_edge_srepr_matches_live_operator(tmp_path):
    """Spot-check: the frozen store's compute_heat_capacity edge carries the
    same formula fingerprint the live operator produces."""
    from omai.map_data import DOMAINS
    from omai.operator.identity import edge_id, formula_fingerprint, node_id

    hc = None
    for d in DOMAINS:
        for op in d.edges:
            if op.name == "compute_heat_capacity":
                hc = op
    assert hc is not None, "compute_heat_capacity not found in DOMAINS"

    run_genesis(tmp_path)
    edges = Store(tmp_path).read()["edges"]
    entry = edges[edge_id(hc, node_id)]
    assert entry["meta"]["name"] == "compute_heat_capacity"
    assert entry["meta"]["formula_srepr"] == formula_fingerprint(hc.formula)


def test_genesis_records_are_data_only_no_domain_objects():
    """A payload must be JSON-serializable (identity dicts + strings), so the
    store is rebuildable from the log without importing domain modules."""
    import json
    for op, payload, reason in genesis_records():
        json.dumps(payload)  # raises TypeError if a Space/Operator leaked in
        assert isinstance(reason, str)


# --------------------------------------------------------------------------
# Repo-state drift alarm: the committed map/ matches the code.
# --------------------------------------------------------------------------

_REPO_MAP = Path(__file__).resolve().parents[1] / "map"


def test_committed_map_verifies_clean():
    """The committed map/ replays and matches its own materialized view."""
    assert Store(_REPO_MAP).verify() == []


def test_committed_genesis_is_the_frozen_prefix():
    """The frozen-prefix property: replaying the FIRST 100 committed log
    records (the genesis contribution) reproduces map/GENESIS exactly.

    This replaced the original fresh-migration equality when the first
    post-genesis record landed (2026-07-08, an edit_meta on
    BareDynamicalMatrix's display symbol): the store now legitimately
    extends past genesis, so a fresh run_genesis over the LIVE domains
    need not equal the frozen hash. Genesis is history, not head. The
    Python-vs-store drift alarm is the sync-clean test
    (tests/test_sync.py), which compares against the head."""
    import json

    committed = (_REPO_MAP / "GENESIS").read_text().strip()
    lines = (_REPO_MAP / "log.jsonl").read_text().splitlines()
    assert len(lines) >= 100, "genesis contribution incomplete"
    record_100 = json.loads(lines[99])
    assert record_100["version"] == committed
