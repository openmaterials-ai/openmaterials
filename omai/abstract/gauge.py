"""Symbolic gauge actions and invariance proofs.

A GaugeAction is a sympy-encoded transformation acting on a pattern in
formulas. Given a formula F and a gauge action g, the substrate can
mechanically check whether F is invariant under g via symbolic
substitution + simplification.

This is Level 2 of the gauge-invariance enforcement (see substrate doc).
It works cleanly for:

  * simple symbolic substitutions (e.g., U(1) phase: e → exp(iθ) e)
  * finite group actions encoded as patterns over indexed expressions

It does NOT (yet) handle:

  * continuous Lie group actions acting non-trivially on subspaces
    (e.g., U(d) rotation within a degenerate subspace) — needs symbolic
    Lie group theory beyond what sympy offers out of the box
  * data-dependent gauges (gauges that only act at specific data points
    like degenerate ω) — requires runtime knowledge of degeneracies

For those, the substrate falls back to Level 1 structural declarations.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class GaugeAction:
    """A symbolic gauge transformation.

    `pattern` is a sympy expression containing Wild symbols indicating
    the parts that get matched (e.g., `e[i_wild, q_wild, nu_wild]`).
    `transform` is the transformed form, in terms of the same Wild
    symbols (e.g., `exp(I*theta[q_wild, nu_wild]) * e[i_wild, q_wild, nu_wild]`).
    """

    name: str
    description: str
    pattern: sp.Basic
    transform: sp.Basic

    def apply_to(self, expr: sp.Basic) -> sp.Basic:
        """Apply the gauge action to an expression: pattern → transform."""
        return expr.replace(self.pattern, self.transform)

    def verifies_invariance(self, expr: sp.Basic) -> bool:
        """Whether `expr` is invariant under this gauge action.

        Verification: apply the transform, subtract from the original,
        run sympy.simplify, and check the result is zero. This works
        for substitution-based gauges where the transformed expression
        algebraically reduces back to the original.

        Returns False if sympy can't prove invariance — which is not the
        same as "expr is not invariant"; some invariances are true but
        require additional reasoning (real-valued assumptions on the
        gauge parameter, Lie-group manipulations, etc.) that sympy.simplify
        doesn't do automatically.
        """
        try:
            transformed = self.apply_to(expr)
            diff = sp.simplify(transformed - expr)
            return diff == 0 or diff == sp.S.Zero
        except Exception:
            return False


def check_invariance(
    operation_formula: sp.Basic,
    gauge_actions: Iterable[GaugeAction],
) -> dict[str, bool]:
    """Check whether an operation's formula is invariant under each
    gauge action.

    Returns a dict mapping each gauge action's name to True/False.
    Useful for building tables of "this operation preserves these gauges"
    that the substrate can use to propagate invariance claims through
    the DAG.
    """
    return {g.name: g.verifies_invariance(operation_formula) for g in gauge_actions}
