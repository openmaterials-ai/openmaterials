"""omai.materialization — the bridge between abstract states and concrete data.

Per substrate Principle 1, the materialization functor connects the abstract
world (typed witnesses with no numerical content) to the numeric world
(discretized arrays in concrete units). This package contains the
materialization-layer machinery:

  * `units` — concrete unit choices that materializations carry, with
    strict same-dimension conversion
  * `adapter` — StateAdapterSpec and OperationAdapterSpec, which declare
    how a particular code's outputs map onto abstract states (units,
    conventions, discretization choices)

Domain instances of these specs (kaldo, phono3py, ShengBTE, ...) live
alongside their domain DAG, e.g. omai.thermal_transport.materialized.
"""

from omai.materialization.adapter import (
    OperationAdapterSpec,
    StateAdapterSpec,
    cross_operation_algorithmic_match,
    cross_operation_discretization_match,
    cross_state_convention_match,
    cross_state_total_factor,
    cross_state_unit_factor,
)
from omai.materialization.units import Unit, conversion_factor

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
