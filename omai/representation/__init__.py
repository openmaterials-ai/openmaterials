"""omai.representation — the bridge between operator states and concrete data.

Per Principle 1, the representation functor connects the operator
world (typed witnesses with no numerical content) to the numeric world
(discretized arrays in concrete units). This package contains the
representation-layer machinery:

  * `units` — concrete unit choices that representations carry, with
    strict same-dimension conversion
  * `adapter` — StateAdapterSpec and OperationAdapterSpec, which declare
    how a particular code's outputs map onto operator states (units,
    conventions, discretization choices)

Domain instances of these specs (kaldo, phono3py, ShengBTE, ...) live
alongside their domain DAG, e.g. omai.thermal_transport.representation.
"""

from omai.representation.adapter import (
    OperationAdapterSpec,
    StateAdapterSpec,
    from_operator_form_factor,
    representation_algorithmic_match,
    representation_discretization_match,
    representation_convention_match,
    inter_representation_factor,
    inter_representation_unit_factor,
    to_operator_form_factor,
)
from omai.representation.compare import RepresentationComparisonResult, compare
from omai.representation.instance import Representation, represent
from omai.representation.units import Unit, conversion_factor

__all__ = [
    "RepresentationComparisonResult",
    "Representation",
    "OperationAdapterSpec",
    "StateAdapterSpec",
    "Unit",
    "compare",
    "conversion_factor",
    "representation_algorithmic_match",
    "representation_discretization_match",
    "representation_convention_match",
    "from_operator_form_factor",
    "inter_representation_factor",
    "inter_representation_unit_factor",
    "represent",
    "to_operator_form_factor",
]
