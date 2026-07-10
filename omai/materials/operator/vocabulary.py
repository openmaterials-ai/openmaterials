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
    # Charge number z of the mobile carrier in the executable Nernst-Einstein
    # relation sigma = n_c z^2 e^2 D / (k_B T) (second supersede): a
    # dimensionless integer (the oxidation state, else valence-electron count),
    # the numeric value riding conditions at evidence time. The elementary
    # charge e enters as a per-edge parameter (bound to ENERGY/VOLTAGE) rather
    # than a bare constant, so it never collides with the phonon eigenvector e.
    "z",
})

register_space_symbols({
    "Diffusivity": {"D"},
    "ActivationEnergy": {"E_a"},
    "MeanSquaredDisplacement": {r"\mathrm{slope}_{MSD}"},
    # Config-thermo scan. sigma is the ionic conductivity; E_{cfg} the
    # cluster-expansion configurational energy. The cluster-expansion and
    # carrier-density solver functions are applied functions (invisible to
    # the free-symbol check), and their arguments (Structure, Potential) are
    # already-registered symbols, so no further entries are needed.
    "ElectricalConductivity[carrier=ionic]": {r"\sigma_{ion}"},
    "ConfigurationalEnergy": {"E_{cfg}"},
    # Second supersede: the carrier number density, the Nernst-Einstein input.
    "CarrierDensity": {"n_c"},
})
