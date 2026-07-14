r"""Symbol-dimension registry of the composites (effective-medium) domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.composites.operator` is imported, next to the vocabulary module. Four of
this domain's five edges are executable closed forms the dimensional gate PROVES
(the fifth, depolarization_factors, is a Piecewise the gate skips), so these
bindings are load-bearing: they let dimension_of evaluate both sides of the Nan
random / aligned and Hasselman-Johnson formulas.

  k_m           -> THERMAL_CONDUCTIVITY   (matrix conductivity km)
  k_f           -> THERMAL_CONDUCTIVITY   (filler tensor; its diagonal k_f[1,1]=k11, k_f[3,3]=k33)
  G_{int}       -> INTERFACE_CONDUCTANCE  (Kapitza interface conductance G, W/(m^2 K))
  d_1           -> LENGTH                 (equatorial inclusion dimension)
  d_3           -> LENGTH                 (polar inclusion dimension)
  a_{rad}       -> LENGTH                 (sphere radius, Hasselman-Johnson)
  f_{vol}       -> DIMENSIONLESS          (filler volume fraction)
  L_{11}, L_{33}-> DIMENSIONLESS          (depolarization factors)
  p             -> DIMENSIONLESS          (aspect ratio d3/d1)
  \kappa_c      -> THERMAL_CONDUCTIVITY   (composite effective conductivity)

The gate then proves the Nan / HJ closed forms because the interface term
2 (1/G) k_ii / d_i = (m^2 K/W)(W/mK)/m is dimensionless, beta_ii is a ratio of
two THERMAL_CONDUCTIVITY quantities, and the Hasselman-Johnson alpha = (km/G)/a
is a length over a length; so the effective kappa carries km's
THERMAL_CONDUCTIVITY exactly. No collision: k_m, k_f, G_{int}, f_{vol},
L_{11}, L_{33}, \kappa_c, a_{rad}, p are otherwise-unused base names (d_1 / d_3
are this domain's; \kappa is already bound to THERMAL_CONDUCTIVITY by
thermal_transport, a harmless matching union).
"""
from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    INTERFACE_CONDUCTANCE,
    LENGTH,
    THERMAL_CONDUCTIVITY,
)

register_symbol_dimensions({
    "k_m": THERMAL_CONDUCTIVITY,
    "k_f": THERMAL_CONDUCTIVITY,
    "G_{int}": INTERFACE_CONDUCTANCE,
    "d_1": LENGTH,
    "d_3": LENGTH,
    "a_{rad}": LENGTH,
    "f_{vol}": DIMENSIONLESS,
    "L_{11}": DIMENSIONLESS,
    "L_{33}": DIMENSIONLESS,
    "p": DIMENSIONLESS,
    r"\kappa_c": THERMAL_CONDUCTIVITY,
})
