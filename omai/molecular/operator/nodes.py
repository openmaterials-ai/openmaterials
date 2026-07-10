r"""Operator nodes of the molecular domain.

Molecular quantum chemistry and reaction energetics, the map's FIRST molecular
code slice (AtomisticSkills arXiv 2605.24002: the ORCA quantum-chemistry skills
chem-dft-orca-{singlepoint,optimization,advanced-calculation} and the MLIP/chem
reaction skills chem-neb-barrier, chem-ts-optimization, chem-bond-dissociation).
Three ObservableSpaces, all scalar molecular energetics built on the per-MOLECULE
basis (a finite system with no periodic boundary conditions, no Brillouin zone),
distinct from the periodic per-cell energetics of the ground-state slice.

Node table:

  Node                          quantity tag              dimension  indices
  ----------------------------  ------------------------  ---------  -------
  HOMOLUMOGap                   homo_lumo_gap             ENERGY     ()
  ReactionBarrier[construction=  reaction_barrier          ENERGY     ()
    neb_mep]
  BondDissociationEnergy        bond_dissociation_energy  ENERGY     ()

All three REUSE the plain ENERGY exponent vector (1,2,-2,0,0,0,0) shared with
TotalEnergy, FormationEnergy, ReactionEnergy, and the other energy-difference
nodes: the dimension does NO separating work. Node identity is NAME-based
(omai/operator/space.py Space.__hash__/__eq__ hash on the node NAME, and the
derived quantity tag enters the identity hash), so each stays a distinct node
PURELY by carrying a fresh quantity tag, exactly as ConfigurationalEnergy and
ReactionEnergy stay distinct from TotalEnergy despite the shared exponent vector.

The per-molecule basis (load-bearing). ORCA total energies are all-electron (or
ECP) Gaussian-basis energies on the isolated-molecule energy zero, NOT the
pseudopotential zero of the periodic codes; an MLIP molecular energy is on the
per-element atom_refs zero. These molecular energetics must NEVER be numerically
subtracted against a periodic per-cell TotalEnergy nor across constructions; the
FORBIDDEN cross-substrate subtraction rule lives in the descriptions here and in
the rail notes, not in a composite identity key.

  * HOMOLUMOGap is the KS gap between two DISCRETE frontier molecular orbitals of
    a finite system. A COUSIN of the periodic BandGap (same ENERGY dimension, same
    KS-eigenvalue-gap family, same KS-not-quasiparticle and semilocal-functional
    caveats) but NEVER the same node: BandGap is VBM-to-CBM over the Brillouin
    zone, and a molecule has no bands, so equating them is a category error. Kept
    apart by its homo_lumo_gap tag.
  * ReactionBarrier is minted ONCE this slice as ReactionBarrier[construction=
    neb_mep], the CI-NEB minimum-energy-path barrier (chem-neb-barrier via ase.mep
    NEBTools.get_barrier, eV, MLIP). The construction LABEL_KEY carries the
    disambiguation: the sella static-TS (static_ts_mlip) and ORCA static-TS
    (static_ts_dft) routes join this ONE reaction_barrier family LATER without a
    re-mint (the carrier-label precedent: same tag, same dimension, distinct nodes
    only by the label). EMPHATICALLY DISTINCT from the Arrhenius ActivationEnergy
    (a diffusivity-slope, not a PES barrier, a tempting name collision).
  * BondDissociationEnergy is the energy to cleave one bond, a difference of
    relaxed fragment total energies. A LABELED SIBLING of the solid-state
    ReactionEnergy (both stoichiometric total-energy differences) but on the
    per-molecule basis, kept apart by its bond_dissociation_energy tag; kcal/mol
    is the chemist's native convention (the chem-bond-dissociation script truncates
    the eV->kcal/mol factor to 23.0605; record the exact 23.060547830619 on the
    encode side).

Deferred this slice (each with a named hook, so minting later is a clean add):

  * MolecularFrequency (the molecular normal-mode axis, index kind `mode` now
    registered): a molecule's 3N-6 discrete vibrational modes have no q and no
    branch. Minting it means deciding the imaginary-mode convention (imaginary
    modes are printed NEGATIVE cm^-1; a transition state wants exactly 1); the
    molecular frequencies enter THIS slice as representation-level artifacts on
    the orca rail. Defer the node until the convention is fixed.
  * The molecular thermochemistry family (ZeroPointEnergy, MolecularEnthalpy,
    MolecularGibbsEnergy, the T*S entropy correction): per-molecule gas-phase RRHO
    ENERGY scalars, kept apart from the CALPHAD per-mole-of-atoms and phonon
    per-mole-of-cells nodes. Deferred; the RRHO bundle needs the MolecularFrequency
    node first (the modes drive the partition function).
  * SolvationFreeEnergy, DipoleMoment, NMRShift: not surfaced by any parser today
    (the skills tag solvation on/off and read dipole/NMR from the property file
    manually), so deferred. Solvated single points ride TotalEnergy provenance.
"""
from __future__ import annotations

from omai.operator.dimensions import ENERGY
from omai.operator.space import Field, ObservableSpace, Space

HOMO_LUMO_GAP = ObservableSpace(
    name="HOMOLUMOGap",
    fields=(Field("E_gap_mol", ENERGY, indices=()),),
    tier="Molecular",
    description=(
        "Kohn-Sham HOMO-LUMO gap of a MOLECULE: the eV difference "
        "E_LUMO - E_HOMO between the two discrete frontier molecular orbitals "
        "(highest occupied, lowest unoccupied) of a finite system, ORCA's "
        "orbital-energy block reduced to homo_lumo_gap_eV "
        "(parse_orca_output.py:86-93). Dimension ENERGY (1,2,-2,0,0,0,0), served "
        "in eV. A COUSIN of the periodic BandGap (a distinct uid by the "
        "homo_lumo_gap tag): same ENERGY dimension, the same "
        "KS-eigenvalue-gap family, the same caveats (both are KS gaps NOT "
        "quasiparticle gaps, both underestimated by semilocal functionals, both "
        "ride the Potential / method provenance). But NEVER the same node: "
        "BandGap is the gap between the valence-band MAXIMUM and the "
        "conduction-band MINIMUM over the Brillouin zone, whereas a MOLECULE has "
        "NO bands (no periodicity, no BZ, no VBM/CBM), only two discrete MOs. "
        "Calling a molecular HOMO-LUMO gap a band gap is a category error; this "
        "is the discrete-orbital / band split, mirroring the per-molecule / "
        "per-cell TotalEnergy basis split. The functional / basis-set string "
        "(def2-SVP default, low accuracy) is method provenance, recorded on the "
        "producing edge, not in this scalar node."
    ),
)

REACTION_BARRIER = ObservableSpace(
    name="ReactionBarrier[construction=neb_mep]",
    fields=(Field("E_barrier", ENERGY, indices=()),),
    labels={"construction": "neb_mep"},
    tier="Molecular",
    description=(
        "Reaction / migration barrier energy: the peak-minus-reactant energy "
        "along a reaction path. Minted this slice as the neb_mep construction: "
        "the CI-NEB minimum-energy-path barrier from chem-neb-barrier via "
        "ase.mep NEBTools.get_barrier()[0] (calculate_barrier.py:126-127, "
        "results['barrier_eV']:144; idpp interpolation, 7 images, an MLIP "
        "calculator), a single ENERGY scalar per reaction in eV. Dimension "
        "ENERGY (1,2,-2,0,0,0,0). It JOINS one reaction_barrier family through "
        "the construction LABEL_KEY (a registered value): the sella static-TS "
        "route (construction=static_ts_mlip, chem-ts-optimization, the barrier a "
        "downstream reactant/product/TS MLIP-energy difference) and the ORCA "
        "static-TS route (construction=static_ts_dft, chem-dft-orca molecular "
        "DFT, Hartree->eV, all-electron zero) join the SAME node family LATER "
        "with the SAME reaction_barrier tag and ENERGY dimension, distinct nodes "
        "only by the construction label, NO re-mint (the carrier-label pattern). "
        "CROSS-CONSTRUCTION SUBTRACTION IS FORBIDDEN: an MLIP-eV NEB barrier and "
        "an ORCA all-electron Hartree->eV barrier sit on different energy zeros "
        "and must never be differenced. EMPHATICALLY DISTINCT from the Arrhenius "
        "ActivationEnergy (activation_energy tag, E_a from the temperature "
        "dependence of diffusivity D(T) = D0 exp(-E_a/k_B T)): that is a "
        "diffusivity SLOPE, NOT a PES barrier, and the shared word is a trap."
    ),
)

BOND_DISSOCIATION_ENERGY = ObservableSpace(
    name="BondDissociationEnergy",
    fields=(Field("BDE", ENERGY, indices=()),),
    tier="Molecular",
    description=(
        "Bond dissociation energy: the energy to cleave one chemical bond of a "
        "molecule, a difference of relaxed fragment total energies, "
        "BDE_homolytic = E(A.) + E(B.) - E(A-B) from chem-bond-dissociation "
        "(calculate_bde.py:8, bde_eV:486; rdkit enumerates and fragments the "
        "bonds, the MLIP supplies the fragment energies). A single ENERGY scalar "
        "per bond in eV; dimension ENERGY (1,2,-2,0,0,0,0). A LABELED SIBLING of "
        "the solid-state ReactionEnergy (both are stoichiometric total-energy "
        "differences), kept a distinct node by the bond_dissociation_energy tag: "
        "ReactionEnergy is a balanced solid-state reaction combined from per-atom "
        "formation energies, whereas a BDE is a molecule-fragment energy "
        "difference on the per-MOLECULE basis (molecular fragments, not a "
        "periodic cell). Homolytic cleavage needs open-shell radical fragments "
        "(charge / spin set per fragment, calculate_bde.py:162); heterolytic "
        "needs charged fragments; which cleavage is an instance condition, not "
        "the node. kcal/mol is the chemist's native convention (1 eV = "
        "23.060547830619 kcal/mol; the script hardcodes the TRUNCATED 23.0605, so "
        "record the exact factor on the encode side); served here in the "
        "canonical eV. rdkit is catalog-only (fragmentation); only the MLIP "
        "energy difference is the physics."
    ),
)

NODES: tuple[Space, ...] = (
    HOMO_LUMO_GAP,
    REACTION_BARRIER,
    BOND_DISSOCIATION_ENERGY,
)
