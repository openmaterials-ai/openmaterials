r"""VASP adapter specs for the DFT ground-state domain.

VASP is the DFT engine AtomisticSkills (arXiv 2605.24002) drives through
atomate2, anchored in `scans/atomate2-vasp-atomistic-skills.json` (review
2026-07-09; every maker class and TaskDoc field verified against the atomate2
0.1.4 and emmet-core 0.87.1 wheels). This is the "vasp" rail, NOT a separate
"atomate2" rail: atomate2 is the workflow layer, and its maker classes and
TaskDoc paths are recorded inside these specs' code_api and notes. VASP is a
SECOND representation of every node QE already grounds (TotalEnergy, Forces,
Stress, Structure), plus MagneticMoment (pymatgen scan) and the electronic
BandGap this scan lands.

  operator Space   VASP / atomate2 artifact                        units
  ---------------  ----------------------------------------------  ----------
  Structure        POSCAR / CONTCAR (TaskDoc.structure)            angstrom
  TotalEnergy      TaskDoc.output.energy = e_0_energy              eV
  Forces           TaskDoc.output.forces                           eV/A
  Stress           TaskDoc.output.stress (emmet OutputDoc)         kbar
  MagneticMoment   Outcar.magnetization (per site)                 mu_B
  BandGap          BSVasprun.get_band_gap()['energy']              eV

Convention traps this module pins down (all review-verified against the
wheels and pymatgen 2025.6.14):

  * Stress is kbar from BOTH the raw pymatgen Vasprun.stress AND the atomate2
    TaskDoc.output.stress routes (emmet OutputDoc.stress is documented "units
    of kB", tasks.py:110-111), NOT GPa. The AtomisticSkills comment "Atomate2
    standardizes stress to GPa" (atomate2_utils.py:454) is false, so its
    conversion at :456 is 10x too large; an upstream defect, not a map issue.
  * Stress SIGN: VASP is compression-positive, sigma_VASP = -(1/V)dE/d(strain),
    the SAME sign as the map's Stress store (the QE convention). VASP -> store
    needs NO sign flip. AtomisticSkills re-signs to ASE tension-positive in its
    two atomate2 paths (the -1 at atomate2_utils.py:456,726) but NOT its raw
    Vasprun path (vasp_parser.py:79-81, no -1); the un-flipped raw path is the
    store-consistent one. Confirmed independently by pymatgen
    ElasticTensor.from_independent_strains, c_ij *= -0.1 (elastic.py:518-519).
  * TotalEnergy is the e_0_energy variant (energy(sigma->0), the sigma->0
    extrapolation Vasprun.final_energy returns), DECLARED here. The other VASP
    variants e_fr_energy (smeared free energy F = E - TS_smear) and e_wo_entrp
    (energy without entropy) are DIFFERENT quantities, not this node.
  * Absolute energy zero is PAW + XC-preset dependent (omat / mp / matpes-pbe /
    matpes-r2scan / mp-r2scan); VASP and QE agree only on RELATIVE energies.
  * ase.units.GPa in the scan env is CODATA-2014 (1/ase.units.GPa =
    160.21766208), ~1e-8 from the pymatgen CODATA-2018 constant; negligible.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.edges import (
    compute_band_gap,
    compute_forces_hf,
    compute_stress_cell,
    solve_ground_state,
)
from omai.dft_ground_state.operator.nodes import (
    BAND_GAP,
    FORCES,
    MAGNETIC_MOMENT_STATE,
    STRESS,
    STRUCTURE,
    TOTAL_ENERGY,
)


VASP_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="vasp",
    code_api={
        "structure": "VASP POSCAR (input) / CONTCAR (relaxed); atomate2 TaskDoc.structure, pymatgen Vasprun.final_structure",
    },
    notes=(
        "The crystal structure a VASP run consumes as a POSCAR and emits as "
        "the relaxed CONTCAR: lattice and positions in angstrom (or "
        "fractional), the same opaque Structure node QE grounds via "
        "CELL_PARAMETERS / ATOMIC_POSITIONS. atomate2 surfaces it as "
        "TaskDoc.structure; pymatgen round-trips via Poscar / "
        "Vasprun.final_structure (atomate2_utils.py:121-145, :443-445). A "
        "RelaxMaker run is Structure-in / (Structure, TotalEnergy, Forces, "
        "Stress)-out; a StaticMaker is Structure-in at fixed geometry. Opaque "
        "at the operator layer: an artifact, not a numeric unit."
    ),
)


VASP_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="vasp",
    observable_units={"E_tot": "ev"},
    code_api={
        "E_tot": "atomate2 TaskDoc.output.energy (e_0_energy); pymatgen Vasprun.final_energy, eV",
    },
    notes=(
        "The converged SCF total energy per cell, in eV (VASP native; emmet "
        "OutputDoc.energy is 'eV'). VARIANT DECLARED: this is e_0_energy, the "
        "energy(sigma->0) extrapolation that pymatgen Vasprun.final_energy "
        "returns (outputs.py:700-710, with the electronic-diff bugfix "
        "reconstruction) and TaskDoc.output.energy carries. The OTHER VASP "
        "variants are DIFFERENT quantities, not this node: e_fr_energy is the "
        "smeared free energy F = E - TS_smear (the free-energy TOTEN), and "
        "e_wo_entrp is the energy without entropy (outputs.py:6213-6215) - "
        "the per-cell analog of the QE '!' smeared-free-energy trap. A "
        "cross-code EXPECTED_AGREE with QE must compare the SAME variant AND "
        "account for the different absolute energy zero: VASP's PAW + XC "
        "preset (omat / mp / matpes-pbe / matpes-r2scan / mp-r2scan) fixes "
        "the zero, so VASP and QE agree only on RELATIVE energies. Produced "
        "by StaticMaker / RelaxMaker (and the MP / MatPES variants)."
    ),
)


VASP_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="vasp",
    observable_units={"F": "eV_per_A"},
    code_api={
        "F": "atomate2 TaskDoc.output.forces; pymatgen Vasprun.forces[-1] (final ionic step), eV/A",
    },
    notes=(
        "Per-atom Cartesian Hellmann-Feynman forces in eV/A (VASP native; "
        "emmet OutputDoc.forces 'units of eV/A'), shape (n_atoms, 3). Same "
        "unit as the map's Forces node and the MLIP rails; QE grounds the "
        "same node in Ry/bohr (factor 25.71104309541616). "
        "Vasprun.forces[-1] takes the FINAL ionic step "
        "(vasp_parser.py:68-71); the finite-displacement route to "
        "ForceConstants harvests exactly these per-supercell forces, the same "
        "family the QE finite-displacement note describes. No per-atom vs "
        "per-cell ambiguity: forces are inherently per-atom."
    ),
)


VASP_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="vasp",
    observable_units={"sigma": "kbar"},
    code_api={
        "sigma": "atomate2 TaskDoc.output.stress (emmet OutputDoc, kbar) / pymatgen Vasprun.stress[-1] (kbar)",
    },
    notes=(
        "Cell stress in kbar from BOTH VASP routes (SINGLE unit): the raw "
        "pymatgen Vasprun.stress varray (outputs.py:557-558) AND the atomate2 "
        "TaskDoc.output.stress, whose emmet OutputDoc.stress field is "
        "documented 'The stress on the cell in units of kB.' "
        "(emmet-core 0.87.1 tasks.py:110-111) and populated by copying the "
        "raw pymatgen ionic-step stress with no conversion (:158-181). NOT "
        "GPa: the AtomisticSkills comment 'Atomate2 standardizes stress to "
        "GPa' (atomate2_utils.py:454) is false, so its conversion at :456 "
        "(*-1.0*ase.units.GPa, treating kbar as GPa) is 10x too large - an "
        "upstream source defect, not a map issue (the map stores kbar). SIGN "
        "CONVENTION: VASP prints stress compression-positive, "
        "sigma_VASP = -(1/V)dE/d(strain), the SAME sign as the map's Stress "
        "store (the QE convention, qe.py); VASP -> store needs NO sign flip. "
        "Confirmed independently of the AtomisticSkills comments by pymatgen "
        "ElasticTensor.from_independent_strains, which applies "
        "c_ij *= -0.1 (elastic.py:518-519) on its stress-FIT route (the -1 "
        "flips VASP to the tension-positive continuum convention, consistent "
        "only if VASP is compression-positive). AtomisticSkills re-signs to "
        "ASE tension-positive in its two atomate2 paths "
        "(atomate2_utils.py:456,726) but NOT its raw Vasprun path "
        "(vasp_parser.py:79-81, no -1); the un-flipped raw path is the "
        "store-consistent one. 1 kbar = 0.1 GPa exactly; "
        "1 GPa = 0.006241509125883258 eV/A^3 (ase.units.GPa, CODATA-2014, "
        "1/ase.units.GPa = 160.21766208, ~1e-8 from the pymatgen "
        "CODATA-2018 elasticity constant, negligible)."
    ),
)


VASP_MAGNETIC_MOMENT = SpaceRepresentationSpec(
    space=MAGNETIC_MOMENT_STATE,
    representation_name="vasp",
    observable_units={"m": "mu_B"},
    code_api={
        "m": "pymatgen Outcar.magnetization (per site) / Outcar.total_magnetization (cell), mu_B; ISPIN=2 collinear",
    },
    notes=(
        "Per-site magnetic moments in Bohr magnetons from a spin-polarized "
        "(ISPIN=2) collinear VASP run: pymatgen Outcar.magnetization gives "
        "the per-site dict and Outcar.total_magnetization the cell total "
        "(vasp_parser.py:121-122; mat-magnetic-density parses the atomate2 "
        "results in parse_magnetic_moments.py). VASP is the DFT ground truth "
        "for the same node the pymatgen scan and the MLIP matgl (CHGNet "
        "magmom head) also ground; the FM/AFM/FiM/NM ordering is a downstream "
        "label over these moments, not part of the node."
    ),
)


VASP_BAND_GAP = SpaceRepresentationSpec(
    space=BAND_GAP,
    representation_name="vasp",
    observable_units={"E_gap": "ev"},
    code_api={
        "E_gap": "pymatgen BSVasprun.get_band_structure().get_band_gap()['energy'] / Vasprun / TaskDoc, eV",
    },
    notes=(
        "The electronic band gap in eV from a VASP band-structure run: "
        "pymatgen BSVasprun.get_band_structure().get_band_gap()['energy'], "
        "with bs.is_metal() and bs.efermi alongside "
        "(mat-electronic-structure plot_band_structure.py:69-78; "
        "get_mp_electronic_structure.py:79-84). This is the Kohn-Sham "
        "eigenvalue gap read from the vasprun.xml / TaskDoc, the KS gap "
        "(quantity=ks_gap), NOT the fundamental quasiparticle gap; semilocal "
        "functionals underestimate it, so it is strongly XC-functional "
        "dependent and rides with the Potential provenance. The band "
        "structure E(k) and electronic DOS g(E) are hidden electronic "
        "intermediates (like the KS wavefunctions), not mapped; the "
        "direct/indirect character (is_gap_direct) is a downstream label."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how atomate2 realizes the VASP workflows)
# ---------------------------------------------------------------------------

VASP_SOLVE_GROUND_STATE = OperatorRepresentationSpec(
    operator=solve_ground_state,
    representation_name="vasp",
    discretization_choices={
        "ENCUT": "plane-wave kinetic-energy cutoff (eV), from the preset input set",
        "k_mesh": "KPOINTS / KSPACING mesh (Monkhorst-Pack or gamma-centered)",
        "smearing": "ISMEAR / SIGMA (Gaussian / Methfessel-Paxton / tetrahedron); the energy variant depends on it",
        "EDIFF": "SCF self-consistency threshold on the total energy (eV)",
        "potcar_xc": "the POTCAR (PAW) set + XC functional (the preset omat / mp / matpes-pbe / matpes-r2scan / mp-r2scan), the Potential provenance",
    },
    notes=(
        "atomate2 realizes solve_ground_state as a StaticMaker / RelaxMaker "
        "run (atomate2.vasp.jobs.core, and the MP / MatPES variants in "
        "jobs.mp / jobs.matpes), submitted via jobflow run_locally or "
        "jobflow-remote, parsed to emmet.core.tasks.TaskDoc by VaspDrone / "
        "get_vasp_task_document (atomate2_utils.py:414-431); the maker "
        "classes are VERIFIED present in the atomate2 0.1.4 wheel. atomate2 "
        "is the workflow / provenance layer, the VASP analog of "
        "QE_SOLVE_GROUND_STATE: the preset fixes the XC functional, ENCUT, "
        "ISMEAR/SIGMA, EDIFF, and the POTCAR set, so two runs differing in "
        "POTCAR / XC / cutoff realize different Potentials; the k-mesh, "
        "smearing, and EDIFF are discretization choices of the solve itself. "
        "atomate2 is pinned to the catalog's verified 0.1.4 wheel, with the "
        "caveat that the AtomisticSkills atomate2-agent env leaves it "
        "unversioned in core_env.yaml, so a maker rename upstream would need "
        "a re-pin."
    ),
)


VASP_COMPUTE_BAND_GAP = OperatorRepresentationSpec(
    operator=compute_band_gap,
    representation_name="vasp",
    discretization_choices={
        "bandstructure_type": "BandStructureMaker mode (line / uniform / both): the NSCF k-path or dense mesh the gap is read from",
        "nscf_kpoints": "the NSCF k-point sampling (line-mode k-path density or uniform mesh); a coarse mesh can miss the true VBM/CBM",
    },
    notes=(
        "atomate2 realizes compute_band_gap as a BandStructureMaker flow "
        "(atomate2.vasp.flows.core, VERIFIED in the wheel; "
        "atomate2_utils.py:195-198), a static SCF followed by line / uniform "
        "NSCF; pymatgen reads the gap off the resulting vasprun.xml "
        "(BSVasprun.get_band_structure().get_band_gap()). The quantity is the "
        "KS eigenvalue gap (scheme quantity=ks_gap); the XC functional in the "
        "Potential provenance sets its magnitude, and the k-sampling is the "
        "discretization of where the VBM/CBM are located, not what the gap "
        "is."
    ),
)


VASP_COMPUTE_FORCES_HF = OperatorRepresentationSpec(
    operator=compute_forces_hf,
    representation_name="vasp",
    discretization_choices={
        "force_convergence": "EDIFFG (the ionic-step force threshold in a relax); the static forces are read at the converged geometry",
    },
    notes=(
        "The Hellmann-Feynman forces atomate2 reads off the same "
        "StaticMaker / RelaxMaker TaskDoc as the energy "
        "(TaskDoc.output.forces): no separate maker, one more response of the "
        "SCF solve. eV/A, the final ionic step."
    ),
)


VASP_COMPUTE_STRESS_CELL = OperatorRepresentationSpec(
    operator=compute_stress_cell,
    representation_name="vasp",
    discretization_choices={
        "tstress": "the stress-tensor computation flag (LSTRESS / ISIF>=2 in a relax); the value is TaskDoc.output.stress in kbar",
    },
    notes=(
        "The cell stress atomate2 reads off the same StaticMaker / "
        "RelaxMaker TaskDoc as the energy (TaskDoc.output.stress, kbar, "
        "compression-positive): no separate maker. The sign matches the "
        "map's Stress store (no flip); the kbar-vs-GPa unit trap and the "
        "AtomisticSkills 10x / ASE-re-sign facts live on the VASP_STRESS "
        "space spec."
    ),
)
