r"""Symbol-dimension registry of the electronic-transport domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.electronic_transport.operator` is imported, next to the vocabulary module.

All five electronic-transport formulas contain opaque solver functions (the
static-dielectric assembly and the four BoltzTraP2 / iterative-BTE transport
tensors), so the dimensional gate classifies them SKIPPED rather than proven,
exactly like the thermochemistry and materials edges: these bindings document
the intended dimensions and keep future closed-form refinements provable, they
do not force a proof today.

Collision notes: \varepsilon_0 is DIMENSIONLESS (as the existing
\varepsilon_\infty of DielectricTensor); \sigma_{el} carries
ELECTRICAL_CONDUCTIVITY (the same dimension as the materials \sigma_{ion}, kept
apart at the node level by the carrier label, not the dimension); S is SEEBECK;
\kappa_e is THERMAL_CONDUCTIVITY (the same dimension as the lattice thermal
conductivity, kept apart at the node level by the electronic_thermal_conductivity
tag); \mu_e is MOBILITY.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ELECTRICAL_CONDUCTIVITY,
    MOBILITY,
    SEEBECK,
    THERMAL_CONDUCTIVITY,
)

register_symbol_dimensions({
    r"\varepsilon_0": DIMENSIONLESS,
    r"\sigma_{el}": ELECTRICAL_CONDUCTIVITY,
    "S": SEEBECK,
    r"\kappa_e": THERMAL_CONDUCTIVITY,
    r"\mu_e": MOBILITY,
})
