"""ase adapter specs for the thermal-transport DAG.

ASE (Atomic Simulation Environment, https://wiki.fysik.dtu.dk/ase/) is not
a thermal-transport code in itself — it is the *calculator-interface
protocol* that kaldo, phonopy, phono3py, and many other Python-driven
materials-science codes use to evaluate forces, energies, and stresses on
a candidate atomic configuration. Concretely, the `ase.Atoms` object
holds an attached `Atoms.calc` whose `get_forces()` / `get_potential_energy()`
methods drive force-field, DFT, or ML-IP backends behind a uniform API.

This adapter exists to make the *shared ASE-calculator anchor* across the
BTE codes first-class in the operator/representation layer. When kaldo,
phonopy, and phono3py all wire their force evaluations through the same
ASE calculator instance (e.g. `LAMMPSlib(pair_style=...)`), the cross-code
κ comparison's "but you used different forces" caveat goes away: the
operator-layer Potential is pinned at the ASE protocol level.

The ASE adapter does NOT supply numerical thermal-transport observables
(frequencies, linewidths, κ) — those belong to the downstream codes. Its
sole responsibility was, at first, to declare `provide_potential` in a
code-agnostic way, so any other adapter can cite "ASE Atoms.calc" as its
Potential source.

The matcalc/ASE scan (arXiv 2605.24002, scans/matcalc-ase-atomistic-skills)
extended this adapter beyond Potential-hosting with the ASE delta: ASE is a
THIRD engine (with gpumd and lammps) that produces the mapped Trajectory
node (via ase.md integrators + ase.io TrajectoryWriter, 13 ensembles), and
it produces relaxed Structures (via ase.optimize optimizers + ase.filters
cell filters; that Structure spec lives in
omai.dft_ground_state.representation.ase, where the Structure node lives, and
build_codes merges it into this one "ase" rail). The Potential entry gained
the matcalc-driver scheme
vocabulary (optimizer in {FIRE, BFGS}, cell_filter in {FrechetCellFilter,
ExpCellFilter}, ensemble the 13 MD variants, fmax conventions per
calculator). Per the atomate2 ruling, matcalc mints no separate rail: these
schemes live on ase / MLIP operator specs, not a matcalc rail.

CODATA-generation boundary note (matcalc/ASE scan, verified live). ASE's
own unit basis (ase.units) is CODATA-2014: ase.units.GPa = 160.21766208
(_e = 1.6021766208e-19), ase.units.fs = 0.09822694788464063. matcalc's
analysis boundary (matcalc.units.eVA3ToGPa, pymatgen ElasticTensor) is
CODATA-2018 (160.21766339999996, scipy.e = 1.602176634e-19). So ASE's raw
stress rides CODATA-2014 while the derived elastic / EOS moduli ride
CODATA-2018: three CODATA generations coexist at the matcalc boundary
(ase 2014, matcalc/pymatgen 2018), a ~1e-8 relative split, physically
negligible but a real provenance record.

References:
  * Atoms.calc — https://wiki.fysik.dtu.dk/ase/ase/atoms.html#ase.Atoms.calc
  * Calculator backends — https://wiki.fysik.dtu.dk/ase/ase/calculators/

Concrete backends commonly used in this project's worked examples:
  * `ase.calculators.lammpslib.LAMMPSlib` — LAMMPS classical potentials
    (Tersoff, EAM, ReaxFF, …) driven by an in-Python LAMMPS instance.
  * `gpaw.GPAW` — DFT via GPAW, real-space grid.
  * `ase.calculators.kim.KIM` — OpenKIM portal models (Tersoff, EAM, …
    drawn from the public KIM-API repository).
  * MACE, NequIP, Orb, M3GNet, … — Python-wrapped ML interatomic
    potentials; each ships an `ase.calculators.calculator.Calculator`
    subclass.
"""

from __future__ import annotations

from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator.edges import provide_potential
from omai.thermal_transport.operator.nodes import POTENTIAL, TRAJECTORY


ASE_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="ase",
    code_api={"potential": "ase.Atoms.calc"},
    notes=(
        "The Potential is the ASE calculator object attached to the "
        "ase.Atoms instance via `atoms.calc = SomeCalculator(...)`. "
        "Concrete backends include LAMMPSlib (LAMMPS classical potentials), "
        "GPAW (DFT), KIM (OpenKIM portal models), and ML-IP wrappers "
        "(MACE, NequIP, Orb, M3GNet, …). Force evaluation is uniform: "
        "`atoms.get_forces()` returns (n_atoms, 3) in eV/Å regardless of "
        "the backend. Stress and energy similarly. The ASE protocol is "
        "what kaldo, phonopy, and phono3py all consume when their "
        "Phonons / Phono3py / Phonopy objects are built from an Atoms "
        "instance with `.calc` set. MATCALC-DRIVER SCHEME VOCABULARY "
        "(matcalc/ASE scan): matcalc drives this same ASE calculator through "
        "its property calculators, whose ASE-algorithm choices are schemes on "
        "the operators, not new nodes: optimizer in {FIRE (matcalc default), "
        "BFGS (SurfaceCalc / NEBCalc default; the mat-sample-pes-by-md sampler "
        "also uses BFGS)}; cell_filter in {FrechetCellFilter (matcalc "
        "RelaxCalc), ExpCellFilter (the mat-sample-pes-by-md sampler)}; "
        "constraints FixAtoms / FixSymmetry; ensemble in the 13 ase.md "
        "variants (see the Trajectory spec); fmax conventions per calculator "
        "(RelaxCalc / ElasticityCalc / EOSCalc / Phonon3Calc / SurfaceCalc "
        "0.1 eV/A, PhononCalc / QHACalc 1e-5 for the tight phonon pre-relax). "
        "run_ase reads get_stress(voigt=False), a 3x3 tensor (NOT an ASE "
        "Voigt-6). matcalc mints no unit basis of its own (only eVA3ToGPa, a "
        "scipy conversion): the atomate2 ruling applies, so these are "
        "operator schemes, not a matcalc rail."
    ),
)


ASE_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="ase",
    code_api={
        "r": "ase.md integrator frames via ase.io.trajectory.TrajectoryWriter (positions, A)",
        "v": "ase.md integrator frames (velocities, A per ASE time unit)",
    },
    notes=(
        "ASE is the THIRD engine (with gpumd and lammps) that produces the "
        "mapped Trajectory node: ase.md initializes velocities "
        "(MaxwellBoltzmannDistribution), selects an integrator by ensemble, "
        "attaches an ase.io.trajectory.TrajectoryWriter observer at "
        "loginterval, and reads the frames back (matcalc MDCalc, _md.py:31-443; "
        "the mat-sample-pes-by-md sampler runs its own ase.md loop). 13 "
        "ensembles: nve (VelocityVerlet); nvt* (NoseHooverChainNVT / "
        "NVTBerendsen / Langevin / Andersen / Bussi); npt* (NPT / NPTBerendsen "
        "/ MTKNPT / Inhomogeneous_NPTBerendsen). The Trajectory is "
        "gauge-dependent (integrator, ensemble, thermostat, initial-condition "
        "noise: the md_ensemble_noise gauge group), with cross-code content in "
        "the time-averaged contractions. Positions A, velocities A per ASE "
        "time unit (ase.units.fs = 0.09822694788464063, CODATA-2014); "
        "timestep 1.0 fs default. NOTE matcalc MDCalc itself is a "
        "capability-only calc no skill drives; the Trajectory production the "
        "skills do runs through their own ase.md code."
    ),
)


ASE_PROVIDE_POTENTIAL = OperatorRepresentationSpec(
    operator=provide_potential,
    representation_name="ase",
    notes=(
        "Provides Potential via the ASE calculator protocol. The user "
        "constructs an `ase.Atoms` instance and assigns "
        "`atoms.calc = SomeCalculator(...)`; downstream adapters "
        "(kaldo, phonopy, phono3py) consume this Atoms object directly. "
        "Algorithmic conventions on FC2/FC3 derivation (symmetry_group, "
        "FD displacement magnitude, etc.) remain with the downstream "
        "adapter (ASE is purely the force-evaluation interface). "
        "DEFERRED (matcalc/ASE scan, with reasons): the NEB migration barrier "
        "(chem-neb-barrier drives raw ase.mep NEB + NEBTools directly, NOT "
        "matcalc NEBCalc) is queued with the MD / chem family task; the QHA "
        "finite-T thermodynamics (Gibbs G(T), thermal expansion alpha(T), "
        "Cp(T); mat-qha-thermal-expansion via matcalc QHACalc) owes a basis "
        "reconciliation to the thermochemistry domain's second slice before it "
        "lands. CAPABILITY-ONLY matcalc calcs no skill drives (MDCalc, "
        "SurfaceCalc, EnergeticsCalc, NEBCalc, GBCalc, InterfaceCalc, "
        "LAMMPSMDCalc, ChainedCalc) are catalog-only: they ground map nodes in "
        "principle but enter no provenance from the current skill set, so they "
        "are not encoded."
    ),
)
