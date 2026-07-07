"""Tests for the log-first store (kernel P3).

The store is an append-only change log with a chained version hash, a
materialized current view, and verify(). Determinism is load-bearing: every
version hash is a pure function of the record content and the prev hash, so a
record's version never depends on wall-clock time or ordering beyond the
explicit seq/prev chain. Dates always come from the caller.

The store must be rebuildable from log.jsonl alone: these tests never import
omai domain modules; they push synthetic identity dicts and formula strings
inline, exactly the shape the genesis migration will emit.
"""
from __future__ import annotations

import json

import pytest

from omai.operator.identity import canonical_json, version_hash
from omai.store import CHANGE_OPS, Store, make_record

GENESIS_PREV = "0" * 64


# --------------------------------------------------------------------------
# Synthetic payloads (no domain imports): identity dicts inline.
# --------------------------------------------------------------------------

def _node_payload(uid, name, symbol="x", tier="Sources"):
    return {
        "uid": uid,
        "identity": {"node": {"quantity": name.lower(), "fields": [],
                              "gauge": "observable", "labels": {}}},
        "meta": {"name": name, "symbol": symbol,
                 "description": f"the {name}", "tier": tier},
    }


def _edge_payload(uid, name, out_uid, in_uid):
    return {
        "uid": uid,
        "identity": {"edge": {"output": out_uid, "outputs": [out_uid],
                             "inputs": [in_uid], "formula": "none", "schemes": {}}},
        "meta": {"name": name, "description": f"produces via {name}",
                 "formula_srepr": "Symbol('a')", "formula_latex": "a",
                 "schemes": {}},
    }


NODE_A = _node_payload("a" * 64, "Alpha")
NODE_B = _node_payload("b" * 64, "Beta")
EDGE_AB = _edge_payload("e" * 64, "make_beta", "b" * 64, "a" * 64)


# --------------------------------------------------------------------------
# make_record: version is version_hash(prev, {all fields except version}).
# --------------------------------------------------------------------------

def test_make_record_shape_and_version():
    rec = make_record(seq=1, op="add_node", payload=NODE_A, author="genesis",
                       date="2026-07-07", reason="genesis", prev=GENESIS_PREV)
    assert set(rec) == {"seq", "op", "payload", "author", "date", "reason",
                        "prev", "version"}
    unversioned = {k: v for k, v in rec.items() if k != "version"}
    assert rec["version"] == version_hash(GENESIS_PREV, unversioned)
    assert len(rec["version"]) == 64


def test_make_record_rejects_unknown_op():
    with pytest.raises(ValueError):
        make_record(seq=1, op="frobnicate", payload={}, author="a",
                    date="2026-07-07", reason="r", prev=GENESIS_PREV)


# --------------------------------------------------------------------------
# push / head / chain: three synthetic records with fixed dates. Version of
# record 2 depends on record 1.
# --------------------------------------------------------------------------

def test_head_empty_store_is_zeros(tmp_path):
    s = Store(tmp_path)
    assert s.head == GENESIS_PREV


def test_push_returns_version_and_advances_head(tmp_path):
    s = Store(tmp_path)
    v1 = s.push("add_node", NODE_A, "genesis", "2026-07-07", "add alpha")
    assert s.head == v1
    v2 = s.push("add_node", NODE_B, "genesis", "2026-07-07", "add beta")
    assert s.head == v2
    assert v1 != v2


def test_chain_record2_depends_on_record1(tmp_path):
    s = Store(tmp_path)
    v1 = s.push("add_node", NODE_A, "genesis", "2026-07-07", "add alpha")
    v2 = s.push("add_edge", EDGE_AB, "genesis", "2026-07-07", "add edge")
    # v2 is version_hash(v1, record2-without-version): recompute it.
    log = [json.loads(ln) for ln in (tmp_path / "log.jsonl").read_text().splitlines()]
    rec2 = log[1]
    assert rec2["prev"] == v1
    unversioned = {k: v for k, v in rec2.items() if k != "version"}
    assert v2 == version_hash(v1, unversioned)


def test_genesis_record_prev_is_zeros(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "add alpha")
    log = [json.loads(ln) for ln in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert log[0]["prev"] == GENESIS_PREV
    assert log[0]["seq"] == 1


def test_log_lines_are_canonical_json(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "add alpha")
    line = (tmp_path / "log.jsonl").read_text().splitlines()[0]
    rec = json.loads(line)
    assert line == canonical_json(rec)


def test_push_rejects_unknown_op(tmp_path):
    s = Store(tmp_path)
    with pytest.raises(ValueError):
        s.push("frobnicate", {}, "a", "2026-07-07", "r")


# --------------------------------------------------------------------------
# read(): full and at-version.
# --------------------------------------------------------------------------

def test_read_full_has_nodes_and_edges_keyed_by_uid(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    s.push("add_edge", EDGE_AB, "genesis", "2026-07-07", "e")
    m = s.read()
    assert set(m["nodes"]) == {"a" * 64, "b" * 64}
    assert set(m["edges"]) == {"e" * 64}
    assert m["nodes"]["a" * 64]["meta"]["name"] == "Alpha"
    assert m["nodes"]["a" * 64]["identity"] == NODE_A["identity"]


def test_read_at_version_replays_up_to_that_record(tmp_path):
    s = Store(tmp_path)
    v1 = s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    m1 = s.read(v1)
    assert set(m1["nodes"]) == {"a" * 64}
    assert "b" * 64 not in m1["nodes"]


def test_read_unknown_version_raises(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    with pytest.raises(ValueError):
        s.read("f" * 64)


# --------------------------------------------------------------------------
# diff(a, b): records strictly after a, up to and including b.
# --------------------------------------------------------------------------

def test_diff_exact_slice(tmp_path):
    s = Store(tmp_path)
    v1 = s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    v2 = s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    v3 = s.push("add_edge", EDGE_AB, "genesis", "2026-07-07", "e")
    recs = s.diff(v1, v3)
    assert [r["version"] for r in recs] == [v2, v3]
    # a==b yields empty
    assert s.diff(v3, v3) == []
    # from genesis (all)
    assert [r["version"] for r in s.diff(GENESIS_PREV, v3)] == [v1, v2, v3]


# --------------------------------------------------------------------------
# verify(): clean, then reports on three tamper cases.
# --------------------------------------------------------------------------

def _good_store(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    s.push("add_edge", EDGE_AB, "genesis", "2026-07-07", "e")
    return s


def test_verify_clean_on_good_store(tmp_path):
    s = _good_store(tmp_path)
    assert s.verify() == []


def test_verify_reports_tampered_payload_line(tmp_path):
    s = _good_store(tmp_path)
    log_path = tmp_path / "log.jsonl"
    lines = log_path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["meta"]["name"] = "Tampered"  # changed content, stale version
    lines[0] = canonical_json(rec)
    log_path.write_text("\n".join(lines) + "\n")
    problems = Store(tmp_path).verify()
    assert problems, "tampered payload must be reported"
    assert any("version" in p.lower() or "hash" in p.lower() for p in problems)


def test_verify_reports_truncated_current_file(tmp_path):
    s = _good_store(tmp_path)
    # Drop a node from the materialized view: current/ no longer matches replay.
    nodes_path = tmp_path / "current" / "nodes.json"
    nodes = json.loads(nodes_path.read_text())
    nodes.pop("a" * 64)
    nodes_path.write_text(json.dumps(nodes, sort_keys=True, indent=1))
    problems = Store(tmp_path).verify()
    assert problems, "truncated current/ must be reported"
    assert any("current" in p.lower() or "materiali" in p.lower() for p in problems)


def test_verify_reports_edit_meta_to_unknown_uid(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("edit_meta", {"uid": "z" * 64, "meta": {"name": "Ghost"}},
           "genesis", "2026-07-07", "rename a ghost")
    problems = s.verify()
    assert problems, "edit_meta to an unknown uid must be reported"
    assert any(("z" * 12) in p or "unknown" in p.lower() for p in problems)


def test_verify_reports_broken_seq_density(tmp_path):
    s = _good_store(tmp_path)
    log_path = tmp_path / "log.jsonl"
    lines = log_path.read_text().splitlines()
    # Delete the middle record: seq becomes 1, 3 (not dense) and the chain breaks.
    del lines[1]
    log_path.write_text("\n".join(lines) + "\n")
    problems = Store(tmp_path).verify()
    assert problems, "non-dense seq must be reported"


# --------------------------------------------------------------------------
# edit_meta / deprecate / supersede / equate visible in read().
# --------------------------------------------------------------------------

def test_edit_meta_replaces_fields_in_read(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("edit_meta", {"uid": "a" * 64, "meta": {"name": "AlphaRenamed"}},
           "author", "2026-07-08", "rename")
    entry = s.read()["nodes"]["a" * 64]
    assert entry["meta"]["name"] == "AlphaRenamed"
    # untouched meta fields survive
    assert entry["meta"]["symbol"] == "x"


def test_deprecate_sets_flag_in_read(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("deprecate", {"uid": "a" * 64, "note": "obsolete"},
           "author", "2026-07-08", "deprecate alpha")
    assert s.read()["nodes"]["a" * 64]["deprecated"] is True


def test_supersede_marks_old_entries_in_read(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    s.push("supersede", {"old_uids": ["a" * 64], "new_uids": ["b" * 64],
                         "note": "alpha replaced by beta"},
           "author", "2026-07-08", "supersede")
    entry = s.read()["nodes"]["a" * 64]
    assert entry["superseded_by"] == ["b" * 64]


def test_equate_records_equivalence_set_on_each_listed_entry(tmp_path):
    s = Store(tmp_path)
    s.push("add_node", NODE_A, "genesis", "2026-07-07", "a")
    s.push("add_node", NODE_B, "genesis", "2026-07-07", "b")
    s.push("equate", {"uids": ["a" * 64, "b" * 64], "note": "same physics"},
           "author", "2026-07-08", "equate")
    m = s.read()
    assert set(m["nodes"]["a" * 64]["equivalent_to"]) == {"a" * 64, "b" * 64}
    assert set(m["nodes"]["b" * 64]["equivalent_to"]) == {"a" * 64, "b" * 64}


def test_change_ops_membership():
    assert CHANGE_OPS == ("add_node", "add_edge", "edit_meta", "deprecate",
                          "supersede", "equate")
