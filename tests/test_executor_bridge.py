"""Dimensional bridge: V_cell typing + automatic unit reconciliation."""
from __future__ import annotations

import numpy as np

from omai.operator.dimensions import VOLUME
from omai.thermal_transport.operator import (
    contract_kappa_direct,
    contract_volumetric_heat_capacity,
)


def test_v_cell_is_typed_volume_parameter_on_both_contractions():
    for op in (contract_kappa_direct, contract_volumetric_heat_capacity):
        params = {p.name: p.dimension for p in op.parameters}
        assert "V_{cell}" in params, f"{op.name} missing V_{{cell}} parameter"
        assert params["V_{cell}"] is VOLUME


import sympy as sp
from omai.representation.executor import _dimensional_bridge, apply_edge, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT,
    compute_heat_capacity, identity_dm, sum_linewidths,
)


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def test_bridge_is_unity_for_closed_form_and_identity_edges():
    assert _dimensional_bridge(compute_heat_capacity) == 1.0
    assert _dimensional_bridge(identity_dm) == 1.0
    assert _dimensional_bridge(sum_linewidths) == 1.0


def test_bridge_for_kappa_direct_is_1e22():
    from omai.thermal_transport.operator import contract_kappa_direct
    assert _dimensional_bridge(contract_kappa_direct) == 1e22


def test_bridge_for_volumetric_cv_is_1e30():
    from omai.thermal_transport.operator import contract_volumetric_heat_capacity
    assert _dimensional_bridge(contract_volumetric_heat_capacity) == 1e30


def test_bridge_for_molar_cv_is_unity():
    from omai.thermal_transport.operator import contract_molar_heat_capacity
    assert _dimensional_bridge(contract_molar_heat_capacity) == 1.0


def test_apply_edge_kappa_yields_physical_units_without_manual_factor():
    from omai.thermal_transport.operator import contract_kappa_direct
    rng = np.random.default_rng(3)
    N_q, N_modes = 4, 6
    c = rng.random((N_q, N_modes))
    v = rng.random((3, N_q, N_modes))
    F = rng.random((3, N_q, N_modes))
    v_cell = 40.0
    out = apply_edge(
        contract_kappa_direct,
        _op_rep(HEAT_CAPACITY, "c", c),
        _op_rep(GROUP_VELOCITY, "v", v),
        _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", F),
        constants={"V_{cell}": v_cell},
    )
    expected = np.einsum("qn,aqn,bqn->ab", c, v, F) / (N_q * v_cell) * 1e22
    np.testing.assert_allclose(out.data, expected, rtol=1e-10)


def test_bridge_computable_for_every_executable_edge():
    """No executable edge may raise in _dimensional_bridge (e.g. an input
    dimension lacking a canonical si_scale). Guards the regression where
    contract_molar_free_energy / _internal_energy hit the 'energy' dimension
    which had no unit."""
    from omai.thermal_transport.operator import EDGES
    for op in EDGES:
        if not op.is_executable_in_sympy:
            continue
        bridge = _dimensional_bridge(op)   # must not raise
        assert np.isfinite(bridge) and bridge > 0, f"{op.name}: bad bridge {bridge}"


def test_bridge_unity_for_molar_energy_contractions():
    from omai.thermal_transport.operator import (
        contract_molar_free_energy, contract_molar_internal_energy,
        contract_molar_entropy,
    )
    assert _dimensional_bridge(contract_molar_free_energy) == 1.0
    assert _dimensional_bridge(contract_molar_internal_energy) == 1.0
    assert _dimensional_bridge(contract_molar_entropy) == 1.0


def test_apply_edge_molar_free_energy_executes_without_raising():
    from omai.thermal_transport.operator import (
        HELMHOLTZ_FREE_ENERGY, contract_molar_free_energy,
    )
    f = np.array([[1e-21, 2e-21], [3e-21, 4e-21]])  # (N_q, N_modes), per-mode J
    out = apply_edge(contract_molar_free_energy, _op_rep(HELMHOLTZ_FREE_ENERGY, "f", f))
    # bridge is 1.0; result is N_A * sum(f) / N_q
    N_A = 6.02214076e23
    expected = N_A * np.sum(f) / f.shape[0]
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-10)
