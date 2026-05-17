"""Tests for the representation-layer executor (Task 3D / T2).

One test per closed-form edge in the scope listed in
``docs/superpowers/plans/2026-05-13-phase1-consolidation.md § Task 3D``:

  * ``identity_dm`` — literal pass-through ``D[i,j,q] = D_bare[i,j,q]``.
  * ``sum_linewidths`` — Matthiessen sum
    ``Γ_tot = Γ_anh + Γ_iso + Γ_bnd``.
  * ``combine_kappa_wigner`` — sum
    ``κ^W = κ^{W,pop} + κ^{W,coh}``.
  * ``contract_molar_heat_capacity`` — full-BZ sum × N_A / N_q.
  * ``compute_heat_capacity`` — sinh form per mode.
  * ``compute_free_energy`` — log form per mode.
  * ``compute_entropy`` — ℏω/T n_BE − k_B log(1 − e^{-x}).
  * ``compute_internal_energy`` — ℏω (1/2 + n_BE).

Plus a negative test verifying that an implicit edge
(``solve_bte_direct``: linear system in the unknown) raises
``ExternalSolveRequired``.

All input ω arrays are in the operator-layer canonical frequency unit
(linear THz); T is in K; the hand-computed reference values use the
same hbar effective factor as the executor (h · 1e12 J / linear-THz).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from omai.representation.executor import (
    ExternalSolveRequired,
    apply_edge,
    operator_form_spec,
)
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    ANHARMONIC_LINEWIDTH,
    BARE_DYNAMICAL_MATRIX,
    BOUNDARY_LINEWIDTH,
    FREQUENCY_STATE,
    HEAT_CAPACITY,
    ISOTOPIC_LINEWIDTH,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    combine_kappa_wigner,
    compute_entropy,
    compute_free_energy,
    compute_heat_capacity,
    compute_internal_energy,
    contract_molar_heat_capacity,
    identity_dm,
    solve_bte_direct,
    sum_linewidths,
)


# ---------------------------------------------------------------------------
# Constants for hand-computed reference values
# ---------------------------------------------------------------------------
# Match the executor's effective hbar: ℏω with ω in linear THz produces an
# energy in J via h · 1e12. The executor uses h = 6.62607015e-34 (J·s).
_H_PLANCK = 6.62607015e-34
_HBAR_EFF = _H_PLANCK * 1.0e12  # J / (linear THz)
_KB = 1.380649e-23  # J / K
_N_A = 6.02214076e23


def _make_op_rep(state, observable_name, data) -> Representation:
    """Helper: build an operator-form Representation."""
    return Representation(
        state_adapter_spec=operator_form_spec(state),
        observable_name=observable_name,
        data=np.asarray(data),
        is_operator_form=True,
    )


# ---------------------------------------------------------------------------
# 3D-T1: identity_dm — literal pass-through
# ---------------------------------------------------------------------------


def test_apply_edge_identity_dm_passes_data_through_unchanged() -> None:
    """``identity_dm`` should return D = D_bare elementwise."""
    rng = np.random.default_rng(0)
    data = rng.random((3, 3, 5))  # arbitrary (i, j, q) array
    bare = _make_op_rep(BARE_DYNAMICAL_MATRIX, "D_bare", data)
    out = apply_edge(identity_dm, bare)
    assert out.is_operator_form is True
    assert out.state.name == "DynamicalMatrix"
    assert out.observable_name == "D"
    np.testing.assert_array_equal(out.data, data)


# ---------------------------------------------------------------------------
# 3D-T2: sum_linewidths — three-input Matthiessen sum
# ---------------------------------------------------------------------------


def test_apply_edge_sum_linewidths_is_elementwise_three_way_sum() -> None:
    """``sum_linewidths`` should return Γ_tot = Γ_anh + Γ_iso + Γ_bnd."""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 20.0, 30.0, 40.0])
    c = np.array([100.0, 200.0, 300.0, 400.0])
    rep_a = _make_op_rep(ANHARMONIC_LINEWIDTH, "Gamma", a)
    rep_b = _make_op_rep(ISOTOPIC_LINEWIDTH, "Gamma", b)
    rep_c = _make_op_rep(BOUNDARY_LINEWIDTH, "Gamma", c)
    out = apply_edge(sum_linewidths, rep_a, rep_b, rep_c)
    np.testing.assert_array_equal(out.data, a + b + c)
    assert out.state.name == "Linewidth[channel=total]"


# ---------------------------------------------------------------------------
# 3D-T3: combine_kappa_wigner — two-input sum on 3×3 tensors
# ---------------------------------------------------------------------------


def test_apply_edge_combine_kappa_wigner_is_elementwise_tensor_sum() -> None:
    """κ^W = κ^{W,pop} + κ^{W,coh}, elementwise on (α, β)."""
    rng = np.random.default_rng(1)
    pop = rng.random((3, 3))
    coh = rng.random((3, 3))
    rep_pop = _make_op_rep(
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS, "kappa", pop
    )
    rep_coh = _make_op_rep(
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES, "kappa", coh
    )
    out = apply_edge(combine_kappa_wigner, rep_pop, rep_coh)
    np.testing.assert_allclose(out.data, pop + coh)
    assert out.state.name == "ThermalConductivity[transport_model=wigner]"


# ---------------------------------------------------------------------------
# 3D-T4: contract_molar_heat_capacity — sum-and-multiply contraction
# ---------------------------------------------------------------------------


def test_apply_edge_contract_molar_heat_capacity_matches_full_bz_sum() -> None:
    """C_V_mol = N_A · Σ_qν c_qν / N_q on a synthetic (N_q, 3N_atoms) array."""
    rng = np.random.default_rng(2)
    # Shape (N_q, 3*N_atoms) with N_q=5, N_atoms=2 → 3*N_atoms=6.
    c = rng.random((5, 6)) * 1e-23
    rep_c = _make_op_rep(HEAT_CAPACITY, "c", c)
    out = apply_edge(contract_molar_heat_capacity, rep_c)
    expected = _N_A * np.sum(c) / c.shape[0]
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-12)
    assert out.state.name == "MolarHeatCapacity"


# ---------------------------------------------------------------------------
# 3D-T5: compute_heat_capacity — closed-form per-mode sinh form
# ---------------------------------------------------------------------------


def test_apply_edge_compute_heat_capacity_matches_bose_einstein_closed_form() -> None:
    """c(ω,T) = (ℏω)² / (4 k_B T² sinh²(ℏω/2k_BT))."""
    omega = np.array([5.0, 10.0, 20.0])  # linear THz
    T_value = 300.0
    rep_omega = _make_op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _make_op_rep(TEMPERATURE_STATE, "temperature", T_value)
    out = apply_edge(compute_heat_capacity, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (2 * _KB * T_value)
    c_ref = (_HBAR_EFF * omega) ** 2 / (
        4 * _KB * T_value ** 2 * np.sinh(x) ** 2
    )
    np.testing.assert_allclose(out.data, c_ref, rtol=1e-12)
    assert out.state.name == "HeatCapacity"


# ---------------------------------------------------------------------------
# 3D-T6: compute_free_energy — closed-form Helmholtz f(ω,T)
# ---------------------------------------------------------------------------


def test_apply_edge_compute_free_energy_matches_closed_form() -> None:
    """f(ω,T) = ℏω/2 + k_B T log(1 - exp(-ℏω/k_BT))."""
    omega = np.array([3.0, 7.5, 15.0])
    T_value = 250.0
    rep_omega = _make_op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _make_op_rep(TEMPERATURE_STATE, "temperature", T_value)
    out = apply_edge(compute_free_energy, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (_KB * T_value)
    f_ref = _HBAR_EFF * omega / 2 + _KB * T_value * np.log(1 - np.exp(-x))
    np.testing.assert_allclose(out.data, f_ref, rtol=1e-12)
    assert out.state.name == "HelmholtzFreeEnergy"


# ---------------------------------------------------------------------------
# 3D-T7: compute_entropy — closed-form s(ω,T) with n_BE expansion
# ---------------------------------------------------------------------------


def test_apply_edge_compute_entropy_matches_bose_einstein_form() -> None:
    """s(ω,T) = ℏω/T · n_BE(ω,T) − k_B log(1 - exp(-x))."""
    omega = np.array([4.0, 8.0, 16.0])
    T_value = 400.0
    rep_omega = _make_op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _make_op_rep(TEMPERATURE_STATE, "temperature", T_value)
    out = apply_edge(compute_entropy, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (_KB * T_value)
    n_BE = 1.0 / (np.exp(x) - 1.0)
    s_ref = _HBAR_EFF * omega / T_value * n_BE - _KB * np.log(1 - np.exp(-x))
    np.testing.assert_allclose(out.data, s_ref, rtol=1e-12)
    assert out.state.name == "Entropy"


# ---------------------------------------------------------------------------
# 3D-T8: compute_internal_energy — closed-form ℏω(1/2 + n_BE)
# ---------------------------------------------------------------------------


def test_apply_edge_compute_internal_energy_matches_bose_einstein_form() -> None:
    """e(ω,T) = ℏω (1/2 + n_BE(ω,T))."""
    omega = np.array([2.0, 6.0, 12.0])
    T_value = 500.0
    rep_omega = _make_op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _make_op_rep(TEMPERATURE_STATE, "temperature", T_value)
    out = apply_edge(compute_internal_energy, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (_KB * T_value)
    n_BE = 1.0 / (np.exp(x) - 1.0)
    e_ref = _HBAR_EFF * omega * (0.5 + n_BE)
    np.testing.assert_allclose(out.data, e_ref, rtol=1e-12)
    assert out.state.name == "InternalEnergy"


# ---------------------------------------------------------------------------
# 3D-N1: implicit edge — solve_bte_direct must raise ExternalSolveRequired
# ---------------------------------------------------------------------------


def test_apply_edge_refuses_implicit_solve_bte_direct() -> None:
    """The LBTE-direct linear system M·F = c·v has F on both sides; the
    heuristic correctly marks it not sympy-executable, and ``apply_edge``
    must raise ``ExternalSolveRequired``.

    No inputs are required to trigger the early-return; the executability
    gate fires first.
    """
    with pytest.raises(ExternalSolveRequired):
        apply_edge(solve_bte_direct)


# ---------------------------------------------------------------------------
# 3D-N2: input/state mismatches surface as ValueError
# ---------------------------------------------------------------------------


def test_apply_edge_raises_value_error_on_wrong_input_count() -> None:
    """``apply_edge`` should ValueError when len(inputs) != len(op.inputs)."""
    omega = _make_op_rep(FREQUENCY_STATE, "omega", np.array([5.0]))
    # compute_heat_capacity has 2 inputs (Frequency, Temperature); pass only 1.
    with pytest.raises(ValueError, match="expects 2 inputs"):
        apply_edge(compute_heat_capacity, omega)


def test_apply_edge_raises_value_error_on_input_not_in_operator_form() -> None:
    """Inputs must be in operator form; non-canonical inputs surface clearly."""
    omega_rep = Representation(
        state_adapter_spec=operator_form_spec(FREQUENCY_STATE),
        observable_name="omega",
        data=np.array([5.0]),
        is_operator_form=False,  # deliberately not operator form
    )
    T_rep = _make_op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    with pytest.raises(ValueError, match="not in operator form"):
        apply_edge(compute_heat_capacity, omega_rep, T_rep)


def test_apply_edge_raises_value_error_on_state_mismatch() -> None:
    """``apply_edge`` should ValueError when an input's state doesn't match
    the corresponding ``op.inputs`` entry."""
    # Pass a Temperature Representation where a Frequency Representation is
    # expected as the first input of compute_heat_capacity.
    T_rep = _make_op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    omega_rep = _make_op_rep(FREQUENCY_STATE, "omega", np.array([5.0]))
    with pytest.raises(ValueError, match="input state mismatch"):
        apply_edge(compute_heat_capacity, T_rep, omega_rep)
