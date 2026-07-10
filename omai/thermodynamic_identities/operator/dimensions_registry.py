r"""Symbol-dimension registry of the thermodynamic-identities domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.thermodynamic_identities.operator` is imported, next to the vocabulary
module. Unlike every other domain (whose edges carry opaque solver functions and
are SKIPPED by the gate), THIS domain's six edges are all executable closed forms
the gate PROVES, so these four new bindings are load-bearing: they let
dimension_of evaluate both sides of every identity.

Only the four NEW field symbols need binding; every input symbol is already bound
by the domain that owns its node (\alpha_V, K, C_V^{vol}, C_V^{mol}, C_P, T,
\kappa, \kappa_e, \sigma_{el}, S, V_{cell}, N_A), and re-binding one with the same
dimension is a harmless union while a different dimension would (correctly) raise.

  V_m           -> VOLUME_PER_MOLE      (MolarVolume, m^3/mol = N_A V_cell)
  PF            -> POWER_FACTOR         (PowerFactor, W/(m K^2) = sigma_e S^2)
  ZT            -> DIMENSIONLESS        (the figure of merit)
  \kappa_{tot}  -> THERMAL_CONDUCTIVITY (the lattice + electronic sum)

No collision: V_m, PF, ZT, \kappa_{tot} are otherwise-unused global base names
(verified against every existing edge formula). \kappa_{tot} is distinct from the
lattice \kappa^{...} variants and from \Gamma^{tot}.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    POWER_FACTOR,
    THERMAL_CONDUCTIVITY,
    VOLUME_PER_MOLE,
)

register_symbol_dimensions({
    "V_m": VOLUME_PER_MOLE,
    "PF": POWER_FACTOR,
    "ZT": DIMENSIONLESS,
    r"\kappa_{tot}": THERMAL_CONDUCTIVITY,
})
