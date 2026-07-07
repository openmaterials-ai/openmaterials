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


def test_run_genesis_yields_51_nodes_and_49_edges(tmp_path):
    run_genesis(tmp_path)
    m = Store(tmp_path).read()
    assert len(m["nodes"]) == 51
    assert len(m["edges"]) == 49


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
    assert ops.count("add_node") == 51
    assert ops.count("add_edge") == 49
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


def test_committed_genesis_matches_a_fresh_migration(tmp_path):
    """The frozen map/GENESIS equals the hash of a fresh run_genesis. This is
    the drift alarm between the Python authoring layer and the committed store:
    a change to any node/edge identity (or the migration order) that is not
    re-frozen fails here."""
    committed = (_REPO_MAP / "GENESIS").read_text().strip()
    fresh = run_genesis(tmp_path)
    assert committed == fresh
