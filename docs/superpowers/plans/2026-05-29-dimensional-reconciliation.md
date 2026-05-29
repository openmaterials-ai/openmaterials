# Dimensional Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the executor automatically reconcile a contraction's result against its output's declared canonical unit, eliminating the hand-applied power-of-ten factors (κ's 1e22, volumetric Cv's 1e30).

**Architecture:** Give each dimension's canonical `Unit` an absolute SI scale. In `apply_edge`, after contracting, compute a *dimensional bridge* — but only for **pure-monomial contraction** edges (RHS is a product/quotient of input Indexed-bases and declared Parameter symbols). The bridge = (∏ input/param canonical-unit SI scale ^ power) / (output canonical-unit SI scale). Closed-form edges (ℏ/k_B-bearing, transcendental) and sum/identity edges are not monomials, so they get bridge=1.0 and are untouched.

**Tech Stack:** Python 3.9, sympy (`as_powers_dict`, `atoms(sp.Sum)`, `atoms(sp.Function)`), numpy, pytest.

**Constraints:** git author `gbarbalinardo` / `giuseppe.barbalinardo@gmail.com`, no Claude co-author trailers. Work on `main`. Run pytest from the repo root `/mnt/data/Development/openmaterials-ai`. The **central correctness constraint**: every edge in the pre-existing `tests/test_executor.py` must yield bridge=1.0 and unchanged results — this is the regression guard, verified in Task 3 before the new κ/Cv bridge tests.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `omai/operator/dimensions.py` | dimension tags | Modify — add `VOLUME` |
| `omai/representation/units.py` | `Unit` + registry + conversions | Modify — `si_scale` field, `angstrom`/`angstrom_cubed` units, `dimension_si_scale` helper, populate si_scale |
| `omai/thermal_transport/operator/edges.py` | operator edges | Modify — `Parameter("V_{cell}", VOLUME)` on the two contraction edges |
| `omai/representation/executor.py` | `apply_edge` | Modify — `_dimensional_bridge` helper + apply it |
| `tests/test_units_si_scale.py` | unit tests for si_scale + helper | Create |
| `tests/test_executor_bridge.py` | bridge tests (κ→1e22, Cv→1e30, monomial gate) | Create |
| `tests/test_validation_engine_silicon.py` | Example B | Modify — drop ×1e22 |
| `experiments/silicon_tersoff/run_validation.py` | Example B driver | Modify — drop ×1e22 |

---

## Task 1: SI scales on canonical units

**Files:**
- Modify: `omai/operator/dimensions.py`
- Modify: `omai/representation/units.py`
- Test: `tests/test_units_si_scale.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_units_si_scale.py`:

```python
"""SI scales on canonical units + dimension_si_scale lookup."""
from __future__ import annotations

import pytest

from omai.operator.dimensions import (
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    THERMAL_CONDUCTIVITY,
    VOLUME,
)
from omai.representation.units import UNITS, dimension_si_scale


def test_volume_dimension_registered():
    assert VOLUME.name == "volume"


def test_length_and_volume_have_canonical_units():
    # angstrom (length) and angstrom_cubed (volume) are registered, canonical.
    assert UNITS["angstrom"].dimension is LENGTH
    assert UNITS["angstrom"].to_operator == 1.0
    assert UNITS["angstrom_cubed"].dimension is VOLUME
    assert UNITS["angstrom_cubed"].to_operator == 1.0


def test_dimension_si_scale_values():
    assert dimension_si_scale(FREQUENCY) == 1e12
    assert dimension_si_scale(LENGTH) == 1e-10
    assert dimension_si_scale(LENGTH_TIMES_FREQUENCY) == 1e2
    assert dimension_si_scale(ENERGY_PER_TEMPERATURE) == 1.0
    assert dimension_si_scale(THERMAL_CONDUCTIVITY) == 1.0
    assert dimension_si_scale(VOLUME) == 1e-30


def test_dimension_si_scale_raises_for_dimension_without_scale():
    # OPAQUE has no canonical unit / si_scale; lookup must raise clearly.
    from omai.operator.dimensions import OPAQUE
    with pytest.raises(ValueError, match="no canonical unit"):
        dimension_si_scale(OPAQUE)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_units_si_scale.py -v`
Expected: FAIL — `ImportError: cannot import name 'VOLUME'` (and `dimension_si_scale`).

- [ ] **Step 3: Add the VOLUME dimension**

In `omai/operator/dimensions.py`, add a `VOLUME` dimension next to the other declarations and include it in the `DIMENSIONS` registry. Find the block of `Dimension(...)` module constants and add:

```python
VOLUME = Dimension("volume")
```

Then add `VOLUME` to the `DIMENSIONS` dict/list (follow the existing pattern in that file — it registers every dimension in a `DIMENSIONS` mapping keyed by `.name`).

- [ ] **Step 4: Add `si_scale` to `Unit`, register length/volume units, populate scales**

In `omai/representation/units.py`:

(a) Import `LENGTH` and `VOLUME` from dimensions (extend the existing `from omai.operator.dimensions import (...)` block to include `LENGTH` and `VOLUME` if not already present).

(b) Add the `si_scale` field to `Unit` (default `None` so non-canonical units need not set it):

```python
@dataclass(frozen=True)
class Unit:
    name: str
    dimension: Dimension
    to_operator: float
    si_scale: float | None = None
```

(c) Add `si_scale=` to each **canonical** unit definition (the `to_operator=1.0` ones), and register the two new units. Edit the existing definitions:

```python
LINEAR_THZ = Unit("linear_THz", FREQUENCY, 1.0, si_scale=1e12)
# ANGULAR_THZ stays si_scale=None (non-canonical)

J_PER_K = Unit("J_per_K", ENERGY_PER_TEMPERATURE, 1.0, si_scale=1.0)
# EV_PER_K stays None

J_PER_M3_PER_K = Unit("J_per_m3_per_K", ENERGY_PER_TEMPERATURE_PER_VOLUME, 1.0, si_scale=1.0)
J_PER_K_PER_MOL = Unit("J_per_K_per_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, 1.0, si_scale=1.0)

ANGSTROM_LINEAR_THZ = Unit("angstrom_linear_THz", LENGTH_TIMES_FREQUENCY, 1.0, si_scale=1e2)
# KM_PER_S stays None

W_PER_M_PER_K = Unit("W_per_m_per_K", THERMAL_CONDUCTIVITY, 1.0, si_scale=1.0)

J_PER_MOL = Unit("J_per_mol", ENERGY_PER_MOLE, 1.0, si_scale=1.0)
# KJ_PER_MOL stays None

EV_PER_A3 = Unit("eV_per_A3", ENERGY_PER_LENGTH_CUBED, 1.0, si_scale=None)  # not needed for any executable bridge yet
```

Add the two NEW canonical units (place near the other definitions):

```python
# Canonical length unit: Angstrom.
ANGSTROM = Unit("angstrom", LENGTH, 1.0, si_scale=1e-10)

# Canonical volume unit: cubic Angstrom (cell volume V_cell).
ANGSTROM_CUBED = Unit("angstrom_cubed", VOLUME, 1.0, si_scale=1e-30)
```

(d) Add `ANGSTROM` and `ANGSTROM_CUBED` to the `UNITS` registry list (the `for u in [...]` comprehension).

- [ ] **Step 5: Add the `dimension_si_scale` helper**

In `omai/representation/units.py`, after `conversion_factor`, add:

```python
def dimension_si_scale(dimension: Dimension) -> float:
    """Absolute SI scale of `dimension`'s canonical unit.

    The canonical unit for a dimension is the registered Unit with
    to_operator == 1.0. Returns its si_scale. Raises ValueError if the
    dimension has no canonical unit with an si_scale set — that is the
    signal to register one (this is how we discovered `length` lacked a
    unit).
    """
    for u in UNITS.values():
        if u.dimension == dimension and u.to_operator == 1.0 and u.si_scale is not None:
            return u.si_scale
    raise ValueError(
        f"dimension {dimension.name!r} has no canonical unit with an si_scale; "
        f"register one in omai/representation/units.py"
    )
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_units_si_scale.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Full suite (no regression from the Unit field change)**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ -q 2>&1 | tail -3`
Expected: zero FAILED (adding an optional field + new units must not break existing unit/representation tests).

- [ ] **Step 8: Commit**

```bash
git add omai/operator/dimensions.py omai/representation/units.py tests/test_units_si_scale.py
git commit -m "units: si_scale on canonical units; angstrom (length) + angstrom_cubed (volume); dimension_si_scale"
```

---

## Task 2: Type `V_cell` as a Parameter

**Files:**
- Modify: `omai/thermal_transport/operator/edges.py`
- Test: `tests/test_executor_bridge.py` (create here; Task 3 appends)

The formula symbol is exactly `V_{cell}` (with LaTeX braces). The Parameter **must be named `"V_{cell}"`** so the bridge's name lookup matches the symbol. (The design spec wrote `V_cell`; the exact-symbol name is the corrected, robust choice — the bridge keys parameter dimensions by symbol name.)

- [ ] **Step 1: Write the failing test**

Create `tests/test_executor_bridge.py`:

```python
"""Dimensional bridge: V_cell typing + automatic unit reconciliation."""
from __future__ import annotations

import numpy as np

from omai.operator.dimensions import VOLUME
from omai.thermal_transport.operator import (
    contract_kappa_direct,
    contract_volumetric_heat_capacity,
)


def test_v_cell_is_typed_volume_parameter_on_both_contractions():
    for op in (contract_kappa_direct, contract_volumetric_heat_capacity):
        params = {p.name: p.dimension for p in op.parameters}
        assert "V_{cell}" in params, f"{op.name} missing V_{{cell}} parameter"
        assert params["V_{cell}"] is VOLUME
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_bridge.py -v`
Expected: FAIL — `V_{cell}` not in the (currently empty) parameters.

- [ ] **Step 3: Declare the Parameter on both edges**

In `omai/thermal_transport/operator/edges.py`:

(a) Ensure `VOLUME` and `Parameter` are imported. The dimensions import line is `from omai.operator.dimensions import FREQUENCY, LENGTH, LENGTH_PER_TIME, TEMPERATURE` — add `VOLUME`. Confirm `Parameter` is imported from `omai.operator.operator` (the file already imports `Operator`; add `Parameter` to that import if absent).

(b) Find `contract_kappa_direct = Operator(...)`. It currently has no `parameters=`. Add:

```python
    parameters=(Parameter("V_{cell}", VOLUME),),
```

(c) Find `contract_volumetric_heat_capacity = Operator(...)` and add the identical `parameters=(Parameter("V_{cell}", VOLUME),),`.

Do not change formulas, schemes, or the `is_executable_in_sympy_override` already on `contract_kappa_direct`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_bridge.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Full suite (operator/DAG validation must still pass)**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ -q 2>&1 | tail -3`
Expected: zero FAILED. (Adding a Parameter must not trip `validate_dag` or edge/node counts.)

- [ ] **Step 6: Commit**

```bash
git add omai/thermal_transport/operator/edges.py tests/test_executor_bridge.py
git commit -m "operator: type V_cell as a VOLUME Parameter on the kappa and volumetric-Cv contractions"
```

---

## Task 3: The monomial-gated dimensional bridge in `apply_edge`

**Files:**
- Modify: `omai/representation/executor.py`
- Test: `tests/test_executor_bridge.py` (append)

- [ ] **Step 1: Write the regression-guard + bridge tests**

Append to `tests/test_executor_bridge.py`:

```python
import sympy as sp
from omai.representation.executor import _dimensional_bridge, apply_edge, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT,
    FREQUENCY_STATE, TEMPERATURE_STATE,
    compute_heat_capacity, identity_dm, sum_linewidths,
)


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


# --- the central regression guard: closed-form / identity / sum edges = bridge 1.0 ---

def test_bridge_is_unity_for_closed_form_and_identity_edges():
    # compute_heat_capacity (sinh kernel, ℏ/k_B inside) -> not a monomial -> 1.0
    assert _dimensional_bridge(compute_heat_capacity) == 1.0
    # identity_dm (D = D_bare, same dimension) -> 1.0
    assert _dimensional_bridge(identity_dm) == 1.0
    # sum_linewidths (additive) -> 1.0
    assert _dimensional_bridge(sum_linewidths) == 1.0


# --- the contraction edges get the real bridge ---

def test_bridge_for_kappa_direct_is_1e22():
    from omai.thermal_transport.operator import contract_kappa_direct
    assert _dimensional_bridge(contract_kappa_direct) == 1e22


def test_bridge_for_volumetric_cv_is_1e30():
    from omai.thermal_transport.operator import contract_volumetric_heat_capacity
    assert _dimensional_bridge(contract_volumetric_heat_capacity) == 1e30


def test_bridge_for_molar_cv_is_unity():
    # N_A · Σc / N_q : inputs all SI (J/K), output J/(K·mol) -> 1.0
    from omai.thermal_transport.operator import contract_molar_heat_capacity
    assert _dimensional_bridge(contract_molar_heat_capacity) == 1.0


# --- end-to-end: kappa contraction now yields W/(m·K) with NO caller-side factor ---

def test_apply_edge_kappa_yields_physical_units_without_manual_factor():
    from omai.thermal_transport.operator import contract_kappa_direct
    rng = np.random.default_rng(3)
    N_q, N_modes = 4, 6
    c = rng.random((N_q, N_modes))
    v = rng.random((3, N_q, N_modes))
    F = rng.random((3, N_q, N_modes))
    v_cell = 40.0
    out = apply_edge(
        contract_kappa_direct,
        _op_rep(HEAT_CAPACITY, "c", c),
        _op_rep(GROUP_VELOCITY, "v", v),
        _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", F),
        constants={"V_{cell}": v_cell},
    )
    expected = np.einsum("qn,aqn,bqn->ab", c, v, F) / (N_q * v_cell) * 1e22
    np.testing.assert_allclose(out.data, expected, rtol=1e-10)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_bridge.py -v`
Expected: FAIL — `ImportError: cannot import name '_dimensional_bridge'` (and the κ end-to-end value is currently 1e22× too small).

- [ ] **Step 3: Implement `_dimensional_bridge`**

In `omai/representation/executor.py`, add this module-level helper (near the other helpers at the bottom):

```python
def _dimensional_bridge(op: Operator) -> float:
    """Unit-bridge factor for a pure-monomial contraction edge; 1.0 otherwise.

    Applies iff the operator's formula RHS — with each Sum made transparent to
    its summand (summation over a dimensionless index does not change units) —
    is a monomial in the input Indexed-bases and declared-Parameter symbols:
    a product/quotient of those factors at integer powers, with no factor
    wrapped in a transcendental function and no additive structure. Counters
    (N_q, N) and physics constants (ℏ, k_B, N_A) are excluded. The bridge is
    (∏ input/param canonical-unit SI scale ** power) / (output canonical SI),
    rescaling the raw canonical-unit contraction into the output's declared
    canonical unit. Closed-form (ℏ/k_B-bearing, transcendental), identity, and
    additive edges are not monomials → 1.0 (left untouched).
    """
    from omai.representation.units import dimension_si_scale

    formula = op.formula
    if not isinstance(formula, sp.Eq):
        return 1.0
    rhs = formula.rhs

    # Make Sums transparent to their summands (units are sum-invariant).
    mono = rhs
    for s in list(mono.atoms(sp.Sum)):
        mono = mono.xreplace({s: s.function})

    # Transcendental function of any input, or additive structure → not a
    # pure-monomial contraction.
    if mono.atoms(sp.Function):
        return 1.0
    if isinstance(sp.expand(mono), sp.Add):
        return 1.0

    # Build base-name/symbol-name -> dimension for inputs and declared params.
    # Each input space contributes one IndexedBase, located via the existing
    # executor helper _find_input_indexed_atoms (the same mapping apply_edge uses).
    name_to_dim: dict[str, object] = {}
    for space in op.inputs:
        for a in _find_input_indexed_atoms(rhs, space):
            name_to_dim[str(a.base.name)] = space.fields[0].dimension
    for p in op.parameters:
        name_to_dim[p.name] = p.dimension

    # Net power of each base/symbol in the monomial.
    powers = mono.as_powers_dict()
    si_num = 1.0
    for base, exp in powers.items():
        if isinstance(base, sp.Indexed):
            nm = str(base.base.name)
        elif isinstance(base, sp.Symbol):
            nm = str(base.name)
        else:
            continue  # numeric coefficient
        if nm in name_to_dim:
            si_num *= dimension_si_scale(name_to_dim[nm]) ** int(exp)
        # else: counter / physics constant / dimensionless → excluded

    out_dim = op.outputs[0].fields[0].dimension
    return si_num / dimension_si_scale(out_dim)
```

Then apply it in `apply_edge`. Find where the result array is finalized (the block that builds `result_arr` and wraps it as the output Representation, near the end of `apply_edge`). Immediately before constructing the output `Representation`, insert:

```python
    # Dimensional reconciliation: rescale the raw canonical-unit contraction
    # into the output space's declared canonical unit (no-op for closed-form,
    # identity, and additive edges — see _dimensional_bridge).
    result_arr = result_arr * _dimensional_bridge(op)
```

(If the local variable holding the result is named differently, adapt — it is the numpy array produced by the final `lambdify` call that is then wrapped in the returned `Representation`.)

- [ ] **Step 4: Run the bridge tests**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_bridge.py -v`
Expected: PASS (all — monomial gate at 1.0 for closed-form/identity/sum, 1e22 for κ, 1e30 for volumetric Cv, 1.0 for molar Cv, and the end-to-end κ in W/(m·K)).

- [ ] **Step 5: REGRESSION GUARD — pre-existing executor tests unchanged**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor.py tests/test_executor_sum_general.py -v 2>&1 | tail -25`
Expected: ALL pass. Every closed-form edge (compute_heat_capacity, compute_free_energy, compute_entropy, compute_internal_energy), identity_dm, sum_linewidths, combine_kappa_wigner, and **contract_molar_heat_capacity** must produce the SAME values as before (their bridge is 1.0). If `contract_molar_heat_capacity`'s value changed, the bridge mis-fired — its bridge MUST be 1.0 (c is J/K, output J/(K·mol), both SI). **Do not modify these tests**; fix `_dimensional_bridge` if any regress.

Note: `test_executor_sum_general.py::test_general_sum_evaluates_cvF_tensor_contraction` currently expects the raw (pre-bridge) κ value. After this task the κ contraction is multiplied by 1e22. Update THAT ONE test's expected value to `... * 1e22` (it is testing the executor's own contraction, which now includes the bridge) — this is a legitimate expected-value update, not loosening. Leave all `test_executor.py` tests untouched.

- [ ] **Step 6: Full suite**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ -q 2>&1 | tail -4`
Expected: zero FAILED (Example B in `test_validation_engine_silicon.py` may now FAIL because it still applies a manual ×1e22 on top of the now-bridged result — that is fixed in Task 4. If it fails for exactly that reason (κ now 1e22× too large), proceed to Task 4; any OTHER failure must be fixed here.)

- [ ] **Step 7: Commit**

```bash
git add omai/representation/executor.py tests/test_executor_bridge.py tests/test_executor_sum_general.py
git commit -m "executor: monomial-gated dimensional bridge (kappa->1e22, volumetric Cv->1e30, closed-form->1.0)"
```

---

## Task 4: Drop the manual ×1e22 from Example B

**Files:**
- Modify: `tests/test_validation_engine_silicon.py`
- Modify: `experiments/silicon_tersoff/run_validation.py`

After Task 3 the executor produces κ in W/(m·K) directly, so the example's hand-applied `× 1e22` is now a double-count and must be removed.

- [ ] **Step 1: Remove ×1e22 from the test**

In `tests/test_validation_engine_silicon.py`, find `test_example_b_kappa_direct_matches_kaldo`. The framework κ is currently scaled by `1e22` before comparison (look for `1e22` or `* 1e22` applied to `result.representation.data` or `kappa`). Remove that factor so the comparison is the raw `result.representation.data` (now already in W/(m·K)) against kaldo's `kappa_inverse_tensor_WmK.npy`. Keep the `rel < 0.05` assertion. If the test imported/defined a `1e22` constant only for this, remove it.

- [ ] **Step 2: Remove ×1e22 from the driver**

In `experiments/silicon_tersoff/run_validation.py`, find `example_b()` where it prints the framework κ (a line applying `* 1e22` / `1e22`). Remove the `1e22` factor so it prints `np.trace(result.representation.data)/3.0` directly. Update the adjacent comment if it mentions the manual factor.

- [ ] **Step 3: Run Example B**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_validation_engine_silicon.py -v`
Expected: all pass — `test_example_b_kappa_direct_matches_kaldo` matches kaldo at the same ~3.9e-7 it did with the manual factor (now achieved automatically). If it's now off by 1e22 in either direction, the bridge/removal is inconsistent — investigate before proceeding.

- [ ] **Step 4: Run the driver to confirm the printed κ**

Run: `cd /mnt/data/Development/openmaterials-ai && PYTHONPATH=. python experiments/silicon_tersoff/run_validation.py`
Expected: Example B prints framework κ ≈ kaldo κ (both ~tens of W/m·K, matching). Report the two printed values.

- [ ] **Step 5: Commit**

```bash
git add tests/test_validation_engine_silicon.py experiments/silicon_tersoff/run_validation.py
git commit -m "validation engine: drop manual x1e22 from Example B; bridge now automatic"
```

---

## Task 5: Full suite, substrate-doc note, close

**Files:**
- Modify: `docs/operator_representation_substrate.tex`
- Modify: `docs/followups.md`

- [ ] **Step 1: Full suite**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ -q 2>&1 | tail -4`
Expected: zero FAILED. Report the summary line.

- [ ] **Step 2: Substrate-doc note**

In `docs/operator_representation_substrate.tex`, find the subsection `The validation engine: execute, compose, cross-check` (added previously). Append one paragraph at its end:

```latex
The executor reconciles units dimensionally: each dimension's canonical unit
carries an absolute SI scale, and when an operator's formula is a pure
contraction (a monomial in its input fields and declared parameters), the
executor rescales the raw canonical-unit result into the output's declared
canonical unit automatically. This is what lets the $\kappa_{\mathrm{LBTE}}$
contraction of Å/THz-canonical group velocity and mean free displacement with
an Å$^3$ cell volume emerge directly in $\mathrm{W/(m\cdot K)}$, with no
hand-applied conversion. Closed-form edges (whose constants already carry the
SI conversion) and additive edges are not monomials and are left untouched.
```

Rebuild the PDF: `cd /mnt/data/Development/openmaterials-ai/docs && pdflatex -interaction=nonstopmode -halt-on-error operator_representation_substrate.tex 2>&1 | tail -5` (run twice for the TOC; first run's exit code reports errors). Confirm exit 0 and a regenerated PDF.

- [ ] **Step 3: Update followups**

In `docs/followups.md`, find the "Validation engine (landed ...)" section and update the first follow-up bullet (the "κ-contraction unit reconciliation" one) to mark it resolved:

```markdown
- **κ-contraction unit reconciliation — RESOLVED (2026-05-29).** The executor
  now applies a monomial-gated dimensional bridge: each dimension's canonical
  unit carries an SI scale (`Unit.si_scale`, `dimension_si_scale`), and pure
  contraction edges are rescaled to the output's declared canonical unit
  automatically. κ → 1e22 and volumetric Cv → 1e30 emerge with no hand
  constants; Example B dropped its manual ×1e22. `V_cell` is now a typed
  VOLUME Parameter. See spec 2026-05-29-dimensional-reconciliation-design.md.
```

Leave the other follow-up bullets (group_velocities layout split, compute_dos) unchanged.

- [ ] **Step 4: Confirm only intended files staged**

Run `git status` and confirm only `docs/operator_representation_substrate.tex`, `docs/operator_representation_substrate.pdf`, `docs/followups.md` are staged (the `.aux/.log/.toc/.out` are gitignored).

- [ ] **Step 5: Commit**

```bash
git add docs/operator_representation_substrate.tex docs/operator_representation_substrate.pdf docs/followups.md
git commit -m "dimensional reconciliation: substrate-doc note + followups resolved"
```

- [ ] **Step 6: Final full-suite confirmation**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ -q 2>&1 | tail -3`
Expected: zero FAILED.

---

## Self-Review Notes (for the executor of this plan)

- **Spec coverage:** Component A → Task 1 (si_scale, units, helper); Component B → Task 1 (angstrom/angstrom_cubed/VOLUME); Component C → Task 2 (V_cell Parameter); Component D → Task 3 (monomial-gated bridge); Example B → Task 4; doc/criteria → Task 5.
- **Correction over the spec:** the V_cell Parameter is named `"V_{cell}"` (exact sympy symbol, with braces) not `"V_cell"` — the bridge keys parameter dimensions by symbol name, so the name must match the formula symbol.
- **The regression guard (Task 3 Step 5) is the load-bearing check:** every pre-existing `test_executor.py` edge must keep bridge=1.0 and unchanged values. Only `test_executor_sum_general.py::test_general_sum_evaluates_cvF_tensor_contraction` gets a legitimate `*1e22` expected-value update (it tests the executor's own κ contraction, which now includes the bridge).
- **Type consistency:** `dimension_si_scale(dim)` (Task 1) is used by `_dimensional_bridge(op)` (Task 3). `Unit.si_scale` (Task 1) read by `dimension_si_scale`. `Parameter("V_{cell}", VOLUME)` (Task 2) read by `_dimensional_bridge`'s `name_to_dim`. `_find_input_indexed_atoms` is an existing executor helper reused by `_dimensional_bridge`.
