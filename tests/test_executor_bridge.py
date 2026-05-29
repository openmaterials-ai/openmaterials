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
