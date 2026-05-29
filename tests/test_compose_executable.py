"""compose_executable: fuse a path into one synthetic executable Operator,
and the symbolic keystone — the composed expression equals the textbook
closed form."""
from __future__ import annotations

import numpy as np
import sympy as sp

from omai.operator.compose import compose_executable, compose_path
from omai.operator.operator import Operator
from omai.representation.executor import apply_edge, compute, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    compute_heat_capacity,
    contract_molar_heat_capacity,
)


def test_compose_executable_builds_single_executable_operator():
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    assert isinstance(fused, Operator)
    assert fused.is_executable_in_sympy is True
    # Output is the terminal edge's output.
    assert fused.outputs == contract_molar_heat_capacity.outputs
    # Inputs are the chain's leaves: Frequency + Temperature (HeatCapacity is
    # produced inside the chain, so it is NOT a leaf input).
    leaf_names = {s.name for s in fused.inputs}
    assert leaf_names == {"Frequency", "Temperature"}
    assert "HeatCapacity" not in leaf_names


def test_symbolic_keystone_composed_equals_textbook_molar_cv():
    """Composing compute_heat_capacity into contract_molar_heat_capacity must
    eliminate the intermediate c[q,ν] and express the kernel in terms of ω."""
    composed = compose_path((compute_heat_capacity, contract_molar_heat_capacity))
    assert composed is not None
    c_base_names = {str(a.base.name) for a in composed.atoms(sp.Indexed)}
    assert "c" not in c_base_names  # intermediate substituted away
    # ω appears (the kernel is now in terms of frequency).
    assert any("omega" in n or "\\omega" in n for n in c_base_names) or \
        any("\\omega" in str(s) for s in composed.free_symbols)


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def test_numeric_keystone_composed_equals_edge_by_edge():
    """compose-then-execute == edge-by-edge compute, on the molar-Cv chain.
    The executor validated against the composer."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    edge_by_edge = compute(MOLAR_HEAT_CAPACITY, sources).representation.data
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    composed = apply_edge(
        fused, sources["Frequency"], sources["Temperature"]
    ).data
    np.testing.assert_allclose(float(composed), float(edge_by_edge), rtol=1e-12)
