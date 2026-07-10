"""The thermochemistry Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.thermochemistry import representation as thermo_rep
from omai.thermochemistry.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "AssessedDatabase": r"\mathcal{D}",
    "MolarGibbsEnergy": r"G_{\mathrm{m}}",
    "MolarEnthalpy": r"H_{\mathrm{m}}",
    "ChemicalPotential": r"\mu",
    "PhaseFraction": r"f_{\mathrm{p}}",
    "TransitionTemperature": r"T_{\mathrm{trans}}",
    "CalphadMolarEntropy": r"S_{\mathrm{m}}",
}

THERMOCHEMISTRY = Domain(
    name="thermochemistry",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Thermochemistry",
            "Assessed phase thermodynamics: Gibbs energies, chemical "
            "potentials, phase fractions, and transition temperatures from "
            "CALPHAD databases.",
        ),
    ),
    representation_package=thermo_rep,
)
