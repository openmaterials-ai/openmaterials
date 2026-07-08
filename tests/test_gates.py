"""Tests for the contribution validation gates and the gated propose() entry
(kernel P4).

A contribution is an ordered list of proposed records
(``[{"op": ..., "payload": ...}, ...]``). ``validate_contribution`` checks it
against a materialized map (``Store.read()`` shape) through six gates, in order:
registry, identity, reachability, connectivity, gauge, dimensional. It returns
[] when admissible, else one human-readable problem per issue, each prefixed by
the failing gate name in brackets.

The fixture store is built in tmp_path from real map elements (Potential,
ForceConstants[order=2], compute_force_constants[order=2]) with payloads built
by the live identity module, exactly the shape genesis emits. The committed
``map/`` is never touched: every store here lives in tmp_path.
"""
from __future__ import annotations

import sympy as sp
import pytest

# Importing the domain nodes/edges also triggers the domain dimensions_registry
# side effects, populating SYMBOL_DIMENSIONS for the dimensional gate.
from omai.operator.identity import (
    canonical_json,
    edge_id,
    edge_identity,
    edge_uid_from_identity,
    node_id,
    node_identity,
    node_uid_from_identity,
)
from omai.store import GateError, Store
from omai.thermal_transport.operator.edges import (
    compute_force_constants_2,
    compute_force_constants_3,
)
from omai.thermal_transport.operator.nodes import (
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    POTENTIAL,
)


# --------------------------------------------------------------------------
# Real-element payload builders (the shape genesis emits and the store stores).
# --------------------------------------------------------------------------

_SYMBOLS = {
    "Potential": "V",
    "ForceConstants[order=2]": r"\Phi^{(2)}",
    "ForceConstants[order=3]": r"\Phi^{(3)}",
}


def _node_payload(space):
    return {
        "uid": node_id(space),
        "identity": node_identity(space),
        "meta": {
            "name": space.name,
            "symbol": _SYMBOLS.get(space.name, space.name),
            "description": space.description,
            "tier": space.tier,
        },
    }


def _edge_payload(op):
    formula = op.formula
    srepr = sp.srepr(formula) if isinstance(formula, sp.Basic) else (
        " ".join(formula.split()) if isinstance(formula, str) else None)
    latex = None
    if isinstance(formula, sp.Basic):
        try:
            latex = sp.latex(formula)
        except Exception:
            latex = None
    elif isinstance(formula, str):
        latex = formula
    return {
        "uid": edge_id(op, node_id),
        "identity": edge_identity(op, node_id),
        "meta": {
            "name": op.name,
            "description": op.description,
            "formula_srepr": srepr,
            "formula_latex": latex,
            "schemes": {k: v for k, v in sorted(op.schemes.items())},
        },
    }


def _fixture_store(tmp_path):
    """A tiny real store: Potential, ForceConstants[order=2], and the edge
    compute_force_constants[order=2] connecting them."""
    s = Store(tmp_path / "map")
    s.push("add_node", _node_payload(POTENTIAL), "test", "2026-07-07", "n1")
    s.push("add_node", _node_payload(FORCE_CONSTANTS_2), "test", "2026-07-07", "n2")
    s.push("add_edge", _edge_payload(compute_force_constants_2), "test",
           "2026-07-07", "e1")
    return s


def _rec(op, payload):
    return {"op": op, "payload": payload}


# --------------------------------------------------------------------------
# Identity helpers (one hashing implementation, reused by the gates).
# --------------------------------------------------------------------------

def test_node_uid_helper_matches_node_id():
    assert node_uid_from_identity(node_identity(FORCE_CONSTANTS_2)) == node_id(
        FORCE_CONSTANTS_2)


def test_edge_uid_helper_matches_edge_id():
    assert edge_uid_from_identity(
        edge_identity(compute_force_constants_2, node_id)) == edge_id(
        compute_force_constants_2, node_id)


# --------------------------------------------------------------------------
# Gate 1: registry.
# --------------------------------------------------------------------------

def test_registry_rejects_unregistered_quantity_tag(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    payload = _node_payload(FORCE_CONSTANTS_3)
    payload["identity"]["quantity"] = "not_a_registered_quantity"
    # recompute uid so the failure lands on registry, not identity mismatch
    payload["uid"] = node_uid_from_identity(payload["identity"])
    problems = validate_contribution(
        [_rec("add_node", payload)], current)
    assert any(p.startswith("[registry]") for p in problems), problems


# --------------------------------------------------------------------------
# Gate 2: identity.
# --------------------------------------------------------------------------

def test_identity_rejects_tampered_uid(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    payload = _node_payload(FORCE_CONSTANTS_3)
    payload["uid"] = "0" * 64  # wrong uid for this identity
    problems = validate_contribution([_rec("add_node", payload)], current)
    assert any(p.startswith("[identity]") for p in problems), problems


def test_identity_exact_reconvergence_is_no_op_not_error(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    # Re-add Potential with its exact identity: convergence, not an error.
    problems = validate_contribution(
        [_rec("add_node", _node_payload(POTENTIAL))], current)
    assert problems == [], problems


def test_identity_same_uid_different_identity_is_error(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    payload = _node_payload(POTENTIAL)  # uid already in current
    # tamper the identity dict but keep the (now-stale) existing uid
    payload["identity"]["labels"] = {"order": "2"}
    problems = validate_contribution([_rec("add_node", payload)], current)
    # uid no longer matches identity -> identity gate fires
    assert any(p.startswith("[identity]") for p in problems), problems


# --------------------------------------------------------------------------
# Gate 3: reachability.
# --------------------------------------------------------------------------

def test_reachability_rejects_missing_input(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    # add FC3 node then an edge whose input references a uid that is neither in
    # current nor added earlier in the contribution.
    edge_payload = _edge_payload(compute_force_constants_3)
    edge_payload["identity"]["inputs"] = ["f" * 64]
    edge_payload["uid"] = edge_uid_from_identity(edge_payload["identity"])
    problems = validate_contribution(
        [_rec("add_node", _node_payload(FORCE_CONSTANTS_3)),
         _rec("add_edge", edge_payload)], current)
    assert any(p.startswith("[reachability]") for p in problems), problems


# --------------------------------------------------------------------------
# Gate 4: connectivity.
# --------------------------------------------------------------------------

def test_connectivity_two_disconnected_new_nodes_fail_touch_existing(tmp_path):
    """Two brand-new nodes with an edge between only them, touching no
    pre-existing node of current, fails connectivity's touch-existing rule."""
    from omai.gates import validate_contribution
    from omai.operator.space import ObservableSpace, Field
    from omai.operator.dimensions import ENERGY
    from omai.operator.operator import Operator
    # Two synthetic nodes with registered content, connected only to each other.
    a = ObservableSpace(name="Entropy", fields=(Field("s", ENERGY, indices=("q", "nu")),))
    b = ObservableSpace(name="InternalEnergy",
                        fields=(Field("u", ENERGY, indices=("q", "nu")),))
    op = Operator(name="x", inputs=(a,), outputs=(b,), formula=None)
    a_p, b_p = _node_payload(a), _node_payload(b)
    e_p = _edge_payload(op)
    problems = validate_contribution(
        [_rec("add_node", a_p), _rec("add_node", b_p), _rec("add_edge", e_p)],
        current={"nodes": {}, "edges": {}})
    assert any(p.startswith("[connectivity]") for p in problems), problems


def test_connectivity_bare_single_node_no_edge_fails(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    problems = validate_contribution(
        [_rec("add_node", _node_payload(FORCE_CONSTANTS_3))], current)
    assert any(p.startswith("[connectivity]") for p in problems), problems


def test_connectivity_skipped_for_pure_meta_contribution(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    uid = node_id(POTENTIAL)
    problems = validate_contribution(
        [_rec("edit_meta", {"uid": uid, "meta": {"description": "new"}})],
        current)
    assert problems == [], problems


# --------------------------------------------------------------------------
# Gate 5: gauge.
# --------------------------------------------------------------------------

def test_gauge_rejects_malformed_gauge_class(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    payload = _node_payload(FORCE_CONSTANTS_3)
    payload["identity"]["gauge"] = "hidden/notakind/notagroup"
    payload["uid"] = node_uid_from_identity(payload["identity"])
    problems = validate_contribution([_rec("add_node", payload)], current)
    assert any(p.startswith("[gauge]") for p in problems), problems


def test_gauge_accepts_registered_hidden_class(tmp_path):
    """A well-formed hidden gauge class (registered kind + registered group)
    passes the gauge gate (may still trip connectivity, which we ignore here)."""
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    payload = _node_payload(FORCE_CONSTANTS_3)
    payload["identity"]["gauge"] = (
        "hidden/scaffolding/ud_degenerate_subspace_on_eigenvectors")
    payload["uid"] = node_uid_from_identity(payload["identity"])
    problems = validate_contribution([_rec("add_node", payload)], current)
    assert not any(p.startswith("[gauge]") for p in problems), problems


# --------------------------------------------------------------------------
# Gate 6: dimensional.
# --------------------------------------------------------------------------

def test_dimensional_rejects_proven_mismatch(tmp_path):
    """An add_edge whose formula_srepr is Eq(T, L) built from registered
    symbols (T temperature vs L length) is a proven dimensional mismatch."""
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    # Build an edge payload from FC3 (valid structurally) but swap in a
    # dimensionally-inconsistent formula srepr.
    edge_payload = _edge_payload(compute_force_constants_3)
    edge_payload["meta"]["formula_srepr"] = sp.srepr(
        sp.Eq(sp.Symbol("T"), sp.Symbol("L")))
    problems = validate_contribution(
        [_rec("add_node", _node_payload(FORCE_CONSTANTS_3)),
         _rec("add_edge", edge_payload)], current)
    assert any(p.startswith("[dimensional]") for p in problems), problems


def test_dimensional_unparseable_formula_is_error(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    edge_payload = _edge_payload(compute_force_constants_3)
    edge_payload["meta"]["formula_srepr"] = "this is (not sympy"
    problems = validate_contribution(
        [_rec("add_node", _node_payload(FORCE_CONSTANTS_3)),
         _rec("add_edge", edge_payload)], current)
    assert any(p.startswith("[dimensional]") for p in problems), problems


def test_dimensional_unknown_side_is_skip_not_error(tmp_path):
    """The real FC3 formula's RHS is a Derivative of unknown-dimension symbols:
    unknown on a side is a skip, never a guess."""
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    current = s.read()
    # A valid contribution reusing FC3: dimensional gate must skip (not error).
    problems = validate_contribution(
        [_rec("add_node", _node_payload(FORCE_CONSTANTS_3)),
         _rec("add_edge", _edge_payload(compute_force_constants_3))], current)
    assert not any(p.startswith("[dimensional]") for p in problems), problems


# --------------------------------------------------------------------------
# A valid contribution passes; propose() lands it; exact re-proposal is a no-op.
# --------------------------------------------------------------------------

def _valid_contribution():
    return [_rec("add_node", _node_payload(FORCE_CONSTANTS_3)),
            _rec("add_edge", _edge_payload(compute_force_constants_3))]


def test_valid_contribution_returns_empty(tmp_path):
    from omai.gates import validate_contribution
    s = _fixture_store(tmp_path)
    assert validate_contribution(_valid_contribution(), s.read()) == []


def test_propose_lands_valid_contribution(tmp_path):
    s = _fixture_store(tmp_path)
    head_before = s.head
    records = _valid_contribution()
    new_head = s.propose(records, author="alice", date="2026-07-08",
                         reason_prefix="add cubic FC")
    assert new_head != head_before
    assert s.head == new_head
    m = s.read()
    assert node_id(FORCE_CONSTANTS_3) in m["nodes"]
    assert edge_id(compute_force_constants_3, node_id) in m["edges"]


def test_propose_raises_gate_error_on_invalid(tmp_path):
    s = _fixture_store(tmp_path)
    bad = _node_payload(FORCE_CONSTANTS_3)
    bad["identity"]["quantity"] = "bogus"
    bad["uid"] = node_uid_from_identity(bad["identity"])
    with pytest.raises(GateError) as excinfo:
        s.propose([_rec("add_node", bad)], author="a", date="2026-07-08",
                  reason_prefix="x")
    # the exception carries the problem list
    assert any("[registry]" in p for p in excinfo.value.problems)
    # nothing landed
    assert node_uid_from_identity(bad["identity"]) not in s.read()["nodes"]


def test_exact_reproposal_is_no_op_returns_head_unchanged(tmp_path):
    s = _fixture_store(tmp_path)
    s.propose(_valid_contribution(), author="alice", date="2026-07-08",
              reason_prefix="add cubic FC")
    head_after_first = s.head
    n_records_after_first = len(s.read()["nodes"]) + len(s.read()["edges"])
    # Re-propose the identical contribution: all no-ops, head unchanged, no new
    # records appended.
    returned = s.propose(_valid_contribution(), author="alice",
                         date="2026-07-09", reason_prefix="add cubic FC again")
    assert returned == head_after_first
    assert s.head == head_after_first
    n_records_after_second = len(s.read()["nodes"]) + len(s.read()["edges"])
    assert n_records_after_second == n_records_after_first
