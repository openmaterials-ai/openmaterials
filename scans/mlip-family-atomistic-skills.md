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

**Anchoring caveat.** None of `mace-torch`, `matgl`, or `fairchem-core` is
importable in the miniconda base env, and the per-agent conda envs are not
installed on this machine. Every unit (eV, eV/A, eV/A^3), the ASE Voigt stress
order, the MACE committee `calc.results` keys, and the CHGNet magmom head are
anchored to **AtomisticSkills wrapper usage + canonical package docstrings**, not
a read package source line. Flagged per entry and in the open questions.

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
(`ml-mlip-benchmark/scripts/run_benchmark.py:53-55`), i.e. **kbar -> eV/A^3 with a
sign flip** (1 eV/A^3 = 1602.1766208 kbar = 160.2176634 GPa; VASP stress carries
the opposite sign). Energy metrics there are **per atom** (`/num_atoms`,
`run_benchmark.py:119`), forces eV/A, confirming the table independently.

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
   `PESCalculator` native default is **GPa**; the wrapper overrides it with
   `stress_unit="eV/A3"` (`matgl_wrapper.py:129`) - a consumer that builds
   `PESCalculator` without that kwarg is off by 160x. Benchmark kbar conversion
   `-1/1602.1766208` includes the **sign flip** (`run_benchmark.py:53-55`).
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

1. Agent envs not installed: units, ASE Voigt stress order/sign, MACE committee
   `energy_var`/`forces_var` keys, and the CHGNet magmom head are anchored to
   usage + docstrings, not a read package line. A reviewer with an env should
   confirm each.
2. Provenance placement: `(model_type, model_name, head/task, is_fine_tuned)` as
   labels on the Potential-representation node vs separate code entries. The
   mat-elasticity instance credits only the skill today; the encode stage must
   decide where the model credit lives.
3. CHGNet magmoms vs charges: the matgl wrapper flags CHGNet capability as
   `'charges'` (`matgl_wrapper.py:288`) though CHGNet's documented extra head is
   **magnetic moments** (mu_B). Confirm the head semantics; either way it is an
   unclaimed output (no AtomisticSkills consumer of the live MLIP magmom).
4. `force_type` `{conservative, direct}` scheme on the Potential representation
   (fairchem ships both; it affects MD energy conservation and thus the
   Trajectory gauge).
5. matcalc-on-MLIP as the real producer of the downstream nodes: record both the
   driver and the checkpoint.
6. MLIP -> LAMMPS export (`mat-lammps-md`) is a **second realization** of the
   same PES (ASE calculator vs LAMMPS pair style). The LAMMPS `Potential` node
   (`codes.json` lammps `pair_style`) and this MLIP node are the same physics via
   two engines - a cross-engine EXPECTED_AGREE candidate.
