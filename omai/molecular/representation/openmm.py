r"""OpenMM (classical force-field molecular dynamics) adapter specs.

OpenMM as the AtomisticSkills drug-* skills drive it (arXiv 2605.24002, anchored
in scans/md-chem-bio-atomistic-skills.json, 19 entries, deep-review verified
2026-07-10): drug-protein-ligand-md (run_md.py: the full MM-MD workflow),
drug-complex-system-builder (build_complex.py: System + force-field assembly),
drug-protein-prep (openmm.app.Modeller + pdbfixer), drug-mmpbsa-gbsa (endpoint
energies). A NEW engine class: classical force fields, distinct from the MLIP and
DFT PES rails. OpenMM is not importable in the miniconda base env; all unit /
usage claims anchor to the vendored skill scripts.

  operator Space   OpenMM artifact                                        native
  ---------------  -----------------------------------------------------  ---------
  Trajectory       app.DCDReporter production.dcd (run_md.py:298-299)      nm, fs
  Temperature      StateDataReporter temperature (run_md.py:213-220)      kelvin
  Pressure         MonteCarloBarostat setpoint (run_md.py:234)            atm
  TotalEnergy      getPotentialEnergy (run_md.py:44)                      kJ/mol (per cell)

Trajectory is the FIFTH engine to produce the map's Trajectory node, after
gpumd, lammps, ase.md, and (implicitly) the MLIP MD routes: a genuine Trajectory
on a CLASSICAL fitted force field rather than an MLIP or DFT PES. The four-phase
workflow (minimize -> restrained NVT -> restrained-then-released NPT ->
production NPT, LangevinMiddleIntegrator) makes the frames canonical-ensemble
samples, not a microcanonical trace.

The MM checkpoint analog (openmmforcefields). The (protein_ff, ligand_ff,
water_model, nonbondedMethod) tuple (build_complex.py:97-117,133,186; default
amber/ff14SB + openff-2.2.0 + tip3p + PME) is to an OpenMM run exactly what a
checkpoint is to an MLIP run and (functional, basis_set, pseudopotential) is to a
DFT run: the method provenance every Trajectory / energy / force rides on.
openmmforcefields (the SystemGenerator assigning ligand parameters via SMIRNOFF
openff or GAFF) is the provenance registry. The water model (tip3p default) is
the single biggest provenance knob (tip3p vs opc changes every downstream
number), a method choice, NOT a system property. It is a representation-level
gauge on the OpenMM-produced nodes, not a node itself.

The MM TotalEnergy (a fourth energy zero, labeled). The OpenMM potential energy
is a per-SIMULATION-CELL extensive energy on a CLASSICAL FORCE-FIELD zero (a sum
of bonded + PME electrostatics + LJ terms), reported in kJ/mol (run_md.py:44). It
is the SAME TotalEnergy node the periodic and molecular-DFT codes ground,
distinct only by the provenance label (basis=per_cell, engine=openmm,
potential_class=classical_forcefield); the label FORBIDS cross-substrate
subtraction against the MLIP, DFT-pseudopotential, and DFT-all-electron/ORCA
zeros (FOUR incompatible energy zeros now coexist). Capability-level for now: the
skills report PE / total-energy only as an equilibration diagnostic (density / T
convergence), not as a standalone deliverable.

Unit traps this module pins (all review-verified against scipy CODATA):

  * kJ/mol energy, kelvin, atm, femtosecond timestep, nanometer length: the
    OpenMM internal units (run_md.py:44,148,234,147,95-97). 1 eV = 96.48533212331
    kJ/mol (exact). kJ/mol here is per-mole-of-MOLECULES (ENERGY_PER_MOLE), a
    different basis from the CALPHAD per-mole-of-atoms and phonon per-mole-of-cells
    nodes; an OpenMM PE for a solvated box is extensive per-cell, served in the
    canonical ENERGY unit.
  * The OpenMM (nm, fs) vs MDAnalysis (Angstrom, ps) handoff: the energy base
    matches (kJ/mol) but LENGTH and TIME bases differ. A Trajectory written in nm
    with fs timesteps is read into Angstrom with a ps axis by MDAnalysis. The
    length/time-base MISMATCH at the OpenMM->MDAnalysis handoff is a real trap.
  * Two temperature definitions in run_md.py: the hand-rolled 2*KE/(3N*R) (:42, no
    dof correction, a small-system bias) vs the StateDataReporter dof-corrected T
    (:213). Serve the dof-corrected observable.
  * The barostat pressure is a control SETPOINT in atm (run_md.py:234), NOT a
    measured virial pressure; do not conflate it with the mechanical Pressure
    observable (a stress trace).

Deferred with reasons: MM-GBSA / MM-PBSA binding free energy (a fitted RANKING
score, single-trajectory endpoint, not an absolute affinity, compute_mmgbsa.py:11
'relative ranking rather than absolute binding'); Vina docking score (an
empirical scoring function, not a free energy); rdkit informatics (conformers /
fingerprints / descriptors / logP: molecular identity and fitted models, not
physics); the RRHO thermochemistry bundle (needs the MolecularFrequency node
first, the named hook); Density / RDF g(r) / coordination number (equilibration
diagnostics, no operator today); RMSD / RMSF / hbonds (bio-structural descriptors
outside the materials-physics map). openbabel (CLI format conversion) and
biopython (unused) enter no map provenance.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
from omai.mechanics.operator.nodes import PRESSURE
from omai.thermal_transport.operator.nodes import TEMPERATURE_STATE, TRAJECTORY


OPENMM_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="openmm",
    code_api={"r": "app.DCDReporter('production.dcd') (drug-protein-ligand-md/run_md.py:298-299)"},
    notes=(
        "The MM-MD Trajectory: positions written as DCD frames in nm with a fs "
        "timestep (run_md.py:298-299), consumed by drug-trajectory-analysis via "
        "mda.Universe (which reads them into Angstrom, a ps axis: the OpenMM(nm,fs) "
        "-> MDAnalysis(Angstrom,ps) handoff trap). The FIFTH Trajectory-producing "
        "engine (after gpumd, lammps, ase.md, MLIP MD), on a CLASSICAL fitted "
        "force field. LangevinMiddleIntegrator + MonteCarloBarostat, so frames are "
        "canonical-ensemble samples, not a microcanonical NVE trace. The engine "
        "label gains 'openmm'; the provenance MUST record the force-field set "
        "(protein_ff, ligand_ff, water_model, nonbondedMethod) as the checkpoint "
        "analog. A HiddenSpace (md_ensemble_noise gauge), so no comparison unit."
    ),
)


OPENMM_TEMPERATURE = SpaceRepresentationSpec(
    space=TEMPERATURE_STATE,
    representation_name="openmm",
    observable_units={"temperature": "kelvin"},
    code_api={"temperature": "StateDataReporter(temperature=True) (run_md.py:213-220)"},
    notes=(
        "Kinetic temperature from equipartition, the StateDataReporter "
        "dof-corrected value (run_md.py:213), in kelvin. The SAME Temperature node "
        "the LAMMPS / gpumd thermal scans ground; the target T is a thermostat "
        "setpoint (control parameter, default 300 K), the reported T the "
        "observable. NOTE the hand-rolled 2*KE/(3N*R) at :42 omits the "
        "constrained / COM dof correction (a small-system bias): serve the "
        "dof-corrected reporter value."
    ),
)


OPENMM_PRESSURE = SpaceRepresentationSpec(
    space=PRESSURE,
    representation_name="openmm",
    observable_units={"P": "atm"},
    code_api={"P": "MonteCarloBarostat(pressure*atmosphere, ...) (run_md.py:234)"},
    notes=(
        "The NPT barostat pressure SETPOINT, 1 atm by default "
        "(run_md.py:234, MonteCarloBarostat(pressure*atmosphere, temp, 25)). A "
        "control parameter in atm, NOT a measured virial pressure: do not conflate "
        "it with the mechanical Pressure observable (a stress trace, quoted in "
        "GPa/bar). Served here as the control setpoint; the map's Pressure node "
        "carries it as an evaluation condition."
    ),
)


OPENMM_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="openmm",
    observable_units={"E_tot": "ev"},
    code_api={"E_tot": "getPotentialEnergy().value_in_unit(kilojoule_per_mole) (run_md.py:44)"},
    notes=(
        "The MM potential / total energy of the simulation cell "
        "(run_md.py:44,190-191; StateDataReporter potentialEnergy/totalEnergy "
        ":216-219,308-311). kJ/mol NATIVE (1 eV = 96.48533212331 kJ/mol exact), "
        "served in the canonical ENERGY unit eV. PER SIMULATION CELL (a solvated "
        "protein-ligand box), extensive, on a CLASSICAL FORCE-FIELD zero (bonded + "
        "PME electrostatics + LJ), a FOURTH energy zero. The SAME TotalEnergy node "
        "the periodic and molecular-DFT codes ground, distinct only by the "
        "provenance label (basis=per_cell, engine=openmm, "
        "potential_class=classical_forcefield); the label FORBIDS subtraction "
        "against the MLIP, DFT-pseudopotential, and ORCA all-electron zeros (four "
        "incompatible zeros). A thermostatted / barostatted PE fluctuates; its "
        "ensemble mean is the reportable quantity. Capability-level: the skills "
        "use it only as an equilibration diagnostic, not a standalone deliverable."
    ),
)
