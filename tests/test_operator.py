"""Tests for the operator layer (states, operations, DAG structure)."""

from __future__ import annotations

import pytest

from omai.operator import State, Operation, topological_order
from omai.thermal_transport.operator import (
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
    assert len(NODES) == 38


def test_edge_count():
    assert len(EDGES) == 38


def test_cumulative_kappa_parameterised():
    """Cumulative κ is terminal Pattern A: type-parameterised on `wrt`."""
    from omai.thermal_transport.operator import (
        CUMULATIVE_KAPPA_MFP,
        CUMULATIVE_KAPPA_OMEGA,
        MEAN_FREE_DISPLACEMENT_DIRECT,
        contract_cumulative_kappa_mfp,
        contract_cumulative_kappa_omega,
    )

    assert CUMULATIVE_KAPPA_OMEGA.type_parameters == {"wrt": "omega"}
    assert CUMULATIVE_KAPPA_MFP.type_parameters == {"wrt": "mfp"}
    assert contract_cumulative_kappa_omega.outputs == (CUMULATIVE_KAPPA_OMEGA,)
    assert contract_cumulative_kappa_mfp.outputs == (CUMULATIVE_KAPPA_MFP,)
    assert MEAN_FREE_DISPLACEMENT_DIRECT in contract_cumulative_kappa_mfp.inputs


def test_wigner_pattern_a_terminal():
    """Wigner κ is terminal Pattern A: type-parameterised state with
    no downstream consumers; decomposable into populations + coherences."""
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        combine_kappa_wigner,
    )

    # All three Wigner states are Observables (gauge-invariant).
    for state in (
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    ):
        assert state.is_observable

    # combine_kappa_wigner takes the two sub-channels.
    assert set(combine_kappa_wigner.inputs) == {
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    }
    assert combine_kappa_wigner.outputs == (THERMAL_CONDUCTIVITY_WIGNER,)


def test_qhgk_is_hidden_state():
    """QHGK κ inherits Linewidth's gauge dependence — modelled as a
    HiddenState terminal node."""
    from omai.operator.state import HiddenState
    from omai.thermal_transport.operator import THERMAL_CONDUCTIVITY_QHGK, compute_kappa_qhgk

    assert isinstance(THERMAL_CONDUCTIVITY_QHGK, HiddenState)
    assert compute_kappa_qhgk.outputs == (THERMAL_CONDUCTIVITY_QHGK,)


def test_linewidth_channels_converge_through_sum():
    """Pattern B: anharmonic, isotopic, boundary channels are sibling
    HiddenStates summed into TotalLinewidth before reaching solve_bte."""
    from omai.thermal_transport.operator import (
        ANHARMONIC_LINEWIDTH,
        BOUNDARY_LINEWIDTH,
        ISOTOPIC_LINEWIDTH,
        TOTAL_LINEWIDTH,
        solve_bte_direct,
        solve_bte_rta,
        sum_linewidths,
    )

    # sum_linewidths takes all three channels and produces the total.
    assert set(sum_linewidths.inputs) == {
        ANHARMONIC_LINEWIDTH, ISOTOPIC_LINEWIDTH, BOUNDARY_LINEWIDTH,
    }
    assert sum_linewidths.outputs == (TOTAL_LINEWIDTH,)
    # Downstream solve_bte_* consumes only the total, not individual channels.
    assert TOTAL_LINEWIDTH in solve_bte_rta.inputs
    assert TOTAL_LINEWIDTH in solve_bte_direct.inputs
    assert ANHARMONIC_LINEWIDTH not in solve_bte_rta.inputs
    assert ANHARMONIC_LINEWIDTH not in solve_bte_direct.inputs


def test_anharmonic_linewidth_alias_is_legacy_linewidth():
    """The Python LINEWIDTH symbol is preserved as a back-compat alias
    for ANHARMONIC_LINEWIDTH."""
    from omai.thermal_transport.operator import ANHARMONIC_LINEWIDTH, LINEWIDTH

    assert LINEWIDTH is ANHARMONIC_LINEWIDTH


def test_harmonic_thermo_sibling_states():
    """F, S, E are sibling Observables off (Frequency, Temperature),
    paralleling HeatCapacity."""
    from omai.thermal_transport.operator import (
        ENTROPY,
        FREQUENCY_STATE,
        HELMHOLTZ_FREE_ENERGY,
        INTERNAL_ENERGY,
        TEMPERATURE_STATE,
        compute_entropy,
        compute_free_energy,
        compute_internal_energy,
    )

    for op, out in (
        (compute_free_energy, HELMHOLTZ_FREE_ENERGY),
        (compute_entropy, ENTROPY),
        (compute_internal_energy, INTERNAL_ENERGY),
    ):
        assert set(s.name for s in op.inputs) == {FREQUENCY_STATE.name, TEMPERATURE_STATE.name}
        assert op.outputs == (out,)


def test_molar_thermo_contractions():
    from omai.thermal_transport.operator import (
        ENTROPY,
        HELMHOLTZ_FREE_ENERGY,
        INTERNAL_ENERGY,
        MOLAR_ENTROPY,
        MOLAR_HELMHOLTZ_FREE_ENERGY,
        MOLAR_INTERNAL_ENERGY,
        contract_molar_entropy,
        contract_molar_free_energy,
        contract_molar_internal_energy,
    )

    assert contract_molar_free_energy.inputs == (HELMHOLTZ_FREE_ENERGY,)
    assert contract_molar_free_energy.outputs == (MOLAR_HELMHOLTZ_FREE_ENERGY,)
    assert contract_molar_entropy.inputs == (ENTROPY,)
    assert contract_molar_entropy.outputs == (MOLAR_ENTROPY,)
    assert contract_molar_internal_energy.inputs == (INTERNAL_ENERGY,)
    assert contract_molar_internal_energy.outputs == (MOLAR_INTERNAL_ENERGY,)


def test_provide_potential_is_nullary():
    from omai.thermal_transport.operator import provide_potential

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
    """The operator layer's operator promise: every edge carries a formula."""
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
    from omai.thermal_transport.operator import (
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
    from omai.operator import validate_dag

    errors = validate_dag(NODES, EDGES)
    assert errors == [], f"discipline violations:\n  " + "\n  ".join(errors)


def test_validator_flags_missing_gauge_group():
    """A scaffolding HiddenState without a gauge_group is rejected."""
    from omai.operator import validate_dag
    from omai.operator.state import HiddenState
    from omai.thermal_transport.operator.nodes import POTENTIAL  # any Observable

    bad = HiddenState(
        physics_type=POTENTIAL.physics_type,  # any
        name="BadHiddenState",
        # gauge_group="" by default
    )
    errors = validate_dag((POTENTIAL, bad), ())
    assert any("gauge_group" in e for e in errors)


def test_validator_flags_dangling_contraction_name():
    """A scaffolding HiddenState that names a non-existent Observable is rejected."""
    from omai.operator import validate_dag
    from omai.operator.state import HiddenState
    from omai.thermal_transport.operator.nodes import POTENTIAL

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
    """The operator layer classifies gauge-invariant vs gauge-dependent nodes."""
    from omai.operator.state import HiddenState, Observable
    from omai.thermal_transport.operator import (
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
    same_name_different_metadata = State(
        physics_type=LINEWIDTH.physics_type, name="Linewidth[channel=anharmonic_3ph]"
    )
    assert LINEWIDTH == same_name_different_metadata


def test_operation_identity_by_name():
    assert compute_heat_capacity == compute_heat_capacity
    # Two ops with the same name compare equal even if other fields differ.
    same_name = Operation(
        name="compute_heat_capacity", inputs=(), outputs=compute_heat_capacity.outputs
    )
    assert compute_heat_capacity == same_name


# -- Smoke tests for the derived-observable DAG nodes ---------------------


def test_compute_dos_inputs_are_frequency():
    from omai.thermal_transport.operator import PHONON_DOS, compute_dos

    assert tuple(s.name for s in compute_dos.inputs) == ("Frequency",)
    assert tuple(s.name for s in compute_dos.outputs) == (PHONON_DOS.name,)


def test_compute_gruneisen_inputs():
    from omai.thermal_transport.operator import (
        GRUNEISEN,
        compute_gruneisen,
    )

    assert set(s.name for s in compute_gruneisen.inputs) == {
        "ForceConstants[order=2]",
        "ForceConstants[order=3]",
        "Frequency",
        "Eigenvectors",
    }
    assert tuple(s.name for s in compute_gruneisen.outputs) == (GRUNEISEN.name,)


def test_compute_phase_space_3phonon_inputs():
    from omai.thermal_transport.operator import (
        PHASE_SPACE_3PH,
        compute_phase_space_3phonon,
    )

    assert tuple(s.name for s in compute_phase_space_3phonon.inputs) == ("Frequency",)
    assert tuple(s.name for s in compute_phase_space_3phonon.outputs) == (
        PHASE_SPACE_3PH.name,
    )


def test_derived_observable_conventions_are_declared():
    """Each derived-observable op declares its algorithmic convention."""
    from omai.thermal_transport.operator import (
        compute_dos,
        compute_gruneisen,
        compute_phase_space_3phonon,
    )

    assert compute_dos.algorithmic_conventions["dos_broadening"] == "gaussian"
    assert (
        compute_gruneisen.algorithmic_conventions["gruneisen_method"]
        == "maradudin_fein"
    )
    assert (
        compute_phase_space_3phonon.algorithmic_conventions["delta_broadening"]
        == "gaussian"
    )


def test_nac_pattern_c_topology():
    """Born charges + NAC follow Pattern C: BareDM intermediate, two edges
    converging on DynamicalMatrix."""
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        BORN_CHARGES,
        DIELECTRIC_TENSOR,
        DYNAMICAL_MATRIX,
        apply_nac_correction,
        compute_dynamical_matrix,
        identity_dm,
    )

    # compute_dynamical_matrix now produces BareDM, not DM.
    assert compute_dynamical_matrix.outputs == (BARE_DYNAMICAL_MATRIX,)
    # Two edges produce DM.
    producers_of_dm = [op for op in EDGES if DYNAMICAL_MATRIX in op.outputs]
    assert set(producers_of_dm) == {identity_dm, apply_nac_correction}
    # The polar branch consumes both BornCharges and DielectricTensor.
    assert set(apply_nac_correction.inputs) == {
        BARE_DYNAMICAL_MATRIX, BORN_CHARGES, DIELECTRIC_TENSOR,
    }
    # Non-polar branch is identity on BareDM.
    assert identity_dm.inputs == (BARE_DYNAMICAL_MATRIX,)


def test_born_charges_and_dielectric_tensor_are_sources():
    """Both NAC inputs come from nullary provide_* operations."""
    from omai.thermal_transport.operator import (
        BORN_CHARGES,
        DIELECTRIC_TENSOR,
        provide_born_charges,
        provide_dielectric_tensor,
    )

    assert provide_born_charges.is_nullary()
    assert provide_born_charges.outputs == (BORN_CHARGES,)
    assert provide_dielectric_tensor.is_nullary()
    assert provide_dielectric_tensor.outputs == (DIELECTRIC_TENSOR,)


def test_compute_linewidth_has_v3_auxiliary_formula():
    """|V_3|² is now a first-class auxiliary equation on compute_linewidth."""
    import sympy as sp

    aux = compute_linewidth.auxiliary_formulas
    assert len(aux) >= 1
    eq = aux[0]
    assert isinstance(eq, sp.Basic)
    free = {str(s) for s in eq.free_symbols}
    # Eigenvector amplitudes and atomic masses must appear in the kernel.
    assert "e" in free
    assert "m" in free
    # ω products belong to the denominator.
    assert any("omega" in s.lower() for s in free)


# -- Stage 1: NAC ---------------------------------------------------------


def test_compute_dynamical_matrix_produces_bare_dm():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        compute_dynamical_matrix,
    )

    assert tuple(s.name for s in compute_dynamical_matrix.outputs) == (
        BARE_DYNAMICAL_MATRIX.name,
    )


def test_apply_nac_correction_inputs():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        BORN_CHARGES,
        DIELECTRIC_TENSOR,
        DYNAMICAL_MATRIX,
        apply_nac_correction,
    )

    assert set(s.name for s in apply_nac_correction.inputs) == {
        BARE_DYNAMICAL_MATRIX.name,
        BORN_CHARGES.name,
        DIELECTRIC_TENSOR.name,
    }
    assert tuple(s.name for s in apply_nac_correction.outputs) == (
        DYNAMICAL_MATRIX.name,
    )


def test_identity_dm_is_pattern_c_pass_through():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        DYNAMICAL_MATRIX,
        identity_dm,
    )

    assert tuple(s.name for s in identity_dm.inputs) == (BARE_DYNAMICAL_MATRIX.name,)
    assert tuple(s.name for s in identity_dm.outputs) == (DYNAMICAL_MATRIX.name,)


# -- Stage 2: harmonic thermo --------------------------------------------


def test_compute_free_energy_inputs_are_freq_and_temperature():
    from omai.thermal_transport.operator import (
        HELMHOLTZ_FREE_ENERGY,
        compute_free_energy,
    )

    assert {s.name for s in compute_free_energy.inputs} == {"Frequency", "Temperature"}
    assert tuple(s.name for s in compute_free_energy.outputs) == (
        HELMHOLTZ_FREE_ENERGY.name,
    )


def test_compute_entropy_inputs_are_freq_and_temperature():
    from omai.thermal_transport.operator import ENTROPY, compute_entropy

    assert {s.name for s in compute_entropy.inputs} == {"Frequency", "Temperature"}
    assert tuple(s.name for s in compute_entropy.outputs) == (ENTROPY.name,)


def test_compute_internal_energy_inputs():
    from omai.thermal_transport.operator import (
        INTERNAL_ENERGY,
        compute_internal_energy,
    )

    assert {s.name for s in compute_internal_energy.inputs} == {
        "Frequency",
        "Temperature",
    }
    assert tuple(s.name for s in compute_internal_energy.outputs) == (
        INTERNAL_ENERGY.name,
    )


# (test_molar_thermo_contractions above already asserts both inputs and outputs
# for the three molar contractions via State-object identity — strictly stronger
# than a name-string output check.)


# -- Stage 3: linewidth channels -----------------------------------------


def test_compute_anharmonic_linewidth_inputs():
    from omai.thermal_transport.operator import (
        ANHARMONIC_LINEWIDTH,
        compute_anharmonic_linewidth,
    )

    assert {s.name for s in compute_anharmonic_linewidth.inputs} == {
        "Frequency",
        "Eigenvectors",
        "ForceConstants[order=3]",
        "Temperature",
    }
    assert tuple(s.name for s in compute_anharmonic_linewidth.outputs) == (
        ANHARMONIC_LINEWIDTH.name,
    )


def test_compute_isotope_scattering_inputs():
    from omai.thermal_transport.operator import (
        EIGENVECTORS,
        FREQUENCY_STATE,
        ISOTOPE_ABUNDANCES,
        ISOTOPIC_LINEWIDTH,
        compute_isotope_scattering,
    )

    assert set(compute_isotope_scattering.inputs) == {
        FREQUENCY_STATE, EIGENVECTORS, ISOTOPE_ABUNDANCES,
    }
    assert compute_isotope_scattering.outputs == (ISOTOPIC_LINEWIDTH,)


def test_compute_boundary_scattering_inputs():
    from omai.thermal_transport.operator import (
        BOUNDARY_LINEWIDTH,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        compute_boundary_scattering,
    )

    assert set(compute_boundary_scattering.inputs) == {FREQUENCY_STATE, GROUP_VELOCITY}
    assert compute_boundary_scattering.outputs == (BOUNDARY_LINEWIDTH,)


def test_sum_linewidths_produces_total():
    from omai.thermal_transport.operator import (
        ANHARMONIC_LINEWIDTH,
        BOUNDARY_LINEWIDTH,
        ISOTOPIC_LINEWIDTH,
        TOTAL_LINEWIDTH,
        sum_linewidths,
    )

    assert set(sum_linewidths.inputs) == {
        ANHARMONIC_LINEWIDTH, ISOTOPIC_LINEWIDTH, BOUNDARY_LINEWIDTH,
    }
    assert sum_linewidths.outputs == (TOTAL_LINEWIDTH,)


def test_solve_bte_consumes_total_linewidth():
    """After stage 3, both solve_bte edges consume Linewidth[channel=total],
    not the legacy Linewidth."""
    from omai.thermal_transport.operator import (
        TOTAL_LINEWIDTH,
        solve_bte_direct,
        solve_bte_rta,
    )

    for op in (solve_bte_rta, solve_bte_direct):
        assert TOTAL_LINEWIDTH.name in {s.name for s in op.inputs}, (
            f"{op.name} should consume TotalLinewidth after stage 3"
        )


def test_provide_isotope_abundances_is_nullary():
    from omai.thermal_transport.operator import (
        ISOTOPE_ABUNDANCES,
        provide_isotope_abundances,
    )

    assert provide_isotope_abundances.is_nullary()
    assert tuple(s.name for s in provide_isotope_abundances.outputs) == (
        ISOTOPE_ABUNDANCES.name,
    )


# -- Stage 4: Wigner + QHGK ---------------------------------------------


def test_compute_kappa_wigner_populations_signature():
    from omai.thermal_transport.operator import (
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        MEAN_FREE_DISPLACEMENT_DIRECT,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        compute_kappa_wigner_populations,
    )

    assert set(compute_kappa_wigner_populations.inputs) == {
        HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT,
    }
    assert compute_kappa_wigner_populations.outputs == (
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    )


def test_compute_kappa_wigner_coherences_signature():
    from omai.thermal_transport.operator import (
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        TOTAL_LINEWIDTH,
        compute_kappa_wigner_coherences,
    )

    assert set(compute_kappa_wigner_coherences.inputs) == {
        HEAT_CAPACITY, FREQUENCY_STATE, GROUP_VELOCITY, TOTAL_LINEWIDTH,
    }
    assert compute_kappa_wigner_coherences.outputs == (
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    )


def test_combine_kappa_wigner_sums_populations_and_coherences():
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        combine_kappa_wigner,
    )

    inputs = {s.name for s in combine_kappa_wigner.inputs}
    assert THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS.name in inputs
    assert THERMAL_CONDUCTIVITY_WIGNER_COHERENCES.name in inputs
    assert tuple(s.name for s in combine_kappa_wigner.outputs) == (
        THERMAL_CONDUCTIVITY_WIGNER.name,
    )


def test_compute_kappa_qhgk_signature():
    from omai.thermal_transport.operator import (
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        TEMPERATURE_STATE,
        THERMAL_CONDUCTIVITY_QHGK,
        TOTAL_LINEWIDTH,
        compute_kappa_qhgk,
    )

    assert set(compute_kappa_qhgk.inputs) == {
        HEAT_CAPACITY,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        TOTAL_LINEWIDTH,
        TEMPERATURE_STATE,
    }
    assert compute_kappa_qhgk.outputs == (THERMAL_CONDUCTIVITY_QHGK,)


# -- Stage 5: cumulative κ ----------------------------------------------


def test_contract_cumulative_kappa_omega_signature():
    from omai.thermal_transport.operator import (
        CUMULATIVE_KAPPA_OMEGA,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        MEAN_FREE_DISPLACEMENT_DIRECT,
        contract_cumulative_kappa_omega,
    )

    assert set(contract_cumulative_kappa_omega.inputs) == {
        HEAT_CAPACITY,
        FREQUENCY_STATE,
        GROUP_VELOCITY,
        MEAN_FREE_DISPLACEMENT_DIRECT,
    }
    assert contract_cumulative_kappa_omega.outputs == (CUMULATIVE_KAPPA_OMEGA,)


def test_contract_cumulative_kappa_mfp_signature():
    from omai.thermal_transport.operator import (
        CUMULATIVE_KAPPA_MFP,
        GROUP_VELOCITY,
        HEAT_CAPACITY,
        MEAN_FREE_DISPLACEMENT_DIRECT,
        contract_cumulative_kappa_mfp,
    )

    assert set(contract_cumulative_kappa_mfp.inputs) == {
        HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT,
    }
    assert contract_cumulative_kappa_mfp.outputs == (CUMULATIVE_KAPPA_MFP,)
