"""Operator layer: typed witnesses, operator operations, and operator workflows.

Nothing in this layer carries numerical content. States are claims that a
physics quantity exists symbolically, with a provenance recording how the
claim was derived. Edges carry the sympy formula; states do not.

When extending the DAG with a new quantity or variant, follow the rules in
`docs/skills/extend_dag.md` (the operational checklist) and
`docs/operator_representation_substrate.tex` § "DAG extension rules" (the
canonical statement). In brief:

  * Pattern A — type-level parameter on the state: only when the parameter
    changes the gauge type AND the state is terminal-ish.
  * Pattern B — sibling states + converging edge: variants with different
    input chains that combine before a downstream consumer.
  * Pattern C — shared output, alternative producing edges (with a small
    upstream intermediate to avoid cycles): same-typed output, different
    production formula.
"""

from omai.operator.crystal_symmetry import SymmetryGroup
from omai.operator.dimensions import Dimension
from omai.operator.gauge import GaugeAction, check_invariance
from omai.operator.operation import Operation, Parameter, topological_order
from omai.operator.physics_types import PhysicsType
from omai.operator.state import Field, HiddenState, Observable, State
from omai.operator.validate import validate_dag

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
    "SymmetryGroup",
    "check_invariance",
    "topological_order",
    "validate_dag",
]
