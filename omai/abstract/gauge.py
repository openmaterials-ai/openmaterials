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


# ---------------------------------------------------------------------------
# Factories: build GaugeActions from data
# ---------------------------------------------------------------------------


def fc2_gauge_from_symmetry_op(
    op: "SymmetryOperation",  # noqa: F821 (forward-ref to avoid import cycle)
    fc2_indexed_base: sp.IndexedBase,
    i_wild: sp.Wild,
    j_wild: sp.Wild,
    R_wild: sp.Wild,
) -> GaugeAction | None:
    """Build a GaugeAction encoding `op`'s action on FC², if substitution-friendly.

    Returns None when the operation's rotation has off-diagonal coupling
    between Cartesian components (e.g., 90° rotation around z mixing x↔y).
    Such operations are declared but not symbolically verified by the
    current substrate machinery — see the substrate doc for the levels of
    tractability.

    Substitution-friendly today: operations whose rotation matrix is a
    diagonal sign matrix (entries +1, -1, 0 with at most one non-zero per
    row/column AND the non-zero on the diagonal). This covers identity,
    inversion, and Cartesian mirror planes; it excludes general rotations.
    """
    from omai.abstract.crystal_symmetry import SymmetryOperation

    if not isinstance(op, SymmetryOperation):
        return None

    R = op.rotation
    # Check diagonal structure
    is_diagonal = all(R[i][j] == 0 for i in range(3) for j in range(3) if i != j)
    if not is_diagonal:
        return None
    signs = (R[0][0], R[1][1], R[2][2])
    if any(s not in (-1, 1) for s in signs):
        return None
    # Action on Φ²_{ij}(R_vec):
    #     Φ²_{ij}(R_vec) → ε_i ε_j Φ²_{ij}(R_op · R_vec)
    # Cartesian indices are 0/1/2 in spglib's lattice basis; for a fully
    # diagonal rotation, ε_i depends on i. Without expanding the index
    # space, we collapse to the special case ε_i · ε_j = constant when
    # signs are identical along all three Cartesian directions.
    if signs == (1, 1, 1):
        # Identity — gauge is trivial
        return GaugeAction(
            name=f"identity_{op.name}_on_FC2",
            description="Identity action: Φ²_{ij}(R) → Φ²_{ij}(R).",
            pattern=fc2_indexed_base[i_wild, j_wild, R_wild],
            transform=fc2_indexed_base[i_wild, j_wild, R_wild],
        )
    if signs == (-1, -1, -1):
        # Inversion — (-1)(-1) = +1 sign overall; R_vec → -R_vec
        return GaugeAction(
            name=f"inversion_{op.name}_on_FC2",
            description=(
                f"Spatial inversion ({op.name}): "
                "Φ²_{ij}(R) → Φ²_{ij}(-R) (signs cancel pairwise)."
            ),
            pattern=fc2_indexed_base[i_wild, j_wild, R_wild],
            transform=fc2_indexed_base[i_wild, j_wild, -R_wild],
        )
    # Mixed signs (mirror planes): the ε_i ε_j factor depends on which
    # Cartesian components i and j are. Substrate would need to expand
    # the index space (separate FC² components for each (i, j) Cartesian
    # pair) to encode this cleanly. Deferred.
    return None
