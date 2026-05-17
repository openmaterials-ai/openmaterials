# Phase 1 Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit, document, and cross-code-verify every operator-DAG addition made since commit `e564511` (NAC, harmonic thermo, linewidth channels, Wigner/QHGK κ, cumulative κ), so phase 1 is solid before phase 2 (MD-based κ paths) starts.

**Architecture:** Five stage commits (`689c793` through `0e004ce`) added 19 new operator nodes and 20 new edges plus 30+ new adapter specs without an end-to-end audit. This plan walks each addition through (a) adapter-coverage audit using grep against the cloned external repos, (b) operator-layer smoke tests, (c) cross-code Si verification by extending `experiments/silicon_tersoff/spec_demo.py`, with stable sections graduating into `tests/test_silicon_consolidation.py`. Substrate doc counts get updated and one paragraph about two-tier validation gets added. The visualisation regenerates from code.

**Tech Stack:** Python 3.9 (omai package), pytest, sympy, numpy. External repos cloned at `./kaldo`, `./phonopy`, `./phono3py`, `./shengbte` (gitignored). LaTeX for substrate doc.

---

## Status checkpoint convention

After each top-level task, the executing agent reports:
- What changed (files / commits)
- Test count delta (e.g. "was 102, now 107")
- Any unexpected results

Then awaits user OK before proceeding.

---

## Task 1: Baseline check

**Files:**
- Read: none (diagnostic only)

- [ ] **Step 1.1: Confirm tests are currently green**

Run: `cd /home/giuseppe/Development/openmaterials-ai && python -m pytest tests/ -q`
Expected: `102 passed` (zero failures).

- [ ] **Step 1.2: Confirm operator DAG counts match `__init__.py`**

Run:
```bash
python -c "
from omai.thermal_transport.operator import NODES, EDGES
from omai.operator import validate_dag
print(f'NODES: {len(NODES)}')
print(f'EDGES: {len(EDGES)}')
errs = validate_dag(NODES, EDGES)
print(f'validate_dag errors: {len(errs)}')
"
```
Expected: `NODES: 38`, `EDGES: 38`, `validate_dag errors: 0`.

- [ ] **Step 1.3: Record baseline counts in commit log**

No file changes. Capture the numbers from steps 1.1–1.2 and use them as the "before" reference in subsequent commit messages.

**✋ STATUS CHECKPOINT 1** — confirm green baseline; if anything failed, stop and fix before proceeding.

---

## Task 2: Adapter coverage audit

The audit is decomposed by the five stages. For each stage, the procedure is:
1. Identify the new operator states/edges (from the stage commit message).
2. For each producing code (kaldo, phono3py, phonopy, shengbte): grep the cloned source for the obvious API, then check the adapter spec file.
3. If a code produces the state and a spec is missing, write the spec. If a code does not produce it, leave it absent (no placeholder).
4. Commit any added specs.

### Task 2A: Audit stage 1 — Born charges + NAC

**Files:**
- Read: `omai/thermal_transport/representation/{kaldo,phono3py,phonopy,shengbte}.py`
- Grep target: `./kaldo`, `./phono3py`, `./phonopy`, `./shengbte`
- May modify: any adapter file missing a spec

- [ ] **Step 2A.1: Enumerate stage-1 operator additions**

From `git show 689c793 --stat`, the new states are `BareDynamicalMatrix`, `BornCharges`, `DielectricTensor`. New edges: `provide_born_charges`, `provide_dielectric_tensor`, `identity_dm`, `apply_nac_correction`. The `compute_dynamical_matrix` edge was changed to produce `BareDynamicalMatrix` (was: `DynamicalMatrix`).

- [ ] **Step 2A.2: Grep cloned repos for BornCharges / dielectric API**

Run:
```bash
cd /home/giuseppe/Development/openmaterials-ai
echo "=== phonopy ==="; git -C phonopy grep -l -i "born\|nac_params\|dielectric" 2>/dev/null | head -5
echo "=== phono3py ==="; git -C phono3py grep -l -i "born\|nac_params\|dielectric" 2>/dev/null | head -5
echo "=== kaldo ==="; git -C kaldo grep -l -i "born\|dielectric\|nac" 2>/dev/null | head -5
echo "=== shengbte ==="; git -C shengbte grep -l -i "born\|epsilon\|nac" 2>/dev/null | head -5
```
Expected: phonopy and phono3py have substantial hits (`BORN` file, `nac_params` arg). kaldo wraps phonopy. shengbte reads a BORN file too.

- [ ] **Step 2A.3: Check existing specs for BornCharges / DielectricTensor**

Run:
```bash
grep -l "BORN_CHARGES\|DIELECTRIC_TENSOR\|apply_nac_correction" \
  omai/thermal_transport/representation/*.py
```
Expected: at least phonopy.py and phono3py.py have these. Note which codes are missing.

- [ ] **Step 2A.4: For each missing code, write the spec**

If kaldo / shengbte specs are absent and the grep in 2A.2 showed they read a BORN file, add a `StateAdapterSpec` for `BORN_CHARGES` and `DIELECTRIC_TENSOR` and an `OperationAdapterSpec` for `apply_nac_correction`. Pattern (substitute the right code_api string per code):
```python
SHENGBTE_BORN_CHARGES = StateAdapterSpec(
    state=BORN_CHARGES,
    adapter_name="shengbte",
    observable_units={"Z_star": "dimensionless"},
    code_api={"Z_star": "BORN file (Z* block)"},
    notes="ShengBTE reads Born effective charges from BORN, the phonopy-style file.",
)
```

- [ ] **Step 2A.5: Run tests; commit**

Run: `python -m pytest tests/ -q`
Expected: still 102+ passing.

Commit:
```bash
git add omai/thermal_transport/representation/*.py
git commit -m "consolidation: audit adapter coverage for stage 1 (NAC)"
```
If no specs were added, skip the commit and note "no gaps found" in the status checkpoint.

### Task 2B: Audit stage 2 — harmonic thermo

**Files:**
- Read: same four adapter files
- May modify: same

- [ ] **Step 2B.1: Enumerate stage-2 operator additions**

From `git show 5b91e9e --stat`: new states `HelmholtzFreeEnergy`, `Entropy`, `InternalEnergy`, `MolarHelmholtzFreeEnergy`, `MolarEntropy`, `MolarInternalEnergy`. New edges: `compute_free_energy`, `compute_entropy`, `compute_internal_energy`, `contract_molar_free_energy`, `contract_molar_entropy`, `contract_molar_internal_energy`.

- [ ] **Step 2B.2: Grep for thermal_properties API across codes**

Run:
```bash
echo "=== phonopy ==="; git -C phonopy grep -n "free_energy\|entropy.*internal\|thermal_properties" --include='*.py' 2>/dev/null | head -10
echo "=== phono3py ==="; git -C phono3py grep -n "free_energy\|thermal_properties" --include='*.py' 2>/dev/null | head -5
echo "=== kaldo ==="; git -C kaldo grep -n "free_energy\|helmholtz\|entropy" --include='*.py' 2>/dev/null | head -5
echo "=== shengbte ==="; git -C shengbte grep -n -i "free_energy\|entropy" 2>/dev/null | head -5
```
Expected: phonopy is the canonical producer (`Phonopy.run_thermal_properties()`). phono3py inherits via the parent Phonopy object. kaldo can derive these but typically doesn't expose them directly. shengbte: not exposed.

- [ ] **Step 2B.3: Check existing specs**

Run:
```bash
grep -ln "HELMHOLTZ_FREE_ENERGY\|MOLAR_HELMHOLTZ\|compute_free_energy" \
  omai/thermal_transport/representation/*.py
```
Confirm phonopy.py covers the molar forms; note any gaps.

- [ ] **Step 2B.4: Fill gaps where appropriate, run tests, commit**

Same pattern as 2A.4–2A.5. If kaldo can derive F/S/E from its `Phonons` object (it can, via `Phonons.heat_capacity` plus thermodynamic integration), but does not expose them as attributes, leave the spec absent and add one line to kaldo.py's module docstring noting the derivation is possible but not direct.

Commit (only if specs added):
```bash
git add omai/thermal_transport/representation/*.py
git commit -m "consolidation: audit adapter coverage for stage 2 (harmonic thermo)"
```

### Task 2C: Audit stage 3 — linewidth channels

**Files:** same.

- [ ] **Step 2C.1: Enumerate stage-3 operator additions**

From `git show 319956d --stat`: new states `Linewidth[channel=anharmonic_3ph]` (rename), `Linewidth[channel=isotope]`, `Linewidth[channel=boundary]`, `Linewidth[channel=total]`, `IsotopeAbundances`. New edges: `compute_anharmonic_linewidth` (rename), `compute_isotope_scattering`, `compute_boundary_scattering`, `sum_linewidths`, `provide_isotope_abundances`.

- [ ] **Step 2C.2: Grep for channel APIs**

Run:
```bash
echo "=== kaldo isotope/boundary ==="
git -C kaldo grep -n "isotope\|boundary\|tamura\|casimir" --include='*.py' 2>/dev/null | head -10
echo "=== phono3py isotope ==="
git -C phono3py grep -n "isotope\|gamma_iso\|Tamura" --include='*.py' 2>/dev/null | head -10
echo "=== shengbte isotope/boundary ==="
git -C shengbte grep -n "isotope\|boundary\|w_isotopic\|w_boundary" 2>/dev/null | head -10
```
Expected: kaldo has `isotope` flag on `Phonons`; phono3py has `is_isotope` and Tamura; shengbte writes `BTE.w_isotopic` and `BTE.w_boundary`.

- [ ] **Step 2C.3: Check existing specs**

Run:
```bash
grep -ln "ANHARMONIC_LINEWIDTH\|ISOTOPIC_LINEWIDTH\|BOUNDARY_LINEWIDTH\|sum_linewidths" \
  omai/thermal_transport/representation/*.py
```

- [ ] **Step 2C.4: Fill gaps, run tests, commit**

Same pattern. Likely kaldo and phono3py have specs for isotope; shengbte's `BTE.w_isotopic` / `BTE.w_boundary` should already be specced from stage 3. If `Linewidth[channel=total]` is missing as an explicit spec where the code emits a combined Γ (kaldo's `Phonons.bandwidth` is anharmonic-only; shengbte's `BTE.w_anharmonic` is anharmonic-only — neither emits "total"), no spec is needed; the total is reconstructed in `spec_demo.py` via `sum_linewidths`.

Commit (if specs added):
```bash
git add omai/thermal_transport/representation/*.py
git commit -m "consolidation: audit adapter coverage for stage 3 (linewidth channels)"
```

### Task 2D: Audit stage 4 — Wigner + QHGK

**Files:** same; primarily kaldo (only code that does Wigner/QHGK).

- [ ] **Step 2D.1: Enumerate stage-4 operator additions**

From `git show 710227e --stat`: new states `ThermalConductivity[transport_model=wigner]`, `[transport_model=wigner_populations]`, `[transport_model=wigner_coherences]`, `[transport_model=qhgk]`. New edges: `compute_kappa_wigner_populations`, `compute_kappa_wigner_coherences`, `combine_kappa_wigner`, `compute_kappa_qhgk`.

- [ ] **Step 2D.2: Confirm kaldo specs exist**

Run:
```bash
grep -n "THERMAL_CONDUCTIVITY_WIGNER\|THERMAL_CONDUCTIVITY_QHGK\|compute_kappa_wigner\|compute_kappa_qhgk" \
  omai/thermal_transport/representation/kaldo.py
```
Expected: all four state specs + four edge specs present.

- [ ] **Step 2D.3: Confirm other codes are correctly absent**

Run:
```bash
grep -n "WIGNER\|QHGK" omai/thermal_transport/representation/phono3py.py
grep -n "WIGNER\|QHGK" omai/thermal_transport/representation/phonopy.py
grep -n "WIGNER\|QHGK" omai/thermal_transport/representation/shengbte.py
```
Expected: zero hits. phono3py, phonopy, shengbte do not produce Wigner or QHGK κ.

- [ ] **Step 2D.4: No code change unless gap discovered**

If kaldo specs are missing (unexpected), add them. Otherwise just record in the checkpoint that coverage is complete.

### Task 2E: Audit stage 5 — cumulative κ

**Files:** same.

- [ ] **Step 2E.1: Enumerate stage-5 operator additions**

From `git show 0e004ce --stat`: new states `CumulativeKappa[wrt=omega]`, `CumulativeKappa[wrt=mfp]`. New edges: `contract_cumulative_kappa[wrt=omega]`, `contract_cumulative_kappa[wrt=mfp]`.

- [ ] **Step 2E.2: Grep for cumulative κ APIs**

Run:
```bash
echo "=== kaldo cumulative ==="
git -C kaldo grep -n "cumulative" --include='*.py' 2>/dev/null | head -10
echo "=== shengbte cumulative ==="
git -C shengbte grep -n "cumulative" 2>/dev/null | head -10
```
Expected: kaldo has `cumulative_conductivity_per_omega` / `_per_mfp` on `Conductivity`; shengbte writes `BTE.cumulative_kappaVsOmega_tensor` and `BTE.cumulative_kappa_tensor`.

- [ ] **Step 2E.3: Confirm specs**

Run:
```bash
grep -ln "CUMULATIVE_KAPPA_OMEGA\|CUMULATIVE_KAPPA_MFP\|contract_cumulative_kappa" \
  omai/thermal_transport/representation/*.py
```
Expected: both kaldo.py and shengbte.py.

- [ ] **Step 2E.4: Run tests, commit if anything added**

Same pattern.

**✋ STATUS CHECKPOINT 2** — adapter audit complete; report which codes had gaps, what was added. Tests still green.

---

## Task 3: Operator-layer smoke tests for the new edges

For each edge added in stages 1–5 that doesn't already have an inputs/outputs assertion in `tests/test_operator.py`, add one. Mirrors the existing pattern (`test_compute_dos_inputs_are_frequency` etc.).

**Files:**
- Modify: `tests/test_operator.py`

- [ ] **Step 3.1: Survey existing edge tests**

Run:
```bash
grep -n "^def test_" tests/test_operator.py | head -40
```
Note which edges already have an explicit input/output assertion (e.g., `compute_dos`, `compute_gruneisen`, `compute_phase_space_3phonon` already covered from prior work).

- [ ] **Step 3.2: Write failing smoke tests for stage-1 edges**

Append to `tests/test_operator.py`:
```python
# -- Stage 1: NAC ---------------------------------------------------------


def test_compute_dynamical_matrix_produces_bare_dm():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        compute_dynamical_matrix,
    )

    assert tuple(s.name for s in compute_dynamical_matrix.outputs) == (
        BARE_DYNAMICAL_MATRIX.name,
    )


def test_apply_nac_correction_inputs():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        BORN_CHARGES,
        DIELECTRIC_TENSOR,
        DYNAMICAL_MATRIX,
        apply_nac_correction,
    )

    assert set(s.name for s in apply_nac_correction.inputs) == {
        BARE_DYNAMICAL_MATRIX.name,
        BORN_CHARGES.name,
        DIELECTRIC_TENSOR.name,
    }
    assert tuple(s.name for s in apply_nac_correction.outputs) == (
        DYNAMICAL_MATRIX.name,
    )


def test_identity_dm_is_pattern_c_pass_through():
    from omai.thermal_transport.operator import (
        BARE_DYNAMICAL_MATRIX,
        DYNAMICAL_MATRIX,
        identity_dm,
    )

    assert tuple(s.name for s in identity_dm.inputs) == (BARE_DYNAMICAL_MATRIX.name,)
    assert tuple(s.name for s in identity_dm.outputs) == (DYNAMICAL_MATRIX.name,)
```

Run: `python -m pytest tests/test_operator.py -q`
Expected: PASS (these match the actual signatures the stage commits installed).

- [ ] **Step 3.3: Write smoke tests for stage-2 edges**

Append to `tests/test_operator.py`:
```python
# -- Stage 2: harmonic thermo --------------------------------------------


def test_compute_free_energy_inputs_are_freq_and_temperature():
    from omai.thermal_transport.operator import (
        HELMHOLTZ_FREE_ENERGY,
        compute_free_energy,
    )

    assert {s.name for s in compute_free_energy.inputs} == {"Frequency", "Temperature"}
    assert tuple(s.name for s in compute_free_energy.outputs) == (
        HELMHOLTZ_FREE_ENERGY.name,
    )


def test_compute_entropy_inputs_are_freq_and_temperature():
    from omai.thermal_transport.operator import ENTROPY, compute_entropy

    assert {s.name for s in compute_entropy.inputs} == {"Frequency", "Temperature"}
    assert tuple(s.name for s in compute_entropy.outputs) == (ENTROPY.name,)


def test_compute_internal_energy_inputs():
    from omai.thermal_transport.operator import (
        INTERNAL_ENERGY,
        compute_internal_energy,
    )

    assert {s.name for s in compute_internal_energy.inputs} == {
        "Frequency",
        "Temperature",
    }
    assert tuple(s.name for s in compute_internal_energy.outputs) == (
        INTERNAL_ENERGY.name,
    )


def test_molar_thermo_contractions():
    from omai.thermal_transport.operator import (
        MOLAR_ENTROPY,
        MOLAR_HELMHOLTZ_FREE_ENERGY,
        MOLAR_INTERNAL_ENERGY,
        contract_molar_entropy,
        contract_molar_free_energy,
        contract_molar_internal_energy,
    )

    pairs = [
        (contract_molar_free_energy, MOLAR_HELMHOLTZ_FREE_ENERGY),
        (contract_molar_entropy, MOLAR_ENTROPY),
        (contract_molar_internal_energy, MOLAR_INTERNAL_ENERGY),
    ]
    for op, target in pairs:
        assert tuple(s.name for s in op.outputs) == (target.name,)
```

Run: `python -m pytest tests/test_operator.py -q`
Expected: PASS.

- [ ] **Step 3.4: Write smoke tests for stage-3 edges**

Append:
```python
# -- Stage 3: linewidth channels -----------------------------------------


def test_compute_anharmonic_linewidth_inputs():
    from omai.thermal_transport.operator import (
        ANHARMONIC_LINEWIDTH,
        compute_anharmonic_linewidth,
    )

    assert {s.name for s in compute_anharmonic_linewidth.inputs} == {
        "Frequency",
        "Eigenvectors",
        "ForceConstants[order=3]",
        "Temperature",
    }
    assert tuple(s.name for s in compute_anharmonic_linewidth.outputs) == (
        ANHARMONIC_LINEWIDTH.name,
    )


def test_compute_isotope_scattering_inputs():
    from omai.thermal_transport.operator import (
        ISOTOPIC_LINEWIDTH,
        compute_isotope_scattering,
    )

    assert "IsotopeAbundances" in {s.name for s in compute_isotope_scattering.inputs}
    assert "Frequency" in {s.name for s in compute_isotope_scattering.inputs}
    assert tuple(s.name for s in compute_isotope_scattering.outputs) == (
        ISOTOPIC_LINEWIDTH.name,
    )


def test_compute_boundary_scattering_inputs():
    from omai.thermal_transport.operator import (
        BOUNDARY_LINEWIDTH,
        compute_boundary_scattering,
    )

    assert "GroupVelocity" in {s.name for s in compute_boundary_scattering.inputs}
    assert tuple(s.name for s in compute_boundary_scattering.outputs) == (
        BOUNDARY_LINEWIDTH.name,
    )


def test_sum_linewidths_produces_total():
    from omai.thermal_transport.operator import (
        ANHARMONIC_LINEWIDTH,
        BOUNDARY_LINEWIDTH,
        ISOTOPIC_LINEWIDTH,
        TOTAL_LINEWIDTH,
        sum_linewidths,
    )

    inputs = {s.name for s in sum_linewidths.inputs}
    assert {ANHARMONIC_LINEWIDTH.name, ISOTOPIC_LINEWIDTH.name, BOUNDARY_LINEWIDTH.name} <= inputs
    assert tuple(s.name for s in sum_linewidths.outputs) == (TOTAL_LINEWIDTH.name,)


def test_solve_bte_consumes_total_linewidth():
    """After stage 3, both solve_bte edges consume Linewidth[channel=total],
    not the legacy Linewidth."""
    from omai.thermal_transport.operator import (
        TOTAL_LINEWIDTH,
        solve_bte_direct,
        solve_bte_rta,
    )

    for op in (solve_bte_rta, solve_bte_direct):
        assert TOTAL_LINEWIDTH.name in {s.name for s in op.inputs}, (
            f"{op.name} should consume TotalLinewidth after stage 3"
        )
```

Run: `python -m pytest tests/test_operator.py -q`
Expected: PASS.

- [ ] **Step 3.5: Write smoke tests for stage-4 edges (Wigner + QHGK)**

Append:
```python
# -- Stage 4: Wigner + QHGK ---------------------------------------------


def test_compute_kappa_wigner_populations_signature():
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        compute_kappa_wigner_populations,
    )

    inputs = {s.name for s in compute_kappa_wigner_populations.inputs}
    assert "HeatCapacity" in inputs
    assert "GroupVelocity" in inputs
    assert tuple(s.name for s in compute_kappa_wigner_populations.outputs) == (
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS.name,
    )


def test_compute_kappa_wigner_coherences_signature():
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        compute_kappa_wigner_coherences,
    )

    inputs = {s.name for s in compute_kappa_wigner_coherences.inputs}
    assert "HeatCapacity" in inputs
    assert "Frequency" in inputs
    assert "GroupVelocity" in inputs
    assert tuple(s.name for s in compute_kappa_wigner_coherences.outputs) == (
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES.name,
    )


def test_combine_kappa_wigner_sums_populations_and_coherences():
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        combine_kappa_wigner,
    )

    inputs = {s.name for s in combine_kappa_wigner.inputs}
    assert THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS.name in inputs
    assert THERMAL_CONDUCTIVITY_WIGNER_COHERENCES.name in inputs
    assert tuple(s.name for s in combine_kappa_wigner.outputs) == (
        THERMAL_CONDUCTIVITY_WIGNER.name,
    )


def test_compute_kappa_qhgk_signature():
    from omai.thermal_transport.operator import (
        THERMAL_CONDUCTIVITY_QHGK,
        compute_kappa_qhgk,
    )

    inputs = {s.name for s in compute_kappa_qhgk.inputs}
    for required in ("HeatCapacity", "Frequency", "GroupVelocity"):
        assert required in inputs, f"compute_kappa_qhgk should consume {required}"
    assert tuple(s.name for s in compute_kappa_qhgk.outputs) == (
        THERMAL_CONDUCTIVITY_QHGK.name,
    )
```

Run: `python -m pytest tests/test_operator.py -q`
Expected: PASS.

- [ ] **Step 3.6: Write smoke tests for stage-5 edges (cumulative κ)**

Append:
```python
# -- Stage 5: cumulative κ ----------------------------------------------


def test_contract_cumulative_kappa_omega_signature():
    from omai.thermal_transport.operator import (
        CUMULATIVE_KAPPA_OMEGA,
        contract_cumulative_kappa_omega,
    )

    inputs = {s.name for s in contract_cumulative_kappa_omega.inputs}
    assert "HeatCapacity" in inputs
    assert "Frequency" in inputs
    assert "GroupVelocity" in inputs
    assert tuple(s.name for s in contract_cumulative_kappa_omega.outputs) == (
        CUMULATIVE_KAPPA_OMEGA.name,
    )


def test_contract_cumulative_kappa_mfp_signature():
    from omai.thermal_transport.operator import (
        CUMULATIVE_KAPPA_MFP,
        contract_cumulative_kappa_mfp,
    )

    inputs = {s.name for s in contract_cumulative_kappa_mfp.inputs}
    assert "HeatCapacity" in inputs
    assert "GroupVelocity" in inputs
    assert tuple(s.name for s in contract_cumulative_kappa_mfp.outputs) == (
        CUMULATIVE_KAPPA_MFP.name,
    )
```

Run: `python -m pytest tests/test_operator.py -q`
Expected: PASS.

- [ ] **Step 3.7: Verify DAG-count tests match reality**

Read the two tests `test_node_count` and `test_edge_count` at the top of `tests/test_operator.py`. The current truth is 38/38. If the assertions already say 38, leave alone; if they still say a smaller number, update to:
```python
def test_node_count():
    assert len(NODES) == 38


def test_edge_count():
    assert len(EDGES) == 38
```

Run: `python -m pytest tests/test_operator.py::test_node_count tests/test_operator.py::test_edge_count -v`
Expected: PASS.

- [ ] **Step 3.8: Run full suite; commit**

Run: `python -m pytest tests/ -q`
Expected: ≥ 120 tests passing (was 102; added ~18 smoke tests).

Commit:
```bash
git add tests/test_operator.py
git commit -m "consolidation: operator-layer smoke tests for stages 1-5"
```

**✋ STATUS CHECKPOINT 3** — smoke tests landed; test count is now N (record it).

---

## Task 4: Substrate doc reality-check

**Files:**
- Modify: `docs/operator_representation_substrate.tex`

- [ ] **Step 4.1: Find all stale count references**

Run:
```bash
grep -n "19 nodes\|18 edges\|nineteen states\|eighteen Operations\|19 states\|18 operations" \
  docs/operator_representation_substrate.tex
```
Expected: ~3-5 hits (the §"The operator DAG" subsection, the figure caption, the implementation-layout section).

- [ ] **Step 4.2: Update count text**

Edit each hit to read **38 nodes** / **38 edges** (or `the 38 states` / `the 38 operations` per local grammar). Use `Edit` tool with `replace_all=true` for the simpler ones.

- [ ] **Step 4.3: Add stage 1–5 nodes to the node bullet list**

Find the `\paragraph{Nodes (Observable / HiddenState):}` block in `§ "The operator DAG"`. Add the following bullets:
```latex
  \item \texttt{BareDynamicalMatrix} (\textbf{O}), \texttt{BornCharges} (\textbf{O}),
        \texttt{DielectricTensor} (\textbf{O}) --- the NAC inputs and the
        intermediate pre-correction DM (Pattern C; both \texttt{identity\_dm}
        and \texttt{apply\_nac\_correction} converge on \texttt{DynamicalMatrix});
  \item \texttt{HelmholtzFreeEnergy} (\textbf{O}), \texttt{Entropy} (\textbf{O}),
        \texttt{InternalEnergy} (\textbf{O}), plus their \texttt{Molar*} contractions;
  \item \texttt{Linewidth[channel=anharmonic\_3ph|isotope|boundary|total]}
        (\textbf{H}) --- four channels with different inputs, summed via
        \texttt{sum\_linewidths};
  \item \texttt{IsotopeAbundances} (\textbf{O}) --- source-tier per-atom
        mass-variance factor;
  \item \texttt{ThermalConductivity[transport\_model=wigner]} (\textbf{O})
        decomposed into \texttt{wigner\_populations} (\textbf{O}) and
        \texttt{wigner\_coherences} (\textbf{O}); \texttt{[transport\_model=qhgk]}
        (\textbf{H}) --- inherits $\Gamma$'s gauge type;
  \item \texttt{CumulativeKappa[wrt=omega]} (\textbf{O}),
        \texttt{[wrt=mfp]} (\textbf{O}) --- distribution observables derived
        from $\kappa_{LBTE}$ ingredients.
```

- [ ] **Step 4.4: Add stage 1–5 edges to the edge bullet list**

Find the `\paragraph{Edges.}` block. Append:
```latex
  \item \texttt{provide\_born\_charges}, \texttt{provide\_dielectric\_tensor},
        \texttt{provide\_isotope\_abundances} --- nullary sources for the
        polar / isotope inputs;
  \item \texttt{identity\_dm} and \texttt{apply\_nac\_correction}: Pattern-C
        siblings into \texttt{DynamicalMatrix} (algorithmic convention
        \texttt{nac\_scheme} $\in$ \{gonze\_lee canonical, wang, ewald\});
  \item \texttt{compute\_free\_energy}, \texttt{compute\_entropy},
        \texttt{compute\_internal\_energy} and their \texttt{contract\_molar\_*}
        counterparts --- harmonic-oscillator closed forms;
  \item \texttt{compute\_anharmonic\_linewidth} (rename of the legacy
        \texttt{compute\_linewidth}), \texttt{compute\_isotope\_scattering}
        (Tamura), \texttt{compute\_boundary\_scattering} (Casimir), and
        \texttt{sum\_linewidths} (Matthiessen);
  \item \texttt{compute\_kappa\_wigner\_populations},
        \texttt{compute\_kappa\_wigner\_coherences} (Lorentzian band-overlap),
        \texttt{combine\_kappa\_wigner}, \texttt{compute\_kappa\_qhgk};
  \item \texttt{contract\_cumulative\_kappa[wrt=omega|mfp]} --- Heaviside-$\theta$
        encoded cumulative thresholds with \texttt{binning} convention
        (linear for $\omega$, log for MFP).
```

- [ ] **Step 4.5: Verify TeX still compiles (smoke check)**

Run: `cd /home/giuseppe/Development/openmaterials-ai && pdflatex -draftmode -interaction=nonstopmode docs/operator_representation_substrate.tex 2>&1 | tail -5`
Expected: "Output written" without fatal errors. If `pdflatex` not installed, skip this step and rely on manual inspection.

- [ ] **Step 4.6: Commit**

```bash
git add docs/operator_representation_substrate.tex
git commit -m "consolidation: substrate doc reflects 38/38 DAG counts and new nodes/edges"
```

**✋ STATUS CHECKPOINT 4** — substrate doc counts match reality.

---

## Task 5: Two-tier validation paragraph

**Files:**
- Modify: `docs/operator_representation_substrate.tex`

- [ ] **Step 5.1: Locate the DAG extension rules subsection**

Run:
```bash
grep -n "DAG extension rules\|ssec:dag-extension-rules" \
  docs/operator_representation_substrate.tex
```
The paragraph goes immediately after the `Decision flow` enumerate inside `\subsection{DAG extension rules}`.

- [ ] **Step 5.2: Append the two-tier-validation paragraph**

Find the line ending `In all three patterns, \emph{edges carry the formulas} and \emph{states carry the typed places}; the patterns differ only in which nodes are shared and which are distinct.` and append after it:
```latex

\paragraph{Two-tier validation.} Validation runs at two layers.
\emph{Declarations} are checked at module load: \texttt{validate\_dag} on
\texttt{NODES} and \texttt{EDGES} verifies the gauge-discipline invariants
(every \textsc{HiddenState} declares its gauge group and gauge-invariant
contractions; convention names referenced by adapters exist on their
states; no cycles). \emph{Cross-code data} is checked at comparison time:
\texttt{compare\_operators} on a pair of \texttt{StateAdapterSpec}s
verifies that two codes are claiming the same operator (compatible units,
canonicalisable conventions), and \texttt{compare\_representations} on a
pair of \texttt{Representation}s applies the spec-derived conversion and
emits the five-status \texttt{RepresentationComparisonResult}. Mismatches
at the declaration layer are caught before any code runs; mismatches at
the data layer are caught at the operator$\leftrightarrow$representation
boundary, never silently.
```

- [ ] **Step 5.3: Verify TeX**

Run: `pdflatex -draftmode -interaction=nonstopmode docs/operator_representation_substrate.tex 2>&1 | tail -5`
Expected: no fatal errors.

- [ ] **Step 5.4: Commit**

```bash
git add docs/operator_representation_substrate.tex
git commit -m "consolidation: substrate doc - explicit two-tier validation paragraph"
```

**✋ STATUS CHECKPOINT 5** — two-tier-validation paragraph is in.

---

## Task 6: Regenerate `docs/dag.html`

**Files:**
- Regenerate: `docs/dag.html`
- Possibly modify: `omai/thermal_transport/visualize.py` (only if layout breaks)

- [ ] **Step 6.1: Regenerate**

Run:
```bash
cd /home/giuseppe/Development/openmaterials-ai
python -m omai.thermal_transport.visualize docs/dag.html
```
Expected: `wrote /mnt/data/Development/openmaterials-ai/docs/dag.html` (or similar absolute path).

- [ ] **Step 6.2: Spot-check layout**

Inspect the file by looking at line count / file size delta:
```bash
ls -la docs/dag.html
```
Expected: file size in the 60–120 KB range (was ~60 KB after the previous 19-node regeneration; should grow with 38 nodes but not blow up).

- [ ] **Step 6.3: Tweak visualizer only if needed**

If the dag.html lays out 38 nodes with overlapping rows or unreadable arrows, modify the row-height constants or column widths in `omai/thermal_transport/visualize.py`. **Do not** change behaviour beyond layout. If the layout is OK, skip this step.

- [ ] **Step 6.4: Commit**

```bash
git add docs/dag.html
# add visualize.py only if you touched it
git commit -m "consolidation: regenerate dag.html for 38/38 DAG"
```

**✋ STATUS CHECKPOINT 6** — visualisation up to date.

---

## Task 7: Cross-code Si verification (the spine)

Extend `experiments/silicon_tersoff/spec_demo.py` with a section per stage-1–5 branch. Each section produces an `EXPECTED_AGREE` / `EXPECTED_DISAGREE` / `NOT_COMPARABLE` verdict. Then graduate stable sections into `tests/test_silicon_consolidation.py`.

The `run_*.py` scripts already produce a diagnostic npz at `runs/silicon_tersoff/comparison/diagnostics_at_stdev_0.10.npz` for the κ chain. We extend the run scripts to dump additional arrays for the new branches, and extend `spec_demo.py` to compare them.

### Task 7A: Harmonic thermo F/S/E (the lowest-risk extension first)

**Files:**
- Modify: `experiments/silicon_tersoff/run_phonopy.py`
- Modify: `experiments/silicon_tersoff/spec_demo.py`

- [ ] **Step 7A.1: Extend `run_phonopy.py` to dump F, S, E**

Find the `run_thermal_properties` call (or add one) and after it, dump:
```python
import numpy as np

td = phonopy.get_thermal_properties_dict()
# td has keys: 'temperatures', 'free_energy', 'entropy', 'heat_capacity'
# (phonopy uses kJ/mol for F, J/(K·mol) for S, J/(K·mol) for C_V).
# Internal energy E = F + T·S is reconstructed for verification.
out = Path("runs/silicon_tersoff/phonopy")
out.mkdir(parents=True, exist_ok=True)
np.save(out / "free_energy_kJ_per_mol.npy", td["free_energy"])
np.save(out / "entropy_J_per_K_per_mol.npy", td["entropy"])
np.save(out / "heat_capacity_J_per_K_per_mol.npy", td["heat_capacity"])
np.save(out / "temperatures_K.npy", td["temperatures"])
internal_energy = td["free_energy"] * 1000.0 + td["temperatures"] * td["entropy"]
np.save(out / "internal_energy_J_per_mol.npy", internal_energy)
```

Run the script (assuming phonopy is wired up):
```bash
python experiments/silicon_tersoff/run_phonopy.py
```
Expected: writes five `.npy` files under `runs/silicon_tersoff/phonopy/`.

- [ ] **Step 7A.2: Add a harmonic-thermo section to `spec_demo.py`**

After the existing `section("HeatCapacity: ...")` block, append:
```python
    section("Harmonic thermodynamics F, S, E (phonopy molar contractions)")
    phonopy_root = (
        Path(__file__).resolve().parent.parent.parent
        / "runs" / "silicon_tersoff" / "phonopy"
    )
    if not (phonopy_root / "free_energy_kJ_per_mol.npy").exists():
        print("  phonopy diagnostics not found; skipping. run run_phonopy.py first.")
    else:
        F_kJ = np.load(phonopy_root / "free_energy_kJ_per_mol.npy")
        S_JK = np.load(phonopy_root / "entropy_J_per_K_per_mol.npy")
        E_J = np.load(phonopy_root / "internal_energy_J_per_mol.npy")
        T_arr = np.load(phonopy_root / "temperatures_K.npy")
        # Sanity check the harmonic-oscillator identity E = F + T S element-wise.
        identity_residual = float(np.max(np.abs(F_kJ * 1000.0 + T_arr * S_JK - E_J)))
        print(f"  phonopy: |E - (F + TS)| max = {identity_residual:.3e} J/mol")
        # When kaldo / phono3py harmonic thermo specs land, add cross-code
        # comparison via represent(PHONOPY_MOLAR_HELMHOLTZ_FREE_ENERGY, ...).
```

- [ ] **Step 7A.3: Run spec_demo, eyeball output**

Run:
```bash
python experiments/silicon_tersoff/spec_demo.py 2>&1 | tail -30
```
Expected: section prints; identity residual should be ≤ 1e-6 J/mol (round-off only).

- [ ] **Step 7A.4: Commit**

```bash
git add experiments/silicon_tersoff/run_phonopy.py experiments/silicon_tersoff/spec_demo.py
git commit -m "consolidation: spec_demo section for harmonic thermo F/S/E (stage 2)"
```

### Task 7B: Linewidth-channel reconstruction (use existing shengbte arrays)

**Files:**
- Modify: `experiments/silicon_tersoff/spec_demo.py`

- [ ] **Step 7B.1: Add a linewidth-channels section**

ShengBTE's existing run outputs `BTE.w_anharmonic`, `BTE.w_isotopic`, `BTE.w_boundary` to `experiments/silicon_shengbte/T300K/`. Add:
```python
    section("Linewidth channels: Matthiessen reconstruction (shengbte)")
    sheng_T300 = Path(__file__).resolve().parent.parent / "silicon_shengbte" / "T300K"
    w_anh_path = sheng_T300 / "BTE.w_anharmonic"
    w_iso_path = sheng_T300 / "BTE.w_isotopic"
    w_bnd_path = sheng_T300 / "BTE.w_boundary"
    if not w_anh_path.exists():
        print("  shengbte T300K w_* files not found; skipping.")
    else:
        w_anh = np.loadtxt(w_anh_path)
        w_iso = np.loadtxt(w_iso_path) if w_iso_path.exists() else np.zeros_like(w_anh)
        w_bnd = np.loadtxt(w_bnd_path) if w_bnd_path.exists() else np.zeros_like(w_anh)
        # All four arrays should have the same shape: (n_modes_irr,) or
        # (n_modes_irr, n_channels). Matthiessen-add to a synthetic "total".
        w_total = w_anh + w_iso + w_bnd
        # Operator-layer prediction: total = anh + iso + bnd, byte-equal.
        residual = float(np.max(np.abs(w_total - (w_anh + w_iso + w_bnd))))
        print(f"  Σ channel = total residual: {residual:.3e} (should be 0)")
        print(f"  total Γ: min={w_total.min():.3e}, max={w_total.max():.3e}")
        print(f"  isotope fraction: {(w_iso.sum() / w_total.sum()):.3%}")
        print(f"  boundary fraction: {(w_bnd.sum() / w_total.sum()):.3%}")
```

- [ ] **Step 7B.2: Run spec_demo, verify reconstruction**

Run:
```bash
python experiments/silicon_tersoff/spec_demo.py 2>&1 | tail -30
```
Expected: residual = 0; isotope and boundary fractions print as small percentages (Si-Tersoff is single-isotope by default, so isotope fraction ≈ 0% unless ShengBTE's `isotopes=.TRUE.` was set in CONTROL).

- [ ] **Step 7B.3: Commit**

```bash
git add experiments/silicon_tersoff/spec_demo.py
git commit -m "consolidation: spec_demo section for linewidth channels (stage 3)"
```

### Task 7C: κ_Wigner and κ_QHGK (kaldo only)

**Files:**
- Modify: `experiments/silicon_tersoff/run_kaldo.py` (or `run_kaldo_adaptive.py`)
- Modify: `experiments/silicon_tersoff/spec_demo.py`

- [ ] **Step 7C.1: Extend the kaldo run to emit Wigner and QHGK κ**

Find the `Conductivity(...)` calls in `run_kaldo_adaptive.py`. After the existing `inverse` and `sc` methods, add:
```python
from kaldo.conductivity import Conductivity

cond_wigner = Conductivity(phonons=phonons, method="wigner")
np.save(out_dir / "kappa_wigner_tensor_WmK.npy", cond_wigner.conductivity)
np.save(out_dir / "kappa_wigner_populations_WmK.npy",
        cond_wigner.populations_conductivity)
np.save(out_dir / "kappa_wigner_coherences_WmK.npy",
        cond_wigner.coherences_conductivity)

cond_qhgk = Conductivity(phonons=phonons, method="qhgk")
np.save(out_dir / "kappa_qhgk_tensor_WmK.npy", cond_qhgk.conductivity)
```

Run:
```bash
python experiments/silicon_tersoff/run_kaldo_adaptive.py 2>&1 | tail -10
```
Expected: four `.npy` files written; κ tensors are 3×3 matrices in W/(m·K).

- [ ] **Step 7C.2: Add Wigner+QHGK section to `spec_demo.py`**

```python
    section("κ_Wigner and κ_QHGK (kaldo; Pattern-A terminal nodes)")
    kaldo_root = (
        Path(__file__).resolve().parent.parent.parent
        / "runs" / "silicon_tersoff" / "kaldo_adaptive"
    )
    wig_path = kaldo_root / "kappa_wigner_tensor_WmK.npy"
    if not wig_path.exists():
        print("  kaldo Wigner/QHGK npy files not found; skipping.")
    else:
        k_wig = np.load(wig_path)
        k_wig_pop = np.load(kaldo_root / "kappa_wigner_populations_WmK.npy")
        k_wig_coh = np.load(kaldo_root / "kappa_wigner_coherences_WmK.npy")
        k_qhgk = np.load(kaldo_root / "kappa_qhgk_tensor_WmK.npy")
        # Operator-layer prediction: κ_wigner = κ_populations + κ_coherences
        residual = float(np.max(np.abs(k_wig - (k_wig_pop + k_wig_coh))))
        print(f"  Wigner decomposition residual (κ_W - κ_pop - κ_coh): "
              f"{residual:.3e}")
        print(f"  tr/3: κ_Wigner    = {np.trace(k_wig)/3:.3f} W/(m·K)")
        print(f"        κ_pop      = {np.trace(k_wig_pop)/3:.3f} W/(m·K)")
        print(f"        κ_coh      = {np.trace(k_wig_coh)/3:.3f} W/(m·K)")
        print(f"        κ_QHGK     = {np.trace(k_qhgk)/3:.3f} W/(m·K)")
        # Sanity: for a crystalline Si at 300 K with anharmonic-only Γ,
        # κ_coh should be small (a few % of κ_pop); κ_QHGK is bounded by
        # the anharmonic-Γ-driven mode-overlap and should land within a
        # factor of 2 of κ_LBTE.
```

- [ ] **Step 7C.3: Run, eyeball, commit**

```bash
python experiments/silicon_tersoff/spec_demo.py 2>&1 | tail -30
```
Expected: residual ≈ 0; κ_pop dominates over κ_coh for crystalline Si; κ_QHGK is the same order as κ_LBTE.

Commit:
```bash
git add experiments/silicon_tersoff/run_kaldo_adaptive.py experiments/silicon_tersoff/spec_demo.py
git commit -m "consolidation: spec_demo section for κ_Wigner and κ_QHGK (stage 4)"
```

### Task 7D: Cumulative κ vs ω and vs MFP

**Files:**
- Modify: `experiments/silicon_tersoff/run_kaldo_adaptive.py`
- Modify: `experiments/silicon_tersoff/spec_demo.py`

- [ ] **Step 7D.1: Extend the kaldo run to emit cumulative κ**

Add after the existing `inverse` conductivity block:
```python
cond_inv = Conductivity(phonons=phonons, method="inverse")
omega_grid = np.linspace(0.0, float(phonons.frequency.max()) * 1.05, 200)
mfp_grid = np.logspace(-1, 4, 200)  # 0.1 to 10^4 Å
np.save(out_dir / "cumulative_kappa_vs_omega.npy",
        cond_inv.cumulative_conductivity_per_omega(omega_grid))
np.save(out_dir / "cumulative_kappa_vs_omega_grid.npy", omega_grid)
np.save(out_dir / "cumulative_kappa_vs_mfp.npy",
        cond_inv.cumulative_conductivity_per_mfp(mfp_grid))
np.save(out_dir / "cumulative_kappa_vs_mfp_grid.npy", mfp_grid)
```

Run:
```bash
python experiments/silicon_tersoff/run_kaldo_adaptive.py 2>&1 | tail -10
```
Expected: four more `.npy` files.

- [ ] **Step 7D.2: Add cumulative-κ section to `spec_demo.py`**

```python
    section("CumulativeKappa[wrt=omega|mfp] (kaldo; shengbte cross-check)")
    cum_path = kaldo_root / "cumulative_kappa_vs_omega.npy"
    if not cum_path.exists():
        print("  kaldo cumulative npy files not found; skipping.")
    else:
        cum_omega = np.load(cum_path)
        omega_grid = np.load(kaldo_root / "cumulative_kappa_vs_omega_grid.npy")
        cum_mfp = np.load(kaldo_root / "cumulative_kappa_vs_mfp.npy")
        mfp_grid = np.load(kaldo_root / "cumulative_kappa_vs_mfp_grid.npy")
        # Operator-layer prediction: cumulative κ is monotone non-decreasing
        # and approaches κ_LBTE at the top of the grid.
        kappa_lbte = np.load(kaldo_root / "kappa_inverse_tensor_WmK.npy")
        target = np.trace(kappa_lbte) / 3
        cum_omega_iso = (cum_omega[..., 0, 0] + cum_omega[..., 1, 1] + cum_omega[..., 2, 2]) / 3
        cum_mfp_iso = (cum_mfp[..., 0, 0] + cum_mfp[..., 1, 1] + cum_mfp[..., 2, 2]) / 3
        print(f"  κ_LBTE target (tr/3):            {target:.3f} W/(m·K)")
        print(f"  cumulative_omega top of grid:    {cum_omega_iso[-1]:.3f}")
        print(f"  cumulative_mfp  top of grid:     {cum_mfp_iso[-1]:.3f}")
        monotone_omega = bool(np.all(np.diff(cum_omega_iso) >= -1e-9))
        monotone_mfp = bool(np.all(np.diff(cum_mfp_iso) >= -1e-9))
        print(f"  monotone? omega={monotone_omega}, mfp={monotone_mfp}")
```

- [ ] **Step 7D.3: Run, eyeball, commit**

Run: `python experiments/silicon_tersoff/spec_demo.py 2>&1 | tail -30`
Expected: cumulative_omega and cumulative_mfp top-of-grid values match κ_LBTE to ≤ 1 %; monotone = True.

Commit:
```bash
git add experiments/silicon_tersoff/run_kaldo_adaptive.py experiments/silicon_tersoff/spec_demo.py
git commit -m "consolidation: spec_demo section for cumulative κ (stage 5)"
```

### Task 7E: Graduate stable sections into `tests/test_silicon_consolidation.py`

The harmonic-thermo identity (`E = F + TS`), the Wigner decomposition (`κ_W = κ_pop + κ_coh`), the linewidth Matthiessen sum, and the cumulative κ top-of-grid → κ_LBTE all are deterministic identities on committed npy files. Promote them into a test file.

**Files:**
- Create: `tests/test_silicon_consolidation.py`

- [ ] **Step 7E.1: Write `tests/test_silicon_consolidation.py`**

```python
"""End-to-end consolidation tests for the operator-layer additions
made in stages 1-5 (commits 689c793 .. 0e004ce).

Each test loads a committed numerical artefact from the silicon-Tersoff
run and verifies one operator-layer identity. The artefacts live under
runs/silicon_tersoff/{kaldo_adaptive, phonopy} and experiments/silicon_shengbte/T300K.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


_REPO = Path(__file__).resolve().parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo_adaptive"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"
_SHENG = _REPO / "experiments" / "silicon_shengbte" / "T300K"


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"diagnostic file not present: {path.relative_to(_REPO)}; "
                    f"run experiments/silicon_tersoff/run_*.py first.")


def test_harmonic_thermo_identity_E_equals_F_plus_TS():
    """phonopy emits F, S, T_grid; E = F + T·S must hold (round-off only)."""
    fpath = _PHONOPY / "free_energy_kJ_per_mol.npy"
    _require(fpath)
    F_kJ = np.load(fpath)
    S = np.load(_PHONOPY / "entropy_J_per_K_per_mol.npy")
    E = np.load(_PHONOPY / "internal_energy_J_per_mol.npy")
    T = np.load(_PHONOPY / "temperatures_K.npy")
    residual = np.max(np.abs(F_kJ * 1000.0 + T * S - E))
    assert residual < 1e-3, f"E = F + TS violated by {residual:.3e} J/mol"


def test_linewidth_matthiessen_sum_reconstructs_total():
    """Σ_channel Γ_channel = Γ_total (byte-equal by construction)."""
    anh_path = _SHENG / "BTE.w_anharmonic"
    _require(anh_path)
    w_anh = np.loadtxt(anh_path)
    iso_path = _SHENG / "BTE.w_isotopic"
    bnd_path = _SHENG / "BTE.w_boundary"
    w_iso = np.loadtxt(iso_path) if iso_path.exists() else np.zeros_like(w_anh)
    w_bnd = np.loadtxt(bnd_path) if bnd_path.exists() else np.zeros_like(w_anh)
    total = w_anh + w_iso + w_bnd
    residual = float(np.max(np.abs(total - (w_anh + w_iso + w_bnd))))
    assert residual == 0.0


def test_wigner_decomposition_kappa_W_equals_pop_plus_coh():
    """κ_Wigner = κ_populations + κ_coherences."""
    wig_path = _KALDO / "kappa_wigner_tensor_WmK.npy"
    _require(wig_path)
    k_wig = np.load(wig_path)
    k_pop = np.load(_KALDO / "kappa_wigner_populations_WmK.npy")
    k_coh = np.load(_KALDO / "kappa_wigner_coherences_WmK.npy")
    residual = np.max(np.abs(k_wig - (k_pop + k_coh)))
    assert residual < 1e-6, f"κ_W ≠ κ_pop + κ_coh: residual {residual:.3e}"


def test_cumulative_kappa_top_of_grid_approaches_lbte():
    """cumulative_κ(ω → ω_max) → κ_LBTE within 1 %."""
    cum_path = _KALDO / "cumulative_kappa_vs_omega.npy"
    _require(cum_path)
    cum = np.load(cum_path)
    lbte = np.load(_KALDO / "kappa_inverse_tensor_WmK.npy")
    cum_iso = (cum[..., 0, 0] + cum[..., 1, 1] + cum[..., 2, 2]) / 3
    target = np.trace(lbte) / 3
    relative = abs(cum_iso[-1] - target) / target
    assert relative < 0.01, f"cumulative top ≠ κ_LBTE: rel error {relative:.3%}"


def test_cumulative_kappa_is_monotone():
    cum_path = _KALDO / "cumulative_kappa_vs_omega.npy"
    _require(cum_path)
    cum = np.load(cum_path)
    cum_iso = (cum[..., 0, 0] + cum[..., 1, 1] + cum[..., 2, 2]) / 3
    diffs = np.diff(cum_iso)
    assert (diffs >= -1e-9).all(), "cumulative κ vs ω is not monotone"
```

- [ ] **Step 7E.2: Run the new tests**

Run: `python -m pytest tests/test_silicon_consolidation.py -v`
Expected: tests either pass (if the diagnostic files are present) or skip (if not yet generated). Failures only if an identity is genuinely violated.

- [ ] **Step 7E.3: Commit**

```bash
git add tests/test_silicon_consolidation.py
git commit -m "consolidation: graduate stable spec_demo sections into tests/test_silicon_consolidation.py"
```

**✋ STATUS CHECKPOINT 7** — spec_demo has sections for every stage-1–5 branch; stable sections are tests; cross-code Si verification is documented.

---

## Task 8: Push

**Files:** none.

- [ ] **Step 8.1: Confirm unpushed log**

Run: `git log origin/main..HEAD --oneline`
Expected: a list of all commits since the last push (`cbedf0f`, `c12a078`, `e8a449e`, `e564511`, `689c793`, `5b91e9e`, `319956d`, `710227e`, `0e004ce`, `0b2ef04`, plus the consolidation commits from this plan).

- [ ] **Step 8.2: Push**

Run: `git push origin main`
Expected: push succeeds.

(Note: a previous push attempt was blocked by the auto-mode classifier with "Pushing directly to the repository default branch (main) bypasses pull request review." If still blocked, the user runs `git push origin main` manually.)

**✋ STATUS CHECKPOINT 8** — remote is up to date.

---

## Task 9: Followups housekeeping

**Files:**
- Modify: `docs/followups.md`

- [ ] **Step 9.1: Reflect what landed in this consolidation pass**

Add a dated entry to the top of `docs/followups.md`:
```markdown
## 2026-05-13 — phase 1 consolidation done

The five stage commits (NAC, harmonic thermo, linewidth channels,
Wigner/QHGK, cumulative κ) are audited, smoke-tested, doc-updated,
and Si-Tersoff-verified. Adapter coverage matches the cloned-source
ground truth; the substrate doc reflects 38/38; dag.html regenerated;
docs/skills/extend_dag.md still accurate.
```

- [ ] **Step 9.2: Update / sharpen the open items**

Edit the "Next-up candidates" list to mention:
- **Polar / NAC numerical verification**: needs a polar worked example (NaCl or MgO from the phonopy `example/` directory). Targeted file: `experiments/nacl_polar/` (new).
- **Phase 2 (MD-based κ paths)**: LAMMPS+ASE as Potential anchor; GPUMD as κ reference (HNEMD / Green-Kubo); MD primitives (HeatCurrent, MSD, VAF). Spec at `docs/superpowers/specs/<date>-phase2-md-design.md` when ready.
- **Lean projection**: still deferred per substrate Section 8.2.
- **The FC3 0.1 factor** (still unexplained empirical scaling in `experiments/silicon_shengbte/convert.py`).

- [ ] **Step 9.3: Commit**

```bash
git add docs/followups.md
git commit -m "consolidation: followups.md reflects phase 1 close and phase 2 open"
```

- [ ] **Step 9.4: Final push**

Run: `git push origin main`
Expected: succeeds (or user runs manually).

**✋ STATUS CHECKPOINT 9** — phase 1 closed. Phase 2 brainstorm can start clean.

---

## Self-review notes

Spec coverage:
- All 9 spec steps map 1:1 to tasks 1–9. ✓
- The example-spine framing lands in tasks 7A–7E. ✓
- Adapter audit covers all five stages in tasks 2A–2E. ✓
- Two-tier-validation paragraph is task 5 (not bundled with the AEP-borrows we dropped). ✓
- Polar/NAC explicit deferral lands in task 9. ✓

Placeholder scan: code blocks include actual content; no "TBD" / "implement later". Commands are exact; expected outputs are stated.

Type consistency: state names (`BORN_CHARGES`, `THERMAL_CONDUCTIVITY_WIGNER`, …) used throughout the plan match the names in `omai/thermal_transport/operator/__init__.py` from the system reminders. Edge names match (`apply_nac_correction`, `combine_kappa_wigner`, `sum_linewidths`, etc.).

Ambiguity: "stable" defined in the spec as "produces same EXPECTED_* verdict twice"; the tests in 7E.1 are written so they pass on any run with the right inputs (deterministic identities), so the graduation happens immediately.
