"""Tests for the sympy chain composer (Task 3E / T3-evolve).

The composer walks a sequence of operator-layer edges and substitutes
each closed-form edge's RHS into the next. It bails at the first
implicit-equation edge with the partial expression attached.

Test scope:

  * single-edge composition returns the edge's RHS unchanged;
  * a two-edge closed-form chain substitutes correctly, eliminating
    the intermediate IndexedBase;
  * a path containing an implicit edge raises ``ImplicitEdgeBoundary``
    with the partial expression and the offending edge attached;
  * an empty path returns ``None``.
"""

from __future__ import annotations

import sympy as sp
import pytest

from omai.operator.compose import ImplicitEdgeBoundary, compose_path
from omai.thermal_transport.operator import (
    compute_heat_capacity,
    contract_molar_heat_capacity,
    solve_bte_direct,
)


# ---------------------------------------------------------------------------
# Single-edge composition: result is the edge's RHS unchanged.
# ---------------------------------------------------------------------------


def test_compose_single_edge_returns_rhs() -> None:
    """A path of one explicit edge should return that edge's formula RHS."""
    result = compose_path((compute_heat_capacity,))
    assert result == compute_heat_capacity.formula.rhs


# ---------------------------------------------------------------------------
# Two-edge closed-form chain: substitute the producing edge's RHS for its
# LHS IndexedBase wherever it appears in the consuming edge's RHS. After
# composition, the intermediate `c` IndexedBase should be gone.
# ---------------------------------------------------------------------------


def test_compose_chain_substitutes_rhs_into_lhs() -> None:
    """compute_heat_capacity -> contract_molar_heat_capacity should produce
    a closed-form expression for the molar heat capacity in which the
    intermediate per-mode `c[q, nu]` IndexedBase no longer appears.
    """
    result = compose_path((compute_heat_capacity, contract_molar_heat_capacity))
    assert result is not None

    c_base = sp.IndexedBase("c")
    bases = result.atoms(sp.IndexedBase)
    assert c_base not in bases, (
        f"intermediate IndexedBase {c_base!r} should have been substituted "
        f"away; remaining bases: {sorted(b.name for b in bases)}"
    )

    # The downstream IndexedBase used by the producer (\omega) should now
    # appear in the result — confirming the substitution actually moved
    # content from the producer's RHS into the consumer's RHS.
    omega_base = sp.IndexedBase(r"\omega")
    assert omega_base in bases


# ---------------------------------------------------------------------------
# Halt at implicit edge: solve_bte_direct's formula is a linear system in
# the unknown F (LHS contains F under the matrix product). compose_path
# must raise ImplicitEdgeBoundary with the partial expression for the
# upstream chain.
# ---------------------------------------------------------------------------


def test_compose_halts_at_implicit_edge_with_partial() -> None:
    """A path that reaches an implicit edge should raise
    ``ImplicitEdgeBoundary`` with the partial expression (the RHS of
    the last explicit edge) attached, and the offending edge identified.
    """
    with pytest.raises(ImplicitEdgeBoundary) as exc_info:
        compose_path((compute_heat_capacity, solve_bte_direct))

    err = exc_info.value
    assert err.edge is solve_bte_direct
    # Partial should be the accumulated expression up to (but not through)
    # the implicit edge — i.e. the heat-capacity RHS.
    assert err.partial is not None
    assert err.partial == compute_heat_capacity.formula.rhs


# ---------------------------------------------------------------------------
# Empty path: trivial base case, returns None (no expression to compose).
# ---------------------------------------------------------------------------


def test_compose_empty_returns_none() -> None:
    """An empty edge tuple produces no expression."""
    assert compose_path(()) is None
