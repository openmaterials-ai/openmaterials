"""omai.spec — materialization-layer adapter conformance.

Adapter specs declare, for one code, what units and conventions its
materialization carries (per State) and what algorithmic / discretization
choices its implementation makes (per Operation). The substrate uses these
to predict cross-adapter unit factors and convention mismatches at spec-
load time, before any code is run.

See docs/symbolic_substrate.tex (Principles 2, 6, 7) for the architectural
motivation. Specific State / Operation instances live alongside the
abstract DAG (e.g. omai.abstract.thermal_transport); adapter specs for
those live in domain submodules of this package.
"""

from omai.spec.adapter import (
    OperationAdapterSpec,
    StateAdapterSpec,
    cross_operation_algorithmic_match,
    cross_operation_discretization_match,
    cross_state_convention_match,
    cross_state_total_factor,
    cross_state_unit_factor,
)
from omai.spec.units import Unit, conversion_factor

__all__ = [
    "OperationAdapterSpec",
    "StateAdapterSpec",
    "Unit",
    "conversion_factor",
    "cross_operation_algorithmic_match",
    "cross_operation_discretization_match",
    "cross_state_convention_match",
    "cross_state_total_factor",
    "cross_state_unit_factor",
]
