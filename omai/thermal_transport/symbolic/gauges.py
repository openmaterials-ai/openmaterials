"""Concrete gauge actions for the thermal-transport DAG.

Each gauge action declares the symbolic transformation that defines a
gauge equivalence on a HiddenState. The substrate's check_invariance
machinery verifies that an operation's formula is invariant under a
declared gauge action via symbolic substitution.

Tractable today (sympy can verify):
  * U(1) phase on Eigenvectors — per-mode phase freedom e_{i,q,ν} → exp(iθ_{q,ν}) e_{i,q,ν}

Not tractable today (declared at Level 1 only):
  * Degenerate-subspace U(d) rotation — data-dependent (acts only where ω is degenerate)
  * BZ-summation choice — permutation of summands with weights, needs combinatoric proof
"""

from __future__ import annotations

import sympy as sp

from omai.abstract.gauge import GaugeAction, fc2_gauge_from_symmetry_op
from omai.thermal_transport.symbolic.edges import _Phi2, _e


# Wild symbols for the gauge patterns. Using Wild lets the substitution match
# any indices in the formula where the targeted IndexedBase appears.
_i_w = sp.Wild("i_w")
_j_w = sp.Wild("j_w")
_q_w = sp.Wild("q_w")
_nu_w = sp.Wild("nu_w")
_R_w = sp.Wild("R_w")


# === U(1) phase on Eigenvectors ===

# Per-mode phase parameter θ_{q,ν}, real-valued (sympy needs `real=True` so
# that conjugate(exp(I·θ)) simplifies to exp(-I·θ)).
_theta = sp.IndexedBase(r"\theta", real=True)

U1_PHASE_ON_EIGENVECTOR = GaugeAction(
    name="U(1)_phase_on_eigenvector",
    description=(
        "Per-mode phase freedom on the eigenvector: "
        "e_{i, q, ν} → exp(i θ_{q, ν}) e_{i, q, ν}. "
        "θ_{q, ν} is real and arbitrary. Each (q, ν) mode has its own phase."
    ),
    pattern=_e[_i_w, _q_w, _nu_w],
    transform=sp.exp(sp.I * _theta[_q_w, _nu_w]) * _e[_i_w, _q_w, _nu_w],
)


# === Crystal symmetry ===
#
# Crystal symmetry is data-driven: each material declares its point group
# as a CrystalPointGroup (list of SymmetryOperation generators), often
# extracted via spglib in real codes. The substrate then builds the
# corresponding GaugeActions on demand via fc2_gauge_from_symmetry_op.
#
# What's "tractable today" for symbolic invariance proofs: operations
# whose rotation is diagonal in Cartesian indices (identity, inversion,
# and the trivial Cartesian-aligned mirror planes when all three signs
# are identical). General rotations and mixed-sign mirrors require
# expanding the FC² index space and are deferred.
#
# Below: spatial inversion as a concrete, machine-verifiable instance.

from omai.abstract.crystal_symmetry import INVERSION

CRYSTAL_INVERSION_ON_FC2 = fc2_gauge_from_symmetry_op(
    INVERSION, _Phi2, _i_w, _j_w, _R_w
)
assert CRYSTAL_INVERSION_ON_FC2 is not None, "inversion must be substitution-friendly"


GAUGES: tuple[GaugeAction, ...] = (
    U1_PHASE_ON_EIGENVECTOR,
    CRYSTAL_INVERSION_ON_FC2,
)


def symmetrized_fc2(
    fc2: sp.IndexedBase | None = None,
    i=None,
    j=None,
    R=None,
) -> sp.Expr:
    """The symmetrized harmonic FC² under the Z/2 inversion orbit.

    Φ²_sym_{ij}(R) = (Φ²_{ij}(R) + Φ²_{ij}(-R)) / 2

    Invariant under `CRYSTAL_INVERSION_ON_FC2` by construction; sympy can
    verify this mechanically via `verifies_invariance`. Extending to a
    larger group: replace this 2-element average with a sum over the full
    group orbit normalized by |G|.
    """
    fc2 = fc2 if fc2 is not None else _Phi2
    if i is None:
        i = sp.Symbol("i", integer=True)
    if j is None:
        j = sp.Symbol("j", integer=True)
    if R is None:
        R = sp.Symbol("R")
    return (fc2[i, j, R] + fc2[i, j, -R]) / 2
