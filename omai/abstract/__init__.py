"""Abstract layer: typed witnesses, symbolic operations, and abstract workflows.

Nothing in this layer carries numerical content. States are claims that an abstract
physics quantity exists, with a provenance recording how the claim was derived.
"""

from omai.abstract.dimensions import Dimension
from omai.abstract.gauge import GaugeAction, check_invariance
from omai.abstract.operation import Operation, Parameter, topological_order
from omai.abstract.physics_types import PhysicsType
from omai.abstract.state import Field, HiddenState, Observable, State
from omai.abstract.validate import validate_substrate

__all__ = [
    "Dimension",
    "Field",
    "GaugeAction",
    "HiddenState",
    "Observable",
    "Operation",
    "Parameter",
    "PhysicsType",
    "State",
    "check_invariance",
    "topological_order",
    "validate_substrate",
]
