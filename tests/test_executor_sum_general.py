"""General Sum evaluator + supplied-constants channel."""
from __future__ import annotations

import numpy as np
import sympy as sp

from omai.operator.compose import compose_executable
from omai.representation.executor import apply_edge, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    FREQUENCY_STATE, TEMPERATURE_STATE, MOLAR_HEAT_CAPACITY,
    GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT, THERMAL_CONDUCTIVITY_DIRECT,
    HEAT_CAPACITY,
    compute_heat_capacity, contract_molar_heat_capacity, contract_kappa_direct,
    contract_volumetric_heat_capacity,
)

_N_A = 6.02214076e23
_H = 6.62607015e-34
_HBAR_EFF = _H * 1.0e12
_KB = 1.380649e-23


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def test_apply_edge_binds_supplied_V_cell_constant():
    """contract_volumetric_heat_capacity = Σ c / (V_cell · N_q); supplying
    V_cell via constants lets the executor evaluate it."""
    c = np.array([[1.0, 2.0], [3.0, 4.0]])  # (N_q=2, N_modes=2)
    rep = _op_rep(HEAT_CAPACITY, "c", c)
    v_cell = 40.0
    out = apply_edge(contract_volumetric_heat_capacity, rep, constants={"V_{cell}": v_cell})
    expected = np.sum(c) / (v_cell * c.shape[0])
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-12)


def test_general_sum_evaluates_composed_sinh_summand_scalar():
    """Σ_qν c(ω_qν,T) with the sinh kernel *inside* the Sum (composed molar Cv)
    evaluates to N_A/N_q · Σ c — equal to executing the two edges separately."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    rep_omega = _op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    out = apply_edge(fused, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (2 * _KB * 300.0)
    c = (_HBAR_EFF * omega) ** 2 / (4 * _KB * 300.0 ** 2 * np.sinh(x) ** 2)
    expected = _N_A * np.sum(c) / omega.shape[0]
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-10)


def test_general_sum_evaluates_cvF_tensor_contraction():
    """κ[α,β] = (1/(N_q V)) Σ_qν c[q,ν] v[α,q,ν] F[β,q,ν] — a tensor contraction
    (free α,β survive the sum). Compare to a hand einsum."""
    rng = np.random.default_rng(3)
    N_q, N_modes = 4, 6
    c = rng.random((N_q, N_modes))
    v = rng.random((3, N_q, N_modes))
    F = rng.random((3, N_q, N_modes))
    v_cell = 40.0
    rep_c = _op_rep(HEAT_CAPACITY, "c", c)
    rep_v = _op_rep(GROUP_VELOCITY, "v", v)
    rep_F = _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", F)
    out = apply_edge(contract_kappa_direct, rep_c, rep_v, rep_F,
                     constants={"V_{cell}": v_cell})
    expected = np.einsum("qn,aqn,bqn->ab", c, v, F) / (N_q * v_cell)
    assert out.data.shape == (3, 3)
    np.testing.assert_allclose(out.data, expected, rtol=1e-10)


def test_contract_kappa_direct_is_executable():
    assert contract_kappa_direct.is_executable_in_sympy is True
