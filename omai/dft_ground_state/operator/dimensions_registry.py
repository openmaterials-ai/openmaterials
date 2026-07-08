r"""Symbol-dimension registry of the DFT ground-state domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.dft_ground_state.operator` is imported, next to the vocabulary module.
These bindings let the dimensional gate prove the Hellmann-Feynman force
formula (ENERGY / LENGTH = FORCE) and the stress formula
(ENERGY / (1 * VOLUME) = ENERGY_PER_LENGTH_CUBED).

V_{cell} is already registered (VOLUME) by the thermal domain and reused here.
V (the opaque potential argument of E_KS) is deliberately left unregistered, so
the solve_ground_state formula stays a dimensional SKIP rather than a guess.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    FORCE,
    LENGTH,
)

register_symbol_dimensions({
    "E_{tot}": ENERGY,
    r"F^{at}": FORCE,
    "F_j(R)": FORCE,
    r"R^{at}": LENGTH,
    r"\sigma": ENERGY_PER_LENGTH_CUBED,
    # A homogeneous strain is dimensionless (dL / L).
    r"\varepsilon^{str}": DIMENSIONLESS,
})
