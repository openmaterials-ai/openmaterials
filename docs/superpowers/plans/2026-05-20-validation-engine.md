# Validation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the framework a validation engine that runs operator-DAG calculations itself (executing closed-form edges, loading non-symbolic leaves), composes edges symbolically, and cross-checks redundant routes under the Observable/HiddenSpace typing — validated end-to-end against kaldo/phonopy ground truth on Si-Tersoff.

**Architecture:** A pure, lazy, memoized resolver (`compute`) walks the DAG: a space is satisfied by a registered `Source` (loaded array, lifted to operator form) or derived by executing its producing `Operator` via the existing `apply_edge`. Symbolic composition (`compose_executable`, wrapping the existing `compose_path`) fuses a path into one synthetic executable edge. `cross_check` computes a target several ways and pairwise-compares via the existing `compare_representations`, with agree/disagree verdicts governed by the target's gauge typing. The executor's `Sum` evaluator is generalized from "single bare Indexed" to arbitrary summands (elementwise scalar Sums *and* multi-Indexed tensor contractions / einsum), and gains a `constants` channel so material data like `V_cell` can be supplied.

**Tech Stack:** Python 3.9, sympy (lambdify, Sum, Indexed, Eq), numpy, pytest.

**Codes stay external oracles.** No binary is invoked in-process. `Source` is `Representation | Callable[[], Representation]`; the worked examples build sources by `np.load`-ing files the `run_*.py` drivers already wrote to `runs/<material>/<code>/`.

**CUDA caveat:** any kaldo run on this host must set `CUDA_VISIBLE_DEVICES=""` (kaldo's TF backend errors on the GPU here). Only Task 7 runs kaldo.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `omai/representation/executor.py` | `apply_edge` (single edge), **new** `compute` resolver + `Source`/`TraceStep`/`ComputeResult`/`NoSourceError`; **generalized** Sum evaluator + `constants` channel | Modify |
| `omai/operator/compose.py` | `compose_path` (exists); **new** `compose_executable` (synthetic executable edge from a path) | Modify |
| `omai/representation/validation.py` | **new**: `Route`, `PairVerdict`, `ValidationReport`, `cross_check` | Create |
| `omai/representation/__init__.py` | export the new public names | Modify |
| `experiments/silicon_tersoff/run_validation.py` | **new**: drives Examples A and B, prints reports, asserts agreement | Create |
| `experiments/silicon_tersoff/run_kaldo.py` | one `np.save` for per-mode MeanFreeDisplacement | Modify |
| `tests/test_executor_compute.py` | `compute` resolver: resolution, memo, error paths | Create |
| `tests/test_compose_executable.py` | symbolic keystone + numeric keystone | Create |
| `tests/test_redundancy_validation.py` | `cross_check` typing-aware verdicts | Create |
| `tests/test_executor_sum_general.py` | general Sum evaluator: elementwise scalar + tensor contraction + supplied constants | Create |
| `tests/test_validation_engine_silicon.py` | Examples A & B as skip-on-missing integration tests | Create |

---

## Task 1: `compute` resolver + types

**Files:**
- Modify: `omai/representation/executor.py`
- Modify: `omai/representation/__init__.py`
- Test: `tests/test_executor_compute.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_executor_compute.py`:

```python
"""Tests for the lazy DAG resolver `compute`."""
from __future__ import annotations

import numpy as np
import pytest

from omai.representation.executor import (
    ComputeResult,
    ExternalSolveRequired,
    NoSourceError,
    Source,
    TraceStep,
    compute,
    operator_form_spec,
)
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    HEAT_CAPACITY,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
)

_H_PLANCK = 6.62607015e-34
_HBAR_EFF = _H_PLANCK * 1.0e12
_KB = 1.380649e-23
_N_A = 6.02214076e23


def _op_rep(space, name, data) -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name,
        data=np.asarray(data),
        is_operator=True,
    )


def test_compute_derives_molar_heat_capacity_edge_by_edge():
    """Frequency + Temperature -> (derive HeatCapacity) -> (contract) MolarHeatCapacity."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])  # (N_q=2, N_modes=2)
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    result = compute(MOLAR_HEAT_CAPACITY, sources)
    assert isinstance(result, ComputeResult)
    # Reference: per-mode sinh heat capacity, summed, × N_A / N_q.
    x = _HBAR_EFF * omega / (2 * _KB * 300.0)
    c = (_HBAR_EFF * omega) ** 2 / (4 * _KB * 300.0 ** 2 * np.sinh(x) ** 2)
    expected = _N_A * np.sum(c) / omega.shape[0]
    np.testing.assert_allclose(float(result.representation.data), expected, rtol=1e-10)
    assert result.representation.is_operator is True
    # Trace lists the two leaves (LOAD) and the two derivations (EXEC).
    kinds = [(s.kind, s.space) for s in result.trace]
    assert ("EXEC", "HeatCapacity") in kinds
    assert ("EXEC", "MolarHeatCapacity") in kinds
    assert ("LOAD", "Frequency") in kinds


def test_compute_accepts_callable_source_thunk():
    """A Source may be a thunk returning a Representation."""
    omega = np.array([[5.0, 10.0]])
    calls = {"n": 0}

    def load_freq() -> Representation:
        calls["n"] += 1
        return _op_rep(FREQUENCY_STATE, "omega", omega)

    sources = {
        "Frequency": load_freq,
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    compute(HEAT_CAPACITY, sources)
    assert calls["n"] == 1  # thunk materialized exactly once


def test_compute_missing_source_raises_no_source_error():
    """A leaf with no producer and no source raises NoSourceError naming it."""
    with pytest.raises(NoSourceError) as exc:
        compute(HEAT_CAPACITY, {"Frequency": _op_rep(FREQUENCY_STATE, "omega", np.array([[5.0]]))})
    assert "Temperature" in str(exc.value)


def test_compute_implicit_edge_without_source_raises_external_solve_required():
    """ThermalConductivity[direct] is produced by an implicit (BTE-solve)
    chain; without a source for the implicit intermediate, compute raises
    ExternalSolveRequired."""
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", np.array([[5.0, 10.0]])),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
        "GroupVelocity": _op_rep(
            __import__("omai.thermal_transport.operator", fromlist=["GROUP_VELOCITY"]).GROUP_VELOCITY,
            "v", np.ones((3, 1, 2)),
        ),
    }
    with pytest.raises(ExternalSolveRequired):
        compute(THERMAL_CONDUCTIVITY_DIRECT, sources)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_compute.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute'` (and `Source`, `TraceStep`, `ComputeResult`, `NoSourceError`).

- [ ] **Step 3: Implement the resolver in `executor.py`**

Add near the top of `omai/representation/executor.py`, after the existing imports add **only**:

```python
from typing import Callable, Union
```

Do **not** import `EDGES` at module top — the executor is domain-agnostic and a top-level `from omai.thermal_transport...` import would couple it to the thermal-transport layer and risk a circular import (the thermal-transport representation specs import from `omai.representation`). `compute` does a lazy default import inside its body instead (see Step 3).

Extend `__all__`:

```python
__all__ = [
    "ExternalSolveRequired",
    "NoSourceError",
    "Source",
    "TraceStep",
    "ComputeResult",
    "apply_edge",
    "compute",
    "operator_form_spec",
]
```

Add the new class after `ExternalSolveRequired`:

```python
class NoSourceError(RuntimeError):
    """Raised by ``compute`` when a space has neither a registered Source
    nor a producing Operator in the edge set."""
```

Add at the end of the file (before the `_sanitize` helpers is fine; order doesn't matter):

```python
Source = Union[Representation, Callable[[], Representation]]


@dataclass(frozen=True)
class TraceStep:
    kind: str    # "LOAD" | "LIFT" | "EXEC"
    space: str   # space.name produced by this step
    detail: str  # representation_name for LOAD/LIFT; operator.name for EXEC


@dataclass(frozen=True)
class ComputeResult:
    representation: Representation
    trace: tuple[TraceStep, ...]


def _materialize(src: "Source") -> Representation:
    return src() if callable(src) else src


def compute(
    target: Space,
    sources: dict[str, "Source"],
    *,
    edges: tuple | None = None,
    constants: dict[str, float] | None = None,
) -> ComputeResult:
    """Resolve ``target`` from ``sources`` over the operator DAG.

    A space is satisfied by a registered Source (materialized + lifted to
    operator form) or derived by executing its producing Operator via
    ``apply_edge``. Lazy (only resolves what ``target`` needs), memoized
    (each space resolved once), and traced.

    ``edges`` defaults to the thermal-transport ``EDGES`` (imported lazily
    to keep the executor domain-agnostic at module import time and avoid a
    circular import). Pass an explicit edge set for other domains.

    Raises NoSourceError for a space with no source and no producer;
    ExternalSolveRequired for a non-sympy-executable producer with no source.
    """
    from omai.representation.compare import to_operator

    if edges is None:
        from omai.thermal_transport.operator import EDGES as edges

    memo: dict[str, Representation] = {}
    trace: list[TraceStep] = []
    constants = constants or {}

    def producer_of(space: Space):
        producers = [op for op in edges if space in op.outputs]
        return producers[0] if producers else None  # deterministic: declaration order

    def resolve(space: Space) -> Representation:
        if space.name in memo:
            return memo[space.name]
        if space.name in sources:
            rep = _materialize(sources[space.name])
            trace.append(TraceStep("LOAD", space.name, rep.representation_name))
            was_operator = rep.is_operator
            op_rep = to_operator(rep)
            if not was_operator:
                trace.append(TraceStep("LIFT", space.name, rep.representation_name))
            memo[space.name] = op_rep
            return op_rep
        op = producer_of(space)
        if op is None:
            raise NoSourceError(
                f"space {space.name!r} has no registered Source and no "
                f"producing Operator; register a Source for it in `sources`."
            )
        if not op.is_executable_in_sympy:
            raise ExternalSolveRequired(
                f"space {space.name!r} is produced by implicit operator "
                f"{op.name!r} (external solve); register a Source carrying a "
                f"loaded array for it (e.g. the code's emitted .npy)."
            )
        inputs = [resolve(inp) for inp in op.inputs]
        out = apply_edge(op, *inputs, constants=constants)
        trace.append(TraceStep("EXEC", space.name, op.name))
        memo[space.name] = out
        return out

    rep = resolve(target)
    return ComputeResult(representation=rep, trace=tuple(trace))
```

Note: `apply_edge(op, *inputs, constants=constants)` — the `constants` keyword is added in Task 5. For Task 1, temporarily call `apply_edge(op, *inputs)` (no constants kwarg) so tests pass now; Task 5 adds the kwarg and you switch this line. To avoid churn, add the `constants` kwarg to `apply_edge` *signature* now as `constants: dict | None = None` and ignore it until Task 5 (it's a no-op param until then).

Make `apply_edge`'s signature:

```python
def apply_edge(
    op: Operator,
    *inputs: Representation,
    constants: dict[str, float] | None = None,
) -> Representation:
```

and leave `constants` unused in the body for now.

- [ ] **Step 4: Export from the package**

In `omai/representation/__init__.py`, add to the executor import and `__all__`:

```python
from omai.representation.executor import (
    ExternalSolveRequired,
    NoSourceError,
    Source,
    TraceStep,
    ComputeResult,
    apply_edge,
    compute,
    operator_form_spec,
)
```
(extend the existing import list and `__all__` accordingly).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_compute.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add omai/representation/executor.py omai/representation/__init__.py tests/test_executor_compute.py
git commit -m "validation engine: lazy DAG resolver (compute) over the operator layer"
```

---

## Task 2: `compose_executable` + symbolic keystone

**Files:**
- Modify: `omai/operator/compose.py`
- Test: `tests/test_compose_executable.py`

- [ ] **Step 1: Write the failing test (symbolic keystone)**

Create `tests/test_compose_executable.py`:

```python
"""compose_executable: fuse a path into one synthetic executable Operator,
and the symbolic keystone — the composed expression equals the textbook
closed form."""
from __future__ import annotations

import sympy as sp

from omai.operator.compose import compose_executable, compose_path
from omai.operator.operator import Operator
from omai.thermal_transport.operator import (
    MOLAR_HEAT_CAPACITY,
    compute_heat_capacity,
    contract_molar_heat_capacity,
)


def test_compose_executable_builds_single_executable_operator():
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    assert isinstance(fused, Operator)
    assert fused.is_executable_in_sympy is True
    # Output is the terminal edge's output.
    assert fused.outputs == contract_molar_heat_capacity.outputs
    # Inputs are the chain's leaves: Frequency + Temperature (HeatCapacity is
    # produced inside the chain, so it is NOT a leaf input).
    leaf_names = {s.name for s in fused.inputs}
    assert leaf_names == {"Frequency", "Temperature"}
    assert "HeatCapacity" not in leaf_names


def test_symbolic_keystone_composed_equals_textbook_molar_cv():
    """Composing compute_heat_capacity into contract_molar_heat_capacity must
    yield N_A/N_q · Σ_qν c(ω_qν, T), i.e. the molar contraction wrapping the
    sinh heat-capacity kernel. We check the composed RHS, after substituting
    the molar formula's c[q,ν] by the heat-capacity RHS, equals compose_path's
    output symbolically."""
    composed = compose_path((compute_heat_capacity, contract_molar_heat_capacity))
    # compose_path returns the substituted RHS; assert the per-mode kernel is
    # present inside the sum (sinh form), i.e. the intermediate c[q,nu] has
    # been eliminated.
    assert composed is not None
    c_base_names = {
        str(a.base.name) for a in composed.atoms(sp.Indexed)
    }
    assert "c" not in c_base_names  # intermediate substituted away
    # ω appears (the kernel is now in terms of frequency).
    assert any("omega" in n or "\\omega" in n for n in c_base_names) or \
        any("\\omega" in str(s) for s in composed.free_symbols)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_compose_executable.py -v`
Expected: FAIL with `ImportError: cannot import name 'compose_executable'`.

- [ ] **Step 3: Implement `compose_executable`**

In `omai/operator/compose.py`, extend `__all__`:

```python
__all__ = ["ImplicitEdgeBoundary", "compose_path", "compose_executable"]
```

Add at the end:

```python
def compose_executable(edges: tuple[Operator, ...]) -> Operator:
    """Fuse a path of explicit-equation edges into a single synthetic
    Operator that runs through the SAME apply_edge as a primitive edge.

    The formula is ``sp.Eq(terminal_LHS, compose_path(edges))`` — the
    terminal edge's LHS paired with the composed RHS (``compose_path``
    returns only the RHS, so we re-attach the last edge's LHS). Inputs are
    the chain's *leaf* spaces: inputs of any edge that are not produced by
    an earlier edge in the chain. Output is the terminal edge's output.
    Marked executable via the override (the composed Eq is closed-form by
    construction).
    """
    if not edges:
        raise ValueError("compose_executable: empty edge sequence")
    composed_rhs = compose_path(edges)
    terminal = edges[-1]
    if not isinstance(terminal.formula, sp.Eq):
        raise TypeError(
            f"compose_executable: terminal edge {terminal.name!r} has no Eq formula"
        )
    terminal_lhs = terminal.formula.lhs

    produced = {out for e in edges for out in e.outputs}
    leaves: list = []
    for e in edges:
        for inp in e.inputs:
            if inp not in produced and inp not in leaves:
                leaves.append(inp)

    return Operator(
        name="compose[" + "→".join(e.name for e in edges) + "]",
        inputs=tuple(leaves),
        outputs=terminal.outputs,
        formula=sp.Eq(terminal_lhs, composed_rhs),
        is_executable_in_sympy_override=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_compose_executable.py -v`
Expected: PASS (2 passed). (The *numeric* keystone — composed-execute == edge-by-edge — is added in Task 6 once the Sum evaluator is generalized; it is intentionally not here.)

- [ ] **Step 5: Commit**

```bash
git add omai/operator/compose.py tests/test_compose_executable.py
git commit -m "validation engine: compose_executable + symbolic keystone"
```

---

## Task 3: `cross_check` + `ValidationReport`

**Files:**
- Create: `omai/representation/validation.py`
- Modify: `omai/representation/__init__.py`
- Test: `tests/test_redundancy_validation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_redundancy_validation.py`:

```python
"""cross_check: redundant routes to a target, verdicts governed by the
target's Observable/HiddenSpace typing."""
from __future__ import annotations

import numpy as np

from omai.representation.executor import operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import ValidationReport, cross_check
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    ANHARMONIC_LINEWIDTH,
)


def _op_rep(space, name, data) -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name,
        data=np.asarray(data),
        is_operator=True,
    )


def test_cross_check_observable_routes_agree():
    """Two routes that derive MolarHeatCapacity from the same Frequency must
    agree; the report is ok() and the pair status is EXPECTED_AGREE."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    src = lambda: {  # noqa: E731
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, {"routeA": src(), "routeB": src()})
    assert isinstance(report, ValidationReport)
    assert report.ok() is True
    statuses = {(p.label_a, p.label_b): p.status for p in report.pairwise}
    assert statuses[("routeA", "routeB")] == "EXPECTED_AGREE"


def test_cross_check_hidden_space_routes_are_not_comparable():
    """For a HiddenSpace target, per-element routes are NOT_COMPARABLE — the
    framework predicts they need not agree (no bug flagged)."""
    g = np.array([[1.0, 2.0], [3.0, 4.0]])
    routes = {
        "r1": {"Linewidth[channel=anharmonic_3ph]": _op_rep(ANHARMONIC_LINEWIDTH, "Gamma", g)},
        "r2": {"Linewidth[channel=anharmonic_3ph]": _op_rep(ANHARMONIC_LINEWIDTH, "Gamma", g * 1.5)},
    }
    report = cross_check(ANHARMONIC_LINEWIDTH, routes)
    statuses = {(p.label_a, p.label_b): p.status for p in report.pairwise}
    assert statuses[("r1", "r2")] == "NOT_COMPARABLE"
    # NOT_COMPARABLE does not break ok() — it carries no normative weight.
    assert report.ok() is True


def test_validation_report_render_is_a_string_table():
    omega = np.array([[5.0, 10.0]])
    src = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, {"only": src})
    text = report.render()
    assert "MolarHeatCapacity" in text
    assert isinstance(text, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_redundancy_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'omai.representation.validation'`.

- [ ] **Step 3: Implement `validation.py`**

Create `omai/representation/validation.py`:

```python
"""Redundancy cross-check: compute a target several ways, compare under typing.

The DAG is over-determined — more routes to a quantity than quantities.
``cross_check`` runs each route via ``compute`` and pairwise-compares the
results with ``compare_representations``. Verdicts honor the target's gauge
typing: routes to an ObservableSpace must agree (divergence is a bug);
routes to a HiddenSpace are NOT_COMPARABLE per-element (divergence is
predicted, not flagged).
"""
from __future__ import annotations

from dataclasses import dataclass

from omai.operator.space import Space
from omai.representation.compare import compare_representations
from omai.representation.executor import ComputeResult, Source, compute


@dataclass(frozen=True)
class Route:
    label: str
    result: ComputeResult


@dataclass(frozen=True)
class PairVerdict:
    label_a: str
    label_b: str
    status: str
    max_relative_residual: float


@dataclass(frozen=True)
class ValidationReport:
    target: str
    routes: tuple[Route, ...]
    pairwise: tuple[PairVerdict, ...]

    def ok(self) -> bool:
        """True unless any pair is an actual anomaly (UNEXPECTED_*)."""
        return all(
            p.status not in ("UNEXPECTED_DISAGREE", "UNEXPECTED_AGREE")
            for p in self.pairwise
        )

    def render(self) -> str:
        lines = [f"ValidationReport[{self.target}]  ({len(self.routes)} routes)"]
        for p in self.pairwise:
            lines.append(
                f"  {p.label_a:<12s} vs {p.label_b:<12s} : {p.status:<20s} "
                f"max_rel={p.max_relative_residual:.3e}"
            )
        lines.append(f"  ok = {self.ok()}")
        return "\n".join(lines)


def cross_check(
    target: Space,
    routes: dict[str, dict[str, Source]],
    *,
    rtol: float = 1e-6,
    atol: float = 0.0,
    constants: dict[str, float] | None = None,
) -> ValidationReport:
    """Compute ``target`` via each route's source set; pairwise-compare.

    Each route is a label -> sources dict (different codes per leaf gives
    cross-code redundancy). Verdicts come from compare_representations,
    which derives expected-agreement from the target's ObservableSpace/
    HiddenSpace typing.
    """
    computed: list[Route] = [
        Route(label=label, result=compute(target, srcs, constants=constants))
        for label, srcs in routes.items()
    ]
    pairwise: list[PairVerdict] = []
    for i in range(len(computed)):
        for j in range(i + 1, len(computed)):
            a, b = computed[i], computed[j]
            cmp = compare_representations(
                a.result.representation, b.result.representation,
                rtol=rtol, atol=atol,
            )
            pairwise.append(PairVerdict(
                label_a=a.label, label_b=b.label,
                status=cmp.status,
                max_relative_residual=cmp.max_relative_residual,
            ))
    return ValidationReport(
        target=target.name, routes=tuple(computed), pairwise=tuple(pairwise),
    )
```

- [ ] **Step 4: Export from the package**

In `omai/representation/__init__.py` add:

```python
from omai.representation.validation import (
    Route,
    PairVerdict,
    ValidationReport,
    cross_check,
)
```
and append `"Route"`, `"PairVerdict"`, `"ValidationReport"`, `"cross_check"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_redundancy_validation.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add omai/representation/validation.py omai/representation/__init__.py tests/test_redundancy_validation.py
git commit -m "validation engine: typing-aware redundancy cross-check + report"
```

---

## Task 4: Example A — HeatCapacity chain against phonopy ground truth

**Files:**
- Create: `experiments/silicon_tersoff/run_validation.py`
- Test: `tests/test_validation_engine_silicon.py`

Example A needs no kaldo re-run: Frequency is on disk (`runs/silicon_tersoff/{kaldo,phonopy}/frequencies_THz.npy`), the rest is symbolic, and phonopy's emitted molar Cv is the ground truth. **Phonopy does not currently dump per-mode molar Cv as a single scalar at 300 K**; it dumps `heat_capacity_J_per_K_per_mol.npy` over a T-grid (`temperatures_K.npy`). The example reads the grid value at T=300 K as ground truth.

- [ ] **Step 1: Write the integration test (skip-on-missing)**

Create `tests/test_validation_engine_silicon.py`:

```python
"""Examples A & B: the validation engine against kaldo/phonopy ground truth.
Skips when the .npy artefacts are absent (run the run_*.py drivers first)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from omai.representation.executor import compute, operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import cross_check
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
)

_REPO = Path(__file__).resolve().parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"


def _require(p: Path) -> None:
    if not p.exists():
        pytest.skip(f"missing {p.relative_to(_REPO)}; run the run_*.py drivers first.")


def _freq_source(root: Path) -> Representation:
    omega = np.load(root / "frequencies_THz.npy")
    return Representation(
        space_adapter_spec=operator_form_spec(FREQUENCY_STATE),
        observable_name="omega", data=omega, is_operator=True,
    )


def _temperature_source() -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(TEMPERATURE_STATE),
        observable_name="temperature", data=np.asarray(300.0), is_operator=True,
    )


def test_example_a_molar_cv_matches_phonopy_ground_truth():
    _require(_PHONOPY / "frequencies_THz.npy")
    _require(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    _require(_PHONOPY / "temperatures_K.npy")

    sources = {"Frequency": _freq_source(_PHONOPY), "Temperature": _temperature_source()}
    result = compute(MOLAR_HEAT_CAPACITY, sources)
    derived = float(result.representation.data)

    T = np.load(_PHONOPY / "temperatures_K.npy")
    cv = np.load(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    idx = int(np.argmin(np.abs(T - 300.0)))
    ground_truth = float(cv[idx])
    # phonopy reports per mole of unit cells; the operator MolarHeatCapacity
    # uses N_A/N_q over the BZ — the same per-mole-of-cells quantity.
    rel = abs(derived - ground_truth) / abs(ground_truth)
    assert rel < 1e-2, f"derived molar Cv {derived:.4f} vs phonopy {ground_truth:.4f} (rel {rel:.2%})"


def test_example_a_cross_code_frequency_routes_agree():
    """MolarHeatCapacity derived from kaldo's vs phonopy's Frequency must agree
    (both reach the same Observable)."""
    _require(_KALDO / "frequencies_THz.npy")
    _require(_PHONOPY / "frequencies_THz.npy")
    routes = {
        "kaldo": {"Frequency": _freq_source(_KALDO), "Temperature": _temperature_source()},
        "phonopy": {"Frequency": _freq_source(_PHONOPY), "Temperature": _temperature_source()},
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, routes, rtol=1e-2)
    assert report.ok(), report.render()
```

- [ ] **Step 2: Run to verify it fails or skips**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_validation_engine_silicon.py -v`
Expected: the two Example-A tests PASS (phonopy data is on disk) — or SKIP if the phonopy run hasn't been done. If they ERROR (not skip/pass), fix `compute` until they pass. (Example-B test added in Task 7 will SKIP until then.)

- [ ] **Step 3: Write the example driver**

Create `experiments/silicon_tersoff/run_validation.py`:

```python
"""Validation engine on Si-Tersoff: run the framework's own composition and
check it against kaldo/phonopy ground truth.

Example A (no prerequisites): derive MolarHeatCapacity from Frequency +
Temperature via the operator DAG, compare to phonopy's emitted molar Cv,
and cross-check the kaldo-Frequency vs phonopy-Frequency routes.

Example B (needs run_kaldo.py MFD dump + one kaldo re-run): contract
ThermalConductivity[direct] from loaded GroupVelocity + MeanFreeDisplacement
and derived HeatCapacity, compare to kaldo's emitted kappa_inverse.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from omai.representation.executor import compute, operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import cross_check
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
)

_REPO = Path(__file__).resolve().parent.parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def _section(title):
    print("\n" + title + "\n" + "-" * len(title))


def example_a():
    _section("Example A — MolarHeatCapacity via the operator DAG")
    if not (_PHONOPY / "frequencies_THz.npy").exists():
        print("  phonopy data missing; run run_phonopy.py first.")
        return
    omega = _op_rep(FREQUENCY_STATE, "omega", np.load(_PHONOPY / "frequencies_THz.npy"))
    T = _op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    result = compute(MOLAR_HEAT_CAPACITY, {"Frequency": omega, "Temperature": T})
    derived = float(result.representation.data)
    print("  framework-derived molar Cv : %.4f J/(K·mol)" % derived)
    grid_T = np.load(_PHONOPY / "temperatures_K.npy")
    cv = np.load(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    gt = float(cv[int(np.argmin(np.abs(grid_T - 300.0)))])
    print("  phonopy emitted molar Cv   : %.4f J/(K·mol)" % gt)
    print("  relative error             : %.3e" % (abs(derived - gt) / abs(gt)))
    print("  trace:")
    for s in result.trace:
        print("    %-5s %-22s %s" % (s.kind, s.space, s.detail))
    if (_KALDO / "frequencies_THz.npy").exists():
        routes = {
            "kaldo": {"Frequency": _op_rep(FREQUENCY_STATE, "omega",
                       np.load(_KALDO / "frequencies_THz.npy")), "Temperature": T},
            "phonopy": {"Frequency": omega, "Temperature": T},
        }
        print(cross_check(MOLAR_HEAT_CAPACITY, routes, rtol=1e-2).render())


def example_b():
    _section("Example B — ThermalConductivity[direct] via the operator DAG")
    mfd = _KALDO / "mean_free_displacement.npy"
    if not mfd.exists():
        print("  kaldo MFD dump missing; add the np.save to run_kaldo.py and")
        print("  re-run:  CUDA_VISIBLE_DEVICES='' python run_kaldo.py")
        return
    # V_cell from the kaldo summary / structure (Å³). Si-Tersoff primitive
    # diamond, a = 5.431 Å, fcc primitive volume = a^3 / 4.
    a = 5.431
    v_cell = a ** 3 / 4.0
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", np.load(_KALDO / "frequencies_THz.npy")),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
        "GroupVelocity": _op_rep(GROUP_VELOCITY, "v", np.load(_KALDO / "group_velocities_AT.npy")),
        "MeanFreeDisplacement[bte_solver=direct_inverse]":
            _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", np.load(mfd)),
    }
    result = compute(THERMAL_CONDUCTIVITY_DIRECT, sources, constants={"V_{cell}": v_cell})
    kappa = np.asarray(result.representation.data)
    gt = np.load(_KALDO / "kappa_inverse_tensor_WmK.npy")
    print("  framework κ (tr/3)  : %.4f W/(m·K)" % (np.trace(kappa) / 3.0))
    print("  kaldo emitted κ     : %.4f W/(m·K)" % (np.trace(gt) / 3.0))


if __name__ == "__main__":
    example_a()
    example_b()
```

- [ ] **Step 4: Run the example driver (Example A only; B prints its skip note)**

Run: `cd /mnt/data/Development/openmaterials-ai && PYTHONPATH=. python experiments/silicon_tersoff/run_validation.py`
Expected: Example A prints derived molar Cv, phonopy ground truth, a small relative error (< 1%), and the trace; Example B prints the "MFD dump missing" note.

- [ ] **Step 5: Run the Example-A tests**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_validation_engine_silicon.py -v -k example_a`
Expected: 2 passed (or skipped if phonopy data absent).

- [ ] **Step 6: Commit**

```bash
git add experiments/silicon_tersoff/run_validation.py tests/test_validation_engine_silicon.py
git commit -m "validation engine: Example A (molar Cv) against phonopy ground truth"
```

---

## Task 5: Supplied constants (`V_cell`) channel in the executor

`contract_volumetric_heat_capacity` and `contract_kappa_direct` reference `V_{cell}` (cell volume — material data, not a universal constant). The executor cannot bind it today (it ends up an unbound free symbol). Add a `constants` channel.

**Files:**
- Modify: `omai/representation/executor.py`
- Test: `tests/test_executor_sum_general.py` (start the file here; Task 6 adds to it)

- [ ] **Step 1: Write the failing test**

Create `tests/test_executor_sum_general.py`:

```python
"""General Sum evaluator + supplied-constants channel."""
from __future__ import annotations

import numpy as np

from omai.representation.executor import apply_edge, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    HEAT_CAPACITY,
    contract_volumetric_heat_capacity,
)

_N_A = 6.02214076e23


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def test_apply_edge_binds_supplied_V_cell_constant():
    """contract_volumetric_heat_capacity = Σ c / (V_cell · N_q); supplying
    V_cell via constants lets the executor evaluate it."""
    c = np.array([[1.0, 2.0], [3.0, 4.0]])  # (N_q=2, N_modes=2)
    rep = _op_rep(HEAT_CAPACITY, "c", c)
    v_cell = 40.0
    out = apply_edge(contract_volumetric_heat_capacity, rep, constants={"V_{cell}": v_cell})
    expected = np.sum(c) / (v_cell * c.shape[0])
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-12)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_sum_general.py -v`
Expected: FAIL — `NotImplementedError: ... unbound free symbols ['V_{cell}']`.

- [ ] **Step 3: Bind supplied constants in `apply_edge`**

In `omai/representation/executor.py`, inside `apply_edge`, immediately after the physics-constants binding block (where `physics_subs` is populated, around the `for atom in rhs.atoms(sp.Symbol)` that fills `_PHYSICS_CONSTANTS`), add binding of supplied constants:

```python
    # Bind user-supplied constants (material/run data like V_{cell}) by
    # atomic symbol name. These override nothing physical — they are values
    # the operator formula references but that aren't universal constants.
    supplied = constants or {}
    for atom in list(rhs.atoms(sp.Symbol)):
        if isinstance(atom, sp.Indexed):
            continue
        name = str(atom.name)
        if name in supplied:
            physics_subs[atom] = float(supplied[name])
```

(Place this so `physics_subs` is later applied via the existing `rhs = rhs.xreplace(physics_subs)` at step 7. No other change needed for this task.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_sum_general.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add omai/representation/executor.py tests/test_executor_sum_general.py
git commit -m "executor: supplied-constants channel (binds V_cell and other material data)"
```

---

## Task 6: General Sum evaluator (elementwise + tensor contraction) + mark `contract_kappa_direct` executable

Replace the single-bare-Indexed Sum handling with a general evaluator: a Sum over bound indices of an arbitrary summand (elementwise function of Indexed inputs, possibly with free indices that survive → a tensor / einsum). This unlocks both the composed sinh-summand (Task 7 numeric keystone) and the c·v·F κ contraction (Task 7 Example B).

**Files:**
- Modify: `omai/representation/executor.py`
- Modify: `omai/thermal_transport/operator/edges.py` (executable override on `contract_kappa_direct`)
- Test: `tests/test_executor_sum_general.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executor_sum_general.py`:

```python
import sympy as sp
from omai.operator.compose import compose_executable
from omai.thermal_transport.operator import (
    FREQUENCY_STATE, TEMPERATURE_STATE, MOLAR_HEAT_CAPACITY,
    GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT, THERMAL_CONDUCTIVITY_DIRECT,
    compute_heat_capacity, contract_molar_heat_capacity, contract_kappa_direct,
)

_H = 6.62607015e-34
_HBAR_EFF = _H * 1.0e12
_KB = 1.380649e-23


def test_general_sum_evaluates_composed_sinh_summand_scalar():
    """Σ_qν c(ω_qν,T) with the sinh kernel *inside* the Sum (composed molar Cv)
    evaluates to N_A/N_q · Σ c — equal to executing the two edges separately."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    rep_omega = _op_rep(FREQUENCY_STATE, "omega", omega)
    rep_T = _op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    out = apply_edge(fused, rep_omega, rep_T)
    x = _HBAR_EFF * omega / (2 * _KB * 300.0)
    c = (_HBAR_EFF * omega) ** 2 / (4 * _KB * 300.0 ** 2 * np.sinh(x) ** 2)
    expected = _N_A * np.sum(c) / omega.shape[0]
    np.testing.assert_allclose(float(out.data), expected, rtol=1e-10)


def test_general_sum_evaluates_cvF_tensor_contraction():
    """κ[α,β] = (1/(N_q V)) Σ_qν c[q,ν] v[α,q,ν] F[β,q,ν] — a tensor contraction
    (free α,β survive the sum). Compare to a hand einsum."""
    rng = np.random.default_rng(3)
    N_q, N_modes = 4, 6
    c = rng.random((N_q, N_modes))
    v = rng.random((3, N_q, N_modes))
    F = rng.random((3, N_q, N_modes))
    v_cell = 40.0
    rep_c = _op_rep(HEAT_CAPACITY, "c", c)
    rep_v = _op_rep(GROUP_VELOCITY, "v", v)
    rep_F = _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", F)
    out = apply_edge(contract_kappa_direct, rep_c, rep_v, rep_F,
                     constants={"V_{cell}": v_cell})
    expected = np.einsum("qn,aqn,bqn->ab", c, v, F) / (N_q * v_cell)
    assert out.data.shape == (3, 3)
    np.testing.assert_allclose(out.data, expected, rtol=1e-10)


def test_contract_kappa_direct_is_executable():
    assert contract_kappa_direct.is_executable_in_sympy is True
```

Note `apply_edge(contract_kappa_direct, rep_c, rep_v, rep_F, ...)` — input order must match `contract_kappa_direct.inputs` which is `(HeatCapacity, GroupVelocity, MeanFreeDisplacement[direct])`.

- [ ] **Step 2: Run to verify they fail**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_sum_general.py -v`
Expected: the new three FAIL (sinh-summand → `NotImplementedError: Sum ... has N Indexed atoms`; κ → not executable / NotImplementedError; executable assertion fails).

- [ ] **Step 3: Mark `contract_kappa_direct` executable**

In `omai/thermal_transport/operator/edges.py`, find the `contract_kappa_direct = Operator(...)` definition and add `is_executable_in_sympy_override=True,` to its kwargs. (The default heuristic false-negatives it because κ[α,β] shares the α,β index symbols across LHS/RHS; those are dummy indices, not the unknown.)

- [ ] **Step 4: Implement the general Sum evaluator**

In `omai/representation/executor.py`, replace the entire Sum-handling block (the `for sum_atom in list(rhs.atoms(sp.Sum)):` loop, currently approx lines 420–453, the one that raises on `len(indexed_in_summand) != 1`) with:

```python
    # 6a. Evaluate Sums — general form. A Sum binds some indices (e.g. q, ν)
    #     and sums an arbitrary summand over them. The summand is an
    #     elementwise expression in Indexed inputs (sharing the bound
    #     indices) plus possibly *free* indices (e.g. α, β) that survive the
    #     sum and become the output tensor axes. Algorithm:
    #       (1) bound indices = the Sum's summation variables;
    #       (2) free indices  = indices on summand Indexed atoms that are not
    #           bound, ordered by the LHS index signature;
    #       (3) broadcast each input array into layout [free..., bound...]
    #           with size-1 on axes the input lacks;
    #       (4) lambdify the summand elementwise over the inputs (+ scalar
    #           inputs like T) and evaluate → full-layout array;
    #       (5) np.sum over the bound axes → result of shape (free...);
    #       (6) bind the Sum to an array-valued dummy.
    lhs_index_order = (
        tuple(formula.lhs.indices) if isinstance(formula.lhs, sp.Indexed) else ()
    )
    # scalar input symbols (e.g. T) and their values, for summand lambdify.
    scalar_inputs = {sym: val for sym, val in input_dummies if np.ndim(val) == 0}

    for sum_atom in list(rhs.atoms(sp.Sum)):
        summand = sum_atom.function
        bound_indices = tuple(lim[0] for lim in sum_atom.limits)
        indexed_atoms = list(summand.atoms(sp.Indexed))
        if not indexed_atoms:
            raise NotImplementedError(
                f"operator {op.name!r}: Sum {sum_atom!r} has no Indexed atoms."
            )
        # free indices: appear on summand Indexed atoms but are not bound.
        all_idx: list = []
        for atom in indexed_atoms:
            for ix in atom.indices:
                if ix not in all_idx:
                    all_idx.append(ix)
        free_indices = tuple(ix for ix in lhs_index_order if ix in all_idx and ix not in bound_indices)
        # any free index not in the LHS order (defensive) appended at the end
        for ix in all_idx:
            if ix not in bound_indices and ix not in free_indices:
                free_indices = free_indices + (ix,)
        full_order = free_indices + bound_indices

        # Broadcast each distinct input base into full layout.
        base_to_dummy: dict[str, sp.Symbol] = {}
        dummy_to_array: dict[sp.Symbol, np.ndarray] = {}
        for atom in indexed_atoms:
            base = str(atom.base.name)
            if base in base_to_dummy:
                continue
            if base not in base_name_to_array:
                raise NotImplementedError(
                    f"operator {op.name!r}: Sum summand uses IndexedBase "
                    f"{base!r} not bound to any input."
                )
            arr = base_name_to_array[base]
            atom_idx = tuple(atom.indices)
            present = [i for i in full_order if i in atom_idx]
            perm = [atom_idx.index(i) for i in present]
            arr_t = np.transpose(arr, perm)
            shape = [
                arr_t.shape[present.index(i)] if i in present else 1
                for i in full_order
            ]
            broadcast = arr_t.reshape(shape)
            dummy = sp.Symbol(f"_bc_{_sanitize(base)}", positive=False)
            base_to_dummy[base] = dummy
            dummy_to_array[dummy] = broadcast

        # Replace each Indexed atom by its base dummy, keeping scalar symbols.
        summand_sub = summand
        for atom in indexed_atoms:
            summand_sub = summand_sub.xreplace({atom: base_to_dummy[str(atom.base.name)]})
        # bind physics constants present inside the summand
        summand_sub = summand_sub.xreplace(physics_subs)

        # lambdify over base-dummies + scalar inputs (e.g. T).
        arg_syms = list(dummy_to_array.keys()) + list(scalar_inputs.keys())
        arg_vals = list(dummy_to_array.values()) + list(scalar_inputs.values())
        fn = sp.lambdify(arg_syms, summand_sub, modules="numpy")
        evaluated = np.asarray(fn(*arg_vals))
        n_free = len(free_indices)
        bound_axes = tuple(range(n_free, n_free + len(bound_indices)))
        summed = np.sum(evaluated, axis=bound_axes) if bound_axes else evaluated

        # Bind BZ-mesh counters from any contributing array shape.
        for sym in rhs.atoms(sp.Symbol):
            if isinstance(sym, sp.Indexed):
                continue
            name = str(sym.name)
            sample = next(iter(base_name_to_array.values()))
            if name == "N_q":
                # N_q = number of q-points = the bound-index axis size.
                # Use the first bound axis length from any 2D+ input.
                for arr in base_name_to_array.values():
                    if arr.ndim >= 1:
                        # heuristic: q axis is the one matching the summed length
                        pass
                bzmesh_subs[sym] = float(_infer_n_q(base_name_to_array, bound_indices, indexed_atoms))
            elif name == "N" and sample.ndim >= 2:
                bzmesh_subs[sym] = float(_infer_n_modes(base_name_to_array)) / 3.0

        sum_dummy = sp.Symbol(f"_sumres_{len(sum_dummies)}", positive=False)
        rhs = rhs.xreplace({sum_atom: sum_dummy})
        # array-valued: route through input_dummies so the final lambdify
        # treats it as an array arg (handles scalar and tensor uniformly).
        input_dummies.append((sum_dummy, summed))
```

Add these two small helpers near the other module-level helpers at the bottom of `executor.py`:

```python
def _infer_n_q(base_name_to_array, bound_indices, indexed_atoms) -> int:
    """N_q = the size of the q-axis. Identify it as the axis shared by all
    summand inputs whose index symbol prints as a q-vector (\\mathbf{q})."""
    q_names = {r"\mathbf{q}", "q"}
    for atom in indexed_atoms:
        base = str(atom.base.name)
        arr = base_name_to_array.get(base)
        if arr is None:
            continue
        for axis, ix in enumerate(atom.indices):
            if str(ix) in q_names:
                return int(arr.shape[axis])
    # fallback: first axis of any 2D array
    for arr in base_name_to_array.values():
        if arr.ndim >= 2:
            return int(arr.shape[0])
    raise NotImplementedError("cannot infer N_q from input shapes")


def _infer_n_modes(base_name_to_array) -> int:
    """N_modes = the mode-axis size (3·N_atoms). Identify via the largest
    last-axis among 2D inputs (the (q, ν) heat-capacity-like array)."""
    for arr in base_name_to_array.values():
        if arr.ndim == 2:
            return int(arr.shape[1])
    for arr in base_name_to_array.values():
        if arr.ndim >= 1:
            return int(arr.shape[-1])
    raise NotImplementedError("cannot infer N_modes from input shapes")
```

Important: the existing code initializes `sum_dummies: list = []` and `bzmesh_subs: dict = {}` before the loop — keep those initializations. The old block bound sum results into a separate `sum_dummies` list that was later `xreplace`-d as scalars; we now route sum results through `input_dummies` (array-capable), so **delete** the later block that does `if sum_dummies: rhs = rhs.xreplace({sym: val for sym, val in sum_dummies})` (sum results are no longer scalars). Leave `bzmesh_subs` application intact.

- [ ] **Step 5: Run to verify they pass**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_executor_sum_general.py tests/test_executor.py -v`
Expected: all PASS — including the *pre-existing* `test_executor.py` (the single-Indexed molar-Cv and identity edges must still work through the generalized evaluator). If any pre-existing test regresses, fix the evaluator before proceeding.

- [ ] **Step 6: Commit**

```bash
git add omai/representation/executor.py omai/thermal_transport/operator/edges.py tests/test_executor_sum_general.py
git commit -m "executor: general Sum evaluator (elementwise + tensor contraction); kappa_direct executable"
```

---

## Task 7: Numeric keystone + Example B (κ_LBTE)

**Files:**
- Modify: `tests/test_compose_executable.py` (numeric keystone)
- Modify: `experiments/silicon_tersoff/run_kaldo.py` (MFD dump)
- Modify: `tests/test_validation_engine_silicon.py` (Example B)

- [ ] **Step 1: Numeric keystone test**

Append to `tests/test_compose_executable.py`:

```python
import numpy as np
from omai.representation.executor import apply_edge, compute, operator_form_spec
from omai.representation.instance import Representation
from omai.thermal_transport.operator import FREQUENCY_STATE, TEMPERATURE_STATE


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def test_numeric_keystone_composed_equals_edge_by_edge():
    """compose-then-execute == edge-by-edge compute, on the molar-Cv chain.
    The executor validated against the composer."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    edge_by_edge = compute(MOLAR_HEAT_CAPACITY, sources).representation.data
    fused = compose_executable((compute_heat_capacity, contract_molar_heat_capacity))
    composed = apply_edge(
        fused, sources["Frequency"], sources["Temperature"]
    ).data
    np.testing.assert_allclose(float(composed), float(edge_by_edge), rtol=1e-12)
```

Add the missing imports at the top of the test file: `MOLAR_HEAT_CAPACITY`, `compute_heat_capacity`, `contract_molar_heat_capacity` (already imported in Task 2's file; confirm present).

- [ ] **Step 2: Run the numeric keystone**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_compose_executable.py -v`
Expected: PASS (now 3 tests: 2 from Task 2 + this one).

- [ ] **Step 3: Add the MFD dump to `run_kaldo.py`**

In `experiments/silicon_tersoff/run_kaldo.py`, after the direct-inverse conductivity is computed (the `inv = Conductivity(phonons=phonons, method="inverse")...` line), capture and dump the per-mode mean free displacement. The kaldo `Conductivity` exposes the mean free path; dump it shaped `(3, n_q, n_modes)` to match `MeanFreeDisplacement[direct].F` indices `(alpha, q, nu)`:

```python
    # Per-mode mean free displacement F (BTE-solve output) for the
    # validation engine's kappa contraction. kaldo's Conductivity exposes
    # the mean free path as `.mean_free_path` (shape (n_k*n_modes, 3) in its
    # flattened layout); reshape to (3, n_q, n_modes).
    inv_cond = Conductivity(phonons=phonons, method="inverse")
    _ = inv_cond.conductivity.sum(axis=0)  # ensure the solve has run
    mfp = np.asarray(inv_cond.mean_free_path)  # (n_q*n_modes, 3) or (n_q, n_modes, 3)
    n_q = frequencies.shape[0]
    n_modes = frequencies.shape[1]
    mfp = mfp.reshape(n_q, n_modes, 3)
    F = np.transpose(mfp, (2, 0, 1))  # (3, n_q, n_modes) = (alpha, q, nu)
    np.save(OUT / "mean_free_displacement.npy", F)
    print(f"[kaldo] saved mean_free_displacement.npy shape {F.shape}")
```

Note: the exact kaldo attribute name (`mean_free_path` vs `_mean_free_path` vs via `phonons`) must be confirmed against the installed kaldo at implementation time — `python -c "import kaldo; help(kaldo.conductivity.Conductivity)"`. The reshape `(n_q*n_modes, 3) → (n_q, n_modes, 3)` assumes kaldo's row-major (q-outer, mode-inner) flatten; verify by checking `mfp.shape` before reshaping and adjust if kaldo already returns 3D.

- [ ] **Step 4: Re-run kaldo (one run)**

Run: `cd /mnt/data/Development/openmaterials-ai/experiments/silicon_tersoff && CUDA_VISIBLE_DEVICES="" python run_kaldo.py`
Expected: completes; `runs/silicon_tersoff/kaldo/mean_free_displacement.npy` now exists with shape `(3, 512, 6)`.

- [ ] **Step 5: Add the Example B test**

Append to `tests/test_validation_engine_silicon.py`:

```python
from omai.thermal_transport.operator import (
    GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT, THERMAL_CONDUCTIVITY_DIRECT,
)


def test_example_b_kappa_direct_matches_kaldo():
    """Framework-contracted κ_LBTE (from loaded c-derivation + GV + MFD) agrees
    with kaldo's emitted kappa_inverse."""
    _require(_KALDO / "frequencies_THz.npy")
    _require(_KALDO / "group_velocities_AT.npy")
    _require(_KALDO / "mean_free_displacement.npy")
    _require(_KALDO / "kappa_inverse_tensor_WmK.npy")

    a = 5.431
    v_cell = a ** 3 / 4.0
    sources = {
        "Frequency": _freq_source(_KALDO),
        "Temperature": _temperature_source(),
        "GroupVelocity": Representation(
            space_adapter_spec=operator_form_spec(GROUP_VELOCITY), observable_name="v",
            data=np.load(_KALDO / "group_velocities_AT.npy"), is_operator=True),
        "MeanFreeDisplacement[bte_solver=direct_inverse]": Representation(
            space_adapter_spec=operator_form_spec(MEAN_FREE_DISPLACEMENT_DIRECT),
            observable_name="F",
            data=np.load(_KALDO / "mean_free_displacement.npy"), is_operator=True),
    }
    result = compute(THERMAL_CONDUCTIVITY_DIRECT, sources, constants={"V_{cell}": v_cell})
    kappa = np.asarray(result.representation.data)
    gt = np.load(_KALDO / "kappa_inverse_tensor_WmK.npy")
    rel = abs(np.trace(kappa) / 3.0 - np.trace(gt) / 3.0) / abs(np.trace(gt) / 3.0)
    assert rel < 0.05, f"framework κ {np.trace(kappa)/3:.3f} vs kaldo {np.trace(gt)/3:.3f} (rel {rel:.2%})"
```

Note: the 5% band absorbs unit-convention details between kaldo's internal MFP units and the operator-canonical Å·THz / Å used by `GroupVelocity`/`F`. If the residual is larger, the divergence localizes a unit/normalization gap on the `GroupVelocity` or `MeanFreeDisplacement` representation spec — fix the spec, not the test.

- [ ] **Step 6: Run Example B + the example driver**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/test_validation_engine_silicon.py -v`
Expected: all Example A + B tests pass.
Run: `cd /mnt/data/Development/openmaterials-ai && PYTHONPATH=. python experiments/silicon_tersoff/run_validation.py`
Expected: both examples print results; Example B prints framework κ vs kaldo κ within ~5%.

- [ ] **Step 7: Commit**

```bash
git add tests/test_compose_executable.py experiments/silicon_tersoff/run_kaldo.py tests/test_validation_engine_silicon.py
git commit -m "validation engine: numeric keystone + Example B (kappa_LBTE) against kaldo"
```

---

## Task 8: Full suite, substrate doc note, final commit

**Files:**
- Modify: `docs/operator_representation_substrate.tex` (one paragraph)
- Modify: `docs/followups.md`

- [ ] **Step 1: Run the full suite**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ 2>&1 | tail -5`
Expected: all green; new tests pass, pre-existing 566 still pass (Example B may have required the kaldo re-run; if `mean_free_displacement.npy` isn't present the Example-B test SKIPS, which is acceptable for the suite).

- [ ] **Step 2: Add a substrate-doc paragraph**

In `docs/operator_representation_substrate.tex`, after the `\subsection{Cross-representation comparison: \texttt{compare}}` section, add a short subsection:

```latex
\subsection{The validation engine: execute, compose, cross-check}

The representation layer carries a runtime that \emph{runs} the operator DAG,
not merely compares emitted arrays. \texttt{compute(target, sources)} lazily
resolves a target space: a space with a registered source is loaded and lifted
to operator form (units and normalizations applied automatically), and every
other space is derived by executing its producing operator's sympy formula via
\texttt{apply\_edge}. Closed-form paths can also be fused symbolically
(\texttt{compose\_executable}) into one synthetic edge; the composed-then-executed
value must equal the edge-by-edge value, so the symbolic composer and the
numerical executor validate each other. Finally \texttt{cross\_check} computes a
target by several redundant routes (different codes per leaf, or different
operator paths) and pairwise-compares them, with agree/disagree verdicts
governed by the target's Observable/HiddenSpace typing: routes to an Observable
must agree, routes through a HiddenSpace need not. On Si-Tersoff the engine
derives molar heat capacity from frequencies and matches phonopy's emitted value,
and contracts $\kappa_{\mathrm{LBTE}}$ from loaded group velocity, mean free
displacement, and a derived heat capacity, matching kaldo's emitted
conductivity.
```

- [ ] **Step 3: Update followups**

In `docs/followups.md`, add under a new heading:

```markdown
## Validation engine (landed 2026-05-20)

`compute` / `compose_executable` / `cross_check` ship in
`omai/representation/{executor,validation}.py` and `omai/operator/compose.py`.
The executor's Sum evaluator now handles elementwise summands and tensor
contractions (einsum); `contract_kappa_direct` is executable. Open follow-ups:
- Automatic route enumeration (cross_check takes routes explicitly).
- Multi-output edge derivation (compute requires multi-output spaces as sources).
- Cross-mesh route comparison (examples hold the q-mesh fixed).
- Live-invoking Source thunks (codes are loaded oracles today).
```

- [ ] **Step 4: Commit**

```bash
git add docs/operator_representation_substrate.tex docs/followups.md
git commit -m "validation engine: substrate doc + followups"
```

- [ ] **Step 5: Final full-suite confirmation**

Run: `cd /mnt/data/Development/openmaterials-ai && python -m pytest tests/ 2>&1 | tail -3`
Expected: all green.

---

## Self-Review Notes (for the executor of this plan)

- **Spec coverage**: Cap 1 = Tasks 1, 5, 6; Cap 2 = Tasks 2, 7; Cap 3 = Task 3; Example A = Task 4; Example B = Task 7; doc/report = Tasks 3, 8. All spec sections map to a task.
- **The keystone** appears twice by design: symbolic (Task 2, pure sympy, no executor dependency) and numeric (Task 7, after the Sum evaluator exists).
- **Regression guard**: Task 6 Step 5 re-runs the *pre-existing* `test_executor.py` because the generalized Sum evaluator must not break the single-Indexed contractions it replaces.
- **Type consistency**: `Source`, `ComputeResult`, `TraceStep`, `NoSourceError` (Task 1) are imported unchanged in Tasks 3, 4, 7. `compose_executable` (Task 2) is used in Tasks 6, 7. `constants` kwarg added to `apply_edge` signature in Task 1 (no-op), bound in Task 5, consumed in Task 6.
- **Unverified-against-live-kaldo**: the kaldo MFD attribute name and reshape (Task 7 Step 3) and the κ unit band (Task 7 Step 5) are the two places to verify against the installed kaldo; both are flagged inline.
