# matcalc and the ASE delta as used by AtomisticSkills

Scan of **matcalc** (`matcalc 0.5.1`, the property-calculator layer that drives
the MLIPs) and the **ASE delta** (what ASE itself produces beyond hosting a
`Potential`), as AtomisticSkills (arXiv 2605.24002) exercises them. Companion
catalog: `scans/matcalc-ase-atomistic-skills.json` (13 entries after review).
Sources: the matcalc calculator modules under
`src/matcalc/{_relaxation,_elasticity,_eos,_phonon,_phonon3,_md,_stability,_surface,_neb,_qha,_adsorption,_base}.py`
and `src/matcalc/backend/{_ase,_base}.py` + `units.py`, read from the
pip-downloaded sdist; ASE 3.26.0 read live from the base env; and the vendored
AtomisticSkills repo read directly for the skill usage (see the anchoring note).

**Anchoring note (deep review, 2026-07-09).** matcalc is NOT importable in the
miniconda base env; its sources were pip-downloaded
(`pip download --no-deps --dest /tmp/mcsrc matcalc` -> `matcalc-0.5.1.tar.gz`) and
read directly, so every matcalc claim is package-source-backed. ASE 3.26.0 IS
importable and every ASE class / unit claim was checked live. **The scanner's
claim that the AtomisticSkills repository is absent from this machine was FALSE.**
It is PRESENT, vendored at
`/Users/juicy/Development/science/openmaterials-ai/AtomisticSkills` (skills under
`.agents/skills/`, 126 `SKILL.md` dirs). Every AtomisticSkills usage claim below
has been re-anchored to the real skill scripts, with `file:line`. The **only**
matcalc calculators any skill actually drives are `ElasticityCalc`
(`mat-elasticity`), `EOSCalc` (`mat-equation-of-state`), `PhononCalc`
(`mat-phonon`, plus `mat-kinetic-monte-carlo` consuming its `phonon.yaml`),
`Phonon3Calc` (`mat-lattice-thermal-conductivity`), `QHACalc`
(`mat-qha-thermal-expansion`), `AdsorptionCalc` (`mat-surface-adsorption`), and
`RelaxCalc` (pre-relax only, `mat-sample-pes-by-md`). `MDCalc`, `NEBCalc`,
`SurfaceCalc`, `EnergeticsCalc`, `GBCalc`, `InterfaceCalc`, `LAMMPSMDCalc`, and
`ChainedCalc` are driven by NO skill. Three scanner usage claims died on contact:
`mat-sample-pes-by-md` does not drive `MDCalc` (its own `ase.md` sampler +
`RelaxCalc` pre-relax); `mat-surface-energy` does not drive `SurfaceCalc` (its own
pymatgen/ASE slab-bulk code); `mat-solid-free-energy` does not drive `PhononCalc`
(Frenkel-Ladd thermodynamic integration). One calc the scanner never cataloged,
`AdsorptionCalc`, IS driven and produces an adsorption energy with no map node.

## What matcalc IS in this software

matcalc is the **property-calculator layer**: the workflow / discretization tier
that turns an MLIP's opaque PES into the named physics quantities. It is to MLIPs
exactly what atomate2 is to VASP. Every calculator subclasses `PropCalc`
(`_base.py:20`) and takes one thing: an ASE calculator (or a universal-model name
it loads into one). From that single ASE calculator it drives:

- `RelaxCalc` -> geometry optimization -> a **relaxed Structure** + E/F/S
- `ElasticityCalc` -> **strain-stress fit** -> C_ij, K, G, E_Y
- `EOSCalc` -> **Birch-Murnaghan E(V) scan** -> E(V) curve + bulk modulus
- `PhononCalc` -> **phonopy** finite differences -> frequencies, molar thermal
- `Phonon3Calc` -> **phono3py** three-phonon BTE -> thermal conductivity
- `MDCalc` -> **ase.md** integrators -> a **Trajectory** + averaged energies
- `EnergeticsCalc` -> formation / cohesive energy per atom
- `SurfaceCalc` -> surface energy from the slab-bulk difference
- `NEBCalc` -> migration barrier (CI-NEB)
- `QHACalc` -> quasi-harmonic Gibbs / thermal expansion / Cp(T)

The pattern is uniform: `PropCalc._prerelax` (`_base.py:91-145`) relaxes the input
first (and ABORTS the chain if it does not converge), then the calculator samples
the PES around that equilibrium. `run_pes_calc` dispatches to the ASE backend
(`backend/__init__.py:12-33`), which calls `atoms.get_potential_energy()`,
`get_forces()`, `get_stress(voigt=False)` (`backend/_ase.py:147-163`).

> **matcalc = discretization/scheme layer over the MLIP PES.** Every node it
> "produces" is already grounded by a rail (MLIP E/F/S, phonopy, phono3py,
> pymatgen). Its VALUE is the *discretization* (which strains, which volume grid,
> which supercell/mesh), which is a scheme ON the operator, not a new rail.

## Rail vs schemes: the recommendation (schemes-on-operators, like atomate2)

**Recommendation: encode matcalc as an `OperatorRepresentationSpec` (a
scheme/discretization layer) on the operators, NOT as a separate rail.** This is
the same treatment the orchestrator gave atomate2 (whose makers live in
operator-spec schemes, no separate rail).

Evidence that matcalc is schemes, not a rail:

1. **It never mints a new unit basis of its own.** E/F/S come straight off the
   ASE calculator; phonons straight from phonopy; kappa straight from phono3py;
   EOS bulk modulus straight from pymatgen `BirchMurnaghan.b0_GPa`; elastic VRH
   straight from pymatgen `ElasticTensor`. Every output node is rail-grounded
   already.
2. **The calculators are thin orchestrators** of ASE/phonopy/pymatgen:
   `RelaxCalc` wraps `ase.optimize` + `FrechetCellFilter`; `MDCalc` wraps
   `ase.md` + `TrajectoryWriter`; `PhononCalc` wraps `phonopy.Phonopy`;
   `Phonon3Calc` wraps `phono3py.Phono3py`; `EOSCalc` wraps pymatgen
   `BirchMurnaghan`.
3. **The atomate2 precedent** is a structural match: the workflow layer for the
   VASP side is a scheme on `solve_ground_state`, and matcalc is the exact
   analog for the MLIP side.

But matcalc is a **harder** case than atomate2, and the facts must be stated
honestly:

- **matcalc's fit IS physics.** `ElasticityCalc._elastic_tensor_from_strains`
  (`_elasticity.py:182-224`) does the `np.polyfit(strain, stress, 1)` ITSELF,
  component by component, over matcalc's OWN `DeformedStructureSet`
  (`norm_strains=(-0.01,-0.005,0.005,0.01)`, `shear_strains=(-0.06,-0.03,0.03,0.06)`).
  That strain grid IS the `compute_elastic_constants` operator's discretization.
- **`EOSCalc` runs its own volume scan** (`n_points=11` over `+/-0.1`,
  `apply_strain` per point, fixed-volume relaxation each point) before the
  pymatgen BM fit (`_eos.py:116-144`). The grid is a matcalc scheme.

The correct reading of this is that matcalc carries **genuine, matcalc-owned
discretization schemes** (strain grid, EOS volume grid, supercell / mesh /
displacement, optimizer / fmax / cell-filter, ensemble), and those schemes belong
ON the operator representation exactly as atomate2's INCAR flags do. This
**reinforces** schemes-on-operators; it does not argue for a rail. Provenance of
every derived node must record BOTH the matcalc driver+scheme AND the MLIP
checkpoint (the double-provenance the mlip scan already flagged: matcalc is the
"true producer" of elastic/EOS/phonon results, but only via the MLIP PES).

## The ASE delta (beyond Potential-hosting)

The map has ONE ase entry today: `{ase: {Potential: {api: ase.Atoms.calc}}}`.
AtomisticSkills and matcalc exercise far more. What ASE **itself** produces
beyond hosting a calculator:

1. **A relaxed Structure.** `RelaxCalc` uses `ase.optimize` (FIRE default) plus
   `ase.filters.FrechetCellFilter` for cell relaxation, returning a relaxed
   `Structure` (`_relaxation.py`, `backend/_ase.py:119-154`). A
   Structure-producing OPERATION.
2. **A Trajectory.** `MDCalc` drives `ase.md` integrators
   (`VelocityVerlet`/`Langevin`/`NPT`/`NoseHooverChainNVT`/... , 13 ensembles)
   and writes an `ase.io.trajectory.TrajectoryWriter` at `loginterval`
   (`_md.py:344-443`). ASE is a THIRD engine (with gpumd, lammps) that produces
   the map's already-mapped `Trajectory` node. **Correction:** no skill drives
   matcalc `MDCalc`. `mat-sample-pes-by-md` produces the Trajectory through its
   OWN `ase.md` loop (`Inhomogeneous_NPTBerendsen`/`Langevin`/`VelocityVerlet`,
   `ExpCellFilter`, a hand-rolled `TrajectoryObserver`, `sampler.py:17-25,78`),
   using matcalc `RelaxCalc` only for the pre-relax (`sampler.py:313-329`). The
   ASE-delta Trajectory mapping stands; the driver is the skill's own ASE MD, not
   `MDCalc`.
3. **The raw E/F/S interface.** `atoms.get_potential_energy/get_forces/get_stress`
   is the actual production API for the MLIP nodes (already mapped).

**Recommendation:** the single ase `Potential` entry should GAIN scheme
vocabulary (`optimizer` in {FIRE, BFGS, ...}, `cell_filter` in {FrechetCellFilter,
...}, `ensemble` in the 13 MD variants), not new ase code entries. The
Structure-via-relax and Trajectory-via-MD productions are ASE operations already
grounded by other rails.

## Entry counts by status (13 entries after review)

- **already-mapped: 6** - matcalc-relax-structure (`Structure`),
  matcalc-relax-energy-forces-stress (`TotalEnergy`/`Forces`/`Stress`),
  matcalc-phonon3-thermal-conductivity (`ThermalConductivity[rta]`,
  `ForceConstants[order=3]`; drives phono3py rail), matcalc-md-trajectory
  (`Trajectory`; the ASE-delta headline), matcalc-formation-cohesive-energy
  (`FormationEnergy`; capability-only), matcalc-surface-energy (`SurfaceEnergy`;
  capability-only).
- **scheme-on-operator: 3** - matcalc-elastic-tensor-and-moduli
  (`compute_elastic_constants`: `ElasticConstants`/`BulkModulus`/`ShearModulus`/
  `YoungsModulus`), matcalc-eos-bulk-modulus (EOS: `TotalEnergy` curve +
  `BulkModulus` via an alternative-producer edge), matcalc-phonon-thermal
  (phonopy: `Frequency`/`PhononDOS`/`Molar*`/`ForceConstants[order=2]`). These
  ground already-mapped nodes but their fit / scan grids are matcalc-owned
  discretization schemes.
- **new-node-candidate: 3** - matcalc-neb-barrier (migration/NEB barrier, eV; no
  node today; skill-driven via raw `ase.mep`, not `NEBCalc`),
  matcalc-qha-thermodynamics (Gibbs G(T), thermal expansion alpha(T), Cp(T),
  macroscopic Gruneisen(T); driven by `mat-qha-thermal-expansion`), and
  matcalc-adsorption-energy (E_ads eV; driven by `mat-surface-adsorption` via
  `AdsorptionCalc`, a calc the scanner omitted). All three ARE skill-exercised
  today.
- **representation-only: 1** - ase-optimizers-filters-md-interface (the ASE
  machinery matcalc rides on: optimizers, filters, constraints, integrators,
  units, Trajectory; these become schemes/gauges on the operators, not nodes).

## Unit / provenance traps

1. **matcalc elastic default is eV/A^3, not GPa** (`units_GPa=False`,
   `_elasticity.py:58`). A consumer treating `elastic_tensor` /
   `bulk_modulus_vrh` as GPa without checking `units_GPa` is off by 160x.
   AtomisticSkills `mat-elasticity` converts skill-side (`*160.2176634`,
   CODATA-2018), consistent with the default.
2. **THREE CODATA generations at matcalc boundaries.** (a) raw stress rides
   `ase.units.GPa` = CODATA-2014 (`1/ase.units.GPa = 160.21766208`,
   `_e=1.6021766208e-19`, verified live); (b) `matcalc.units.eVA3ToGPa =
   scipy.constants.e/(A^3*giga) = 160.21766339999996` = CODATA-2018 (verified
   live, `scipy.e=1.602176634e-19`); (c) `ElasticityCalc` GPa mode uses pymatgen
   `ElasticTensor.GPa_to_eV_A3 = 160.21766339999996` = CODATA-2018 (verified
   live). **matcalc's analysis boundary is CODATA-2018 (pymatgen side); its PES
   boundary is CODATA-2014 (ASE side).** Same ~1e-8 in-repo split the pymatgen
   and VASP scans flagged, now with matcalc explicitly on the CODATA-2018 side.
3. **Two different bulk moduli.** `EOSCalc.bulk_modulus_bm` (pymatgen BM
   `b0_GPa`, GPa) is the EOS-curvature bulk modulus; `ElasticityCalc.bulk_modulus_vrh`
   (elastic-tensor VRH, eV/A^3 default) is the elastic-average bulk modulus. Same
   `bulk_modulus` tag, two distinct physics routes.
4. **`get_stress(voigt=False)` -> 3x3.** `run_ase` returns a full 3x3 stress in
   `SimulationResult.stress` (`backend/_ase.py:153,162`), NOT an ASE Voigt-6.
   `ElasticityCalc` feeds the 3x3 to pymatgen's fitter.
5. **phonopy under matcalc.** Frequencies are LINEAR THz (matches the map
   canonical linear-THz Frequency, `_phonon.py:189`). `thermal_properties` are
   MOLAR (free_energy kJ/mol, entropy/Cv J/K/mol), mapping to the existing
   `Molar*` nodes, not the per-mode nodes.
6. **fmax and optimizer defaults differ per calculator.** Relax / Elasticity /
   EOS / Phonon3 / Energetics / Surface use `fmax=0.1` eV/A; Phonon / QHA use
   `fmax=1e-5` (tight, phonons need a near-perfect equilibrium). Surface and NEB
   default optimizer BFGS; the rest default FIRE.
7. **Surface energy is eV/A^2 inside matcalc.** `SurfaceCalc.calc` returns
   `gamma` in eV/A^2 with NO J/m^2 conversion (`_surface.py:196`); the
   `16.021766339999996` J/m^2 factor (CODATA-2018) lives in the
   `mat-surface-energy` skill (pymatgen scan trap 7).
8. **Mixed pressure units.** `MDCalc.pressure` is in eV/A^3
   (`1.01325*units.bar`); `QHACalc.pressure` is documented in GPa.

## matcalc calc -> map-node route (the catalog at a glance)

| matcalc calc | physics route | map node(s) | status |
|---|---|---|---|
| `RelaxCalc` | ase.optimize + FrechetCellFilter | `Structure`, `TotalEnergy`, `Forces`, `Stress` | already-mapped |
| `ElasticityCalc` | strain-stress `polyfit` -> pymatgen `ElasticTensor` | `ElasticConstants`, `BulkModulus`, `ShearModulus`, `YoungsModulus` | scheme-on-operator |
| `EOSCalc` | volume scan -> pymatgen `BirchMurnaghan` | `TotalEnergy` (E(V)), `BulkModulus` (BM) | scheme-on-operator |
| `PhononCalc` | phonopy finite-diff | `Frequency`, `PhononDOS`, `Molar*`, `ForceConstants[2]` | scheme-on-operator |
| `Phonon3Calc` | phono3py 3-phonon BTE | `ThermalConductivity[rta]`, `ForceConstants[3]` | already-mapped |
| `MDCalc` | ase.md + TrajectoryWriter | `Trajectory` (the ASE delta) | already-mapped (capability-only; skill uses its own ase.md) |
| `EnergeticsCalc` | E_form vs elemental refs | `FormationEnergy` | already-mapped (capability-only, no skill) |
| `SurfaceCalc` | slab-bulk / (2A) | `SurfaceEnergy` | already-mapped (capability-only, no skill) |
| `AdsorptionCalc` | E_adslab - E_slab - E_ads | AdsorptionEnergy (none) | new-node-candidate (mat-surface-adsorption) |
| `NEBCalc` | ase.mep CI-NEB | migration barrier (none) | new-node-candidate (capability-only; skill uses raw ase.mep) |
| `QHACalc` | phonopy QHA volume scan | Gibbs/expansion/Cp(T) (none) | new-node-candidate (mat-qha-thermal-expansion) |

## Open questions

1. **RESOLVED by deep review.** The AtomisticSkills repo IS on this machine; every
   matcalc kwarg is now anchored to the real skill scripts (`file:line` per
   entry). Surviving skill drivers: `mat-elasticity` (`units_GPa` not passed,
   default eV/A^3, converts `*160.2176634`), `mat-equation-of-state`
   (`n_points=11`, reads `bulk_modulus_bm` GPa), `mat-phonon`,
   `mat-lattice-thermal-conductivity`, `mat-qha-thermal-expansion` (`eos='vinet'`),
   `mat-surface-adsorption` (`AdsorptionCalc`), `mat-sample-pes-by-md` (`RelaxCalc`
   pre-relax only). Killed: `MDCalc`/`SurfaceCalc`/`EnergeticsCalc`/`PhononCalc-via-
   solid-free-energy` were never skill-driven.
2. Rail vs schemes: recommendation is schemes-on-operators (like atomate2),
   confirmed by the live `matcalc.units` read (mints no unit basis, only
   `eVA3ToGPa`). Orchestrator to decide WHERE the matcalc-scheme + MLIP-checkpoint
   double-provenance lands.
3. **EOS bulk-modulus route (recommendation).** The EOS-BM `b0_GPa` is a distinct
   ESTIMATOR of the SAME `BulkModulus` node, not a new quantity. Enter it as an
   ALTERNATIVE PRODUCER EDGE (Pattern C): `TotalEnergy(E(V)) -> BulkModulus` via a
   new op (e.g. `compute_bulk_modulus_eos`), parallel to the existing
   `ElasticConstants -> BulkModulus` (`contract_bulk_modulus`) edge, exactly like
   `ForceConstants[order=2]` today carries both `compute_force_constants[order=2]`
   and `compute_fc2_finite_displacement`. Do NOT mint a second node.
4. ASE delta placement: the single ase `Potential` entry should gain scheme
   vocabulary (optimizer, cell_filter, ensemble). The Trajectory-via-MD production
   flows through the skill's own `ase.md` code, not matcalc `MDCalc`; confirm no
   new ase code entry is needed.
5. NEB barrier (eV), QHA thermodynamics, and AdsorptionEnergy are ALL skill-driven
   new-node candidates (chem-neb-barrier via raw `ase.mep`; mat-qha-thermal-
   expansion via `QHACalc`; mat-surface-adsorption via `AdsorptionCalc`). Decide
   whether to ingest these domains.
6. `cohesive_energy_per_atom` (EnergeticsCalc, eV/atom vs isolated atoms) has no
   map node; minor candidate. Note EnergeticsCalc is capability-only (no skill).
7. matcalc squeezes phono3py kappa to a scalar-per-T (diagonal mean,
   `_phonon3.py:202`), losing the tensor the map's `ThermalConductivity` node
   carries; the mat-lattice-thermal-conductivity skill reads the squeezed scalar
   at 300K/100K. Confirm the encode reads the full tensor off the phono3py object.
8. `ase.units.GPa` CODATA-2014 vs matcalc/pymatgen CODATA-2018 at the matcalc
   boundary: the same ~1e-8 split, now with matcalc on the CODATA-2018 side.
   Record on the elastic / EOS / surface representations.

## Review verdicts (2026-07-09)

Adversarial deep review of commit `d983e17`'s catalog. TOP DUTY discharged: the
AtomisticSkills repo, which the scanner declared absent, is PRESENT
(`AtomisticSkills/.agents/skills/`, 126 skills). Every matcalc usage claim was
re-anchored to the real skill scripts by grepping matcalc imports/calls. All
matcalc source claims were re-verified from `/tmp/mcsrc/matcalc-0.5.1/src/matcalc`
and every CODATA constant checked live in `/Users/juicy/miniconda3/bin/python`.
Graph checked against `docs/data/graph.json` (67-node snapshot: `BandGap` landed,
one `BulkModulus` node reached only by `ElasticConstants -> BulkModulus`
`contract_bulk_modulus`; `ForceConstants[order=2]` carries both an analytic and a
finite-displacement producer). No `mp-api` encode `index.lock` was present during
this review.

### The re-anchoring: how many usage claims survived contact with the real repo

Of the matcalc calculators the scanner attributed to skills, **4 survived intact**,
**1 was wrongly marked "unconfirmed" and is in fact driven, 3 were falsely
attributed to skills (driven by none), and 1 real driver was missed entirely.**

- **SURVIVED (4).** `ElasticityCalc` <- `mat-elasticity` (`calculate_elasticity.py:55,68-77`;
  `units_GPa` NOT passed so default eV/A^3, skill converts `*160.2176634` at
  `:33,86-88`, `use_equilibrium=True` hardcoded, exposes a `symmetry` kwarg the
  scanner missed). `EOSCalc` <- `mat-equation-of-state` (`calculate_eos.py:50,62-67`;
  `n_points` default 11, reads `bulk_modulus_bm` GPa at `:77`). `PhononCalc` <-
  `mat-phonon` (`calculate_phonon.py:26,46-49`). `Phonon3Calc` <-
  `mat-lattice-thermal-conductivity` (`calculate_thermal_conductivity.py:26,60-64`).
- **WRONGLY UNCONFIRMED, actually driven (1).** `QHACalc` <-
  `mat-qha-thermal-expansion` (`calculate_qha.py:25,33-40`, `eos='vinet'`, writes
  `gibbs_temperature.dat` + `thermal_expansion.dat`). The scanner said QHA was "not
  confirmed driven by a specific mat-* skill"; it is.
- **FALSELY ATTRIBUTED, driven by no skill (3).** `MDCalc` (scanner: driven by
  `mat-sample-pes-by-md`; truth: that skill uses `RelaxCalc` for pre-relax only,
  `sampler.py:313-329`, then its OWN `ase.md` loop with `Inhomogeneous_NPTBerendsen`/
  `Langevin`/`VelocityVerlet` + `ExpCellFilter`, `sampler.py:17-25,424,440`).
  `SurfaceCalc` (scanner: driven by `mat-surface-energy`; truth: that skill computes
  gamma with its own pymatgen/ASE code, `calculate_surface_energy.py:110,114`,
  `*16.0218`). `PhononCalc`-via-`mat-solid-free-energy` (scanner listed it as a
  second driver; truth: `mat-solid-free-energy` does Frenkel-Ladd thermodynamic
  integration, no matcalc). `EnergeticsCalc`/`FormationEnergy` also driven by no
  skill.
- **MISSED, actually driven (1).** `AdsorptionCalc` <- `mat-surface-adsorption`
  (`calculate_adsorption.py:58,83-115`), a matcalc calc entirely absent from the
  scanner's 12-entry catalog, producing an adsorption energy (eV) with no map node.
  Added as entry 13.

### Corrections that changed the physics story (not typos)

- **matcalc-md-trajectory: CORRECTED driver.** `MDCalc` is not skill-driven; the
  Trajectory production runs through the skill's own `ase.md` code. The ASE-delta
  Trajectory mapping stands; the misattribution is fixed.
- **matcalc-surface-energy: CORRECTED driver.** `SurfaceCalc` is not skill-driven;
  `mat-surface-energy` is pymatgen/ASE-native and uses the truncated `16.0218`
  literal (not the full CODATA-2018 `16.021766339999996`).
- **matcalc-qha-thermodynamics: CORRECTED status framing.** Upgraded from
  "unconfirmed" to skill-driven (`mat-qha-thermal-expansion`).
- **matcalc-neb-barrier: RE-ANCHORED.** A NEB barrier IS produced by a skill
  (`chem-neb-barrier`), but via `ase.mep` NEB/NEBTools directly
  (`calculate_barrier.py:10,103`), NOT matcalc `NEBCalc`. The candidate node is real
  and skill-emitted.
- **matcalc-adsorption-energy: ADDED.** New entry for the missed, skill-driven
  `AdsorptionCalc`.
- **EOS bulk-modulus route: RECOMMENDATION recorded.** Alternative-producer edge
  (Pattern C) on the single `BulkModulus` node, mirroring the fc2 dual-producer
  precedent verified live in the graph.

### Per-entry verdicts

- matcalc-relax-structure: CONFIRMED. `_relaxation.py:55,62` FIRE + FrechetCellFilter
  default, `relax_cell=True`; `backend/_ase.py:127` cell_filter wrap. Node present.
  Driven (pre-relax) by `mat-sample-pes-by-md` (`sampler.py:323`, FIRE, fmax=0.05).
- matcalc-relax-energy-forces-stress: CONFIRMED. `get_stress(voigt=False)` (3x3) at
  `backend/_ase.py:153,162`; nodes present. Consumer, not new producer.
- matcalc-elastic-tensor-and-moduli: CONFIRMED + RE-ANCHORED. `units_GPa=False`
  default (`_elasticity.py:58`), `np.polyfit(x,y,1)` at `:215`, strain grids at
  `:51-52`, `from_voigt` at `:222`. Skill anchor added. scheme-on-operator holds.
- matcalc-eos-bulk-modulus: CONFIRMED + RE-ANCHORED + EOS-route recommendation.
  `n_points=11` (`_eos.py:57`), `np.linspace(-max,max,11)` (`:124`),
  `constant_volume=True` (`:120`), `bm.b0_GPa` (`:164`). Alternative-producer edge
  recommended.
- matcalc-phonon-thermal: CONFIRMED + CORRECTED driver list. `atom_disp=0.015`,
  `min_length=20.0`, `fmax=1e-5` (`_phonon.py:66-72`), frequencies "THz" (`:189`).
  `mat-solid-free-energy` removed as a driver (Frenkel-Ladd, not phonopy).
  `mat-kinetic-monte-carlo` added as an indirect consumer of `phonon.yaml`.
- matcalc-phonon3-thermal-conductivity: CONFIRMED + RE-ANCHORED. supercells 2x2x2,
  mesh (20,20,20) (`_phonon3.py:59-61`), `kappa[...,:3].mean(axis=-1)` (`:202`),
  fmax 0.1 (`:66`). Driven by `mat-lattice-thermal-conductivity`.
- matcalc-md-trajectory: CONFIRMED node mapping, CORRECTED driver (MDCalc not
  skill-driven). `_md.py:13-21` ase.md integrators, `pressure` eV/A^3 (`:61`).
- matcalc-formation-cohesive-energy: CONFIRMED node, CORRECTED usage (capability-
  only; no skill imports `EnergeticsCalc`). `_stability.py` E_form formula intact.
- matcalc-surface-energy: CONFIRMED node, CORRECTED usage (SurfaceCalc not skill-
  driven; `mat-surface-energy` is pymatgen/ASE-native).
- matcalc-neb-barrier: CONFIRMED candidate, RE-ANCHORED driver (chem-neb-barrier via
  raw ase.mep, not NEBCalc). `_neb.py` source intact.
- matcalc-qha-thermodynamics: CONFIRMED candidate, CORRECTED status (skill-driven
  via `mat-qha-thermal-expansion`). `_qha.py` source intact.
- matcalc-adsorption-energy: NEW (ADDED). `_adsorption.py:14,28` (wraps RelaxCalc),
  driven by `mat-surface-adsorption` (`calculate_adsorption.py:58,83-115`).
- ase-optimizers-filters-md-interface: CONFIRMED representation-only. `ase.units.GPa`
  `= 1/160.21766208` (CODATA-2014), `ase.units.fs = 0.09822694788464063`, verified
  live. Note the skills also use `ExpCellFilter` and `BFGS` (sampler), broadening
  the cell_filter/optimizer scheme vocabulary beyond FrechetCellFilter/FIRE.

### Constants verified live (`/Users/juicy/miniconda3/bin/python`)

- `1/ase.units.GPa = 160.21766208`, `ase.units._e = 1.6021766208e-19` (CODATA-2014).
- `matcalc.units.eVA3ToGPa = scipy.constants.e/(angstrom^3*giga) = 160.21766339999996`,
  `scipy.constants.e = 1.602176634e-19` (CODATA-2018). `matcalc.units` contains this
  ONE symbol only (mints no unit basis; scheme-on-operator basis confirmed).
- pymatgen `ElasticTensor.GPa_to_eV_A3 = 0.006241509074460764`, inverse
  `= 160.21766339999996` (CODATA-2018). All three CODATA generations at the matcalc
  boundaries confirmed: raw stress on CODATA-2014 (ASE), analysis on CODATA-2018
  (matcalc/pymatgen).

### Two-bulk-moduli and get_stress verdicts

- **get_stress(voigt=False) 3x3: CONFIRMED** (`backend/_ase.py:153,162`).
- **Two distinct bulk moduli: CONFIRMED, same node.** EOS-BM (`b0_GPa`, curvature)
  and elastic-VRH (`k_vrh`) are different ESTIMATORS of the SAME physical bulk
  modulus of the SAME material, not different quantities. The map's one
  `BulkModulus` node should receive the EOS route as an alternative producer edge
  (Pattern C), not a second node.

### Decisions for the orchestrator (not for the reviewer)

1. **EOS-BM alternative-producer edge.** Approve `TotalEnergy(E(V)) -> BulkModulus`
   via `compute_bulk_modulus_eos`, parallel to `contract_bulk_modulus`, carrying the
   EOS volume-scan scheme. (Review leans: yes; it mirrors the fc2 dual-producer
   pattern already in the graph.)
2. **Which new-node domains to ingest.** Three are skill-driven TODAY: NEB migration
   barrier (chem-neb-barrier), QHA finite-T thermodynamics (mat-qha-thermal-
   expansion), AdsorptionEnergy (mat-surface-adsorption). Each opens a domain.
3. **matcalc scheme + MLIP-checkpoint double-provenance placement** on the
   compute_elastic_constants / EOS / phonon operators.
4. **ASE Potential scheme vocabulary.** Add optimizer {FIRE, BFGS}, cell_filter
   {FrechetCellFilter, ExpCellFilter}, ensemble (the MD variants) to the single ase
   entry rather than minting new ase code entries.
5. **Capability-only calcs.** MDCalc, SurfaceCalc, EnergeticsCalc, NEBCalc, GBCalc,
   InterfaceCalc, LAMMPSMDCalc, ChainedCalc are matcalc capabilities no skill drives;
   they ground nodes in principle but do not enter provenance from the current skill
   set. Decide whether to encode capability-only calcs at all.

### Not fixed (deliberately)

Line numbers in the JSON `source` lists are occasionally given as ranges or are off
by a line or two, but every cited symbol exists at (or within a line of) the stated
location; not worth per-line churn. No entry was KILLED; the misattributed drivers
were corrected in place and their node mappings retained (the calcs are real, the
usage attributions were wrong).
