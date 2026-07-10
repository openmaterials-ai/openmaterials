r"""Formula symbol vocabulary of the thermochemistry domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.thermochemistry.operator` is imported. Union semantics per space.

Each thermochemistry space carries its own field symbol. The input side is
already covered: Temperature's T is a generic constant, and AssessedDatabase
carries its own placeholder \mathcal{D} (registered here, the CALPHAD analog
of Potential's provided-source placeholder). The opaque solver functions
(G^{min}, H^{eq}, mu^{eq}, f^{eq}, T^{trans}) are applied functions, invisible
to the free-symbol check, so they need no entries.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The assessed database placeholder: the input model symbol the solver
    # functions apply to (like the phonon Potential's provided-source symbol).
    "AssessedDatabase": {r"\mathcal{D}"},
    "MolarGibbsEnergy": {"G_m"},
    "MolarEnthalpy": {"H_m"},
    "ChemicalPotential": {r"\mu"},
    "PhaseFraction": {"NP"},
    "TransitionTemperature": {r"T_{\mathrm{trans}}"},
    "CalphadMolarEntropy": {"S_m"},
})
