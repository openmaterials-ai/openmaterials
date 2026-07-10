r"""Symbol-dimension registry of the materials domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.materials.operator` is imported, next to the vocabulary module.

Note the intentional cross-domain ``D``: here ``D`` is the self-diffusion
coefficient (diffusivity), whereas the thermal-transport domain's ``D`` is
the dynamical matrix, which thermal deliberately does NOT register.
Registration is global by base name, so this diffusivity registration
stands; the dimensional report supplies a per-edge ``local`` override that
blanks ``D``/``D^{bare}`` on the thermal DM-touching edges, so the two
never collide into a false violation.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIFFUSIVITY,
    DIMENSIONLESS,
    ELECTRICAL_CONDUCTIVITY,
    ENERGY,
    LENGTH_SQUARED,
    NUMBER_DENSITY,
    TIME,
)

register_symbol_dimensions({
    "D": DIFFUSIVITY,
    "D_0": DIFFUSIVITY,
    "E_a": ENERGY,
    "d": DIMENSIONLESS,
    # Fitted slope of MSD(t); length^2 / time is exactly diffusivity.
    r"\mathrm{slope}_{MSD}": LENGTH_SQUARED / TIME,
    # Config-thermo scan. sigma is the ionic conductivity (S/m);
    # E_{cfg} the cluster-expansion configurational energy (eV). The
    # cluster-expansion edge carries an opaque solver function, so the gate
    # classifies it SKIPPED; this binding documents the intended dimension.
    r"\sigma_{ion}": ELECTRICAL_CONDUCTIVITY,
    "E_{cfg}": ENERGY,
    # Second supersede (executable Nernst-Einstein). n_c is the carrier number
    # density (L^-3); z the dimensionless charge number. With these bound (and
    # the elementary charge e enters as a per-edge parameter carrying
    # ENERGY/VOLTAGE = TIME . CURRENT), the gate PROVES the executable
    # conductivity: n_c (0,-3,0,0,0,0,0) . z^2 (dimensionless) . e^2
    # (0,0,2,0,0,2,0) . D (0,2,-1,0,0,0,0) / (k_B T) (energy) =
    # (-1,-3,3,0,0,2,0) = ELECTRICAL_CONDUCTIVITY (S/m).
    "n_c": NUMBER_DENSITY,
    "z": DIMENSIONLESS,
})
