r"""Symbol-dimension registry of the quasi-harmonic domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.quasiharmonic.operator` is imported, next to the vocabulary module.

All five quasi-harmonic formulas contain opaque solver functions (the QHA Gibbs
minimization, the EOS bulk modulus, the two G-derived responses, and the
mode-Gruneisen contraction), so the dimensional gate classifies them SKIPPED
rather than proven, exactly like the electronic-transport and thermochemistry
edges: these bindings document the intended dimensions and keep future
closed-form refinements provable, they do not force a proof today.

Collision notes: G_{qha} is ENERGY_PER_MOLE (the mole-energy axis the phonon and
CALPHAD molar nodes share, kept apart at the node level by the qha_gibbs_energy
tag, not the dimension); \alpha_V is THERMAL_EXPANSIVITY (1/K, the map's first
pure inverse-temperature dimension); C_P is ENERGY_PER_TEMPERATURE_PER_MOLE (the
same dimension as the harmonic MolarHeatCapacity C_V, kept apart at the node level
by the heat_capacity_constant_p tag); \gamma_{th} is DIMENSIONLESS (as the mode
\gamma_G, kept apart by the thermal_gruneisen tag). None of these base names is
otherwise used by an edge formula.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    THERMAL_EXPANSIVITY,
)

register_symbol_dimensions({
    r"G_{qha}": ENERGY_PER_MOLE,
    r"\alpha_V": THERMAL_EXPANSIVITY,
    "C_P": ENERGY_PER_TEMPERATURE_PER_MOLE,
    r"\gamma_{th}": DIMENSIONLESS,
})
