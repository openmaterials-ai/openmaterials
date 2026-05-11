"""Tests for the symbolic layer (states, operations, DAG structure)."""

from __future__ import annotations

import pytest

from omai.symbolic import State, Operation, topological_order
from omai.thermal_transport.symbolic import (
    EDGES,
    NODES,
    LINEWIDTH,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    compute_dispersion,
    compute_force_constants_2,
    compute_heat_capacity,
    compute_linewidth,
    contract_kappa_direct,
    contract_kappa_rta,
)


def test_node_count():
    assert len(NODES) == 14


def test_edge_count():
    assert len(EDGES) == 13


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
    direct_inputs = {s.name for s in contract_kappa_direct.inputs}
    assert direct_inputs == {
        "HeatCapacity",
        "GroupVelocity",
        "MeanFreeDisplacement[bte_solver=direct_inverse]",
    }
    rta_inputs = {s.name for s in contract_kappa_rta.inputs}
    assert rta_inputs == {
        "HeatCapacity",
        "GroupVelocity",
        "MeanFreeDisplacement[bte_solver=rta]",
    }


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
            assert inp not in (THERMAL_CONDUCTIVITY_RTA, THERMAL_CONDUCTIVITY_DIRECT)


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
    """The symbolic layer's symbolic promise: every edge carries a formula."""
    assert compute_force_constants_2.formula is not None


def test_every_edge_has_a_sympy_formula():
    """Every edge — sources included — carries a sympy formula."""
    import sympy

    for op in EDGES:
        assert isinstance(op.formula, sympy.Basic), (
            f"edge {op.name} formula should be sympy, got {type(op.formula)}"
        )


def test_every_state_declares_indices():
    """Each state's fields carry explicit index signatures (possibly empty)."""
    for state in NODES:
        for f in state.fields:
            assert isinstance(f.indices, tuple), (
                f"{state.name}.{f.name} indices should be a tuple"
            )


def test_specific_field_indices():
    """Spot-check the index signatures match the formulas."""
    from omai.thermal_transport.symbolic import (
        DYNAMICAL_MATRIX,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        LINEWIDTH,
        THERMAL_CONDUCTIVITY_DIRECT,
    )

    assert FREQUENCY_STATE.fields[0].indices == ("q", "nu")
    assert DYNAMICAL_MATRIX.fields[0].indices == ("i", "j", "q")
    assert GROUP_VELOCITY.fields[0].indices == ("alpha", "q", "nu")
    assert LINEWIDTH.fields[0].indices == ("q", "nu")
    assert THERMAL_CONDUCTIVITY_DIRECT.fields[0].indices == ("alpha", "beta")


def test_symbolic_validates_clean():
    """The thermal-transport DAG satisfies all discipline invariants."""
    from omai.symbolic import validate_dag

    errors = validate_dag(NODES, EDGES)
    assert errors == [], f"discipline violations:\n  " + "\n  ".join(errors)


def test_validator_flags_missing_gauge_group():
    """A scaffolding HiddenState without a gauge_group is rejected."""
    from omai.symbolic import validate_dag
    from omai.symbolic.state import HiddenState
    from omai.thermal_transport.symbolic.nodes import POTENTIAL  # any Observable

    bad = HiddenState(
        physics_type=POTENTIAL.physics_type,  # any
        name="BadHiddenState",
        # gauge_group="" by default
    )
    errors = validate_dag((POTENTIAL, bad), ())
    assert any("gauge_group" in e for e in errors)


def test_validator_flags_dangling_contraction_name():
    """A scaffolding HiddenState that names a non-existent Observable is rejected."""
    from omai.symbolic import validate_dag
    from omai.symbolic.state import HiddenState
    from omai.thermal_transport.symbolic.nodes import POTENTIAL

    bad = HiddenState(
        physics_type=POTENTIAL.physics_type,
        name="BadHiddenState",
        gauge_group="some_gauge",
        kind="scaffolding",
        gauge_invariant_contractions=("DoesNotExist",),
    )
    errors = validate_dag((POTENTIAL, bad), ())
    assert any("DoesNotExist" in e for e in errors)


def test_observable_vs_hidden_state_classification():
    """The symbolic layer classifies gauge-invariant vs gauge-dependent nodes."""
    from omai.symbolic.state import HiddenState, Observable
    from omai.thermal_transport.symbolic import (
        EIGENVECTORS,
        FORCE_CONSTANTS_2,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        LINEWIDTH,
        MEAN_FREE_DISPLACEMENT_DIRECT,
        MEAN_FREE_DISPLACEMENT_RTA,
        POTENTIAL,
        TEMPERATURE_STATE,
        THERMAL_CONDUCTIVITY_DIRECT,
        THERMAL_CONDUCTIVITY_RTA,
    )

    for state in (
        POTENTIAL, TEMPERATURE_STATE, FORCE_CONSTANTS_2,
        FREQUENCY_STATE, HEAT_CAPACITY,
        MEAN_FREE_DISPLACEMENT_DIRECT, THERMAL_CONDUCTIVITY_DIRECT,
    ):
        assert isinstance(state, Observable), f"{state.name} should be Observable"
        assert state.is_observable

    for state in (
        EIGENVECTORS, GROUP_VELOCITY, LINEWIDTH,
        MEAN_FREE_DISPLACEMENT_RTA, THERMAL_CONDUCTIVITY_RTA,
    ):
        assert isinstance(state, HiddenState), f"{state.name} should be HiddenState"
        assert not state.is_observable


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

    # Both RTA and direct variants share the same κ contraction formula
    f = contract_kappa_direct.formula
    assert contract_kappa_rta.formula is f
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
