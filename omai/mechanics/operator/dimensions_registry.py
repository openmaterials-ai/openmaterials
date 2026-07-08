r"""Symbol-dimension registry of the mechanics domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.mechanics.operator` is imported, next to the vocabulary module. These
bindings let the dimensional gate prove all four mechanics edges: the elastic
tensor as energy / (volume * strain^2) = energy / volume (strain is
dimensionless), the pressure as a stress trace, and both Voigt moduli as
contractions of the stiffness tensor. Every mechanics field carries the
energy-density dimension ENERGY_PER_LENGTH_CUBED.

No collision: C, K, G, P are otherwise-unused global base names (no existing
edge formula references them). The reused symbols E_{tot} (ENERGY), \sigma
(ENERGY_PER_LENGTH_CUBED), and \varepsilon^{str} (DIMENSIONLESS) are already
registered by the dft ground-state domain and are not re-registered here.
V_{cell} is registered VOLUME by the thermal domain.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import ENERGY_PER_LENGTH_CUBED

register_symbol_dimensions({
    "C": ENERGY_PER_LENGTH_CUBED,
    "K": ENERGY_PER_LENGTH_CUBED,
    "G": ENERGY_PER_LENGTH_CUBED,
    "P": ENERGY_PER_LENGTH_CUBED,
})
