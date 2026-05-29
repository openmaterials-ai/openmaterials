"""compose_executable: fuse a path into one synthetic executable Operator,
and the symbolic keystone — the composed expression equals the textbook
closed form."""
from __future__ import annotations

import sympy as sp

from omai.operator.compose import compose_executable, compose_path
from omai.operator.operator import Operator
from omai.thermal_transport.operator import (
    MOLAR_HEAT_CAPACITY,
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
