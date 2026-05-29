"""General Sum evaluator + supplied-constants channel."""
from __future__ import annotations

import numpy as np

from omai.representation.executor import apply_edge, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    HEAT_CAPACITY,
    contract_volumetric_heat_capacity,
)

_N_A = 6.02214076e23


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
