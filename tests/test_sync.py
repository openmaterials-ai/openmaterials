"""Tests for the sync tool (kernel P4): propose store change records from the
Python operator layer.

``compute_sync(current)`` diffs the live ``DOMAINS`` (through the same payload
builder genesis uses) against the materialized store view ``current`` and
returns ``{"add", "edit_meta", "deprecate", "re_mint"}`` proposals. It is the
bidirectional drift alarm: on the pristine repo the Python layer and the
committed store agree exactly, so every bucket is empty.

The committed ``map/`` is NEVER mutated by these tests: the pristine check reads
it, and every simulation mutates a deep COPY of the read view.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omai.gates import validate_contribution
from omai.operator.identity import edge_id, node_id
from omai.store import Store
from omai.sync import compute_sync, main
from omai.thermal_transport.operator.edges import compute_force_constants_3
from omai.thermal_transport.operator.nodes import FORCE_CONSTANTS_3


def _pristine_current():
    return Store(Path("map")).read()


# --------------------------------------------------------------------------
# (a) The pristine repo is in sync: every bucket empty (bidirectional drift alarm).
# --------------------------------------------------------------------------

def test_pristine_repo_is_in_sync():
    proposal = compute_sync(_pristine_current())
    assert proposal["add"] == []
    assert proposal["edit_meta"] == []
    assert proposal["deprecate"] == []
    assert proposal["re_mint"] == []


# --------------------------------------------------------------------------
# (b) Deleting a node + its edge from a copy: they reappear as add proposals
#     whose payloads pass validate_contribution against the mutilated copy.
# --------------------------------------------------------------------------

def test_deleted_node_and_edge_reappear_as_add():
    current = _pristine_current()
    fc3_uid = node_id(FORCE_CONSTANTS_3)
    edge_uid = edge_id(compute_force_constants_3, node_id)
    mutilated = copy.deepcopy(current)
    del mutilated["nodes"][fc3_uid]
    del mutilated["edges"][edge_uid]

    proposal = compute_sync(mutilated)
    add_uids = {r["payload"]["uid"] for r in proposal["add"]}
    assert fc3_uid in add_uids
    assert edge_uid in add_uids
    # no spurious deprecations / re_mints (we only removed; nothing changed id)
    assert proposal["deprecate"] == []
    assert proposal["re_mint"] == []

    # The add records pass the gates against the mutilated copy: the edge
    # connects to Potential, which remains.
    problems = validate_contribution(proposal["add"], mutilated)
    assert problems == [], problems


# --------------------------------------------------------------------------
# (c) Altering a description in a copy: exactly one edit_meta, only that key.
# --------------------------------------------------------------------------

def test_description_change_surfaces_as_single_key_edit_meta():
    current = _pristine_current()
    fc3_uid = node_id(FORCE_CONSTANTS_3)
    mutated = copy.deepcopy(current)
    mutated["nodes"][fc3_uid]["meta"]["description"] = "a stale description"

    proposal = compute_sync(mutated)
    edits = [r for r in proposal["edit_meta"]
             if r["payload"]["uid"] == fc3_uid]
    assert len(edits) == 1, proposal["edit_meta"]
    meta = edits[0]["payload"]["meta"]
    # only the changed key is carried
    assert set(meta.keys()) == {"description"}
    # and it carries the live (Python-side) value, not the stale one
    assert meta["description"] == FORCE_CONSTANTS_3.description
    # no adds / deprecates / re_mints from a pure meta drift
    assert proposal["add"] == []
    assert proposal["deprecate"] == []
    assert proposal["re_mint"] == []


# --------------------------------------------------------------------------
# (d) A formula change surfaces as re_mint (old store uid unmatched + new
#     Python uid), never edit_meta. Since the formula is in the edge identity,
#     a real formula change re-mints the edge uid; the stored (old) uid becomes
#     unmatched Python-side while the live edge uid is a new add. They pair by
#     the shared output node into a re_mint proposal.
# --------------------------------------------------------------------------

def test_formula_change_surfaces_as_re_mint_never_edit_meta():
    current = _pristine_current()
    edge_uid = edge_id(compute_force_constants_3, node_id)
    mutated = copy.deepcopy(current)
    entry = mutated["edges"][edge_uid]
    # Simulate a formula change: the identity's formula fingerprint changes, so
    # the uid changes too (the store now holds an edge uid the Python layer no
    # longer produces). Re-key under a fabricated old uid, keeping the SAME
    # output node so the re_mint pairing has an anchor.
    old_uid = "d" * 64
    entry["uid"] = old_uid
    entry["identity"]["formula"] = "Equality(Symbol('a'), Symbol('b'))"
    entry["meta"]["formula_srepr"] = "Equality(Symbol('a'), Symbol('b'))"
    del mutated["edges"][edge_uid]
    mutated["edges"][old_uid] = entry

    proposal = compute_sync(mutated)

    # The live edge uid resurfaces as a new Python-side element and pairs with
    # the unmatched old store uid as a re_mint, NOT an edit_meta.
    re_mint_new = {r["new_uid"] for r in proposal["re_mint"]}
    re_mint_old = {r["old_uid"] for r in proposal["re_mint"]}
    assert edge_uid in re_mint_new, proposal["re_mint"]
    assert old_uid in re_mint_old, proposal["re_mint"]
    assert proposal["re_mint"][0]["why"] == "identity content changed"
    # never an edit_meta for this edge
    assert all(r["payload"]["uid"] != edge_uid
               for r in proposal["edit_meta"])
    # and the re_mint is not silently applied as an add either
    assert edge_uid not in {r["payload"]["uid"] for r in proposal["add"]}


# --------------------------------------------------------------------------
# An unmatched store element with no same-key Python-side new uid deprecates.
# --------------------------------------------------------------------------

def test_unmatched_store_element_with_no_pair_deprecates():
    current = _pristine_current()
    mutated = copy.deepcopy(current)
    # Fabricate a stored node whose quantity tag no thermal/materials node uses,
    # and whose uid the Python layer never produces: it has no re_mint pair.
    ghost_uid = "c" * 64
    mutated["nodes"][ghost_uid] = {
        "uid": ghost_uid,
        "identity": {"quantity": "a_retired_quantity", "fields": [],
                     "gauge": "observable", "labels": {}},
        "meta": {"name": "Ghost", "symbol": "g", "description": "", "tier": ""},
    }
    proposal = compute_sync(mutated)
    dep_uids = {r["payload"]["uid"] for r in proposal["deprecate"]}
    assert ghost_uid in dep_uids
    assert all(r["old_uid"] != ghost_uid for r in proposal["re_mint"])


# --------------------------------------------------------------------------
# (e) The CLI dry run on the pristine repo prints "in sync" and exits 0.
# --------------------------------------------------------------------------

def test_cli_dry_run_pristine_reports_in_sync_exit_0(capsys):
    rc = main([])
    out = capsys.readouterr().out.lower()
    assert rc == 0
    assert "in sync" in out


def test_cli_dry_run_exit_2_when_proposals_exist(tmp_path, capsys, monkeypatch):
    # Build a store missing FC3 + its edge, so sync has proposals. We run the
    # CLI against a throwaway store dir by monkeypatching the store root the CLI
    # reads. The committed map/ is untouched.
    import omai.sync as sync_mod
    current = _pristine_current()
    fc3_uid = node_id(FORCE_CONSTANTS_3)
    edge_uid = edge_id(compute_force_constants_3, node_id)
    # Materialize a mutilated store by replaying genesis minus the two records.
    from omai.genesis import genesis_records
    store = Store(tmp_path / "map")
    for op, payload, reason in genesis_records():
        if payload["uid"] in (fc3_uid, edge_uid):
            continue
        store.push(op, payload, "genesis", "2026-07-07", reason)

    monkeypatch.setattr(sync_mod, "_STORE_ROOT", tmp_path / "map")
    rc = main([])
    out = capsys.readouterr().out.lower()
    assert rc == 2, out
    assert "add" in out


def test_cli_apply_refuses_re_mints_exit_3(tmp_path, capsys, monkeypatch):
    import omai.sync as sync_mod
    fc3_uid = node_id(FORCE_CONSTANTS_3)
    edge_uid = edge_id(compute_force_constants_3, node_id)
    from omai.genesis import genesis_records
    store = Store(tmp_path / "map")
    for op, payload, reason in genesis_records():
        store.push(op, payload, "genesis", "2026-07-07", reason)
    # Re-key the FC3 edge under a fabricated old uid to force a re_mint.
    # Easiest: drop the edge and re-add it with a mutated identity/uid so the
    # live Python uid becomes unmatched. We just rewrite the materialized view's
    # log is overkill; instead mutate via a supersede-free direct approach: push
    # a fresh store missing the real edge but holding a fabricated old one.
    store2 = Store(tmp_path / "map2")
    for op, payload, reason in genesis_records():
        if payload["uid"] == edge_uid:
            payload = json.loads(json.dumps(payload))
            payload["uid"] = "d" * 64
            payload["identity"]["formula"] = "Equality(Symbol('a'), Symbol('b'))"
            payload["meta"]["formula_srepr"] = "Equality(Symbol('a'), Symbol('b'))"
        store2.push(op, payload, "genesis", "2026-07-07", reason)

    monkeypatch.setattr(sync_mod, "_STORE_ROOT", tmp_path / "map2")
    rc = main(["--apply", "--author", "alice", "--date", "2026-07-08",
               "--reason", "sync"])
    out = capsys.readouterr().out.lower()
    assert rc == 3, out
    assert "supersede" in out or "re-mint" in out or "re_mint" in out


def test_cli_apply_lands_adds(tmp_path, capsys, monkeypatch):
    import omai.sync as sync_mod
    fc3_uid = node_id(FORCE_CONSTANTS_3)
    edge_uid = edge_id(compute_force_constants_3, node_id)
    from omai.genesis import genesis_records
    store = Store(tmp_path / "map")
    for op, payload, reason in genesis_records():
        if payload["uid"] in (fc3_uid, edge_uid):
            continue
        store.push(op, payload, "genesis", "2026-07-07", reason)

    monkeypatch.setattr(sync_mod, "_STORE_ROOT", tmp_path / "map")
    rc = main(["--apply", "--author", "alice", "--date", "2026-07-08",
               "--reason", "sync"])
    assert rc == 0
    m = Store(tmp_path / "map").read()
    assert fc3_uid in m["nodes"]
    assert edge_uid in m["edges"]
