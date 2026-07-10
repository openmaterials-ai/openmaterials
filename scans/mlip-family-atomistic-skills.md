# The MLIP family (MACE, matgl, fairchem) as used by AtomisticSkills

Scan of the three machine-learning interatomic potentials that AtomisticSkills
(arXiv 2605.24002) drives: **MACE** (`mace-torch>=0.3.15`), **matgl** (M3GNet /
CHGNet / TensorNet, matgl 4.x), and **fairchem-core** (`>=2.18.0`, UMA / ESEN).
Companion catalog: `scans/mlip-family-atomistic-skills.json` (8 entries).
Sources: the three wrappers under
`AtomisticSkills/src/utils/mlips/{mace,matgl,fairchem}/*_wrapper.py`, the shared
base `src/utils/mlips/base.py` and `loader.py`, the MD driver `md_runner.py`, the
MCP tool layer `src/mcp_server/{mace,matgl,fairchem}_server.py`, the calling
`mat-*` and `ml-*` skills, and `conda-envs/{mace,matgl,fairchem}-agent/`.

**Anchoring caveat (RESOLVED in deep review 2026-07-09).** None of `mace-torch`,
`matgl`, `fairchem-core`, or `chgnet` is importable in the miniconda base env, and
the per-agent conda envs are not installed on this machine. The original scan
therefore anchored every unit, the ASE Voigt stress order, the MACE committee
keys, and the CHGNet magmom head to wrapper usage + docstrings. The deep review
**pip-downloaded all four wheels** (`mace_torch-0.3.16`, `matgl-4.0.3`,
`fairchem_core-2.21.0`, `chgnet-0.4.2`, `--no-deps`) and read the calculator
sources directly, so those claims are now **package-source-backed**. A future
re-run without network reverts them to docstring-anchored. See "Review verdicts
(2026-07-09)".

## What an MLIP IS in this software

An MLIP is a **representation of the opaque `Potential` node**: a parameterized
Born-Oppenheimer PES fit to DFT. Every wrapper subclasses `MLIPModel`
(`base.py:25`) and exposes one physics-relevant method:

```
wrapper = load_wrapper(model_type, model_name, device)   # loader.py:33-52
calc    = wrapper.create_calculator()                    # -> ase Calculator
```

From that **single ASE calculator** the whole map is fed:

- `atoms.get_potential_energy()` -> **TotalEnergy**, eV per cell (`base.py:635`)
- `atoms.get_forces()`           -> **Forces**, eV/A (`base.py:636`)
- `atoms.get_stress()`           -> **Stress**, eV/A^3 Voigt-6 (`base.py:642`)

The `mat-*` physics skills never touch a raw calculator directly for the derived
quantities: they hand the ASE calculator to a **matcalc** driver
(`ElasticityCalc`, `EOSCalc`, `PhononCalc`, `Phonon3Calc`, `RelaxCalc`,
`CustomMDCalc`/`PropCalc`) which post-processes the same PES into the
`ElasticConstants`, `BulkModulus`, EOS, phonon and MD quantities already
catalogued in `pymatgen-atomistic-skills.json`. So on the map:

> **MLIP = source realization of `Potential` -> {TotalEnergy, Forces, Stress}**;
> everything else (pymatgen + matcalc) consumes these three.

The call pattern is identical across skills: `load_wrapper(args.model_type,
args.model_name)` then `wrapper.create_calculator()` then into a matcalc
`PropCalc`. Verified in mat-elasticity, mat-equation-of-state, mat-phonon,
mat-lattice-thermal-conductivity, mat-solid-free-energy, mat-sample-pes-by-md.
The MCP-tool skills (mat-surface-energy, mat-stability, mat-defect-energy,
mat-melting-point, mat-diffusion-analysis) reach the same wrappers through the
`relax_structure` / `run_md` MCP tools. `mat-lammps-md` is the one exception: it
compiles the checkpoint into a LAMMPS pair style and runs a LAMMPS binary, a
second engine for the same PES. `mat-elemental-energies` uses no MLIP (a
precomputed reference library).

## Per-code E / F / S unit findings

All three return **ASE units**, standardized project-wide (`base.py:643-644`,
explicit comment "we standardize to eV/A^3 across the project"):

| Quantity | Unit | ASE API | Notes |
|---|---|---|---|
| TotalEnergy | **eV per cell** (eV/atom in stability/benchmark) | `get_potential_energy()` | absolute zero is model+functional specific |
| Forces | **eV/A** | `get_forces()` | conservative (autograd) vs direct-head |
| Stress | **eV/A^3**, Voigt-6 | `get_stress()` | matgl forced to eV/A3 (see below) |

Unlike the pymatgen elasticity path (which stores eV/A^3 then multiplies by
`160.2176634` for GPa), the **raw calculator** E/F/S are already in ASE eV units.
`mat-elasticity` applies the `160.2176634` factor only after matcalc returns the
elastic tensor in eV/A^3 (`calculate_elasticity.py:33,86-88`).

The clean cross-check is the benchmark's stress conversion: to compare against
VASP labels it multiplies the target stress by **`-1/1602.1766208`**
(`ml-mlip-benchmark/scripts/run_benchmark.py:139`), i.e. **kbar -> eV/A^3 with a
sign flip** (VASP stress carries the opposite sign). Energy metrics there are
**per atom** (`/num_atoms`, `run_benchmark.py:119`), forces eV/A, confirming the
table independently.

**Benchmark-factor finding (2026-07-09).** `1602.1766208` is not an 8th-digit
error. It is exactly `e(CODATA-2014) * 1e22` (electron charge
`1.6021766208e-19 C`), i.e. `1 eV/A^3 = 1602.1766208 kbar` in the CODATA-2014
constant generation - and that is the **correct** generation here, because the
predictions are compared in ASE `eV/A^3` and **ASE 3.26.0's own `units.GPa` still
uses CODATA-2014** (`units._e = 1.6021766208e-19`), so `ase.units.GPa/10 ==
1/1602.1766208` exactly. The pymatgen-scan constant `160.21766339999996` is a
**different** (CODATA-2018 / scipy) generation. Note an in-repo mismatch:
`mat-elasticity` uses `160.2176634` (CODATA-2018, `calculate_elasticity.py:33`)
while the benchmark uses `160.21766208` (CODATA-2014). The two skills disagree in
the 8th digit (~1e-8 relative), physically negligible but a real
constant-generation provenance mismatch to record, not a bug in either.

## Model-provenance scheme recommended

The paper's `mat-elasticity` instances (and `mat-diffusion-analysis`) credit only
the **skill** in `docs/data/codes.json` today. They should also credit the
**model**, as a representation of `Potential`. The model identity is a 4-field
tuple that the code already serializes into `md_inputs.json`
(`base.py:719-745`):

1. **model_type** in `{mace, matgl, fairchem}` (the `--model_type` CLI arg /
   `load_wrapper` first arg, `loader.py:23-44`).
2. **model_name**, the canonical checkpoint id after alias resolution, e.g.
   `MACE-MH-1`, `M3GNet-PES-MatPES-PBE-2025.2`, `CHGNet-PES-MatPES-PBE-2025.2.10`,
   `uma-s-1p2`.
3. **head / task**: MACE head (`omat_pbe` default for MH models,
   `mace_wrapper.py:203-212`); matgl none (single-task PES, functional in the
   name); fairchem `task_name` in `{omat, omol, oc22}` (`omat` = materials,
   `fairchem_wrapper.py:237-241`).
4. **is_fine_tuned** (`base.py:321`, `matgl_wrapper.py:265`,
   `fairchem_wrapper.py:201`): foundation checkpoint vs fine-tuned.

**Recommendation:** add a `codes.json` entry per `model_type` (mace / matgl /
fairchem) mapping `Potential` (api `wrapper.create_calculator()`), `TotalEnergy`
(eV), `Forces` (eV/A), `Stress` (eV/A^3) - mirroring the existing `ase`
`Potential` entry (`ase.Atoms.calc`) - and carry the `(model_name, head/task,
is_fine_tuned)` tuple as **labels on the Potential-representation node** so two
instances from different checkpoints do not false-merge. Also record two schemes:
`force_type` in `{conservative, direct}` and the stress order/sign.

Defaults (read the actual call, do not assume): **wrapper class defaults** differ
from **MCP-tool defaults**.

| model_type | wrapper default | MCP-tool default |
|---|---|---|
| mace | `MACE` -> MACE-MH-1, head `omat_pbe` | `MACE-OMAT-0-small` (`mace_server.py:40`) |
| matgl | `M3GNet` -> M3GNet-PES-MatPES-PBE-2025.2 | `CHGNet-PES-MatPES-PBE-2025.2.10` (`matgl_server.py:43`) |
| fairchem | class `EquiformerV2`, task resolves to `omat` | `uma-s-1p2` (`fairchem_server.py:48`) |

## Entry counts by status (8 entries)

- **already-mapped: 4** - mlip-potential-representation (`Potential`),
  mlip-total-energy (`TotalEnergy`), mlip-forces (`Forces`), mlip-stress
  (`Stress`). These ground 4 existing nodes and are the source tier the whole
  pymatgen/matcalc scan sits on.
- **new-node-candidate: 1** - committee-uncertainty (proposed
  `energy_uncertainty` / `force_uncertainty`, meV/atom and meV/A; MACE-only,
  `calc.results['energy_var'|'forces_var']`).
- **unclaimed-output: 1** - chgnet-magmoms (CHGNet's signature per-site magnetic
  moments, mu_B): present in the checkpoint, **never consumed** as an MLIP output
  in AtomisticSkills.
- **representation-only: 2** - mlip-benchmark-metrics (MAE/RMSE vs DFT) and
  atomic-features-descriptors (learned embeddings). Diagnostics on the Potential
  representation, not physics-DAG nodes.

## Unit / provenance traps

1. **Stress eV/A^3 vs GPa vs kbar.** Raw MLIP stress is eV/A^3. matgl's
   `PESCalculator` native default is **GPa** (verified `ase.py:173`) and
   `use_voigt` defaults **False** (returns a 3x3, not a 6-vector); the wrapper
   overrides `stress_unit="eV/A3"` (`matgl_wrapper.py:129`) but not `use_voigt` -
   harmless because every consumer goes through `get_stress()`, which reduces the
   3x3 to ASE Voigt-6. A consumer that builds `PESCalculator` without that kwarg
   is off by 160x. Benchmark kbar conversion `-1/1602.1766208` includes the
   **sign flip** (`run_benchmark.py:139`); the constant is CODATA-2014 = ASE's own
   `units.GPa` (see benchmark-factor finding above), NOT an error.
2. **Stress Voigt order.** ASE `get_stress` is `(xx, yy, zz, yz, xz, xy)`;
   LAMMPS `stress/atom` is `(xx, yy, zz, xy, xz, yz)`; pymatgen `Tensor.voigt`
   uses reverse map `[[0,5,4],[5,1,3],[4,3,2]]`. Three packings, one tensor.
3. **Energy zero is model+functional specific.** Raw energy is eV/cell;
   stability/benchmark use eV/atom. Absolute zero depends on the functional (PBE
   vs r2SCAN vs OMat) and the per-element references (fairchem `atom_refs`,
   `fairchem_wrapper.py:652-673`). Cross-model / cross-functional agreement must
   be on **relative** energies only.
4. **Forces conservative vs direct.** MACE, matgl PES, UMA are conservative
   (forces = autograd of energy). fairchem `esen-*-direct` checkpoints predict
   forces from a separate head (`fairchem_wrapper.py:51,61`) - not exactly
   `-dE/dr`, so energy is not conserved in NVE. A physics/gauge trap for MD (and
   for any HeatCurrent / Green-Kubo built on the trajectory), not a unit trap.
5. **MACE head is load-bearing.** MH-0/MH-1 require a head; default `omat_pbe`.
   The head picks the training-data domain and functional - a required provenance
   field.
6. **Default model differs wrapper vs MCP tool** (table above).
7. **matcalc is the true producer** of ElasticConstants/EOS/phonon. The wrapper
   only supplies `create_calculator()`; provenance of those nodes must record
   BOTH the matcalc driver AND the MLIP checkpoint.

## Open questions (full list in JSON `open_questions`)

1. RESOLVED 2026-07-09: agent envs still not installed, but the four wheels were
   pip-downloaded and read. Units, ASE Voigt order/sign, MACE `energy_var` /
   `forces_var` keys (present when `num_models>1`), and the CHGNet magmom head are
   now source-verified. See "Review verdicts".
2. Provenance placement: `(model_type, model_name, head/task, is_fine_tuned)` as
   labels on the Potential-representation node vs separate code entries. The
   mat-elasticity instance credits only the skill today; the encode stage must
   decide where the model credit lives.
3. CHGNet magmoms vs charges: RESOLVED 2026-07-09. The matgl wrapper flags CHGNet
   capability as `'charges'` (`matgl_wrapper.py:288`), but CHGNet's extra head is
   **magnetic moments** (mu_B) - CONFIRMED against matgl-4.0.3 (`_chgnet.py:437`
   `sitewise_readout -> g.magmom`; `ext/ase.py:281` `results['magmoms']`) and
   chgnet-0.4.2 (`model.py:574` "in Bohr"). The `'charges'` key is a genuine
   mislabel. Either way it is an unclaimed output (no AtomisticSkills consumer of
   the live MLIP magmom).
4. `force_type` `{conservative, direct}` scheme on the Potential representation
   (fairchem ships both; it affects MD energy conservation and thus the
   Trajectory gauge).
5. matcalc-on-MLIP as the real producer of the downstream nodes: record both the
   driver and the checkpoint.
6. MLIP -> LAMMPS export (`mat-lammps-md`) is a **second realization** of the
   same PES (ASE calculator vs LAMMPS pair style). The LAMMPS `Potential` node
   (`codes.json` lammps `pair_style`) and this MLIP node are the same physics via
   two engines - a cross-engine EXPECTED_AGREE candidate.

## Review verdicts (2026-07-09)

Adversarial deep review of commit `0e09b72`'s MLIP catalog. The previous scan
could not import any of the three packages, so every unit claim was
usage/docstring-anchored. This review **pip-downloaded all four relevant wheels**
(`/Users/juicy/miniconda3/bin/pip download --no-deps`: `mace_torch-0.3.16`,
`matgl-4.0.3`, `fairchem_core-2.21.0`, `chgnet-0.4.2`) into `/tmp/mlipsrc`,
unzipped them, and read the calculator implementations directly:
`mace/calculators/mace.py`, `matgl/ext/ase.py` + `matgl/apps/pes.py` +
`matgl/models/_chgnet.py`, `fairchem/core/calculate/ase_calculator.py`,
`chgnet/model/{model,dynamics}.py`. Every number was recomputed against CODATA
generations and against ASE 3.26.0's own `units`. The three AtomisticSkills
wrappers and the benchmark/committee scripts were opened line by line.

### Benchmark-factor finding (the headline)

The prompt hypothesized that the code's `1602.1766208` is "subtly WRONG in the
8th digit" vs `1602.1766339999996`. **That hypothesis is FALSE.** `1602.1766208`
is `e(CODATA-2014) * 1e22` and is **exactly** ASE 3.26.0's own kbar-per-eV/A^3
(`ase.units.GPa/10 == 1/1602.1766208`, `units._e = 1.6021766208e-19`). Because
the benchmark compares predictions in **ASE `eV/A^3`**, CODATA-2014 is the
**correct** generation - matching the engine that produced the numbers. The
`160.21766339999996` from the pymatgen scan is a different (CODATA-2018 / scipy)
generation used by pymatgen and by `mat-elasticity` (`160.2176634`,
`calculate_elasticity.py:33`). The only real finding is a **skill-to-skill
constant-generation mismatch inside the repo** (benchmark CODATA-2014 vs
elasticity CODATA-2018, ~1e-8 relative), physically negligible and now recorded
in `canonical_units_note` and the stress entry.

### Corrections that changed the record (not typos)

- **chgnet-magmoms: CORRECTED (mislabel confirmed).** The scanner's suspicion is
  upheld against source. matgl-4.0.3 CHGNet has a `sitewise_readout` producing
  `g.magmom` (`_chgnet.py:255-256,437`), surfaced as `results['magmoms']`
  (`ext/ase.py:281`) under `Potential.calc_magmom`; `results['charges']`
  (`ext/ase.py:286`) is a **separate, mutually-exclusive** `calc_charge` path
  (`apps/pes.py:360-368`). chgnet-0.4.2 documents the head as "magnetic moments of
  sites ... in Bohr" (`model.py:574`). So the wrapper's
  `get_model_capabilities()['charges']=True` for CHGNet
  (`matgl_wrapper.py:288`) is a **genuine semantic mislabel**: the extra head is
  magnetic moments (mu_B), not charges. Units and the mislabel are now
  source-backed in the JSON entry and open question 3.
- **mlip-stress: CORRECTED (added a real nuance) + benchmark factor.** matgl's
  `PESCalculator` `use_voigt` defaults **False** (`ase.py:175`), so the calculator
  writes a **full 3x3** stress into `results`, not a Voigt-6; the wrapper only
  overrides `stress_unit`, not `use_voigt`. This is **harmless in the
  AtomisticSkills path** because every consumer goes through
  `ase.Atoms.get_stress()`, which auto-reduces a 3x3 calc result to ASE Voigt-6
  `(xx,yy,zz,yz,xz,xy)` (empirically verified with ASE 3.26.0). A consumer reading
  `calc.results['stress']` off the matgl calculator directly would get a 3x3.
  Added; the benchmark-factor framing ("EXACT ... = 160.2176634 GPa = 1602.1766208
  kbar") was rewritten to the CODATA finding above.
- **Sign story: CONFIRMED (no flip at the matgl/ASE boundary).** matgl computes
  `stress = (1/V) dE/deps` = tensile-positive, documented "compressive-negative"
  (`apps/pes.py:53,349-355`) = the ASE convention. MACE and fairchem also emit
  tensile-positive `full_3x3_to_voigt_6_stress` (`mace.py:726`,
  `ase_calculator.py:254`). The benchmark's `-1` is purely the VASP `sigma = -stress`
  sign, as the scanner said.

### Per-entry verdicts

- **mlip-potential-representation: CONFIRMED.** Wrapper `create_calculator()`
  dispatch, loader, base static path all verified; package-source anchors added.
- **mlip-total-energy: CONFIRMED.** `get_potential_energy()` -> eV/cell
  (`base.py:635`); per-atom in benchmark/stability (`/num_atoms`). Model+functional
  reference caveat holds (fairchem `atom_refs` per task, verified in
  `ase_calculator.py` task property heads).
- **mlip-forces: CONFIRMED.** `get_forces()` -> eV/A. Conservative (MACE autograd,
  matgl `apps/pes.py:314-334` grads, UMA) vs **direct** (fairchem `esen-*-direct`)
  is encoded in the checkpoint name / `MODEL_METADATA` and returned by whatever
  head the predict_unit carries (`ase_calculator.py:249-251`). Force_type scheme
  worthwhile.
- **mlip-stress: CORRECTED** (use_voigt 3x3 nuance + benchmark factor; see above).
  eV/A^3, ASE Voigt order and tensile-positive sign both source-verified. Direct
  match to `Stress`.
- **chgnet-magmoms: CORRECTED** (mislabel confirmed, units mu_B source-backed; see
  above). Stays `unclaimed-output` - no AtomisticSkills script reads the live
  magmom.
- **committee-uncertainty: CONFIRMED.** `mace.py:704-717` writes `<key>_comm` and
  `<key>_var` for `key in {energy,forces,stress,dipole}` when `num_models>1`
  (`mace.py:224`), so `energy_var` AND `forces_var` both exist; the script reads
  exactly those (`run_committee_inference.py:119-120`). Variance is
  `torch.var(unbiased=False)`. Upstream caveat noted: `mace.py:716` scales
  variance by `unit_conv` linearly (not squared) - harmless for the default eV
  models (`unit_conv=1.0`). Stays `new-node-candidate`, MACE-only.
- **mlip-benchmark-metrics: CONFIRMED.** eV/atom, eV/A, eV/A^3 native; meV
  reporting; the `to_voigt` at `run_benchmark.py:143-149` independently confirms
  ASE Voigt order. Stays `representation-only`.
- **atomic-features-descriptors: CONFIRMED.** MACE
  `get_descriptors(invariants_only=True)` exists (`mace.py:792`); matgl inner
  `feature_dict` path; fairchem placeholder (`predict_atomic_features` returns
  empty). Stays `representation-only`.

No entries were KILLED. No anchor failed to support its claim; JSON `source` line
numbers occasionally lag the live wrapper by a few lines but every cited symbol
exists. Line refs to `run_benchmark.py` were corrected (`:53-55` -> `:138-139` for
the conversion; the flag help is at `:52-56`).

### UNVERIFIED

None remaining. The four packages were downloaded and read; the base miniconda env
still lacks them, so a network-less re-run reverts these to docstring-anchored.

### Decisions for the orchestrator (not for the reviewer)

1. **Provenance labels vs code entries.** Carry `(model_type, model_name,
   head/task, is_fine_tuned)` as **labels on the Potential-representation node**
   (recommended, so distinct checkpoints don't false-merge) vs minting separate
   `codes.json` entries per model_type. The paper's `mat-elasticity` instance
   credits only the skill today; the model credit must land somewhere.
2. **Committee-uncertainty node worthiness.** `energy_uncertainty` /
   `force_uncertainty` (meV/atom, meV/A) is a genuine, source-verified MACE-only
   diagnostic on the Potential representation. Worth a diagnostic node attached to
   Potential provenance? (Distinct from the MAE benchmark metrics.) Review leans:
   yes, but low urgency (one skill).
3. **Cross-engine EXPECTED_AGREE candidate.** `mat-lammps-md` compiles the same
   checkpoint into a LAMMPS `pair_style`; the LAMMPS `Potential` node and this MLIP
   `Potential` node are the **same PES via two engines**. Strongest EXPECTED_AGREE
   candidate on E/F/S. Caveat: the two engines carry different eV/A^3<->GPa
   constant generations (CODATA-2014 ASE vs whatever LAMMPS unit-real uses) and
   different Voigt orders (ASE `(xx,yy,zz,yz,xz,xy)` vs LAMMPS
   `(xx,yy,zz,xy,xz,yz)`) - the agreement check must normalize order and tolerate
   the ~1e-8 constant difference.
4. **force_type `{conservative, direct}` scheme.** fairchem ships both; it governs
   energy conservation in NVE and therefore the Trajectory / HeatCurrent gauge.
   Encode as a scheme on the Potential representation.
5. **matgl `charges` capability key.** If the map ever surfaces the CHGNet extra
   head, the wrapper key should be renamed to `'magmoms'` and the output mapped to
   `magnetic_moment` (mu_B), not charge.
