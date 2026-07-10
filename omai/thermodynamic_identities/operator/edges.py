r"""Operators (edges) of the thermodynamic-identities domain.

Six edges, and this domain is special: EVERY edge is EXECUTABLE sympy that the
dimensional gate PROVES (no is_executable_in_sympy_override=False anywhere, no
opaque applied functions). These are the map's own formulas COMBINED, the exact
thermodynamic identities the whole-map physics review (2026-07-10) found the
map's prose already stating but its wiring missing. Each formula is an explicit
Eq whose LHS and RHS share no free symbols, so the executability heuristic holds
and every one is closed-form.

  contract_thermal_gruneisen_identity : (ThermalExpansion, BulkModulus,
                                         VolumetricHeatCapacity) -> ThermalGruneisen
  sum_thermal_conductivity            : (ThermalConductivity[bte_solver=
                                         direct_inverse], ElectronicThermalConductivity)
                                         -> ThermalConductivity[contribution=total]
  contract_molar_volume               : (CellVolume,) -> MolarVolume
  contract_heat_capacity_p_identity   : (MolarHeatCapacity, Temperature, MolarVolume,
                                         ThermalExpansion, BulkModulus)
                                         -> HeatCapacityConstantP
  contract_power_factor               : (ElectricalConductivity[carrier=electronic],
                                         SeebeckCoefficient) -> PowerFactor
  contract_zt                         : (PowerFactor, Temperature,
                                         ThermalConductivity[contribution=total]) -> ZT

Two are SECOND producers (Pattern C) of existing nodes:

  * contract_thermal_gruneisen_identity is the SECOND producer of ThermalGruneisen,
    alongside the existing contract_thermal_gruneisen (the heat-capacity-weighted
    mode-average from the QHA side). The two are genuinely different estimators of
    the SAME macroscopic thermal Gruneisen parameter and MUST agree numerically;
    that agreement is the physics content, exactly the redundant-route pattern
    BulkModulus (three producers) and PhononDOS (two) already bless. This one is
    the thermodynamic-identity route gamma = alpha B / C_V^vol, using the INTENSIVE
    VOLUMETRIC heat capacity: the review proved this is the ONLY combination of the
    map's actual nodes that closes dimensionally (CellVolume x MolarHeatCapacity
    leave a residual N axis; the volumetric C_V needs no volume factor at all).

  * contract_heat_capacity_p_identity is the SECOND producer of
    HeatCapacityConstantP, alongside the existing compute_heat_capacity_p (the QHA
    polyfit-enthalpy-derivative). It encodes C_P = C_V + T V_m alpha^2 B, the exact
    thermodynamic identity the HeatCapacityConstantP node's own description states,
    now executable because MolarVolume (this slice) supplies the missing molar V on
    the SAME per-mole-of-cells basis as the molar C_V and C_P.

Connectivity (ONE weakly connected component, pre-traced and gate-verified):
alpha_V and K bridge edge 1 <-> edge 4 (both consume ThermalExpansion and
BulkModulus); V_m bridges edge 3 <-> edge 4 (contract_molar_volume produces it,
the C_P identity consumes it); T bridges edge 4 <-> edge 6 (both consume
Temperature); PF bridges edge 5 <-> edge 6 (contract_power_factor produces it, ZT
consumes it); kappa_tot bridges edge 2 <-> edge 6 (sum_thermal_conductivity
produces it, ZT consumes it). Every edge touches a pre-existing store node
(ThermalExpansion, BulkModulus, VolumetricHeatCapacity, ThermalGruneisen,
ThermalConductivity[bte_solver=direct_inverse], ElectronicThermalConductivity,
CellVolume, MolarHeatCapacity, Temperature, HeatCapacityConstantP,
ElectricalConductivity[carrier=electronic], SeebeckCoefficient).

Symbols. Every symbol is a base name the dimensional gate already binds, so the
gate PROVES each edge: alpha_V (THERMAL_EXPANSIVITY), K (ENERGY_PER_LENGTH_CUBED),
C_V^{vol} (ENERGY_PER_TEMPERATURE_PER_VOLUME), gamma_{th} (DIMENSIONLESS), kappa /
kappa_e (THERMAL_CONDUCTIVITY), N_A (N^-1), V_{cell} (VOLUME), C_V^{mol} and C_P
(ENERGY_PER_TEMPERATURE_PER_MOLE), T (TEMPERATURE), sigma_{el}
(ELECTRICAL_CONDUCTIVITY), S (SEEBECK), plus the four NEW field symbols this
slice binds (V_m -> VOLUME_PER_MOLE, PF -> POWER_FACTOR, ZT -> DIMENSIONLESS,
kappa_{tot} -> THERMAL_CONDUCTIVITY). Collision watch (the review's ZT caveat): S
is the registered Seebeck symbol (NOT entropy; the per-mode entropy is s, the
molar entropy S_{mol}), sigma_{el} is the electronic conductivity (NOT the stress
sigma nor the ionic sigma_{ion}); both carry the right registered dimension, so
the gate proves the intended physics with no symbol clash.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.thermodynamic_identities.operator.nodes import (
    MOLAR_VOLUME,
    POWER_FACTOR_NODE,
    THERMAL_CONDUCTIVITY_TOTAL,
    ZT,
)
from omai.quasiharmonic.operator.nodes import (
    HEAT_CAPACITY_CONSTANT_P,
    THERMAL_EXPANSION,
    THERMAL_GRUNEISEN,
)
from omai.mechanics.operator.nodes import BULK_MODULUS
from omai.thermal_transport.operator.nodes import (
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    VOLUMETRIC_HEAT_CAPACITY,
)
from omai.thermal_transport.operator.edges import _V_cell as _V_cell_param
from omai.electronic_transport.operator.nodes import (
    ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    ELECTRONIC_THERMAL_CONDUCTIVITY,
    SEEBECK_COEFFICIENT,
)


# ---------------------------------------------------------------------------
# Symbols used by the formulas below. Every one is a base name the dimensional
# gate already binds (existing) or that this domain's dimensions_registry binds
# (the four new fields), so the gate proves every edge.
# ---------------------------------------------------------------------------

# Existing registered symbols (their dimensions come from the domains that own
# them; reused verbatim so the identities differentiate/combine the same
# quantities the store already carries).
_alpha_V = sp.Symbol(r"\alpha_V")        # ThermalExpansion, THERMAL_EXPANSIVITY
_K = sp.Symbol("K")                      # BulkModulus, ENERGY_PER_LENGTH_CUBED
_C_V_vol = sp.Symbol(r"C_V^{vol}")       # VolumetricHeatCapacity
_gamma_th = sp.Symbol(r"\gamma_{th}")    # ThermalGruneisen (DIMENSIONLESS)
_kappa_L = sp.Symbol(r"\kappa")          # lattice ThermalConductivity
_kappa_e = sp.Symbol(r"\kappa_e")        # ElectronicThermalConductivity
_V_cell = _V_cell_param                  # CellVolume, VOLUME (V_{cell})
_C_V_mol = sp.Symbol(r"C_V^{mol}")       # MolarHeatCapacity
_C_P = sp.Symbol("C_P")                  # HeatCapacityConstantP
_T = sp.Symbol("T")                      # Temperature
_sigma_e = sp.Symbol(r"\sigma_{el}")     # ElectricalConductivity[carrier=electronic]
_S = sp.Symbol("S")                      # SeebeckCoefficient (SEEBECK; NOT entropy)
_N_A = sp.Symbol("N_A")                  # Avogadro's number (formula constant, N^-1)

# New field symbols this slice introduces (bound in dimensions_registry).
_V_m = sp.Symbol("V_m")                  # MolarVolume, VOLUME_PER_MOLE
_PF = sp.Symbol("PF")                    # PowerFactor, POWER_FACTOR
_ZT = sp.Symbol("ZT")                    # ZT, DIMENSIONLESS
_kappa_tot = sp.Symbol(r"\kappa_{tot}")  # ThermalConductivity[contribution=total]


# ---------------------------------------------------------------------------
# Operators. Every formula is an explicit closed-form Eq (disjoint LHS/RHS free
# symbols), so is_executable_in_sympy_default is True and the gate PROVES it.
# ---------------------------------------------------------------------------

contract_thermal_gruneisen_identity = Operator(
    name="contract_thermal_gruneisen_identity",
    inputs=(THERMAL_EXPANSION, BULK_MODULUS, VOLUMETRIC_HEAT_CAPACITY),
    outputs=(THERMAL_GRUNEISEN,),
    formula=sp.Eq(_gamma_th, _alpha_V * _K / _C_V_vol),
    description=(
        "Thermodynamic Gruneisen identity gamma_th = alpha_V B / C_V^vol: the "
        "macroscopic (thermodynamic) Gruneisen parameter from the volumetric "
        "thermal expansion, the bulk modulus, and the INTENSIVE volumetric heat "
        "capacity. The whole-map physics review proved this is the ONLY "
        "combination of the map's actual nodes that closes dimensionally: "
        "alpha_V (0,0,0,-1) . B (1,-1,-2,0) / C_V^vol (1,-1,-2,-1) = "
        "(0,0,0,0,0,0,0), exactly dimensionless. Using CellVolume x "
        "MolarHeatCapacity instead leaves a residual N (mole) axis, and a "
        "per-unit-volume C_V with a V factor double-counts the volume, so the "
        "volumetric C_V (which needs NO volume factor) is the clean route. "
        "SECOND PRODUCER (Pattern C) of ThermalGruneisen alongside "
        "contract_thermal_gruneisen (the QHA heat-capacity-weighted mode-average): "
        "two genuinely different estimators of the SAME thermal Gruneisen that "
        "MUST agree numerically, mirroring BulkModulus's three producers. "
        "Closed-form and sympy-executable; the dimensional gate proves the "
        "dimensionless output."
    ),
)

sum_thermal_conductivity = Operator(
    name="sum_thermal_conductivity",
    inputs=(THERMAL_CONDUCTIVITY_DIRECT, ELECTRONIC_THERMAL_CONDUCTIVITY),
    outputs=(THERMAL_CONDUCTIVITY_TOTAL,),
    formula=sp.Eq(_kappa_tot, _kappa_L + _kappa_e),
    description=(
        "Total thermal conductivity kappa_total = kappa_lattice + kappa_electronic: "
        "the exact additive sum of the lattice and electronic heat channels "
        "(parallel heat conductors add), discharging the claim the "
        "ElectronicThermalConductivity node already makes in prose. Both inputs "
        "carry THERMAL_CONDUCTIVITY (1,1,-3,-1), so the sum is dimensionally "
        "trivial and the gate proves it (an Add of two equal known dimensions). "
        "Mirrors the existing sum_linewidths Matthiessen edge (also a same-dimension "
        "additive contraction). The lattice input here NAMES the full-solution "
        "ThermalConductivity[bte_solver=direct_inverse] variant; the other lattice "
        "producers (the Wigner / Green-Kubo / QHGK / RTA transport_model variants) "
        "sum with kappa_electronic ANALOGOUSLY into the same contribution=total node "
        "(one representative producer is wired; the physics is identical for each "
        "lattice route, which one fired riding the provenance). Closed-form and "
        "sympy-executable."
    ),
)

# contract_molar_volume is NULLARY at the store level: CellVolume is a PROMOTED
# PARAMETER (thermal-transport param_promotions), not an ObservableSpace, so the
# map wires it to its consumers through its symbol V_{cell} appearing in the
# consumer's formula (the provide_CellVolume presentation link), exactly as every
# other CellVolume consumer on the map. So this edge takes inputs=() and its
# formula references the promoted V_{cell} parameter; graph.json draws the
# provide_CellVolume -> MolarVolume link automatically because _V_cell is in the
# formula. MolarVolume connects into the contribution component through
# contract_heat_capacity_p_identity (which consumes it alongside pre-existing
# nodes), so the store contribution stays weakly connected and touches
# pre-existing nodes.
contract_molar_volume = Operator(
    name="contract_molar_volume",
    inputs=(),
    outputs=(MOLAR_VOLUME,),
    formula=sp.Eq(_V_m, _N_A * _V_cell),
    description=(
        "Molar volume V_m = N_A V_cell: the CellVolume promoted parameter scaled to "
        "a per-mole-of-cells volume by Avogadro's number N_A (a registered formula "
        "constant carrying dimension N^-1, exactly as k_B carries "
        "ENERGY_PER_TEMPERATURE in the dimcheck registry, so N_A is honest in the "
        "gate). The gate proves it: N_A (0,0,0,0,-1,0,0) . V_cell (0,3,0,0,0,0,0) = "
        "(0,3,0,0,-1,0,0) = VOLUME_PER_MOLE, matching MolarVolume. Encoded as a "
        "nullary producer that reads the promoted V_{cell} parameter (the map wires "
        "CellVolume to every consumer through its symbol in the formula, the "
        "provide_CellVolume link, since CellVolume is a promoted parameter and not "
        "an ObservableSpace node). ON THE PHONON MOLAR BASIS (per mole of primitive "
        "cells, the same cells as the molar C_V / C_P); to cross-code to per mole of "
        "ATOMS, divide by atoms-per-cell. The one node the review found the map "
        "needed to make the molar Gruneisen and C_P - C_V identities executable. "
        "Closed-form and sympy-executable."
    ),
)

contract_heat_capacity_p_identity = Operator(
    name="contract_heat_capacity_p_identity",
    inputs=(MOLAR_HEAT_CAPACITY, TEMPERATURE_STATE, MOLAR_VOLUME,
            THERMAL_EXPANSION, BULK_MODULUS),
    outputs=(HEAT_CAPACITY_CONSTANT_P,),
    formula=sp.Eq(_C_P, _C_V_mol + _T * _V_m * _alpha_V**2 * _K),
    description=(
        "Constant-pressure heat capacity identity C_P = C_V + T V_m alpha^2 B: the "
        "exact thermodynamic difference C_P - C_V = T V_m alpha^2 B_T that the "
        "HeatCapacityConstantP node's own description already states, now "
        "EXECUTABLE because MolarVolume (this slice) supplies the molar V on the "
        "SAME per-mole-of-cells basis as the molar C_V and C_P. The gate proves it: "
        "T V_m alpha^2 B = (0,0,0,1) . (0,3,0,0,-1) . (0,0,0,-2) . (1,-1,-2,0) = "
        "(1,2,-2,-1,-1,0,0) = ENERGY_PER_TEMPERATURE_PER_MOLE, matching both the "
        "molar C_V it adds to and the C_P it produces (an Add of two equal known "
        "dimensions). SECOND PRODUCER (Pattern C) of HeatCapacityConstantP "
        "alongside compute_heat_capacity_p (the QHA polyfit-enthalpy-derivative): "
        "the identity route and the direct QHA route must agree. Closed-form and "
        "sympy-executable."
    ),
)

contract_power_factor = Operator(
    name="contract_power_factor",
    inputs=(ELECTRICAL_CONDUCTIVITY_ELECTRONIC, SEEBECK_COEFFICIENT),
    outputs=(POWER_FACTOR_NODE,),
    formula=sp.Eq(_PF, _sigma_e * _S**2),
    description=(
        "Thermoelectric power factor PF = sigma_e S^2: the electronic electrical "
        "conductivity times the Seebeck coefficient squared, a closed-form "
        "contraction of two existing electronic-transport nodes. The gate proves "
        "the new dimension: sigma_e (-1,-3,3,0,0,2,0) + 2 S (1,2,-3,-1,0,-1,0) = "
        "(1,1,-3,-2,0,0,0) = POWER_FACTOR = W/(m K^2). S is the registered Seebeck "
        "symbol (V/K), NOT entropy; sigma_e is the electronic conductivity, NOT the "
        "stress or ionic sigma. The sole non-temperature input to ZT. Closed-form "
        "and sympy-executable."
    ),
)

contract_zt = Operator(
    name="contract_zt",
    inputs=(POWER_FACTOR_NODE, TEMPERATURE_STATE, THERMAL_CONDUCTIVITY_TOTAL),
    outputs=(ZT,),
    formula=sp.Eq(_ZT, _PF * _T / _kappa_tot),
    description=(
        "Dimensionless thermoelectric figure of merit ZT = PF T / kappa_total = "
        "sigma_e S^2 T / (kappa_lattice + kappa_electronic): the single number a "
        "thermoelectrics colleague reads. The gate proves it dimensionless: "
        "PF (1,1,-3,-2) . T (0,0,0,1) / kappa_total (1,1,-3,-1) = (0,0,0,0,0,0,0). "
        "Its kappa_total input is the ThermalConductivity[contribution=total] node "
        "(itself lattice + electronic via sum_thermal_conductivity), so ZT is the "
        "ONE relation that stitches the lattice and electronic thermal-transport "
        "halves of the map into a single thermoelectrics story. Closed-form and "
        "sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    contract_thermal_gruneisen_identity,
    sum_thermal_conductivity,
    contract_molar_volume,
    contract_heat_capacity_p_identity,
    contract_power_factor,
    contract_zt,
)
