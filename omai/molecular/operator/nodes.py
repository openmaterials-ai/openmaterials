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
  MolecularFrequency            molecular_frequency       FREQUENCY  (m)

MolecularFrequency arrives from the physics review (2026-07-10): the molecular
normal-mode axis, FREQUENCY dimension, indexed by mode number m (the registered
`mode` index kind, the named hook this slice's deferral pointed to). Its
imaginary-mode-negative serialization and n_imaginary saddle-order diagnostic
are the convention the deferral was waiting to fix; explicitly NOT the periodic
phonon (q, nu) Frequency.

The three energy nodes REUSE the plain ENERGY exponent vector (1,2,-2,0,0,0,0)
shared with
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

MolecularFrequency LANDED (physics review, 2026-07-10): the molecular
normal-mode axis is now a node (FREQUENCY, index m = the registered `mode`
kind), with the imaginary-mode convention fixed (imaginary modes serialized
NEGATIVE cm^-1, n_imaginary the saddle-order diagnostic). It is produced by
compute_molecular_frequencies (the mass-weighted-Hessian normal modes).

Deferred still (each with a named hook, so minting later is a clean add):

  * The molecular thermochemistry family (ZeroPointEnergy, MolecularEnthalpy,
    MolecularGibbsEnergy, the T*S entropy correction): per-molecule gas-phase RRHO
    ENERGY scalars, kept apart from the CALPHAD per-mole-of-atoms and phonon
    per-mole-of-cells nodes. This RRHO bundle is the NEXT named hook, now
    UNBLOCKED: it needed the MolecularFrequency node first (the modes drive the
    partition function), which this slice landed.
  * SolvationFreeEnergy, DipoleMoment, NMRShift: not surfaced by any parser today
    (the skills tag solvation on/off and read dipole/NMR from the property file
    manually), so deferred. Solvated single points ride TotalEnergy provenance.
"""
from __future__ import annotations

from omai.operator.dimensions import ENERGY, FREQUENCY
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

MOLECULAR_FREQUENCY = ObservableSpace(
    name="MolecularFrequency",
    fields=(Field("nu_mol", FREQUENCY, indices=("m",)),),
    tier="Molecular",
    description=(
        "Molecular normal-mode vibrational frequencies of a finite molecule: "
        "the 3N-6 (or 3N-5 for a linear molecule) discrete modes obtained by "
        "diagonalizing the mass-weighted Hessian, indexed by mode number m "
        "(the registered `mode` index kind). Dimension FREQUENCY "
        "(0,0,-1,0,0,0,0), served in wavenumbers cm^-1 native (the ORCA / "
        "quantum-chemistry convention). IMAGINARY modes are serialized as "
        "NEGATIVE frequencies (a mode whose Hessian eigenvalue is negative, an "
        "unstable direction); n_imaginary, the count of imaginary modes, is the "
        "SADDLE-ORDER diagnostic (a minimum has 0, a first-order transition "
        "state exactly 1). EXPLICITLY NOT the periodic phonon Frequency node "
        "(the (q, nu) = (qpoint, branch) dispersion omega_qnu over the "
        "Brillouin zone): a molecule has NO q and NO phonon branch (no "
        "periodicity, only the discrete mode index m), so the two never alias, "
        "kept apart by the molecular_frequency tag and the mode-index signature "
        "vs the phonon (qpoint, branch). CONVENTION CAVEAT: cm^-1 is a linear "
        "wavenumber (1 cm^-1 = c . 100 m^-1 = 0.0299792458 linear THz), NOT an "
        "angular frequency; the angular-vs-wavenumber factor 2 pi c is a "
        "representation-layer convention, recorded on the rail. The molecular "
        "thermochemistry (RRHO) bundle that consumes these modes for the "
        "partition function is the next named hook, now unblocked."
    ),
)

NODES: tuple[Space, ...] = (
    HOMO_LUMO_GAP,
    REACTION_BARRIER,
    BOND_DISSOCIATION_ENERGY,
    MOLECULAR_FREQUENCY,
)
