r"""Operator nodes of the thermochemistry domain.

Phase thermodynamics from assessed Gibbs-energy databases: the macroscopic
CALPHAD side of stability, finite-temperature and assessed, distinct from the
0 K DFT hull. Six ObservableSpaces from the pycalphad scan (AtomisticSkills,
arXiv 2605.24002).

Node table:

  Node                  quantity tag           dimension        indices
  --------------------  ---------------------  ---------------  -------
  AssessedDatabase      assessed_database      OPAQUE           ()
  MolarGibbsEnergy      molar_gibbs_energy     ENERGY_PER_MOLE  ()
  MolarEnthalpy         molar_enthalpy         ENERGY_PER_MOLE  ()
  ChemicalPotential     chemical_potential     ENERGY_PER_MOLE  (c)
  PhaseFraction         phase_fraction         DIMENSIONLESS    (p)
  TransitionTemperature transition_temperature TEMPERATURE      ()

The mole axis. MolarGibbsEnergy is the map's first mole-axis observable:
ENERGY_PER_MOLE has exponent vector (1,2,-2,0,-1,0,0), the fifth (N) slot
carrying the amount-of-substance axis. This dimension already exists (the
phonon-side molar nodes reuse it) but no molar-GIBBS or molar-enthalpy node
did, and none carries the CALPHAD basis; those are the new nodes here.

The Molar* false-merge guardrail (load-bearing). CALPHAD's molar quantities
SHARE the ENERGY_PER_MOLE exponent vector with the phonon-side Molar* nodes
(MolarHelmholtzFreeEnergy, MolarInternalEnergy) but are a DIFFERENT physics
and MUST NOT collapse to the same node:

  * potential:  Gibbs G (constant pressure) vs Helmholtz F (constant volume);
  * basis:      per mole of ATOMS (pycalphad v.N:1 system-moles) vs per mole
                of PRIMITIVE UNIT CELLS (phonopy convention);
  * producer:   Gibbs minimization over an assessed TDB vs a phonon-gas sum.

Identity keeps them apart by the quantity tag (molar_gibbs_energy /
molar_enthalpy are fresh tags, never molar_helmholtz_free_energy), so a
CALPHAD MolarGibbsEnergy and a phonopy MolarHelmholtzFreeEnergy have distinct
uids even though their fields share the exponent vector. The basis
(per_mole_of_atoms, constant pressure, SER zero) lives in the descriptions
and the representation notes, not the dimension.

AssessedDatabase is the domain's Sources-tier input artifact, opaque, the
CALPHAD analog of the phonon Potential and the MLIP checkpoint: a frozen,
human-assessed model (the TDB file plus its published assessment identity)
that the equilibrium solve reads. Scalar, no indices.

TransitionTemperature is a DISTINCT node from the source Temperature (an
input the ground-state / thermal-transport domains carry): a transition
temperature is a COMPUTED equilibrium output, the locus where phase stability
changes. Same TEMPERATURE dimension, distinct quantity tag and role.
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_MOLE,
    OPAQUE,
    TEMPERATURE,
)
from omai.operator.space import Field, ObservableSpace, Space

ASSESSED_DATABASE = ObservableSpace(
    name="AssessedDatabase",
    fields=(Field("D_tdb", OPAQUE, indices=()),),
    tier="Thermochemistry",
    description=(
        "The assessed Thermodynamic DataBase (TDB): the frozen, "
        "human-assessed set of Gibbs-energy models (SER-referenced GHSER* "
        "lattice stabilities, Redlich-Kister excess parameters, "
        "magnetic / Einstein contributions) that the equilibrium solve "
        "reads. An INPUT artifact, the CALPHAD analog of the phonon "
        "Potential and the MLIP checkpoint: a frozen human-assessed model "
        "(distinct from the ab-initio-computed side). Its provenance is the "
        "TDB file plus the published assessment identity (e.g. alzn_mey.tdb, "
        "NIMS 2009, parameters from S. an Mey, Z. Metallkd. 84 (1993) "
        "451-455), which every value it produces must record as conditions. "
        "Opaque in Phase 1; scalar."
    ),
)

MOLAR_GIBBS_ENERGY = ObservableSpace(
    name="MolarGibbsEnergy",
    fields=(Field("G_m", ENERGY_PER_MOLE, indices=()),),
    tier="Thermochemistry",
    description=(
        "Assessed molar Gibbs energy G_m of a phase (or of the equilibrium "
        "assemblage): the free energy CALPHAD minimizes, pycalphad's GM. "
        "PER MOLE OF ATOMS (the v.N:1 system-moles normalization), at "
        "CONSTANT PRESSURE, with the SER (Stable Element Reference) as the "
        "energy zero. J/mol, dimension ENERGY_PER_MOLE (1,2,-2,0,-1,0,0), "
        "the map's first mole-axis observable. EXPLICITLY DISTINCT from the "
        "phonon-side Molar* nodes (MolarHelmholtzFreeEnergy, "
        "MolarInternalEnergy), which are a HELMHOLTZ free energy (constant "
        "volume) per mole of PRIMITIVE CELLS from a phonon-gas sum: same "
        "exponent vector, different thermodynamic potential, basis, and "
        "producer, kept apart by the molar_gibbs_energy quantity tag (the "
        "Molar* false-merge guardrail). To compare a G_m to a DFT per-atom "
        "energy, divide J/mol by 96485.33212331 for eV/atom AND bridge the "
        "SER-vs-DFT reference; not an EXPECTED_AGREE pair without that bridge."
    ),
)

MOLAR_ENTHALPY = ObservableSpace(
    name="MolarEnthalpy",
    fields=(Field("H_m", ENERGY_PER_MOLE, indices=()),),
    tier="Thermochemistry",
    description=(
        "Assessed molar enthalpy H_m = G - T dG/dT of a phase, pycalphad's "
        "HM, derived from the Gibbs energy by the Legendre relation. PER "
        "MOLE OF ATOMS, at CONSTANT PRESSURE, SER reference; J/mol, "
        "ENERGY_PER_MOLE. The enthalpy of formation (H_m referenced to SER) "
        "is the CALPHAD analog of the DFT FormationEnergy, but referenced to "
        "SER not DFT elements and in J/mol-atoms not eV/atom (factor "
        "96485.33212331). Same basis notes as MolarGibbsEnergy; a distinct "
        "quantity from the phonon-side molar energies (the guardrail: this "
        "is a Gibbs-side enthalpy per mole of atoms, not a per-cell phonon "
        "internal energy)."
    ),
)

CHEMICAL_POTENTIAL = ObservableSpace(
    name="ChemicalPotential",
    fields=(Field("mu", ENERGY_PER_MOLE, indices=("c",)),),
    tier="Thermochemistry",
    description=(
        "Equilibrium chemical potential mu_c of a component: the partial "
        "molar Gibbs energy, pycalphad's MU, one per non-vacancy component "
        "(the `c` component index). It is the common-tangent hyperplane of "
        "the Gibbs minimization (the Lagrange multipliers of the mass-balance "
        "constraints), the multi-component generalization of the hull "
        "tie-line, and the quantity whose equality across phases defines the "
        "phase boundaries. J/mol per mole of atoms, ENERGY_PER_MOLE. An "
        "OUTPUT of the equilibrium (distinct from the elemental-reference "
        "mu_i supplied as inputs to the stability domain's defect / voltage "
        "closed forms). Provenance = the assessed database plus the "
        "(components, phases, conditions) of the solve."
    ),
)

PHASE_FRACTION = ObservableSpace(
    name="PhaseFraction",
    fields=(Field("NP", DIMENSIONLESS, indices=("p",)),),
    tier="Thermochemistry",
    description=(
        "Equilibrium molar amount (fraction) of each stable phase in the "
        "assemblage, pycalphad's NP, indexed by phase (the `p` axis). Under "
        "the v.N:1 normalization it is the mole fraction of each coexisting "
        "phase (the lever rule): the headline output of the property-diagram "
        "skill, plotted vs temperature to read solidification / "
        "heat-treatment paths. Dimensionless, no analog on the phonon / DFT "
        "map: the distinctive output of a Gibbs-minimization engine (how "
        "much of each phase coexists). A phase-fraction-vs-T curve is an "
        "array / spectrum instance; provenance = the assessed database plus "
        "composition and (T, P)."
    ),
)

TRANSITION_TEMPERATURE = ObservableSpace(
    name="TransitionTemperature",
    fields=(Field("T_trans", TEMPERATURE, indices=()),),
    tier="Thermochemistry",
    description=(
        "A computed phase-transition temperature: a liquidus / solidus / "
        "solvus point or an invariant (eutectic / eutectoid / peritectic) "
        "temperature, the locus where phase stability changes on the "
        "T-x diagram. Kelvin, TEMPERATURE dimension. DISTINCT node from the "
        "input Temperature (a Source the calculation is given): a transition "
        "temperature is COMPUTED by the equilibrium / binplot sweep, an "
        "output. The scalar invariant points are single (T, x) values; the "
        "full liquidus / solidus loci T(x) are a spectrum-layer product "
        "(deferred). Provenance = the assessed database plus components and "
        "phases."
    ),
)

NODES: tuple[Space, ...] = (
    ASSESSED_DATABASE,
    MOLAR_GIBBS_ENERGY,
    MOLAR_ENTHALPY,
    CHEMICAL_POTENTIAL,
    PHASE_FRACTION,
    TRANSITION_TEMPERATURE,
)
