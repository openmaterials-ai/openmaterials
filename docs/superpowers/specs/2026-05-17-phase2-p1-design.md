# Phase 2 P1 — LAMMPS+ASE Potential anchor

**Date**: 2026-05-17
**Parent**: `docs/superpowers/specs/2026-05-17-phase2-md-design.md`
**Scope**: introduce three new adapters (`ase`, `lammps`, `gpumd`) and tie them into the `provide_potential` chain across the four existing BTE codes. P1 is deliberately narrow — just the Potential / force-source anchor. MD-output coverage (in `lammps` and `gpumd`) lands in P2 and P3.

## Why three new adapters

| Adapter | What it covers |
|---|---|
| **`ase`** | Generic ASE-calculator interface. The `Potential` is whatever Python object lives at `Atoms.calc` (LAMMPSlib, GPAW, KIMCalculator, ML-IP wrappers, …). Captures the *protocol*, not a specific backend. |
| **`lammps`** | LAMMPS-native: input scripts, `pair_style` declarations, log parsing, USER-PHONON outputs, native MD (NEMD / Green-Kubo) commands. In P1 only the Potential / pair_style side; the MD outputs are P2/P3 territory. |
| **`gpumd`** | GPUMD-native: NEP potential files, GPUMD's own input syntax (`run.in`), native HNEMD / Green-Kubo MD outputs. In P1 only the Potential / NEP side. |

The `ase` adapter is *the* anchor for cross-code agreement in P1: when kaldo, phono3py, phonopy, and shengbte all wire their force evaluations through the *same* ASE calculator object, the cross-code κ comparison's "but you used different forces" asterisk goes away.

The `lammps` and `gpumd` adapters get skeletons in P1 (`provide_potential` only, plus the basic state coverage required for a clean DAG visualisation) so P2 and P3 have somewhere to grow.

## What lands at the operator layer

**Nothing new.** P1 stays at the representation / adapter level. The operator layer already has `provide_potential` (nullary edge producing the opaque `Potential` Observable). The new adapters just declare *how* they realise that edge.

If the user-supplied design decision changes (Forces becomes a first-class operator state), it goes into a follow-up spec, not P1.

## Per-adapter scope (P1)

### `ase` adapter (new file)

- `omai/thermal_transport/representation/ase.py`
- One `OperationAdapterSpec` for `provide_potential` with `code_api={"potential": "ase.Atoms.calc"}` and notes covering the common ASE-calculator backends (LAMMPSlib, GPAW, KIMCalculator, MACE / OrbForceField / other ML-IPs).
- Possibly one `OperationAdapterSpec` for `compute_force_constants_2` and `compute_force_constants_3` if the FD-displacement loop is the same across all ASE-calculator users (kaldo / phono3py / phonopy all delegate to ASE-calculator force evaluations).

### `lammps` adapter (new file)

- `omai/thermal_transport/representation/lammps.py`
- One `OperationAdapterSpec` for `provide_potential` with `code_api={"potential": "LAMMPS pair_style command + coefficients"}`.
- Notes: distinguishes the LAMMPS-native path (using LAMMPS's own input script) from the LAMMPS-via-ASE path (covered by the `ase` adapter). Documents algorithmic_convention `potential_kind ∈ {tersoff, sw, eam, snap, …}` if the operator layer has that convention; otherwise leave a note.
- All other ops (force_constants, BTE solves, etc.): not in scope for P1.

### `gpumd` adapter (new file)

- `omai/thermal_transport/representation/gpumd.py`
- One `OperationAdapterSpec` for `provide_potential` with `code_api={"potential": "nep.txt or NEP/EAM/Tersoff potential file"}`.
- Notes: GPUMD's potentials are NEP (neuro-evolution potentials) by default; EAM/Tersoff/SW also supported.
- All other ops: not in scope for P1.

### Existing four adapter files (modifications)

For kaldo / phono3py / phonopy / shengbte, the existing `*_PROVIDE_POTENTIAL` `OperationAdapterSpec`s currently have notes like `"kaldo runs against an external calculator (LAMMPS, ASE, ML)."` These already mention ASE-style force sources; the change is to *tighten* the wording to point at the new `ase`/`lammps`/`gpumd` adapters as canonical descriptions of those sources.

Concretely: each of the four updates one or two lines in the existing `notes=` string. No new code.

## Cross-code Si-Tersoff verification

The phase-1 cross-code Si verification already runs kaldo / phono3py / phonopy / shengbte against LAMMPS-Tersoff via `ase.calculators.lammpslib.LAMMPSlib`. In P1 we add one new section to `experiments/silicon_tersoff/spec_demo.py` titled "Shared Potential audit":

- Discover every `provide_potential` `OperationAdapterSpec` across kaldo / phono3py / phonopy / shengbte.
- Verify (programmatically) that each one's notes string references either the `ase` or `lammps` adapter as the canonical Potential source.
- Print a summary of which adapter covers each code's force-evaluation path.

This isn't a numerical test — it's a discoverability check: anyone reading the cross-code Si κ comparison can trace the shared Potential through to the new `ase` adapter.

## Tests

- `tests/test_ase_adapter.py` (new): smoke tests that `ASE_PROVIDE_POTENTIAL` (and any FC ops added) is importable from the package and has the expected `adapter_name`, `code_api`, etc.
- Same for `tests/test_lammps_adapter.py` and `tests/test_gpumd_adapter.py`.
- The existing operator-DAG counts test (`test_node_count`, `test_edge_count`) stays untouched — P1 doesn't add operator states.

## Out of scope (this spec)

- **MD primitives** (Trajectory, HeatCurrent, VAF, MSD) — P2.
- **MD-based κ** (Green-Kubo, NEMD, HNEMD) — P3.
- **LAMMPS USER-PHONON** outputs (dispersion, DM from MD) — P3 or later.
- **`Forces` as a first-class operator state** — deferred (per locked-in design call).
- **A new `potential_kind` algorithmic convention** — if useful, add in a follow-up; not required for P1.

## Success criteria

- Three new adapter files exist with their `provide_potential` specs and (where appropriate) FC-ops specs.
- The `ase` adapter spec is the canonical reference cited from kaldo / phono3py / phonopy / shengbte adapter notes.
- `spec_demo.py` has the new "Shared Potential audit" section, and it reports all four BTE codes pointing at the `ase` adapter (or the `lammps`-native adapter, for runs that bypass ASE).
- pytest stays green; test count grows by the new smoke tests (probably +9 to +12).
- Substrate doc node/edge counts don't change (no operator-layer additions in P1).

## Order

Three commits, one per new adapter:
1. `ase` adapter (largest — most coverage)
2. `lammps` adapter (skeleton — Potential only)
3. `gpumd` adapter (skeleton — Potential only)

Then a fourth commit covering the four BTE-adapter note updates and the `spec_demo.py` audit section. Optionally a fifth commit for `docs/dag.html` regeneration (no operator-DAG changes; only the per-adapter coverage panel would change).
