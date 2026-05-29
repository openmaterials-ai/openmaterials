# Validation engine — operator-side execution, symbolic composition, redundancy cross-check

**Date**: 2026-05-20
**Scope**: turn the framework from "a substrate that *compares what codes claim*" into "a substrate that *runs calculations* and validates itself." Three capabilities over the existing operator DAG, unified by a validation report. No new operator states or edges; no binary invocation; the codes remain external oracles whose outputs are loaded as leaves.

## Why

Phase 1–2 built a typed operator DAG (46 spaces / 47 operators) with sympy formulas on every edge and per-code representation specs declaring units, normalizations, gauges, and schemes. The framework can *declare* what each code computes and *convert* between representations through the operator hub (star topology). What it cannot yet do is **run a calculation itself and check it against ground truth**. Without that, we cannot tell whether the operators (and the unit/normalization mapping) are actually correct — only that they are internally consistent.

The user's framing: the executor is a **validation engine**. The DAG is *over-determined* — there are more ways to reach a quantity than there are quantities. That redundancy is the validation signal: a correct framework + correct codes means every redundant route converges. Divergence localizes a bug to an edge.

## The two semantics, both executable

- **Operator semantics** — symbolic. The sympy formulas compose along a path into a single closed-form expression (`compose_path`, already in `omai/operator/compose.py`).
- **Representation semantics** — numerical. A code's emitted array, lifted to operator form, fed through the closed-form edges (`apply_edge`, already in `omai/representation/executor.py`).

The validation engine runs both and cross-checks them, and cross-checks redundant routes against each other.

## Three capabilities

### Capability 1 — numerical execution (`compute`)

Extend `omai/representation/executor.py`.

```python
Source = Representation | Callable[[], Representation]

@dataclass(frozen=True)
class TraceStep:
    kind: str            # "LOAD" | "LIFT" | "EXEC"
    space: str           # space.name produced by this step
    detail: str          # representation_name for LOAD/LIFT; operator.name for EXEC

@dataclass(frozen=True)
class ComputeResult:
    representation: Representation   # the target, in operator form
    trace: tuple[TraceStep, ...]

def compute(target: Space, sources: dict[str, Source]) -> ComputeResult:
    ...
```

Resolution is **lazy, recursive, memoized**:

```
resolve(space):
    if space.name in memo: return memo[space.name]
    if space.name in sources:
        rep = materialize(sources[space.name])      # call thunk if callable
        op_rep = to_operator(rep)                     # LIFT — unit×normalization applied here
        record LOAD + LIFT; memo and return op_rep
    op = producer_of(space)                           # the operator whose output is `space`
    if op is None:
        raise NoSourceError(space, candidates=...)    # name representations that could provide it
    inputs = [resolve(inp) for inp in op.inputs]      # recurse
    if op.is_executable_in_sympy:
        out = apply_edge(op, *inputs)                 # EXEC (operator-form in → operator-form out)
        record EXEC; memo and return out
    raise ExternalSolveRequired(op)                   # implicit edge with no registered source
```

- **Leaves** come from `sources` (loaded `.npy`, or any thunk). Lifting to operator form is where unit and normalization factors apply automatically — the "constraints embedded" property.
- **Internal nodes** are derived by executing their producing operator symbolically.
- **Implicit edges** (BTE solve, eigenvalue, NAC q→0) are `is_executable_in_sympy=False`; they must appear in `sources` or `compute` raises with a message naming the representations whose specs cover that space.
- **Multiple producers** (Pattern C: `compute_dos` vs `fourier_to_dos`; `identity_dm` vs `apply_nac_correction`): `producer_of` picks deterministically (declaration order in `EDGES`) and records the choice in the trace. Disambiguation override deferred (Capability 3 enumerates all producers explicitly instead).
- **Multi-output edges** (`compute_dispersion` → Frequency + Eigenvectors): `apply_edge` already raises `NotImplementedError`; for this iteration, multi-output spaces must be supplied as sources, not derived. (Single-output derivation only.)

### Capability 2 — symbolic composition + the executor's oracle

`compose_path(edges) -> sp.Expr` already exists. Add a thin bridge that makes a composed path **executable as one shot**:

```python
def compose_executable(edges: tuple[Operator, ...]) -> Operator:
    """Return a synthetic single-output Operator that runs through the
    SAME apply_edge as a primitive edge. Its formula is
    sp.Eq(terminal_LHS, compose_path(edges)) — i.e. the terminal edge's
    LHS paired with the composed RHS (compose_path returns the RHS
    expression only, so we re-attach the last edge's LHS). Its inputs
    are the chain's *leaf* spaces (inputs of the first edge that are not
    produced inside the chain); its output is the terminal edge's output
    space."""
```

This gives the engine's **self-oracle**: for any closed-form path, the composed-then-executed value (Capability 2) must equal the edge-by-edge value (Capability 1), because they are the same mathematics expressed two ways. Disagreement means a bug in `apply_edge` or `compose_path` — caught without any external reference.

### Capability 3 — typing-aware redundancy cross-check (`cross_check`)

New module `omai/representation/validation.py`.

```python
@dataclass(frozen=True)
class Route:
    label: str                       # human label, e.g. "kaldo-leaves" / "compute_dos"
    result: ComputeResult

@dataclass(frozen=True)
class ValidationReport:
    target: str                      # space.name
    routes: tuple[Route, ...]
    pairwise: tuple[PairVerdict, ...]   # (label_a, label_b, status, max_residual)
    def ok(self) -> bool: ...        # True iff every required-agreement pair agrees
    def render(self) -> str: ...     # pretty table

def cross_check(
    target: ObservableSpace | HiddenSpace,
    routes: dict[str, dict[str, Source]],   # label -> source set
    *, rtol: float = 1e-6, atol: float = 0.0,
) -> ValidationReport:
    ...
```

`cross_check` computes the target via each route (each its own `sources` dict — different codes per leaf = cross-code redundancy), then pairwise-compares results using the existing `compare_representations`. **Verdicts are governed by the target's typing:**

- target is an `ObservableSpace` → all routes must agree (status `EXPECTED_AGREE`); divergence is `UNEXPECTED_DISAGREE`, a real bug.
- target is a `HiddenSpace` → per-element agreement is not required (`NOT_COMPARABLE`); only its gauge-invariant contractions (which are Observables) carry an agree/disagree verdict.

This is the framework earning its keep: it doesn't ask "do these match," it asserts "these match *where the gauge discipline says they must*." The RTA-vs-direct κ divergence is *predicted* (RTA κ is a HiddenSpace), not flagged.

`ValidationReport.ok()` is True iff every required-agreement pair agrees, so examples can `assert report.ok()`.

## Data flow

```
.npy on disk ─▶ Source thunk ─▶ Representation (rep form)
   ─▶ to_operator()  [unit × normalization applied: the constraints]
   ─▶ operator-form Representation
   ─▶ apply_edge (symbolic edge)  ─▶ … ─▶ target (operator form)
trace records LOAD / LIFT / EXEC at each step
cross_check runs compute per route, feeds results to compare_representations,
assembles ValidationReport under the target's Observable/Hidden typing
```

## Worked examples

Both live in a new `experiments/silicon_tersoff/run_validation.py`, extending the `spec_demo.py` pattern (skip-on-missing-`.npy`).

### Example A — HeatCapacity chain (zero prerequisites)

All leaves already on disk.

- **Cap 1**: `sources = {Frequency: load(kaldo freq), Temperature: 300.0}`; `compute(MolarHeatCapacity, sources)` derives per-mode `HeatCapacity` (symbolic `compute_heat_capacity`) then contracts (symbolic `contract_molar_heat_capacity`).
- **Cap 2 (keystone)**: `compose_executable([compute_heat_capacity, contract_molar_heat_capacity])`, run once; assert equals the Cap-1 edge-by-edge result.
- **Cap 3 (across codes)**: route "kaldo" (Frequency from kaldo) vs route "phonopy" (Frequency from phonopy); `cross_check(MolarHeatCapacity, {...})` must agree (both reach the same Observable). Plus the triple check: both routes also agree with phonopy's *emitted* molar Cv (ground truth on disk).

The triple agreement — edge-by-edge = composed = phonopy's own Cv — is the single result that proves the engine.

### Example B — κ_LBTE chain (one kaldo re-run)

- **Prerequisite**: dump the per-mode mean free displacement from kaldo's direct-inverse `Conductivity` object (the BTE-solve output — kaldo exposes it as the conductivity's mean-free-path / lambda attribute; the implementation plan pins the exact attribute against the installed kaldo version) and run kaldo once. `F_qν` (MeanFreeDisplacement[direct]) is neither on disk today nor symbolically derivable (implicit edge), so it must be loaded.
- **Cap 1**: `sources = {GroupVelocity: load(kaldo), Frequency: load(kaldo), Temperature: 300.0, MeanFreeDisplacement[direct]: load(kaldo MFD)}`; `compute(ThermalConductivity[bte_solver=direct_inverse], sources)` derives `HeatCapacity` symbolically and runs `contract_kappa_direct`.
- **Validation**: compare the framework-contracted κ against kaldo's *emitted* `kappa_inverse_tensor` (on disk). Agreement proves `contract_kappa_direct` + the unit/normalization lifts are correct end-to-end.
- **Cap 3 (predicted divergence)**: also compute via `contract_kappa_rta` from MFD[rta] (if dumped) and show the report marks the RTA route `NOT_COMPARABLE`/diverging-by-design (HiddenSpace), not a bug.

## Files

- `omai/operator/compose.py` — add `compose_executable` (wraps existing `compose_path`).
- `omai/representation/executor.py` — add `compute`, `Source`, `TraceStep`, `ComputeResult`, `NoSourceError`; reuse `apply_edge`.
- `omai/representation/validation.py` — new: `Route`, `PairVerdict`, `ValidationReport`, `cross_check`.
- `experiments/silicon_tersoff/run_validation.py` — new: drives both examples, prints reports, asserts agreement.
- `experiments/silicon_tersoff/run_kaldo.py` — one `np.save` line for MeanFreeDisplacement.
- `tests/test_executor_compute.py` — `compute` on a synthetic 2-edge chain (no disk); error paths (missing source, implicit edge).
- `tests/test_symbolic_numeric_agreement.py` — the keystone: compose-executed == edge-by-edge, on synthetic + Example A data.
- `tests/test_redundancy_validation.py` — `cross_check` verdicts: Observable routes agree; HiddenSpace routes `NOT_COMPARABLE`.

## Error handling

- **No source and no producer for a space** → `NoSourceError(space, candidates)` where `candidates` lists representation names whose specs cover that space (read from the representation package), so the message says *who could supply it*.
- **Implicit edge with no source** → `ExternalSolveRequired(op)` (existing class), reused with a message pointing at the BTE-solve / eigenvalue boundary.
- **Multi-output space derivation** → `NotImplementedError`; must be supplied as a source this iteration.
- **Missing unit/normalization on a loaded leaf** → the existing `to_operator` path raises a clear KeyError naming the spec field to add. Unchanged.
- **Symbolic ≠ numeric** (Cap 2 keystone fails) → surfaced as a loud test failure with both values; this is the bug-catching path, not an error to swallow.

## Testing

- **Unit, no disk**: synthetic two-edge chain with literal-array sources exercises `compute` resolution, memoization on a diamond, and both error paths.
- **Keystone**: `compose_executable` == edge-by-edge on the synthetic chain and on Example A.
- **Integration, skip-on-missing**: Examples A and B as tests, mirroring `test_silicon_consolidation.py`'s skip-when-`.npy`-absent discipline. Example A needs no re-run; Example B skips until the MFD dump exists.
- **Redundancy verdicts**: a test that `cross_check` on an Observable target returns all-agree and on a HiddenSpace target returns `NOT_COMPARABLE`, confirming the typing drives the verdict.

## Out of scope (this spec)

- **Binary invocation** — codes stay external oracles; `Source` thunks load pre-computed arrays. A live-invoking thunk is admissible later with no core change, but is not built.
- **Across-path redundancy needing MD data** — PhononDOS via `compute_dos` vs `fourier_to_dos` needs an MD trajectory we don't have for Si. Architecture admits it; no demo this round.
- **Multi-output edge derivation** — supply such spaces as sources for now.
- **Path-cost ranking / automatic route discovery** — `cross_check` takes routes explicitly. Automatic enumeration of all redundant routes to a target is a follow-up.
- **Discretization-scheme mismatch detection across routes** — two codes on different q-meshes are not array-comparable; examples hold the mesh fixed (the existing Si-Tersoff 8×8×8). Cross-mesh interpolation is out of scope.

## Success criteria

- `compute(target, sources)` resolves single-output closed-form chains over the real DAG, lazily, with a correct trace.
- `compose_executable` runs and **equals** edge-by-edge `compute` on Example A (the keystone test passes).
- Example A: framework-derived MolarHeatCapacity agrees with phonopy's emitted molar Cv to ≤ 1e-6 relative; kaldo-Frequency and phonopy-Frequency routes agree.
- Example B (after the one kaldo re-run): framework-contracted κ_LBTE agrees with kaldo's emitted `kappa_inverse` to ≤ 1e-6 relative.
- `cross_check` verdicts honor Observable/HiddenSpace typing.
- `ValidationReport.render()` prints a legible route×residual table.
- Full suite stays green; new tests skip cleanly when `.npy` data is absent.

## Order

1. `compute` + `Source`/`Trace`/`ComputeResult` in executor.py; unit tests on synthetic chain.
2. `compose_executable` in compose.py; keystone test on synthetic chain.
3. `cross_check` + `ValidationReport` in validation.py; redundancy verdict test.
4. Example A in run_validation.py (zero prerequisites); integration test.
5. `run_kaldo.py` MFD dump + one kaldo re-run; Example B; integration test.
6. Run full suite; commit.
