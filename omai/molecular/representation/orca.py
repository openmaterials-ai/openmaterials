r"""ORCA (molecular quantum chemistry) adapter specs.

ORCA 6.1 as the AtomisticSkills orca-agent skills drive it (arXiv 2605.24002,
anchored in scans/orca-atomistic-skills.json, 18 entries, deep-review verified
2026-07-10). ORCA is a proprietary binary (not pip-installable), so every
quantity claim anchors to a committed skill file:line: the three
chem-dft-orca-{singlepoint,optimization,advanced-calculation} skills, the shared
src/utils/dft/orca_utils.py, and the pure-regex parse_orca_output.py that reads
ORCA .out files. This is the map's FIRST molecular rail.

  operator Space      ORCA artifact                                        native -> served
  ------------------  ---------------------------------------------------  ----------------
  TotalEnergy         FINAL SINGLE POINT ENERGY (parse_orca_output.py:39)   Hartree -> eV
  Forces              -gradient (run_singlepoint.py:135-143)               Hartree/bohr -> eV/A
  HOMOLUMOGap         homo_lumo_gap_eV (parse_orca_output.py:86-93)        eV
  ReactionBarrier     E(TS)-E(reactant), ORCA static-TS (Hartree -> eV)    (construction=static_ts_dft; deferred)

The per-MOLECULE basis (the ruling). ORCA's TotalEnergy is the EXACT SAME
TotalEnergy node the periodic codes ground, distinct only by a required
provenance label: the spec notes carry (basis=per_molecule,
electron_treatment=all_electron, functional, basis_set, dispersion, solvation) and
the FORBIDDEN CROSS-SUBSTRATE SUBTRACTION rule. ORCA is all-electron (or ECP)
with an atom-centered Gaussian basis; its energy zero is the isolated-atoms /
all-electron reference, NOT the pseudopotential zero of QE/VASP nor the MLIP
atom_refs zero, so an ORCA molecular total and a periodic cell total are on
DIFFERENT absolute scales and must NEVER be subtracted across codes.

Unit and provenance traps this module pins (all review-verified against scipy
CODATA):

  * HARTREE everywhere. ORCA reports Hartree (Eh) natively for ALL energies;
    HARTREE_TO_EV = 27.211386245988 (hardcoded parse_orca_output.py:32, inline at
    run_orca_input.py:93, su.EV_PER_HARTREE at orca_utils.py:27). The map serves
    eV. Forces: Hartree/bohr * HARTREE_TO_EV * BOHR_PER_ANGSTROM -> eV/A
    (run_singlepoint.py:137), the Ry_per_bohr-analog conversion.
  * The final_energy DLPNO / DFT collision: the 'FINAL SINGLE POINT ENERGY' regex
    is method-blind. ORCA writes that header for DFT, DLPNO-CCSD(T), and CASSCF
    alike, all keyed final_energy; a correlated CCSD(T) total and a DFT total
    share the key but are DIFFERENT physics. The method string is provenance.
  * Basis-set provenance is the checkpoint analog: def2-SVP / PBE defaults are
    low-accuracy; results ride on (functional, basis_set, dispersion, solvation,
    special_option). wB97M-V needs a documented hack for any hyphenated functional
    (--functional '' --dispersion '' --special_option wB97M-V, SKILL.md:98-101).
  * Dispersion is folded into the method string (method = f'{functional}-
    {dispersion}', orca_utils.py:160-161) AND parsed separately
    (dispersion_correction_hartree); it is part of the reported total, not
    additive on top.
  * Solvation: --solvation requires --solvent (orca_utils.py:146-150); the
    solvated single point returns the ordinary energy tagged with
    solvation/solvent, NO G_solv difference is computed. Solvated runs ride
    TotalEnergy provenance (SolvationFreeEnergy deferred: no skill computes the
    gas-minus-solvated difference).
  * Thermochemistry (ZPE, enthalpy, Gibbs, entropy correction) is parsed in
    Hartree->eV per-molecule (parse_orca_output.py:127-147); the entropy member is
    the T*S PRODUCT in energy units, NOT the entropy S (divide by temperature_K
    for S). The molecular RRHO thermochemistry BUNDLE is deferred (it needs the
    MolecularFrequency node first).

Molecular frequencies (representation artifacts THIS slice). ORCA emits the
3N-6 normal-mode wavenumbers in cm^-1 (parse_orca_output.py:102, key
frequencies_cm1; imaginary modes printed NEGATIVE cm^-1; n_imaginary 0=min,
1=transition state) with per-mode IR intensities in km/mol (a predicted IR stick
spectrum, consumed by chem-spectrum-matcher). These enter as REPRESENTATION-LEVEL
artifacts on this rail, NOT as a node: the MolecularFrequency node (index kind
`m`/`mode`, now registered) is DEFERRED because minting it means deciding the
imaginary-mode convention (the named hook). cm^-1 is a spectroscopic WAVENUMBER
(nu-tilde = nu/c), the same FREQUENCY dimension as the periodic Frequency only
after the omega = 2*pi*c*nu_tilde bridge.

Deferred with reasons: the molecular RRHO thermochemistry bundle (needs the
MolecularFrequency node first, named hook); DipoleMoment (Debye, a new
charge*length dimension) and NMRShift (ppm), neither surfaced by any parser (the
agent reads calculation.property.txt manually); SolvationFreeEnergy (rides
TotalEnergy provenance until a skill computes G_solv).
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.nodes import FORCES, TOTAL_ENERGY
from omai.molecular.operator.edges import (
    compute_bond_dissociation,
    compute_homo_lumo_gap,
    compute_reaction_barrier,
)
from omai.molecular.operator.nodes import HOMO_LUMO_GAP, REACTION_BARRIER


ORCA_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="orca",
    observable_units={"E_tot": "ev"},
    code_api={"E_tot": "parse_orca_output.py final_energy_eV / run_singlepoint.py results.energy"},
    notes=(
        "The FINAL SINGLE POINT ENERGY of a converged molecular SCF "
        "(parse_orca_output.py:39-43, final_energy_hartree/final_energy_eV; "
        "run_singlepoint.py:116-117 results.energy * HARTREE_TO_EV; "
        "run_orca_input.py:33,90-93 the inline 27.211386245988 literal). "
        "Hartree (Eh) native, served eV (HARTREE_TO_EV = 27.211386245988). "
        "PER-MOLECULE basis (electron_treatment=all_electron, the isolated-atoms "
        "energy zero), the SAME TotalEnergy node the periodic codes ground, "
        "distinct only by this provenance label: (basis=per_molecule, "
        "electron_treatment=all_electron, functional, basis_set, dispersion, "
        "solvation). FORBIDDEN cross-substrate subtraction: an ORCA all-electron "
        "molecular total and a QE/VASP pseudopotential cell total (and an MLIP "
        "atom_refs total) are on DIFFERENT energy zeros, never differenced. The "
        "final_energy key is METHOD-BLIND (DFT, DLPNO-CCSD(T), CASSCF share it; "
        "record the method). Dispersion is folded into the method string and also "
        "parsed separately (dispersion_correction_hartree); it is part of the "
        "reported total. Solvated single points (CPCM/SMD) return the ordinary "
        "energy tagged solvation/solvent, no G_solv difference. The molecular "
        "RRHO thermochemistry (ZPE / enthalpy / Gibbs / T*S entropy correction, "
        "parse_orca_output.py:127-147, Hartree->eV per-molecule) rides ORCA too; "
        "its bundle node family is deferred (needs the MolecularFrequency node), "
        "and the entropy member is the T*S product in energy units, not S."
    ),
)


ORCA_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="orca",
    observable_units={"F": "eV_per_A"},
    code_api={"F": "run_singlepoint.py forces_eV_per_Ang (-gradient)"},
    notes=(
        "Per-atom Cartesian forces from ORCA analytic gradients: F = -gradient * "
        "HARTREE_TO_EV * BOHR_PER_ANGSTROM (run_singlepoint.py:135-143; "
        "run_optimization.py:191-194 at the optimized geometry). Hartree/bohr "
        "native, served eV/A. The SAME Hellmann-Feynman -dE/dR per-atom (i,alpha) "
        "Forces node the periodic codes ground; the force = -gradient sign flip "
        "and the Hartree/bohr -> eV/A conversion are representation-layer. "
        "Vanishes at a relaxed minimum (the optimization skill checks max/rms "
        "force); a transition state is a saddle with exactly one imaginary mode."
    ),
)


ORCA_HOMO_LUMO_GAP = SpaceRepresentationSpec(
    space=HOMO_LUMO_GAP,
    representation_name="orca",
    observable_units={"E_gap_mol": "ev"},
    code_api={"E_gap_mol": "parse_orca_output.py homo_lumo_gap_eV"},
    notes=(
        "The molecular HOMO-LUMO gap homo_lumo_gap_eV = lumo_eV - homo_eV, the "
        "difference of the two discrete frontier KS molecular-orbital energies "
        "(occupied[-1] and virtual[0], parse_orca_output.py:86-93). Native eV "
        "(ORCA prints orbital energies in both Hartree and eV; the parser keeps "
        "eV). A COUSIN of the periodic BandGap, NEVER equated: a molecule has no "
        "bands / no Brillouin zone / no VBM-CBM, only discrete MOs. Both are KS "
        "gaps (not quasiparticle) and both are strongly XC-functional dependent "
        "(the def2-SVP / functional string is provenance on the producing edge)."
    ),
)


ORCA_REACTION_BARRIER = SpaceRepresentationSpec(
    space=REACTION_BARRIER,
    representation_name="orca",
    observable_units={"E_barrier": "ev"},
    code_api={"E_barrier": "run_optimization.py tsopt saddle (agent-level E(TS)-E(reactant))"},
    notes=(
        "ORCA's molecular static transition-state route to a reaction barrier: a "
        "single-ended TS optimization (run_optimization.py:141-146, "
        "readuct.run_tsopt_task) converges a saddle verified by EXACTLY ONE "
        "imaginary mode (:234-247); the barrier E(TS) - E(reactant) is the "
        "agent-level difference of two Hartree->eV energies. This is the "
        "construction=static_ts_dft producer of the SAME reaction_barrier family "
        "(an OVERLAP with the ORCA scan, not a duplicate node). It joins the "
        "family LATER (deferred: the barrier delta is agent-level, no ORCA script "
        "computes it), distinct from the neb_mep node minted this slice only by "
        "the construction label, NO re-mint. FORBIDDEN cross-construction "
        "subtraction: an ORCA all-electron Hartree->eV barrier and an MLIP-eV NEB "
        "barrier sit on different energy zeros. The TS energy itself grounds a "
        "labeled TotalEnergy (saddle-point, 1 imaginary mode)."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs. ORCA is driven two ways: SCINE
# (su.core.get_calculator('dft','orca') for single-point / optimization) and the
# raw ORCA_BINARY_PATH subprocess + regex parser (the advanced skill). The
# method string is the checkpoint analog.
# ---------------------------------------------------------------------------

_ORCA_METHOD_CHOICES = {
    "functional_basis": (
        "the molecular DFT method string: (functional, basis_set) e.g. "
        "PBE/def2-SVP (low-accuracy default) through B3LYP or wB97M-V/def2-TZVP; "
        "wB97M-V and any hyphenated functional need the "
        "--functional '' --special_option hack (SKILL.md:98-101). The "
        "checkpoint analog: every energy / gap / force rides on this string."
    ),
    "dispersion_solvation": (
        "the dispersion correction (D3BJ / D4, folded into the method string, "
        "orca_utils.py:160-161) and the implicit solvation (CPCM / SMD + solvent, "
        "orca_utils.py:146-150). Part of the reported total, provenance on the "
        "instance."
    ),
    "correlation_treatment": (
        "the correlation method: a DFT functional, or DLPNO-CCSD(T) / CASSCF "
        "through the same single-point skill (the final_energy key is "
        "method-blind); frozen-core and DLPNO thresholds are uncaptured "
        "provenance to record."
    ),
}


ORCA_COMPUTE_HOMO_LUMO_GAP = OperatorRepresentationSpec(
    operator=compute_homo_lumo_gap,
    representation_name="orca",
    discretization_choices=_ORCA_METHOD_CHOICES,
    notes=(
        "A converged molecular SCF: the orbital-energy block reduced to "
        "homo_lumo_gap_eV. The functional / basis string is the discretization "
        "(Potential-provenance analog)."
    ),
)


ORCA_COMPUTE_REACTION_BARRIER = OperatorRepresentationSpec(
    operator=compute_reaction_barrier,
    representation_name="orca",
    discretization_choices=_ORCA_METHOD_CHOICES,
    notes=(
        "ORCA's static-TS route to the reaction_barrier family "
        "(construction=static_ts_dft, deferred; the neb_mep construction is the "
        "minted node). A single-ended saddle optimization plus the agent-level "
        "E(TS)-E(reactant) difference in Hartree->eV. Bordered by the MLIP NEB "
        "route (chem-neb-barrier); cross-construction subtraction forbidden."
    ),
)


ORCA_COMPUTE_BOND_DISSOCIATION = OperatorRepresentationSpec(
    operator=compute_bond_dissociation,
    representation_name="orca",
    discretization_choices=_ORCA_METHOD_CHOICES,
    notes=(
        "ORCA can supply the molecular DFT fragment energies a bond dissociation "
        "energy differences (a labeled sibling of the reaction-energy producer); "
        "Hartree->eV per-molecule, kcal/mol the chemist's native convention. The "
        "committed chem-bond-dissociation skill runs on an MLIP, not ORCA; this "
        "spec records the ORCA molecular-DFT route as the alternative producer."
    ),
)
