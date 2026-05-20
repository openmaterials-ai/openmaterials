"""omai.representation — the bridge between operator states and concrete data.

Per Principle 1, the representation functor connects the operator
world (typed witnesses with no numerical content) to the numeric world
(discretized arrays in concrete units). This package contains the
representation-layer machinery:

  * `units` — concrete unit choices that representations carry, with
    strict same-dimension conversion
  * `adapter` — StateRepresentationSpec and OperationRepresentationSpec, which declare
    how a particular code's outputs map onto operator states (units,
    conventions, discretization choices)

Domain instances of these specs (kaldo, phono3py, ShengBTE, ...) live
alongside their domain DAG, e.g. omai.thermal_transport.representation.
"""

from omai.representation.adapter import (
    OperationRepresentationSpec,
    StateRepresentationSpec,
    operator_to_representation,
    representation_algorithmic_match,
    representation_discretization_match,
    representation_convention_match,
    inter_representation_factor,
    inter_representation_unit_factor,
    representation_to_operator,
)
from omai.representation.compare import RepresentationComparisonResult, compare
from omai.representation.instance import Representation, represent
from omai.representation.units import Unit, conversion_factor

__all__ = [
    "RepresentationComparisonResult",
    "Representation",
    "OperationRepresentationSpec",
    "StateRepresentationSpec",
    "Unit",
    "compare",
    "conversion_factor",
    "representation_algorithmic_match",
    "representation_discretization_match",
    "representation_convention_match",
    "operator_to_representation",
    "inter_representation_factor",
    "inter_representation_unit_factor",
    "represent",
    "representation_to_operator",
]
