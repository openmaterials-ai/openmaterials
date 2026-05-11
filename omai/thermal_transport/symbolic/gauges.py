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

from omai.abstract.gauge import GaugeAction
from omai.thermal_transport.symbolic.edges import _e, _Phi2


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


# === Crystal symmetry: spatial inversion ===
#
# A first concrete crystal-symmetry GaugeAction. The full point group is a
# finite set of generators; here we encode the simplest non-trivial
# element — spatial inversion P = -𝟙 — and show that a symmetrized FC²
# tensor is invariant under it (mechanical sympy proof).
#
# Inversion's action on FC²:
#     Φ²_{ij}(R) → Σ_{i'j'} P_{ii'} P_{jj'} Φ²_{i'j'}(P·R)
#                = Σ_{i'j'} (-δ_{ii'})(-δ_{jj'}) Φ²_{i'j'}(-R)
#                = Φ²_{ij}(-R)
#
# Extending to a full point group: add one GaugeAction per generator (or
# build a higher-level CrystalPointGroup that aggregates them and verifies
# invariance under every generator). Done one generator at a time, this
# remains in the "tractable today" tier — sympy substitution + simplify
# handles each finite-group element. Lie-group orbits are out of scope.

CRYSTAL_INVERSION_ON_FC2 = GaugeAction(
    name="crystal_inversion_on_FC2",
    description=(
        "Spatial inversion on the harmonic force-constant tensor: "
        "Φ²_{ij}(R) → Φ²_{ij}(-R). One element of the cubic point group; "
        "the symmetrized FC² (averaged over the Z/2 orbit {𝟙, P}) is "
        "invariant under this action."
    ),
    pattern=_Phi2[_i_w, _j_w, _R_w],
    transform=_Phi2[_i_w, _j_w, -_R_w],
)


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
