"""Tests for the abstract layer (states, operations, DAG structure)."""

from __future__ import annotations

import pytest

from omai.abstract import State, Operation, topological_order
from omai.thermal_transport.symbolic import (
    EDGES,
    NODES,
    LINEWIDTH,
    THERMAL_CONDUCTIVITY_STATE,
    compute_dispersion,
    compute_force_constants_2,
    compute_heat_capacity,
    compute_linewidth,
    contract_kappa,
)


def test_node_count():
    assert len(NODES) == 12


def test_edge_count():
    assert len(EDGES) == 11


def test_provide_potential_is_nullary():
    from omai.thermal_transport.symbolic import provide_potential

    assert provide_potential.is_nullary()
    assert len(provide_potential.outputs) == 1


def test_compute_dispersion_is_multi_output():
    assert compute_dispersion.is_multi_output()
    assert len(compute_dispersion.outputs) == 2
    output_names = {s.name for s in compute_dispersion.outputs}
    assert output_names == {"Frequency", "Eigenvectors"}


def test_compute_heat_capacity_inputs_are_freq_and_temperature():
    """Verifying the user's correction: no group velocity in heat capacity."""
    input_names = {s.name for s in compute_heat_capacity.inputs}
    assert input_names == {"Frequency", "Temperature"}


def test_compute_linewidth_inputs():
    input_names = {s.name for s in compute_linewidth.inputs}
    assert input_names == {"Frequency", "Eigenvectors", "ForceConstants[order=3]", "Temperature"}


def test_contract_kappa_inputs():
    input_names = {s.name for s in contract_kappa.inputs}
    assert input_names == {"HeatCapacity", "GroupVelocity", "MeanFreeDisplacement"}


def test_topological_order_is_valid():
    """Each operation appears after all operations producing its inputs."""
    order = topological_order(EDGES)
    seen: set[State] = set()
    for op in order:
        for inp in op.inputs:
            assert inp in seen, f"{op.name!r} consumes {inp.name!r} before it is produced"
        for out in op.outputs:
            seen.add(out)


def test_thermal_conductivity_is_terminal():
    """No edge has ThermalConductivity as an input."""
    for op in EDGES:
        for inp in op.inputs:
            assert inp != THERMAL_CONDUCTIVITY_STATE


def test_linewidth_state_has_gamma_definition_convention():
    assert "gamma_definition" in LINEWIDTH.canonical_conventions
    assert LINEWIDTH.canonical_conventions["gamma_definition"] == "imag_self_energy"


def test_linewidth_convention_factor_table():
    """The state knows that linewidth_2x_imag_self_energy scales Gamma by 2."""
    factors = LINEWIDTH.convention_factors
    assert (
        "gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0,
    ) in factors


def test_compute_force_constants_2_carries_formula():
    """The substrate's symbolic-substrate promise: every edge carries a formula."""
    assert compute_force_constants_2.formula is not None


def test_every_derived_edge_has_a_sympy_formula():
    """All non-source edges must carry a sympy-typed formula."""
    import sympy

    sources = {"provide_potential", "provide_temperature"}
    for op in EDGES:
        if op.name in sources:
            assert op.formula is None, f"source {op.name} should have no formula"
        else:
            assert isinstance(op.formula, sympy.Basic), (
                f"derived edge {op.name} formula should be sympy, got {type(op.formula)}"
            )


def test_every_observable_declares_indices():
    """Each observable carries an explicit index signature (possibly empty)."""
    for state in NODES:
        for obs in state.observables:
            assert isinstance(obs.indices, tuple), (
                f"{state.name}.{obs.name} indices should be a tuple"
            )


def test_specific_observable_indices():
    """Spot-check the index signatures match the formulas."""
    from omai.thermal_transport.symbolic import (
        DYNAMICAL_MATRIX,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        LINEWIDTH,
        THERMAL_CONDUCTIVITY_STATE,
    )

    assert FREQUENCY_STATE.observables[0].indices == ("q", "nu")
    assert DYNAMICAL_MATRIX.observables[0].indices == ("i", "j", "q")
    assert GROUP_VELOCITY.observables[0].indices == ("alpha", "q", "nu")
    assert LINEWIDTH.observables[0].indices == ("q", "nu")
    assert THERMAL_CONDUCTIVITY_STATE.observables[0].indices == ("alpha", "beta")


def test_heat_capacity_formula_has_omega_T_kB_hbar():
    """The heat-capacity formula must reference its declared ingredients."""
    import sympy

    f = compute_heat_capacity.formula
    free = {str(s) for s in f.free_symbols}
    assert "T" in free
    assert "k_B" in free
    assert r"\hbar" in free


def test_kappa_formula_is_double_sum_over_q_and_nu():
    """contract_kappa's Sum has two bound variables (q and nu), unlike the buggy old version."""
    import sympy

    f = contract_kappa.formula
    sums = list(f.atoms(sympy.Sum))
    assert len(sums) == 1
    bounds = sums[0].limits
    bound_vars = {str(b[0]) for b in bounds}
    assert bound_vars == {r"\mathbf{q}", r"\nu"}


def test_topological_order_detects_cycles():
    """Inject a synthetic cycle and ensure it raises."""
    a = State(physics_type=NODES[0].physics_type, name="A")
    b = State(physics_type=NODES[0].physics_type, name="B")
    op_ab = Operation(name="op_ab", inputs=(a,), outputs=(b,))
    op_ba = Operation(name="op_ba", inputs=(b,), outputs=(a,))
    with pytest.raises(ValueError, match="cycle"):
        topological_order((op_ab, op_ba))


def test_state_identity_by_name():
    assert LINEWIDTH == LINEWIDTH
    same_name_different_metadata = State(physics_type=LINEWIDTH.physics_type, name="Linewidth")
    assert LINEWIDTH == same_name_different_metadata


def test_operation_identity_by_name():
    assert compute_heat_capacity == compute_heat_capacity
    # Two ops with the same name compare equal even if other fields differ.
    same_name = Operation(
        name="compute_heat_capacity", inputs=(), outputs=compute_heat_capacity.outputs
    )
    assert compute_heat_capacity == same_name
