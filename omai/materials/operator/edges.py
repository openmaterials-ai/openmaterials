"""Operators (edges) for the materials domain (grown from AtomisticSkills).

Four edges. The diffusion pair (contract_diffusivity, fit_arrhenius) is the
original slice; compute_ionic_conductivity and compute_configurational_energy
arrive from the config-thermo scan (AtomisticSkills arXiv 2605.24002).

  contract_diffusivity           : (MeanSquaredDisplacement,)         -> Diffusivity
  fit_arrhenius                  : (Diffusivity, Temperature)         -> ActivationEnergy
  compute_ionic_conductivity     : (Diffusivity, Temperature, Structure)
                                       -> ElectricalConductivity[carrier=ionic]
  compute_configurational_energy : (Potential, Structure)            -> ConfigurationalEnergy

The two new edges are implicit (is_executable_in_sympy_override=False), each an
opaque applied function of its inputs, exactly like the thermochemistry Gibbs
edges: the Nernst-Einstein conversion factor needs the number density and the
ionic charge z read off the Structure (n/V and z^2 are Structure-derived, not
free symbols), and the configurational energy is a dot product against a fitted
cluster-expansion Potential. The Structure and Potential inputs are the shared
Sources leaves already in the store, so both edges touch pre-existing nodes.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.materials.operator.nodes import (
    ACTIVATION_ENERGY,
    CONFIGURATIONAL_ENERGY,
    DIFFUSIVITY_STATE,
    ELECTRICAL_CONDUCTIVITY_IONIC,
)
from omai.materials.operator.shared_primitives import (
    MEAN_SQUARED_DISPLACEMENT,
    POTENTIAL,
    STRUCTURE,
    TEMPERATURE,
)

_D = sp.Symbol("D", positive=True)
_D0 = sp.Symbol("D_0", positive=True)
_Ea = sp.Symbol("E_a", positive=True)
_kB = sp.Symbol("k_B", positive=True)
_T = sp.Symbol("T", positive=True)
_d = sp.Symbol("d", positive=True, integer=True)
_slope = sp.Symbol(r"\mathrm{slope}_{MSD}", positive=True)
# Config-thermo symbols. Structure (\mathcal{S}) and Potential (V) are the
# existing registered source symbols, reused here as the opaque-function
# arguments exactly as the dft_ground_state and stability edges do.
_sigma = sp.Symbol(r"\sigma_{ion}", positive=True)
_E_cfg = sp.Symbol("E_{cfg}")
_S = sp.Symbol(r"\mathcal{S}")   # Structure (registered source symbol)
_V_pot = sp.Symbol("V")          # Potential (registered source symbol)
# Opaque solver functions (applied functions, not free symbols).
_sigma_NE = sp.Function(r"\sigma^{NE}")   # Nernst-Einstein conversion
_E_ce = sp.Function("E^{ce}")             # cluster-expansion prediction

# Einstein relation: D = slope of MSD(t) / (2 d). Closed-form in the slope.
contract_diffusivity = Operator(
    name="contract_diffusivity",
    inputs=(MEAN_SQUARED_DISPLACEMENT,),
    outputs=(DIFFUSIVITY_STATE,),
    formula=sp.Eq(_D, _slope / (2 * _d)),
    description="Einstein relation: D = slope(MSD(t)) / (2 d) in the linear regime.",
)

# Arrhenius fit over D(T) at several temperatures. A regression, not a
# closed-form map from a single input, so mark it non-executable in sympy.
fit_arrhenius = Operator(
    name="fit_arrhenius",
    inputs=(DIFFUSIVITY_STATE, TEMPERATURE),
    outputs=(ACTIVATION_ENERGY,),
    formula=sp.Eq(sp.Function("D")(_T), _D0 * sp.exp(-_Ea / (_kB * _T))),
    is_executable_in_sympy_override=False,
    description="Weighted Arrhenius fit of D(T) = D0 exp(-E_a/k_B T) over temperatures.",
)

# Nernst-Einstein ionic conductivity from the tracer diffusivity. The
# conversion factor needs the number density n/V and the ionic charge z^2 read
# off the Structure, so it is an opaque function over (D, T, Structure) rather
# than a closed form in free symbols: implicit, not sympy-executable.
compute_ionic_conductivity = Operator(
    name="compute_ionic_conductivity",
    inputs=(DIFFUSIVITY_STATE, TEMPERATURE, STRUCTURE),
    outputs=(ELECTRICAL_CONDUCTIVITY_IONIC,),
    schemes={"method": "nernst_einstein", "haven_ratio": "1"},
    formula=sp.Eq(_sigma, _sigma_NE(_D, _T, _S)),
    is_executable_in_sympy_override=False,
    description=(
        "Ionic conductivity sigma = sigma^{NE}[D, T, Structure]: the "
        "Nernst-Einstein conversion sigma = (n/V) z^2 e^2 D / (k_B T) applied "
        "to the tracer diffusivity D at temperature T, with the number density "
        "n/V and the ionic charge z^2 (oxidation state, else valence-electron "
        "count) read off the Structure. sigma^{NE} is opaque over the Structure "
        "context; the method scheme records the Nernst-Einstein relation and "
        "the haven_ratio=1 assumption (the tracer, not the collective charge, "
        "diffusivity). pymatgen-analysis-diffusion's "
        "DiffusionAnalyzer.conductivity / get_extrapolated_conductivity. "
        "Implicit (a Structure-dependent conversion), so not sympy-executable."
    ),
)

# Configurational energy predicted by a cluster expansion: a dot product of the
# fitted coefficients against the correlation vector of the configuration, i.e.
# an opaque function over (Potential, Structure). The cluster-expansion
# checkpoint is a Potential-representation analog (an MLIP-checkpoint sibling).
compute_configurational_energy = Operator(
    name="compute_configurational_energy",
    inputs=(POTENTIAL, STRUCTURE),
    outputs=(CONFIGURATIONAL_ENERGY,),
    schemes={"method": "cluster_expansion"},
    formula=sp.Eq(_E_cfg, _E_ce(_V_pot, _S)),
    is_executable_in_sympy_override=False,
    description=(
        "Configurational energy E_cfg = E^{ce}[Potential, Structure]: the "
        "cluster-expansion prediction E = dot(coefs, correlations) evaluated on "
        "a configuration (the Structure) with a fitted cluster expansion (the "
        "Potential-representation analog, an MLIP-checkpoint sibling carrying "
        "the ECI coefficients). E^{ce} is opaque over the fitted checkpoint and "
        "the configuration; the method scheme records the cluster_expansion "
        "method. Fixed lattice, fixed cell, training-referenced (smol "
        "ClusterExpansion.predict / ExpansionProcessor.compute_property). "
        "Implicit (a checkpoint evaluation), so not sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    contract_diffusivity,
    fit_arrhenius,
    compute_ionic_conductivity,
    compute_configurational_energy,
)
