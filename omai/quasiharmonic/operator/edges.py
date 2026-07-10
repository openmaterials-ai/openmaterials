r"""Operators (edges) of the quasi-harmonic domain.

Five edges, all implicit (is_executable_in_sympy_override=False): the QHA Gibbs
producer, the third Pattern-C producer of the existing BulkModulus node, the two
G-derived thermodynamic responses, and the mode-Gruneisen contraction. Each is an
opaque applied function of its inputs with the QHA method / EOS selection recorded
as schemes, exactly like the electronic-transport and thermochemistry edges.

  compute_qha_gibbs          : (TotalEnergy, Structure, Frequency) -> QHAGibbsEnergy
  compute_bulk_modulus_qha   : (TotalEnergy, Structure, Frequency) -> BulkModulus
  compute_thermal_expansion  : (QHAGibbsEnergy,)                   -> ThermalExpansion
  compute_heat_capacity_p    : (QHAGibbsEnergy,)                   -> HeatCapacityConstantP
  contract_thermal_gruneisen : (Gruneisen, Frequency)             -> ThermalGruneisen

compute_bulk_modulus_qha is the THIRD Pattern-C producer of the existing
BulkModulus node, alongside contract_bulk_modulus (the elastic-tensor VRH route)
and compute_bulk_modulus_eos (the T=0 Birch-Murnaghan E(V) curvature). The QHA
route fits an EOS at each temperature's equilibrium volume (matcalc bulk_modulus_P,
GPa); B(T) values are then INSTANCES of BulkModulus whose conditions carry the
temperature (the map doctrine: temperature is an evaluation condition, not a new
node). The node is NOT re-minted; only the edge is new.

Connectivity. The five nodes/edges plus the mechanics contract_density edge form
ONE weakly connected component. compute_qha_gibbs and compute_bulk_modulus_qha
share TotalEnergy / Structure / Frequency (all pre-existing store nodes);
compute_thermal_expansion and compute_heat_capacity_p chain off QHAGibbsEnergy
(produced here); contract_thermal_gruneisen consumes the pre-existing mode
Gruneisen AND Frequency (the heat-capacity weighting is over the mode frequencies),
so Frequency bridges it into the same component. MassDensity (mechanics domain)
chains off the pre-existing Structure. All inputs but QHAGibbsEnergy are
pre-existing, so the additions touch the store and are weakly connected.

Symbols. The output field symbols (G_{qha}, \alpha_V, C_P, \gamma_{th}) are new
and collision-checked; the input arguments E_{tot} (TotalEnergy), \mathcal{S}
(Structure), \omega (Frequency), \gamma_G (mode Gruneisen), and K (BulkModulus,
the EOS route output) are existing registered symbols reused as opaque-function
arguments. The opaque solver functions (G^{qha}, K^{qha}, \alpha^{qha},
C_P^{qha}, \gamma^{qha}) are applied functions, invisible to the free-symbol
check, so they need no vocabulary entries.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.quasiharmonic.operator.nodes import (
    HEAT_CAPACITY_CONSTANT_P,
    QHA_GIBBS_ENERGY,
    THERMAL_EXPANSION,
    THERMAL_GRUNEISEN,
)
from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
from omai.materials.operator.shared_primitives import STRUCTURE
from omai.mechanics.operator.nodes import BULK_MODULUS
from omai.thermal_transport.operator.nodes import FREQUENCY_STATE, GRUNEISEN


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

# Output field symbols (new, registered in this domain's vocabulary).
_G_qha = sp.Symbol(r"G_{qha}")
_alpha_V = sp.Symbol(r"\alpha_V")
_C_P = sp.Symbol("C_P")
_gamma_th = sp.Symbol(r"\gamma_{th}")
# Input arguments (existing registered symbols).
_E_tot = sp.Symbol("E_{tot}")       # TotalEnergy
_S_struct = sp.Symbol(r"\mathcal{S}")  # Structure
_omega = sp.Symbol(r"\omega")       # Frequency
_gamma_G = sp.Symbol(r"\gamma_G")   # mode Gruneisen
_K = sp.Symbol("K")                 # BulkModulus (EOS route output)
# Opaque solver functions (applied functions, not free symbols).
_G_qha_fn = sp.Function("G^{qha}")
_K_qha_fn = sp.Function("K^{qha}")
_alpha_qha_fn = sp.Function(r"\alpha^{qha}")
_C_P_qha_fn = sp.Function("C_P^{qha}")
_gamma_qha_fn = sp.Function(r"\gamma^{qha}")


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

compute_qha_gibbs = Operator(
    name="compute_qha_gibbs",
    inputs=(TOTAL_ENERGY, STRUCTURE, FREQUENCY_STATE),
    outputs=(QHA_GIBBS_ENERGY,),
    schemes={"method": "qha_fvt_minimization"},
    formula=sp.Eq(_G_qha, _G_qha_fn(_E_tot, _S_struct, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Quasi-harmonic Gibbs energy G = G^{qha}[E_tot, Structure, omega]: the "
        "constant-pressure Gibbs energy from minimizing the phonon Helmholtz "
        "surface F(V,T) + pV over volume at each temperature, phonopy PhonopyQHA's "
        "gibbs_temperature. G^{qha} is opaque over the per-volume total energies "
        "E_tot (the E(V) curve of the volume scan), the Structure, and the phonon "
        "frequencies omega (the F(V,T) phonon-gas free energy at each scanned "
        "volume). The TotalEnergy and Frequency inputs stand for the FAMILY of "
        "per-volume evaluations of the F(V,T) scan, the family-of-values "
        "convention compute_bulk_modulus_eos and compute_fc2_finite_displacement "
        "use. The scheme records the qha_fvt_minimization method (matcalc's "
        "F(V,T) volume grid and EOS choice are the discretization). Implicit (a "
        "volume-scan phonon-gas + EOS minimization), so not sympy-executable."
    ),
)

compute_bulk_modulus_qha = Operator(
    name="compute_bulk_modulus_qha",
    inputs=(TOTAL_ENERGY, STRUCTURE, FREQUENCY_STATE),
    outputs=(BULK_MODULUS,),
    schemes={"method": "qha_eos_scan", "eos": "vinet_or_birch_murnaghan"},
    formula=sp.Eq(_K, _K_qha_fn(_E_tot, _S_struct, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Temperature-dependent bulk modulus K = K^{qha}[E_tot, Structure, omega]: "
        "the isothermal bulk modulus fit from an equation of state at each "
        "temperature's QHA equilibrium volume, phonopy PhonopyQHA's "
        "bulk_modulus_temperature (matcalc bulk_modulus_P, GPa). Pattern C: the "
        "THIRD alternative producer of the existing BulkModulus node, alongside "
        "contract_bulk_modulus (the elastic-tensor VRH route) and "
        "compute_bulk_modulus_eos (the T=0 Birch-Murnaghan E(V) curvature). The "
        "node is NOT re-minted; B(T) values are INSTANCES of BulkModulus whose "
        "conditions carry the temperature (temperature is an evaluation "
        "condition, not a new node). K^{qha} is opaque over the per-volume E(V) "
        "energies, the Structure, and the phonon frequencies (the F(V,T) surface). "
        "The scheme records the qha_eos_scan method and the vinet_or_birch_"
        "murnaghan EOS. Implicit (a fit over an external volume scan), so not "
        "sympy-executable; downstream consumers are unaware which of the three "
        "routes fired, exactly as for the two other BulkModulus producers."
    ),
)

compute_thermal_expansion = Operator(
    name="compute_thermal_expansion",
    inputs=(QHA_GIBBS_ENERGY,),
    outputs=(THERMAL_EXPANSION,),
    schemes={"method": "dv_dt_at_gibbs_minimum"},
    formula=sp.Eq(_alpha_V, _alpha_qha_fn(_G_qha)),
    is_executable_in_sympy_override=False,
    description=(
        "Volumetric thermal expansion alpha = alpha^{qha}[G]: the coefficient "
        "alpha(T) = (1/V)(dV/dT)_P read from the temperature dependence of the "
        "QHA equilibrium volume, the volume that minimizes the quasi-harmonic "
        "Gibbs energy at each temperature, phonopy PhonopyQHA's thermal_expansion. "
        "alpha^{qha} is opaque over the QHA Gibbs energy (whose per-temperature "
        "volume minimum V(T) it differentiates); 1/K. Implicit (a numerical "
        "dV/dT along the Gibbs-minimum locus), so not sympy-executable."
    ),
)

compute_heat_capacity_p = Operator(
    name="compute_heat_capacity_p",
    inputs=(QHA_GIBBS_ENERGY,),
    outputs=(HEAT_CAPACITY_CONSTANT_P,),
    schemes={"method": "polyfit_enthalpy_derivative"},
    formula=sp.Eq(_C_P, _C_P_qha_fn(_G_qha)),
    is_executable_in_sympy_override=False,
    description=(
        "Constant-pressure heat capacity C_P = C_P^{qha}[G]: the molar C_P(T) "
        "along the QHA equilibrium path, d(H)/dT at constant pressure, phonopy "
        "PhonopyQHA's heat_capacity_P_polyfit (matcalc default; the numerical "
        "estimator is the sibling). C_P^{qha} is opaque over the QHA Gibbs energy "
        "(the enthalpy H = G + T S it differentiates along the equilibrium path); "
        "J/(K*mol). It is the constant-pressure partner of the harmonic "
        "constant-volume MolarHeatCapacity (C_V), differing by C_P - C_V = "
        "alpha^2 B V T. Implicit (a polyfit-derivative estimator), so not "
        "sympy-executable."
    ),
)

contract_thermal_gruneisen = Operator(
    name="contract_thermal_gruneisen",
    inputs=(GRUNEISEN, FREQUENCY_STATE),
    outputs=(THERMAL_GRUNEISEN,),
    schemes={"method": "heat_capacity_weighted_average"},
    formula=sp.Eq(_gamma_th, _gamma_qha_fn(_gamma_G, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Macroscopic thermal Gruneisen gamma(T) = gamma^{qha}[gamma_G, omega]: the "
        "heat-capacity-weighted average of the mode Gruneisen parameters gamma_qnu, "
        "a single scalar per temperature, phonopy PhonopyQHA's "
        "gruneisen_temperature. A CONTRACTION of the existing MODE Gruneisen "
        "(field gamma_G, (q,nu)-indexed, FC3-produced) over the Brillouin zone, "
        "weighted by the per-mode heat capacities (hence the mode frequencies "
        "omega, which fix the Bose occupation and the mode C_V weights). "
        "gamma^{qha} is opaque over the mode gammas and the frequencies; "
        "dimensionless. The distinct T-only index signature and producer keep it a "
        "DISTINCT node from the mode Gruneisen (not an alias). Implicit (a "
        "weighted BZ average), so not sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    compute_qha_gibbs,
    compute_bulk_modulus_qha,
    compute_thermal_expansion,
    compute_heat_capacity_p,
    contract_thermal_gruneisen,
)
