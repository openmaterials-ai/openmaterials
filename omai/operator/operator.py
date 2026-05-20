"""Operators (edges in the DAG).

An `Operator` is a typed transformation between operator `Space`s. It
declares its input spaces, output space(s), parameters (dimensioned but
unit-free), schemes (canonical-valued semantic choices that change *what*
is computed, as opposed to *how*), and a operator formula.

The formula is the operator layer's claim about what the operator produces:
a sympy expression for closed-form ops, a sympy.Eq for implicit ones, or a
LaTeX string for ones whose formal sympy encoding is awkward (typically
indexed sums over the Brillouin zone).

The operator layer's promise is that every edge carries this formula, so
adapter conformance can be expressed as a statement comparable against the
formula rather than reverse-engineered from kernels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy

from omai.operator.dimensions import Dimension
from omai.operator.space import Space

__all__ = ["Operator", "Parameter", "topological_order"]


@dataclass(frozen=True)
class Parameter:
    name: str
    dimension: Dimension


@dataclass(frozen=True)
class Operator:
    name: str
    inputs: tuple[Space, ...]
    outputs: tuple[Space, ...]  # tuple to support multi-output ops like compute_dispersion
    parameters: tuple[Parameter, ...] = ()
    schemes: dict[str, str] = field(default_factory=dict)
    # The operator statement of what the operator computes. Either a sympy
    # expression / sympy.Eq, or a LaTeX string for ops whose sympy encoding
    # is awkward. None means "described in prose only" (rare).
    formula: sympy.Basic | str | None = None
    # Optional auxiliary equations that *define* symbols appearing in the
    # main formula. E.g., solve_bte_direct's main formula is a linear system
    # in the collision matrix M; the auxiliary formula defines M in terms of
    # fundamentals (Γ, |V₃|², occupations, energy-δ). Codes that claim to
    # implement the Operator must implement both the main formula AND the
    # auxiliary definitions; mismatches here are real physics disagreement.
    auxiliary_formulas: tuple[sympy.Basic | str, ...] = ()
    description: str = ""
    # Explicit override for sympy-executability. None ⇒ use the heuristic
    # (`is_executable_in_sympy_default`): an Eq with disjoint LHS/RHS free
    # symbols is closed-form. Set to False for edges whose formula passes
    # the heuristic but whose execution is, by convention, an external
    # solve. Resolved via the `is_executable_in_sympy` property.
    is_executable_in_sympy_override: bool | None = None

    def __hash__(self) -> int:
        # Identity by name: operators are singletons in the operator-layer registry.
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Operator):
            return NotImplemented
        return self.name == other.name

    def is_nullary(self) -> bool:
        return len(self.inputs) == 0

    def is_multi_output(self) -> bool:
        return len(self.outputs) > 1

    def __post_init__(self) -> None:
        if not self.outputs:
            raise ValueError(f"operator {self.name!r} must have at least one output space")

    def formula_text(self) -> str:
        """Human-readable rendering of the formula."""
        if self.formula is None:
            return self.description or f"<{self.name}: no formula declared>"
        if isinstance(self.formula, str):
            return self.formula
        # sympy expression / Eq
        return sympy.latex(self.formula)

    @property
    def is_executable_in_sympy_default(self) -> bool:
        """Heuristic: an edge is sympy-executable iff its formula is an
        explicit ``sympy.Eq`` whose LHS and RHS share no free symbols.

        The intuition: ``LHS = RHS`` is an explicit closed-form definition of
        LHS in terms of *other* quantities iff LHS doesn't appear in RHS.
        Implicit relations like ``M · F = c · v`` (with F on both sides under
        the matrix product on LHS) flunk this test and must be solved
        externally.
        """
        if not isinstance(self.formula, sympy.Eq):
            return False
        lhs_symbols = self.formula.lhs.free_symbols
        rhs_symbols = self.formula.rhs.free_symbols
        return not (lhs_symbols & rhs_symbols)

    @property
    def is_executable_in_sympy(self) -> bool:
        """Resolved sympy-executability flag.

        Returns the explicit override if set on the Operator
        (``is_executable_in_sympy_override``); otherwise falls back to
        ``is_executable_in_sympy_default``. Consumers (e.g. the representation
        executor) should read this property rather than the raw override.
        """
        if self.is_executable_in_sympy_override is not None:
            return self.is_executable_in_sympy_override
        return self.is_executable_in_sympy_default


def topological_order(operators: tuple[Operator, ...]) -> list[Operator]:
    """Return the operators in topological order.

    Useful for emitting code or rendering the DAG in dependency order. Raises
    ValueError on a cycle (which would mean someone built a non-DAG).

    A space may have more than one producing operator (Pattern C in the DAG
    extension rules: alternative producing edges into a shared output node,
    e.g. identity_dm and apply_nac_correction both producing DynamicalMatrix).
    At runtime exactly one fires per workflow instance; for topological
    ordering, all producers of a space are scheduled before any consumer.
    """
    by_space: dict[Space, list[Operator]] = {}
    for op in operators:
        for out in op.outputs:
            by_space.setdefault(out, []).append(op)

    visited: set[Operator] = set()
    result: list[Operator] = []
    visiting: set[Operator] = set()

    def visit(op: Operator) -> None:
        if op in visited:
            return
        if op in visiting:
            raise ValueError(f"cycle in DAG involving {op.name!r}")
        visiting.add(op)
        for inp in op.inputs:
            for producer in by_space.get(inp, ()):
                visit(producer)
        visiting.discard(op)
        visited.add(op)
        result.append(op)

    for op in operators:
        visit(op)
    return result
