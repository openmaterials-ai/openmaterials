"""Sympy expression dimension evaluator + per-domain symbol registry (kernel P1)."""
from __future__ import annotations

import sympy as sp
import pytest

# Importing the domain packages triggers their dimensions_registry side
# effects (symbol -> Dimension), just like the vocabulary registry.
import omai.thermal_transport.operator  # noqa: F401
import omai.materials.operator  # noqa: F401

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY,
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
    VOLUME,
)
from omai.operator.dimcheck import (
    DimensionalViolation,
    KNOWN_VIOLATIONS,
    dimension_of,
    dimensional_report,
)


def test_heat_capacity_rhs_is_energy_per_temperature():
    from omai.thermal_transport.operator.edges import compute_heat_capacity
    dim = dimension_of(compute_heat_capacity.formula.rhs)
    assert dim == ENERGY_PER_TEMPERATURE


def test_kappa_contraction_rhs_with_local_vcell():
    from omai.thermal_transport.operator.edges import contract_kappa_direct
    # V_{cell} is an edge parameter (dimension VOLUME), supplied via `local`.
    local = {p.name: p.dimension for p in contract_kappa_direct.parameters}
    dim = dimension_of(contract_kappa_direct.formula.rhs, local=local)
    assert dim == THERMAL_CONDUCTIVITY


def test_eq_side_mismatch_detectable_by_caller():
    c = sp.Symbol("c")
    hbar = sp.Symbol(r"\hbar")
    omega = sp.Symbol(r"\omega_c")
    # c is heat capacity (energy/temperature); hbar*omega is energy. The
    # evaluator does not raise on an Eq itself; the caller compares sides.
    lhs = dimension_of(c)
    rhs = dimension_of(hbar * omega)
    assert lhs == ENERGY_PER_TEMPERATURE
    assert rhs == ENERGY
    assert lhs != rhs


def test_exp_of_dimensionful_argument_raises():
    T = sp.Symbol("T")  # registered TEMPERATURE
    with pytest.raises(DimensionalViolation):
        dimension_of(sp.exp(T))


def test_unregistered_symbol_returns_none():
    mystery = sp.Symbol("totally_unregistered_xyz")
    assert dimension_of(mystery) is None
    # And an unknown factor makes the whole product unknown.
    T = sp.Symbol("T")
    assert dimension_of(mystery * T) is None


def test_add_of_incompatible_dimensions_raises():
    T = sp.Symbol("T")  # TEMPERATURE
    f = sp.IndexedBase("f")  # ENERGY
    i, j = sp.symbols("i j")
    with pytest.raises(DimensionalViolation):
        dimension_of(T + f[i, j])


def test_local_none_override_shadows_global():
    # D is DIFFUSIVITY globally (materials registry). A local None override
    # makes it unknown so the whole expression evaluates to None (skip),
    # never a false dimension.
    D = sp.Symbol("D")
    assert dimension_of(D) is not None  # global registration present
    assert dimension_of(D, local={"D": None}) is None


def test_unified_dag_dimensional_report_no_new_violations():
    from omai.map_data import DOMAINS
    from omai.operator.dimcheck import dimensional_report
    nodes, edges, seen = [], [], set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in seen:
                seen.add(s.name); nodes.append(s)
        edges.extend(d.edges)
    report = dimensional_report(tuple(nodes), tuple(edges))
    assert report["violation"] == KNOWN_VIOLATIONS
    assert len(report["ok"]) >= 8
