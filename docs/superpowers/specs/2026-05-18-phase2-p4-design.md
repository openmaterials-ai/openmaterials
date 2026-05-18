# Phase 2 P4 — Cross-paradigm κ worked example (LAMMPS Green-Kubo on Si-Tersoff)

**Date**: 2026-05-18
**Parent**: `docs/superpowers/specs/2026-05-17-phase2-md-design.md`
**Sibling phases**: P1 (LAMMPS+ASE Potential anchor), P2 (MD primitives), P3 (MD-based κ paths). With P3 just landed, all three MD κ contractions exist as typed states + edges + adapter specs — but no end-to-end empirical verification has been run. P4 closes that loop with one MD path: **LAMMPS Green-Kubo on Si-Tersoff**.

## Why

The parent phase-2 spec's success criterion for P3 was:

> `tests/test_silicon_consolidation.py` extended with κ_GK / κ_NEMD / κ_HNEMD verification sections (each may skip if the respective MD run hasn't produced data); the three values agree with κ_LBTE within MD's ~20–30% noise band.

P3 shipped the operator-layer machinery; P4 wires the first MD κ pathway to the Si-Tersoff spec_demo so the framework demonstrates cross-paradigm agreement between BTE and equilibrium MD. NEMD / HNEMD verification land later (NEMD requires LAMMPS NEMD orchestration; HNEMD requires GPUMD + a GPU host) — out of scope this pass.

## Scope

1. **LAMMPS Green-Kubo driver** at `experiments/silicon_tersoff/run_lammps_gk.py`:
   - Generates a LAMMPS input script (`in.silicon_gk`) for an NVT-then-NVE Green-Kubo run on a Si-Tersoff supercell at 300 K.
   - If `lmp` (or `lmp_serial` / `lmp_mpi`) is on `PATH`, runs it; otherwise prints the input script and exits with the "data not produced" notice.
   - Parses the `J0Jt.dat` correlation file written by `fix ave/correlate` and computes κ_αβ = V/(k_B T²) · numpy.trapz(Jcorr, dt).
   - Writes `out/kappa_lammps_gk.npy` (3×3 tensor) for downstream consumers.

2. **Cross-paradigm κ comparison section in `experiments/silicon_tersoff/spec_demo.py`**:
   - New top-level section "Cross-paradigm κ audit (phase 2 P4)" that:
     - Loads κ_LBTE (existing), κ_Wigner (existing), κ_QHGK (existing) from the Phase-1 fixtures.
     - Loads κ_GK from `out/kappa_lammps_gk.npy` *if it exists*.
     - Renders the four κ values side by side and asserts pairwise agreement within an MD-noise band (default 30%).
   - The κ-GK section is gracefully skipped if the .npy file is absent, with a one-line "run `python run_lammps_gk.py` to produce it" note.

3. **Smoke test in `tests/test_silicon_consolidation.py`**:
   - `test_kappa_green_kubo_agrees_with_lbte()`: loads `experiments/silicon_tersoff/out/kappa_lammps_gk.npy` if present; otherwise `pytest.skip`. When loaded, asserts diagonal κ_xx is within 30% of the existing κ_LBTE reference.
   - Same skip-on-missing pattern as the four existing diagnostic-`.npy` tests.

4. **Documentation**:
   - Note in `experiments/silicon_tersoff/README.md` (or equivalent) that the Green-Kubo route is the first MD κ exercised end-to-end.
   - Substrate doc (`docs/operator_representation_substrate.tex`) gets one paragraph in §"Worked example: Silicon" describing the cross-paradigm agreement target.

## Architectural decisions

- **Driver mirrors the existing pattern**. `run_kaldo.py`, `run_phono3py.py`, `run_phonopy.py` all sit alongside the spec; `run_lammps_gk.py` is the next sibling. Outputs land in `experiments/silicon_tersoff/out/`.
- **No new adapter logic needed**. The LAMMPS adapter specs in P2/P3 declare *what* each piece is; the driver just exercises them. The driver references the operator `contract_kappa_green_kubo` edge and the LAMMPS adapter's `LAMMPS_CONTRACT_KAPPA_GREEN_KUBO` spec in its docstring/notes, so the "this is what we're computing" trail is explicit.
- **Skip-on-missing-binary, not skip-on-failure**. If LAMMPS errors, that's a real failure to surface — don't swallow. Only skip if LAMMPS isn't installed.
- **One MD codepath, not all three**. NEMD requires a different LAMMPS input script (Müller-Plathe `fix thermal/conductivity` + binned T(z)) — and a much longer run. HNEMD needs GPUMD. P4 scopes to Green-Kubo only; the other two land in P5 / P6.

## Sympy-formula trace

The driver's docstring + the spec_demo section both spell out:

```
κ^{αβ}_GK = V/(k_B T²) · ∫₀^{τ_max} ⟨J^α(0) J^β(τ)⟩ dτ
```

and cite `contract_kappa_green_kubo` as the operator-layer edge. The trail from framework → adapter → driver → output `.npy` is:

  `contract_kappa_green_kubo`
  → `LAMMPS_CONTRACT_KAPPA_GREEN_KUBO` (spec)
  → `run_lammps_gk.py` (driver — generates in.silicon_gk + parses J0Jt.dat)
  → `out/kappa_lammps_gk.npy`
  → spec_demo's "Cross-paradigm κ audit" section
  → `test_kappa_green_kubo_agrees_with_lbte` (smoke test)

## Out of scope (this spec)

- **NEMD κ on Si-Tersoff** (Müller-Plathe via LAMMPS) — P5.
- **HNEMD κ on Si-Tersoff via GPUMD** — P6.
- **Quantum corrections** for classical-MD-κ vs quantum-BTE-κ comparison.
- **Convergence sweeps** (τ_max, n_lag, supercell size, ensemble repeats). The driver uses sensible defaults; rigour comes later.
- **Polar / NaCl** — separate spec.

## Success criteria

- `run_lammps_gk.py` runs to completion on a LAMMPS-equipped host and writes `out/kappa_lammps_gk.npy`.
- Without LAMMPS: the driver prints the input script and exits cleanly (no traceback).
- `spec_demo.py` runs to completion regardless of whether the .npy is present.
- `tests/test_silicon_consolidation.py` adds one test that skips when the .npy is absent; passes when present and the κ_GK / κ_LBTE ratio is in [0.7, 1.3].
- Total test count stays green (skips counted separately).
- Substrate doc has the new paragraph; no count changes (no new states or edges).

## Order

1. Write the LAMMPS input script template + the driver `run_lammps_gk.py`.
2. Extend `spec_demo.py` with the Cross-paradigm κ audit section.
3. Add the skip-on-missing-`.npy` test to `test_silicon_consolidation.py`.
4. Substrate doc paragraph.
5. Single commit.
