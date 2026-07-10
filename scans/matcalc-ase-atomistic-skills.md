# matcalc and the ASE delta as used by AtomisticSkills

Scan of **matcalc** (`matcalc 0.5.1`, the property-calculator layer that drives
the MLIPs) and the **ASE delta** (what ASE itself produces beyond hosting a
`Potential`), as AtomisticSkills (arXiv 2605.24002) exercises them. Companion
catalog: `scans/matcalc-ase-atomistic-skills.json` (12 entries). Sources: the
matcalc calculator modules under
`src/matcalc/{_relaxation,_elasticity,_eos,_phonon,_phonon3,_md,_stability,_surface,_neb,_qha,_base}.py`
and `src/matcalc/backend/{_ase,_base}.py` + `units.py`, read from the
pip-downloaded sdist; ASE 3.26.0 read live from the base env; and the three prior
committed scans (`mlip-family`, `pymatgen`, `atomate2-vasp`) plus
`docs/data/codes.json` for the AtomisticSkills usage.

**Anchoring caveat.** matcalc is NOT importable in the miniconda base env; its
sources were pip-downloaded (`pip download --no-deps --dest /tmp/mcsrc matcalc`
-> `matcalc-0.5.1.tar.gz`) and read directly, so every matcalc claim is
package-source-backed. ASE 3.26.0 IS importable and every ASE class / unit claim
was checked live. **The AtomisticSkills repository is NOT present on this
machine** (searched `Development/` and `Development/science/`; not found).
AtomisticSkills usage of matcalc and ASE is therefore anchored to the three prior
scans that DID read the skill sources directly, plus `codes.json`, NOT to a live
read in this scan. A re-run with the repo mounted should confirm the exact
matcalc kwargs each `mat-*` skill passes.

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
   the map's already-mapped `Trajectory` node.
3. **The raw E/F/S interface.** `atoms.get_potential_energy/get_forces/get_stress`
   is the actual production API for the MLIP nodes (already mapped).

**Recommendation:** the single ase `Potential` entry should GAIN scheme
vocabulary (`optimizer` in {FIRE, BFGS, ...}, `cell_filter` in {FrechetCellFilter,
...}, `ensemble` in the 13 MD variants), not new ase code entries. The
Structure-via-relax and Trajectory-via-MD productions are ASE operations already
grounded by other rails.

## Entry counts by status (12 entries)

- **already-mapped: 6** - matcalc-relax-structure (`Structure`),
  matcalc-relax-energy-forces-stress (`TotalEnergy`/`Forces`/`Stress`),
  matcalc-phonon3-thermal-conductivity (`ThermalConductivity[rta]`,
  `ForceConstants[order=3]`; drives phono3py rail), matcalc-md-trajectory
  (`Trajectory`; the ASE-delta headline), matcalc-formation-cohesive-energy
  (`FormationEnergy`), matcalc-surface-energy (`SurfaceEnergy`).
- **scheme-on-operator: 3** - matcalc-elastic-tensor-and-moduli
  (`compute_elastic_constants`: `ElasticConstants`/`BulkModulus`/`ShearModulus`/
  `YoungsModulus`), matcalc-eos-bulk-modulus (EOS: `TotalEnergy` curve +
  `BulkModulus`), matcalc-phonon-thermal (phonopy: `Frequency`/`PhononDOS`/
  `Molar*`/`ForceConstants[order=2]`). These ground already-mapped nodes but
  their fit / scan grids are matcalc-owned discretization schemes.
- **new-node-candidate: 2** - matcalc-neb-barrier (migration/NEB barrier, eV; no
  node today) and matcalc-qha-thermodynamics (Gibbs G(T), thermal expansion
  alpha(T), Cp(T), macroscopic Gruneisen(T); a finite-T thermodynamics domain not
  on the map). Neither is confirmed driven by a specific `mat-*` skill in the
  prior scans; flag as open questions.
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
| `MDCalc` | ase.md + TrajectoryWriter | `Trajectory` (the ASE delta) | already-mapped |
| `EnergeticsCalc` | E_form vs elemental refs | `FormationEnergy` | already-mapped |
| `SurfaceCalc` | slab-bulk / (2A) | `SurfaceEnergy` | already-mapped |
| `NEBCalc` | ase.mep CI-NEB | migration barrier (none) | new-node-candidate |
| `QHACalc` | phonopy QHA volume scan | Gibbs/expansion/Cp(T) (none) | new-node-candidate |

## Open questions

1. AtomisticSkills repo is NOT on this machine. The exact matcalc kwargs each
   `mat-*` skill passes (`units_GPa`, `fmax`, `ensemble`, `elemental_refs`,
   strain grids) are anchored to the three prior scans + `codes.json`, not a live
   read. Re-run with the repo mounted to confirm.
2. Rail vs schemes: recommendation is schemes-on-operators (like atomate2),
   because every matcalc output node is already rail-grounded even though
   matcalc's strain / EOS fits are genuine discretization physics. Orchestrator to
   decide WHERE the matcalc-scheme + MLIP-checkpoint double-provenance lands.
3. ASE delta placement: the single ase `Potential` entry should gain scheme
   vocabulary (optimizer, cell_filter, ensemble) rather than new ase code
   entries. Confirm the Structure-via-relax and Trajectory-via-MD productions
   need no new ase code entry.
4. matcalc NEB barrier (eV) and QHA thermodynamics (Gibbs, thermal expansion,
   Cp(T), macroscopic Gruneisen(T)) are new-node candidates NOT confirmed driven
   by a specific `mat-*` skill in the prior scans. Decide whether to ingest these
   domains.
5. `cohesive_energy_per_atom` (EnergeticsCalc, eV/atom vs isolated atoms) has no
   map node; minor candidate distinct from FormationEnergy.
6. matcalc squeezes phono3py kappa to a scalar-per-T (diagonal mean,
   `_phonon3.py:202`), losing the tensor the map's `ThermalConductivity` node
   carries. Confirm the encode reads the full tensor off the phono3py object.
7. `ase.units.GPa` CODATA-2014 vs matcalc/pymatgen CODATA-2018 at the matcalc
   boundary: the same ~1e-8 split, now with matcalc on the CODATA-2018 side.
   Record on the elastic / EOS / surface representations.
