"""Formula symbol vocabulary of the materials domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.materials.operator` is imported. The MeanSquaredDisplacement entry
extends (unions with) the thermal-transport vocabulary for the shared
space: the fitted slope of MSD(t) is a trajectory-derived auxiliary
quantity the Einstein-relation edge references.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_formula_constants, register_space_symbols

register_formula_constants({
    # Spatial dimensionality in the Einstein relation D = slope / (2 d).
    "d",
    # Arrhenius prefactor in D(T) = D_0 exp(-E_a / k_B T); a fit
    # parameter, not a mapped quantity.
    "D_0",
})

register_space_symbols({
    "Diffusivity": {"D"},
    "ActivationEnergy": {"E_a"},
    "MeanSquaredDisplacement": {r"\mathrm{slope}_{MSD}"},
})
