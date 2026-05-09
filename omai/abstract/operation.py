"""Abstract operations (edges in the DAG).

An Operation is a typed transformation between abstract states. It declares
its input states, output state(s), parameters (dimensioned but unit-free),
algorithmic conventions (canonical-valued semantic choices that change *what*
is computed, as opposed to *how*), and a symbolic formula.

The formula is the substrate's claim about what the operation produces: a
sympy expression for closed-form ops, a sympy.Eq for implicit ones, or a
LaTeX string for ones whose formal sympy encoding is awkward (typically
indexed sums over the Brillouin zone).

The substrate's symbolic-substrate promise is that every edge carries this
formula, so adapter conformance can be expressed as a statement comparable
against the formula rather than reverse-engineered from kernels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy

from omai.abstract.dimensions import Dimension
from omai.abstract.state import State

__all__ = ["Operation", "Parameter", "topological_order"]


@dataclass(frozen=True)
class Parameter:
    name: str
    dimension: Dimension


@dataclass(frozen=True)
class Operation:
    name: str
    inputs: tuple[State, ...]
    outputs: tuple[State, ...]  # tuple to support multi-output ops like compute_dispersion
    parameters: tuple[Parameter, ...] = ()
    algorithmic_conventions: dict[str, str] = field(default_factory=dict)
    # The symbolic statement of what the operation computes. Either a sympy
    # expression / sympy.Eq, or a LaTeX string for ops whose sympy encoding
    # is awkward. None means "described in prose only" (rare).
    formula: sympy.Basic | str | None = None
    description: str = ""

    def __hash__(self) -> int:
        # Identity by name: operations are singletons in the substrate registry.
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Operation):
            return NotImplemented
        return self.name == other.name

    def is_nullary(self) -> bool:
        return len(self.inputs) == 0

    def is_multi_output(self) -> bool:
        return len(self.outputs) > 1

    def __post_init__(self) -> None:
        if not self.outputs:
            raise ValueError(f"operation {self.name!r} must have at least one output state")

    def formula_text(self) -> str:
        """Human-readable rendering of the formula."""
        if self.formula is None:
            return self.description or f"<{self.name}: no formula declared>"
        if isinstance(self.formula, str):
            return self.formula
        # sympy expression / Eq
        return sympy.latex(self.formula)


def topological_order(operations: tuple[Operation, ...]) -> list[Operation]:
    """Return the operations in topological order.

    Useful for emitting code or rendering the DAG in dependency order. Raises
    ValueError on a cycle (which would mean someone built a non-DAG).
    """
    by_state: dict[State, Operation] = {}
    for op in operations:
        for out in op.outputs:
            if out in by_state:
                raise ValueError(
                    f"two operations produce the same state {out.name!r}: "
                    f"{by_state[out].name} and {op.name}"
                )
            by_state[out] = op

    visited: set[Operation] = set()
    result: list[Operation] = []
    visiting: set[Operation] = set()

    def visit(op: Operation) -> None:
        if op in visited:
            return
        if op in visiting:
            raise ValueError(f"cycle in DAG involving {op.name!r}")
        visiting.add(op)
        for inp in op.inputs:
            producer = by_state.get(inp)
            if producer is not None:
                visit(producer)
        visiting.discard(op)
        visited.add(op)
        result.append(op)

    for op in operations:
        visit(op)
    return result
