r"""Operator nodes of the thermodynamic-identities domain.

The whole-map physics review (scans/map-physics-review-2026-07-10.md) read the
entire published map as a theoretical physicist and found the map's own prose was
ahead of its wiring: several exact thermodynamic identities the node descriptions
already STATE were not encoded as executable edges, and two textbook identities
(the molar Gruneisen relation and C_P - C_V) were one node short of an honest
encoding. This slice closes that gap. It is special: EVERY edge is EXECUTABLE
sympy the dimensional gate PROVES (no opaque solver functions), because these are
identities that COMBINE the map's existing formulas, not new measurements.

Four new nodes, each minted to make an identity executable:

  Node                                   quantity tag                     dimension          indices
  -------------------------------------  -------------------------------  -----------------  -------
  ThermalConductivity[contribution=total]  thermal_conductivity           THERMAL_CONDUCTIVITY  ()
  MolarVolume                            molar_volume                     VOLUME_PER_MOLE    ()
  PowerFactor                            power_factor                     POWER_FACTOR       ()
  ZT                                     zt                               DIMENSIONLESS      ()

  * ThermalConductivity[contribution=total] JOINS the thermal_conductivity family
    (the SAME thermal_conductivity tag and THERMAL_CONDUCTIVITY dimension as the
    nine lattice kappa nodes) as a distinct node ONLY by the contribution=total
    LABEL_KEY. It is the additive parallel-channel sum kappa_total = kappa_lattice
    + kappa_electronic that the ElectronicThermalConductivity node's own
    description already states in prose but no edge summed. The contribution label
    is a SEPARATE key from transport_model (a different axis: which heat channels
    are summed, not which lattice solver produced kappa), chosen per the
    label-collision discipline so it never aliases a lattice-solver variant.

  * MolarVolume V_m = N_A V_cell, the volume PER MOLE OF PRIMITIVE CELLS: a
    promoted-parameter-style contraction of CellVolume by Avogadro's number.
    NEW dimension VOLUME_PER_MOLE (0,3,0,0,-1,0,0) = m^3/mol. It is on the PHONON
    MOLAR BASIS (per mole of the SAME primitive/unit cells as the phonopy Molar*
    thermodynamics), NOT the CALPHAD per-mole-of-atoms basis; this guardrail is
    load-bearing because MolarVolume is the input that closes C_P - C_V against the
    molar MolarHeatCapacity and HeatCapacityConstantP (both per mole of cells), so
    a per-atom V_m would silently break that identity's basis. To cross-code to a
    per-mole-of-ATOMS molar volume, divide by atoms-per-cell. The review's single
    cleanest addition: it makes BOTH the molar Gruneisen form AND C_P - C_V
    executable and mutually cross-checking.

  * PowerFactor PF = sigma_e S^2, the thermoelectric power factor: the electronic
    electrical conductivity times the Seebeck coefficient squared. NEW dimension
    POWER_FACTOR (1,1,-3,-2,0,0,0) = W/(m K^2). A clean executable contraction of
    two existing electronic-transport nodes; the first fruit of the thermoelectric
    slice and the sole non-temperature input to ZT.

  * ZT the dimensionless thermoelectric figure of merit ZT = PF T / kappa_total =
    sigma_e S^2 T / (kappa_lattice + kappa_electronic). DIMENSIONLESS scalar. It is
    the single relation that stitches the lattice and electronic thermal-transport
    halves of the map into one thermoelectrics story (the review's headline
    connective tissue): its kappa_total input is the contribution=total node above,
    which is itself lattice + electronic, so ZT transitively depends on both
    transport families.

Node identity is NAME-based (omai/operator/space.py hashes on the node name, the
derived quantity tag entering the identity hash), so each stays distinct by its
own tag (or, for the total kappa, the same thermal_conductivity tag plus the
contribution=total label). The dimensions do partial separating work here:
MolarVolume and PowerFactor carry genuinely NEW exponent vectors, while
ThermalConductivity[contribution=total] reuses THERMAL_CONDUCTIVITY (kept apart by
the label) and ZT reuses DIMENSIONLESS (kept apart by its tag, as ThermalGruneisen
and PoissonRatio already are).
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    POWER_FACTOR,
    THERMAL_CONDUCTIVITY,
    VOLUME_PER_MOLE,
)
from omai.operator.space import Field, ObservableSpace, Space

THERMAL_CONDUCTIVITY_TOTAL = ObservableSpace(
    name="ThermalConductivity[contribution=total]",
    fields=(Field("kappa_tot", THERMAL_CONDUCTIVITY, indices=()),),
    labels={"contribution": "total"},
    tier="Thermoelectric",
    description=(
        "Total thermal conductivity kappa_total = kappa_lattice + kappa_electronic: "
        "the additive sum of the lattice and electronic heat-transport channels, "
        "the two carriers of heat conducting in PARALLEL, so their conductivities "
        "add exactly (the Matthiessen-like additivity the map already uses for "
        "sum_linewidths). Dimension THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0) = "
        "W/(m K). It JOINS the thermal_conductivity family (the SAME "
        "thermal_conductivity tag and THERMAL_CONDUCTIVITY dimension as the nine "
        "lattice ThermalConductivity[*] nodes and the ElectronicThermalConductivity "
        "sibling) and is kept a DISTINCT node ONLY by the contribution=total "
        "LABEL_KEY (a registered value). The contribution key is deliberately "
        "SEPARATE from transport_model: transport_model distinguishes the lattice "
        "SOLVER routes (wigner, green_kubo, qhgk, ...) that all produce a "
        "lattice-only kappa, whereas contribution=total names a different axis "
        "(which heat channels are summed), so it never collides with a "
        "lattice-solver value. Discharges the claim the ElectronicThermalConductivity "
        "node already makes in prose (kappa_total = kappa_lattice + "
        "kappa_electronic) but that no edge summed. Scalar; a function of T (and, "
        "for the electronic part, doping)."
    ),
)

MOLAR_VOLUME = ObservableSpace(
    name="MolarVolume",
    fields=(Field("V_m", VOLUME_PER_MOLE, indices=()),),
    tier="Thermoelectric",
    description=(
        "Molar volume V_m = N_A V_cell: the volume PER MOLE OF PRIMITIVE CELLS, a "
        "promoted-parameter-style contraction of the CellVolume by Avogadro's "
        "number N_A. NEW dimension VOLUME_PER_MOLE (0,3,0,0,-1,0,0) = m^3/mol, "
        "exactly CellVolume's VOLUME (0,3,0,0,0,0,0) times N_A's N^-1. ON THE "
        "PHONON MOLAR BASIS: per mole of the SAME primitive / unit cells as the "
        "phonopy Molar* thermodynamics (MolarHeatCapacity, HeatCapacityConstantP, "
        "the QHA G, all per mole of the phonopy cell), NOT the CALPHAD "
        "per-mole-of-ATOMS basis. This basis guardrail is LOAD-BEARING: MolarVolume "
        "is the input that closes C_P - C_V = T V_m alpha^2 B against the molar "
        "MolarHeatCapacity and HeatCapacityConstantP (both per mole of cells), so a "
        "per-atom V_m would silently break that identity by a factor of "
        "atoms-per-cell. To cross-code to a per-mole-of-ATOMS molar volume, divide "
        "by atoms-per-cell. The whole-map physics review's single cleanest "
        "addition: the one node that makes BOTH the molar Gruneisen form and "
        "C_P - C_V executable and mutually cross-checking. Served in m^3/mol "
        "(canonical) or cm^3/mol (1e-6 factor). Scalar; a function of T (V_cell "
        "expands with temperature) recorded in conditions."
    ),
)

POWER_FACTOR_NODE = ObservableSpace(
    name="PowerFactor",
    fields=(Field("PF", POWER_FACTOR, indices=()),),
    tier="Thermoelectric",
    description=(
        "Thermoelectric power factor PF = sigma_e S^2: the electronic electrical "
        "conductivity times the Seebeck coefficient squared, a closed-form "
        "contraction of two existing electronic-transport nodes "
        "(ElectricalConductivity[carrier=electronic] and SeebeckCoefficient). NEW "
        "dimension POWER_FACTOR (1,1,-3,-2,0,0,0) = W/(m K^2), which the "
        "dimensional gate proves from ELECTRICAL_CONDUCTIVITY (-1,-3,3,0,0,2,0) + "
        "2*SEEBECK (1,2,-3,-1,0,-1,0). The numerator of the thermoelectric figure "
        "of merit: ZT = PF T / kappa_total. The first fruit of the thermoelectric "
        "slice the whole-map physics review scoped. Scalar; a function of "
        "temperature and doping (carried in conditions of the sigma_e and S "
        "inputs)."
    ),
)

ZT = ObservableSpace(
    name="ZT",
    fields=(Field("ZT", DIMENSIONLESS, indices=()),),
    tier="Thermoelectric",
    description=(
        "The dimensionless thermoelectric figure of merit ZT = PF T / kappa_total = "
        "sigma_e S^2 T / (kappa_lattice + kappa_electronic): the single number a "
        "thermoelectrics colleague reads to judge a material, the power factor "
        "times temperature over the total thermal conductivity. DIMENSIONLESS "
        "(the gate proves POWER_FACTOR * TEMPERATURE / THERMAL_CONDUCTIVITY cancels "
        "to the all-zero tuple). It is the ONE relation that stitches the lattice "
        "and electronic thermal-transport halves of the map into a single "
        "thermoelectrics story: its kappa_total input is the "
        "ThermalConductivity[contribution=total] node, itself the lattice + "
        "electronic sum, so ZT transitively depends on both transport families. "
        "Kept a distinct node from the other dimensionless scalars (ThermalGruneisen, "
        "PoissonRatio, PhaseSpace3Phonon) by its zt tag (derived from the node "
        "name ZT, the acronym one token as HOMOLUMOGap -> homolumo_gap), as those "
        "are kept apart from each other. Scalar; a function of "
        "temperature and doping recorded in conditions."
    ),
)

NODES: tuple[Space, ...] = (
    THERMAL_CONDUCTIVITY_TOTAL,
    MOLAR_VOLUME,
    POWER_FACTOR_NODE,
    ZT,
)
