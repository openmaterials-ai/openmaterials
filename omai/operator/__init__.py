"""Operator layer: typed witnesses, operators, and operator workflows.

Nothing in this layer carries numerical content. `Space`s are claims that a
physics quantity exists symbolically, with a provenance recording how the
claim was derived. Edges (`Operator`s) carry the sympy formula; spaces do not.

When extending the DAG with a new quantity or variant, follow the rules in
`docs/skills/extend_dag.md` (the operational checklist) and
`docs/operator_representation_substrate.tex` § "DAG extension rules" (the
canonical statement). In brief:

  * Pattern A — labels on the space: only when the label changes the
    gauge type AND the space is terminal-ish.
  * Pattern B — sibling spaces + converging edge: variants with different
    input chains that combine before a downstream consumer.
  * Pattern C — shared output, alternative producing edges (with a small
    upstream intermediate to avoid cycles): same-typed output, different
    production formula.
"""

from omai.operator.crystal_symmetry import SymmetryGroup
from omai.operator.dimensions import Dimension
from omai.operator.gauge import GaugeAction, check_invariance
from omai.operator.operator import Operator, Parameter, topological_order
from omai.operator.space import Field, HiddenSpace, ObservableSpace, Space
from omai.operator.validate import validate_dag

__all__ = [
    "Dimension",
    "Field",
    "GaugeAction",
    "HiddenSpace",
    "ObservableSpace",
    "Operator",
    "Parameter",
    "Space",
    "SymmetryGroup",
    "check_invariance",
    "topological_order",
    "validate_dag",
]
