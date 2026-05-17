"""Symbolic composition of operator-layer edges.

Walks a path of edges in topological order. For each explicit-equation
edge, substitutes the RHS of the previous edge's formula into the LHS
of the next. Bails at any implicit edge with a structured note pointing
at the boundary.

This is the in-sympy realisation of the Lean commitment: given a path
of explicit-equation edges, ``compose_path`` produces a single symbolic
expression for the path's terminal node. Implicit-equation edges (e.g.
``solve_bte_direct``) raise :class:`ImplicitEdgeBoundary`, marking the
open subproblem of composing across an external solve.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operation import Operation

__all__ = ["ImplicitEdgeBoundary", "compose_path"]


class ImplicitEdgeBoundary(Exception):
    """Raised when composition reaches an implicit edge.

    The composed expression up to (but not through) the edge is
    attached as the ``partial`` attribute; the offending edge is
    ``edge``. Callers can recover the symbolic chain produced so far
    and use it as the boundary condition for the external solve.
    """

    def __init__(self, edge: Operation, partial: sp.Expr | None) -> None:
        super().__init__(f"composition halts at implicit edge {edge.name!r}")
        self.edge = edge
        self.partial = partial


def _substitute(prev_lhs: sp.Basic, prev_rhs: sp.Expr, into: sp.Expr) -> sp.Expr:
    """Substitute ``prev_lhs := prev_rhs`` everywhere in ``into``.

    Two cases are handled:

    1. ``prev_lhs`` is a plain :class:`~sympy.core.symbol.Symbol` — use
       :meth:`xreplace`, which is safe inside binders (``Sum``, ``Integral``).
    2. ``prev_lhs`` is an :class:`~sympy.tensor.indexed.Indexed` expression
       (e.g. ``c[q, nu]``) — match every :class:`Indexed` sharing the same
       :class:`IndexedBase` in ``into``, rebinding ``prev_rhs``'s indices
       to the matched ones. This handles the common case where the source
       edge writes ``c[q, nu] = …`` and the consumer edge sums
       ``c[q', nu']`` (or the same ``c[q, nu]`` as a dummy under ``Sum``).

    Limitations: only handles single-IndexedBase LHS expressions. Edges
    whose LHS is a more exotic expression (e.g. a derivative or function
    application) are out of scope for this v0.
    """
    if isinstance(prev_lhs, sp.Symbol):
        return into.xreplace({prev_lhs: prev_rhs})

    if isinstance(prev_lhs, sp.Indexed):
        base = prev_lhs.base
        prev_indices = prev_lhs.indices
        # Build a Wild for each index position; replace every occurrence of
        # base[*wilds] in `into` with prev_rhs[prev_indices := wilds].
        # sympy's ``replace`` invokes the value-builder with keyword args
        # named after the Wild symbols (stripped of the trailing ``_``),
        # so we key the builder by those names.
        wild_names = tuple(f"_compose_w{k}" for k in range(len(prev_indices)))
        wilds = tuple(sp.Wild(name, exclude=()) for name in wild_names)
        pattern = base[wilds] if len(wilds) > 1 else base[wilds[0]]

        def _build(**matched: sp.Basic) -> sp.Expr:
            ordered = tuple(matched[name] for name in wild_names)
            return prev_rhs.subs(dict(zip(prev_indices, ordered)))

        return into.replace(pattern, _build)

    raise NotImplementedError(
        f"compose: don't know how to substitute LHS of type "
        f"{type(prev_lhs).__name__!r} (expected Symbol or Indexed)"
    )


def compose_path(edges: tuple[Operation, ...]) -> sp.Expr | None:
    """Compose a sequence of explicit-equation edges into a single sympy
    expression for the final output.

    For each edge in ``edges`` (in order):

      * If the edge is not :attr:`Operation.is_executable_in_sympy`,
        raise :class:`ImplicitEdgeBoundary` with the partial expression
        accumulated so far.
      * Take the edge's formula (an :class:`sp.Eq`); the LHS is the
        edge's output symbol or indexed expression. Substitute the
        previous accumulator into the current RHS, matching by the
        previous edge's LHS symbol/indexed base. The new accumulator
        is the substituted RHS.

    For an empty path, returns ``None``. For a single-edge path,
    returns the edge's RHS unchanged.

    Raises :class:`ImplicitEdgeBoundary` on the first implicit edge.
    Raises :class:`TypeError` if an edge's formula is not an
    :class:`sp.Eq` (the composer requires an explicit LHS = RHS form).
    """
    if not edges:
        return None

    expr: sp.Expr | None = None
    prev_lhs: sp.Basic | None = None

    for edge in edges:
        if not edge.is_executable_in_sympy:
            raise ImplicitEdgeBoundary(edge=edge, partial=expr)

        if not isinstance(edge.formula, sp.Eq):
            raise TypeError(
                f"compose: edge {edge.name!r} has formula of type "
                f"{type(edge.formula).__name__!r}; expected sympy.Eq"
            )

        this_lhs = edge.formula.lhs
        this_rhs = edge.formula.rhs

        if expr is None:
            # First edge: accumulator is just the RHS.
            expr = this_rhs
        else:
            assert prev_lhs is not None
            expr = _substitute(prev_lhs, expr, this_rhs)

        prev_lhs = this_lhs

    return expr
