"""Concrete gauge actions for the thermal-transport DAG.

Each gauge action declares the operator transformation that defines a
gauge equivalence on a HiddenSpace. The operator layer's check_invariance
machinery verifies that an operator's formula is invariant under a
declared gauge action via operator substitution.

Tractable today (sympy can verify):
  * U(1) phase on Eigenvectors — per-mode phase freedom e_{i,q,ν} → exp(iθ_{q,ν}) e_{i,q,ν}

Crystal symmetry is declared symbolically at the operator level
(see omai.operator.crystal_symmetry.SymmetryGroup) but its concrete
handling — building rotation matrices, running spglib, applying
operations to FC tensors — lives in the materials adapters (phonopy,
kaldo, etc.) where it belongs.

Not tractable today even in principle (declared at Level 1 only):
  * Degenerate-subspace U(d) rotation — data-dependent (acts only where ω is degenerate)
  * BZ-summation choice — permutation of summands with weights, needs combinatoric proof
"""

from __future__ import annotations

import sympy as sp

from omai.operator.gauge import GaugeAction
from omai.thermal_transport.operator.edges import _e


# Wild symbols for the gauge patterns. Using Wild lets the substitution match
# any indices in the formula where the targeted IndexedBase appears.
_i_w = sp.Wild("i_w")
_q_w = sp.Wild("q_w")
_nu_w = sp.Wild("nu_w")


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


GAUGES: tuple[GaugeAction, ...] = (
    U1_PHASE_ON_EIGENVECTOR,
)
