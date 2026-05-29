"""omai.representation — the bridge between operator Spaces and concrete data.

Per Principle 1, the representation functor connects the operator
world (typed witnesses with no numerical content) to the numeric world
(discretized arrays in concrete units and normalizations). This package
contains the representation-layer machinery:

  * `units` — concrete unit choices that representations carry, with
    strict same-dimension conversion
  * `normalizations` — definitional choices (`Γ = 2 Im Σ` vs canonical;
    `eV/Å³` vs `eV/(Å²·nm)`) that compose with units to produce the
    operator-canonical numerical form
  * `adapter` — SpaceRepresentationSpec and OperatorRepresentationSpec,
    which declare how a particular code's outputs map onto operator
    Spaces (units, normalizations, schemes, discretization choices)

Domain instances of these specs (kaldo, phono3py, ShengBTE, ...) live
alongside their domain DAG, e.g. omai.thermal_transport.representation.
"""

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
    operator_to_representation,
    representation_discretization_match,
    representation_scheme_match,
    representation_to_operator,
)
from omai.representation.compare import RepresentationComparisonResult, compare
from omai.representation.executor import (
    ComputeResult,
    NoSourceError,
    Source,
    TraceStep,
    compute,
)
from omai.representation.instance import Representation, represent
from omai.representation.normalizations import NORMALIZATIONS, Normalization
from omai.representation.units import Unit, conversion_factor

__all__ = [
    "NORMALIZATIONS",
    "Normalization",
    "RepresentationComparisonResult",
    "Representation",
    "OperatorRepresentationSpec",
    "SpaceRepresentationSpec",
    "Unit",
    "compare",
    "compute",
    "ComputeResult",
    "conversion_factor",
    "NoSourceError",
    "operator_to_representation",
    "represent",
    "representation_discretization_match",
    "representation_scheme_match",
    "representation_to_operator",
    "Source",
    "TraceStep",
]
