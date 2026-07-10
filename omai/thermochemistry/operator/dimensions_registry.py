r"""Symbol-dimension registry of the thermochemistry domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.thermochemistry.operator` is imported, next to the vocabulary module.

All five thermochemistry formulas contain opaque solver functions (applied
functions the dimension walker returns None for), so the dimensional gate
classifies them SKIPPED rather than proven, exactly like solve_ground_state
and the stability edges: these bindings document the intended dimensions and
keep future closed-form refinements provable, they do not force a proof today.

Collision notes: G_m, H_m, and mu all carry ENERGY_PER_MOLE (the molar-energy
family shared with the phonon-side molar nodes, kept apart at the node level
by the quantity tag, not the dimension); NP is DIMENSIONLESS; T_{trans} is
TEMPERATURE (the same dimension as the input Temperature T, a distinct
quantity by tag).
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_MOLE,
    TEMPERATURE,
)

register_symbol_dimensions({
    "G_m": ENERGY_PER_MOLE,
    "H_m": ENERGY_PER_MOLE,
    r"\mu": ENERGY_PER_MOLE,
    "NP": DIMENSIONLESS,
    r"T_{\mathrm{trans}}": TEMPERATURE,
})
