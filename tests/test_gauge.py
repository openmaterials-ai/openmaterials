"""Tests for the symbolic gauge framework."""

from __future__ import annotations

import sympy as sp

from omai.abstract import GaugeAction, check_invariance
from omai.thermal_transport.symbolic.edges import (
    compute_dynamical_matrix,
    compute_group_velocity,
    compute_heat_capacity,
    compute_linewidth,
    contract_kappa_direct,
)
from omai.thermal_transport.symbolic.gauges import U1_PHASE_ON_EIGENVECTOR


def test_u1_phase_action_acts_on_eigenvector():
    """Direct check of the action: applying once should multiply by exp(iθ)."""
    e = sp.IndexedBase("e")
    i, q, nu = sp.symbols("i q nu", integer=True)
    transformed = U1_PHASE_ON_EIGENVECTOR.apply_to(e[i, q, nu])
    # transformed should be exp(I*θ[q,nu]) * e[i,q,nu]
    assert sp.exp not in {type(transformed)}  # not bare exp, but has exp factor
    # Simplify difference: transformed / (e[i,q,nu]) should be exp(I θ[q,nu])
    factor = sp.simplify(transformed / e[i, q, nu])
    assert "exp(" in str(factor) or factor.has(sp.exp)


def test_compute_group_velocity_is_u1_phase_invariant():
    """Per-mode v = e†(∂D/∂q)e/(2ω) is invariant under e → exp(iθ) e."""
    rhs = compute_group_velocity.formula.rhs
    assert U1_PHASE_ON_EIGENVECTOR.verifies_invariance(rhs), (
        "GroupVelocity formula must be U(1)-phase invariant per mode"
    )


def test_compute_heat_capacity_is_u1_phase_invariant_trivially():
    """HeatCapacity doesn't reference eigenvectors → trivially invariant."""
    rhs = compute_heat_capacity.formula.rhs
    assert U1_PHASE_ON_EIGENVECTOR.verifies_invariance(rhs)


def test_check_invariance_returns_named_dict():
    """check_invariance reports per-gauge invariance for an operation."""
    rhs = compute_group_velocity.formula.rhs
    results = check_invariance(rhs, [U1_PHASE_ON_EIGENVECTOR])
    assert results == {U1_PHASE_ON_EIGENVECTOR.name: True}


def test_gauge_action_fails_invariance_when_eigenvector_appears_unpaired():
    """A formula with a bare (non-paired) eigenvector is not U(1)-invariant."""
    e = sp.IndexedBase("e")
    i, q, nu = sp.symbols("i q nu", integer=True)
    # Construct a deliberately non-invariant expression: just a single e
    expr = e[i, q, nu]
    assert not U1_PHASE_ON_EIGENVECTOR.verifies_invariance(expr)
