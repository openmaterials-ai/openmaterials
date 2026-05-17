# Phase 1 consolidation — design

**Date**: 2026-05-13
**Scope**: bring `omai.thermal_transport` (the BTE / Wigner / QHGK chain — phase 1 of the project's map of materials science) to a verified, documented, pushed state before phase 2 (MD-based κ paths via LAMMPS / ASE / GPUMD) begins.

## Why now

Between commit `e564511` and the current tree, the operator DAG has grown from 19 nodes / 18 edges to **38 / 38** (NAC: BareDM + BornCharges + DielectricTensor + apply_nac_correction; harmonic thermo: HelmholtzFreeEnergy / Entropy / InternalEnergy + their molar contractions; linewidth channels: Anharmonic / Isotopic / Boundary / Total + sum_linewidths + IsotopeAbundances; κ branches: Wigner with populations/coherences sub-fields + QHGK; CumulativeKappa[wrt=omega|mfp]). These additions haven't been audited end-to-end — adapter coverage, doc, dag.html layout, cross-code verification, and the unpushed-commit queue have all drifted.

Phase 2 introduces MD-based κ as a peer of BTE, which will *cross-validate* BTE κ values. The BTE side needs to be visibly solid first; otherwise phase 2's claims compound on unaudited foundations.

## The spine

`experiments/silicon_tersoff/spec_demo.py` is the worked example that drives the audit. Every operator branch added since `e564511` gets a new section there: operator-layer prediction → adapter values → `compare()` verdict. Stable sections graduate into `tests/` (matching the pattern of `tests/test_shengbte_real_data.py`).

Examples come from upstream repos where they exist (kaldo / phonopy / phono3py / shengbte all ship Si examples); we extend the existing `run_*.py` scripts in `experiments/silicon_tersoff/` to emit the new diagnostic arrays.

## Steps

Numbered in dependency order. One commit per logical step (or grouped where natural).

1. **Baseline check** (~5 min) — confirm `pytest tests/ -q` is green at 38/38; confirm `validate_dag` returns `[]`. Already done at design time (NODES=38, EDGES=38, validate_dag errors=0); will re-run tests in execution.

2. **Adapter-coverage audit** (~1–2 hours, the substantive step) — walk through the recent operator additions and, for each, decide per code: produced or not? If produced, write the `StateAdapterSpec`; if not, leave absent (no placeholder). Use the "grep before classifying out-of-scope" rule. Touches `omai/thermal_transport/representation/{kaldo,phono3py,phonopy,shengbte}.py`.

3. **Operator-layer smoke tests** (~30 min) — extend `tests/test_operator.py` with input/output/convention checks for every edge added since `e564511`, mirroring the pattern used for `compute_dos` / `compute_gruneisen` / `compute_phase_space_3phonon`.

4. **Substrate doc reality-check** — update `docs/operator_representation_substrate.tex` node/edge counts (19/18 → 38/38), add the new nodes/edges to the bullet lists, mention the new algorithmic conventions.

5. **Two-tier-validation paragraph** — one paragraph added to substrate doc Section 6 (Lean-compatibility disciplines) or Section 4 (Formal definitions, after the DAG extension rules):
   > Validation runs at two layers. Declarations are checked at module load (`validate_dag` on `NODES` / `EDGES`). Cross-code data is checked at comparison time (`compare_operators` / `compare_representations` on `StateAdapterSpec` pairs and `Representation` pairs). Mismatches at the declaration layer are caught before any code runs; mismatches at the data layer are caught at the operator↔representation boundary.

   (The other two AEP-borrow candidates — "hallucination is an engineering problem" thesis and "generative topology" naming — were considered and dropped on merit: the thesis risks overclaiming for where we are; the rename adds vocabulary without substance.)

6. **Regenerate `docs/dag.html`** and eyeball — the visualizer may need a small layout tweak to handle the extra rows / sibling clusters; fix if so.

7. **Cross-code Si verification** (highest-value validation) — extend `spec_demo.py` with sections for the new branches. Each section produces an `EXPECTED_AGREE` / `EXPECTED_DISAGREE` / `NOT_COMPARABLE` verdict. Branches:
   - **κ_Wigner** — kaldo `Conductivity(method='wigner')`; populations + coherences sub-fields. Extend `run_kaldo.py` to emit `kappa_wigner_*.npy`.
   - **κ_QHGK** — kaldo `Conductivity(method='qhgk')`. Extend `run_kaldo.py`.
   - **CumulativeKappa[wrt=omega]** and **[wrt=mfp]** — shengbte has `BTE.cumulative_kappa*` arrays; kaldo produces them too. Sanity-check shapes match.
   - **Harmonic thermodynamics** (F, S, E) — phonopy emits all four from `run_thermal_properties`. Extend `run_phonopy.py` to dump.
   - **Linewidth channels** — ShengBTE has `BTE.w_isotopic`, `BTE.w_boundary`. Confirm `sum_linewidths` reconstructs `BTE.w_anharmonic + w_isotopic + w_boundary = w_total`.

   A section is "stable" — and graduates into `tests/test_silicon_consolidation.py` (new) or extends `test_shengbte_real_data.py` — when it produces the same `EXPECTED_*` verdict on two consecutive runs against committed input data, with no `UNEXPECTED_*` results outside an explicit allow-list.

8. **Push** all unpushed commits to `origin/main`.

9. **Followups housekeeping** — `docs/followups.md` reflects what landed; remaining open items get sharpened (NaCl/MgO polar verification for NAC; phase 2 plan; Lean projection; FC3 0.1 factor; second domain).

## Out of scope

- Phase 2 (LAMMPS+ASE adapter, GPUMD, MD-based κ branches).
- Polar/NAC numerical verification — Si isn't polar; punt to a separate `experiments/nacl_polar/` worked example in followups.
- Adding new operator nodes/edges. Recent additions are what we're consolidating, not extending.
- Refactoring the visualizer beyond what's needed for the new nodes to lay out.
- Lean projection of the operator layer (deferred per substrate Section 8.2).

## Success criteria

- `pytest tests/ -q` green; expect ≥ 100 tests after step 3 (was 93).
- Every recent operator addition has either a `StateAdapterSpec` from at least one code, or an explicit out-of-scope note in the relevant adapter docstring.
- `substrate.tex` node/edge counts match reality (38/38); bullet lists cover all 19 new nodes/edges.
- `docs/dag.html` regenerates and lays out cleanly.
- `spec_demo.py` has sections for κ_Wigner, κ_QHGK, cumulative κ (both axes), harmonic thermo F/S/E, linewidth-channel reconstruction.
- All commits pushed to `origin/main`.
- `followups.md` updated.

## Order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

Checkpoints between each step: short status report, user OK to proceed.
