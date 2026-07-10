"""Operators (edges) for the materials domain (grown from AtomisticSkills).

Five edges. The diffusion pair (contract_diffusivity, fit_arrhenius) is the
original slice; compute_configurational_energy arrives from the config-thermo
scan (AtomisticSkills arXiv 2605.24002); compute_carrier_density and the
EXECUTABLE compute_ionic_conductivity arrive from the physics review (the
second supersede, 2026-07-10).

  contract_diffusivity           : (MeanSquaredDisplacement,)         -> Diffusivity
  fit_arrhenius                  : (Diffusivity, Temperature)         -> ActivationEnergy
  compute_carrier_density        : (Structure,)                       -> CarrierDensity
  compute_ionic_conductivity     : (CarrierDensity, Diffusivity, Temperature)
                                       -> ElectricalConductivity[carrier=ionic]  (EXECUTABLE)
  compute_configurational_energy : (Potential, Structure)            -> ConfigurationalEnergy

compute_carrier_density and compute_configurational_energy are implicit
(is_executable_in_sympy_override=False), each an opaque applied function of its
inputs: the carrier density is a mobile-species count over the cell volume (an
opaque Structure selector), the configurational energy a dot product against a
fitted cluster-expansion Potential. compute_ionic_conductivity is now
EXECUTABLE: the Nernst-Einstein relation sigma = n_c z^2 e^2 D / (k_B T) is a
closed-form sympy Eq the dimensional gate PROVES, because the number density is
the first-class CarrierDensity input n_c and the charge number z a dimensionless
symbol (the elementary charge e a per-edge parameter carrying ENERGY/VOLTAGE).
This is the SECOND SUPERSEDE: the executable v2 replaces the opaque v1
(Diffusivity, Temperature, Structure) -> ... whose formula was the opaque
sigma^{NE}[D, T, Structure]; the formula fingerprint changed, so the edge id
changed, a genuine re-mint routed through the store's supersede machinery. The
Structure / Diffusivity / Temperature inputs are pre-existing store nodes, so
every edge touches the store.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import ENERGY, VOLTAGE
from omai.operator.operator import Operator, Parameter
from omai.materials.operator.nodes import (
    ACTIVATION_ENERGY,
    CARRIER_DENSITY,
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
# Carrier density and Nernst-Einstein executable symbols (second supersede).
_n_c = sp.Symbol("n_c", positive=True)   # CarrierDensity, NUMBER_DENSITY
_z = sp.Symbol("z")                      # charge number (dimensionless integer)
_e_c = sp.Symbol("e_c", positive=True)   # elementary charge (TIME . CURRENT)
_kB = sp.Symbol("k_B", positive=True)
_T_ne = sp.Symbol("T", positive=True)
# Opaque solver functions (applied functions, not free symbols).
_n_c_fn = sp.Function("n^{c}")            # carrier-count-over-volume selector
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

# Carrier density from the Structure: count the mobile species over the cell
# volume. An opaque selector (which species are mobile) over the Structure, so
# implicit, not sympy-executable.
compute_carrier_density = Operator(
    name="compute_carrier_density",
    inputs=(STRUCTURE,),
    outputs=(CARRIER_DENSITY,),
    formula=sp.Eq(_n_c, _n_c_fn(_S)),
    is_executable_in_sympy_override=False,
    description=(
        "Carrier density n_c = n^{c}[Structure]: the mobile-carrier number "
        "density, the count of mobile charge carriers (the diffusing species) "
        "per unit cell volume. n^{c} is an opaque selector over the Structure "
        "(which species count as mobile is the opaque choice; the count over "
        "the cell volume is the density), the same reason FormationEnergy's "
        "reference chemical potentials stay opaque. Surfaces the L^-3 factor "
        "the executable Nernst-Einstein conductivity needs as a first-class "
        "node. Implicit (a Structure-dependent species count), so not "
        "sympy-executable."
    ),
)

# Nernst-Einstein ionic conductivity, EXECUTABLE form (the second supersede,
# physics review 2026-07-10). The number density is now the first-class
# CarrierDensity input n_c and the charge number z a dimensionless symbol, so
# the conversion is a closed-form sympy Eq the dimensional gate PROVES rather
# than an opaque function over the Structure. This changes the formula
# fingerprint, so the edge id changes: a genuine re-mint routed through the
# store's supersede machinery, superseding the opaque v1.
compute_ionic_conductivity = Operator(
    name="compute_ionic_conductivity",
    inputs=(CARRIER_DENSITY, DIFFUSIVITY_STATE, TEMPERATURE),
    outputs=(ELECTRICAL_CONDUCTIVITY_IONIC,),
    parameters=(Parameter("e_c", ENERGY / VOLTAGE),),
    schemes={"method": "nernst_einstein", "haven_ratio": "1"},
    formula=sp.Eq(_sigma, _n_c * _z**2 * _e_c**2 * _D / (_kB * _T_ne)),
    description=(
        "Ionic conductivity sigma = n_c z^2 e^2 D / (k_B T): the executable "
        "Nernst-Einstein relation from the mobile-carrier number density n_c, "
        "the squared charge number z^2 (dimensionless: the oxidation state, "
        "else valence-electron count, the numeric value riding conditions at "
        "evidence time), the squared elementary charge e^2, the tracer "
        "diffusivity D, over the thermal energy k_B T. The physics review's "
        "second supersede: n_c is now the first-class CarrierDensity node and "
        "z a dimensionless symbol, so the relation is a closed-form sympy Eq "
        "the dimensional gate PROVES, not an opaque Structure-derived function. "
        "The gate derives the chain: n_c (0,-3,0,0,0,0,0) . z^2 (dimensionless) "
        ". e^2 (0,0,2,0,0,2,0) . D (0,2,-1,0,0,0,0) / (k_B T) (energy, "
        "1,2,-2,0,0,0,0) = (-1,-3,3,0,0,2,0) = ELECTRICAL_CONDUCTIVITY (S/m). "
        "e is the elementary charge (TIME . CURRENT = ENERGY / VOLTAGE, so "
        "e^2 carries T^2 I^2); it enters as a per-edge parameter bound to that "
        "dimension so it never collides with the phonon eigenvector e. The "
        "method scheme keeps the Nernst-Einstein relation and the haven_ratio=1 "
        "assumption (the tracer, not the collective charge, diffusivity drives "
        "it; the tracer-D caveat stands). pymatgen-analysis-diffusion's "
        "DiffusionAnalyzer.conductivity / get_extrapolated_conductivity. "
        "SUPERSEDES the opaque v1 (formula fingerprint changed, so the edge id "
        "changed). Closed-form and sympy-executable."
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
    compute_carrier_density,
    compute_ionic_conductivity,
    compute_configurational_energy,
)
