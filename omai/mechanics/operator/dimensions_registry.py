r"""Symbol-dimension registry of the mechanics domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.mechanics.operator` is imported, next to the vocabulary module. These
bindings let the dimensional gate prove all four mechanics edges: the elastic
tensor as stress / dimensionless strain, the pressure as a stress trace, and
both Voigt moduli as contractions of the stiffness tensor. Every mechanics
field carries the energy-density dimension ENERGY_PER_LENGTH_CUBED.

No collision: C, K, G, P are otherwise-unused global base names (no existing
edge formula references them). The reused symbols \sigma
(ENERGY_PER_LENGTH_CUBED) and \varepsilon^{str} (DIMENSIONLESS) are already
registered by the dft ground-state domain and are not re-registered here.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    MASS_DENSITY,
    VOLUME,
)

register_symbol_dimensions({
    "C": ENERGY_PER_LENGTH_CUBED,
    "K": ENERGY_PER_LENGTH_CUBED,
    "G": ENERGY_PER_LENGTH_CUBED,
    "P": ENERGY_PER_LENGTH_CUBED,
    # Mass density rho (2026-07-10): the contract_density output. The edge is
    # implicit (opaque Structure readout) so the gate SKIPS it, but the binding
    # documents the intended M L^-3 and keeps a future closed form provable.
    r"\rho": MASS_DENSITY,
    # The EOS-route equilibrium volume (V_{cell} is already bound to VOLUME by
    # the thermal domain; V_0 is the new equilibrium volume the fit locates).
    "V_0": VOLUME,
    # Young's modulus: pressure-dimensioned, deliberately E_Y (bare E is the
    # thermal MD per-atom energy). Poisson ratio: dimensionless, deliberately
    # the Latin-spelled nu (\nu is the generic branch dummy). With these two
    # bindings the dimensional gate PROVES both contract edges.
    "E_Y": ENERGY_PER_LENGTH_CUBED,
    "nu": DIMENSIONLESS,
})
