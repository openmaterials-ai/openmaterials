# Skill: ingest an external code into the representation layer

**Goal.** Given an external materials-science code (kaldo, phono3py, ShengBTE,
LAMMPS, Quantum ESPRESSO, …), produce a Python module of `StateAdapterSpec`
and `OperationAdapterSpec` instances that pin the code's outputs and
parameters to the operator DAG, so that `compare()` between this code and any
other already-ingested code returns `EXPECTED_AGREE` on the appropriate
Observables.

**Prerequisites.**
- The operator DAG (`omai.operator`, plus a domain instance like
  `omai.thermal_transport.operator`) already declares the relevant States and
  Operations. If a state the code emits has no operator counterpart, that is
  out of scope for this skill — file it as a substrate-extension task.
- At least one reference adapter for the same domain is already ingested
  (kaldo and phono3py for thermal transport). The reference adapters are
  the ground truth against which the new one is validated.
- The external code's authoritative documentation is readable from the
  workspace (README, user manual, source).

## Procedure

### 0. Working rules (apply throughout)

Two rules learned the hard way during prior ingestions; check yourself
against them before each spec decision.

- **Grep before classifying as "out of scope."** Before declaring that a
  code does not expose a given state, run a literal grep across the
  code's source for the obvious API names (e.g. `phase_space`, `dos`,
  `gruneisen`). Several states that an initial reading of the docs
  missed turned out to have a clean public API one or two commits deep
  (kaldo's `Phonons.phase_space`, kaldo's `plotter.plot_dos`, phonopy's
  `PhonopyGruneisen.get_gruneisen()`). A `git grep` in the cloned repo
  is the cheapest authoritative check.

- **Leaves before intermediates.** Prioritize specs for leaf states of
  the operator DAG (DAG outputs — quantities downstream of *all*
  computations: κ, C_V, DOS, Grüneisen, P3). They drive the
  visualization's hide-vs-dash decision and are the cross-code
  comparable observables. Intermediate states (DM, eigenvectors, MFD)
  are scaffolding; their adapter specs can stay implicit (dashed in the
  viewer) until a comparison call actually needs them.

### 1. Read the code's own documentation

Read in order of authoritativeness:

1. The repo's `README.md` (often documents inputs, outputs, units).
2. The user manual or formal docs site.
3. The source headers where output files are written. Search for filenames
   you expect to find in the docs; the surrounding code reveals what's
   actually being written, in what unit, and with what convention.

Catalog, in note form:
- **Every output file or returned array** the code can produce that
  corresponds to a quantity in the operator DAG.
- For each: its declared unit, shape, indexing (e.g. "irreducible wedge"
  vs "full grid"), and any qualifiers ("scattering rate" vs "linewidth" vs
  "imaginary self-energy" — these differ by factors of 1, 2, or 4π).

### 2. Map outputs → operator States

For each operator State in the DAG, find the code's corresponding output (if
any). Record:

| operator State | code's output | shape | per-mode / per-q / contracted |

If the code does not expose a per-mode form of an Observable but only a
contracted one (e.g. `BTE.cv` is volumetric J/m³K, not per-mode J/K),
**skip writing a `StateAdapterSpec` for that state**. The skill does not
silently invent missing data. Note the gap in the adapter module's
docstring.

### 3. Extract unit and convention values

For each mapping:

- **Unit.** Check whether the unit already exists in
  `omai/representation/units.py`. If not, add it with a clear
  `to_canonical` factor. Watch the canonical dimensions — heat capacity
  per mode (`J/K`) is *different* from volumetric heat capacity
  (`J/m³K`); the latter cannot share a Unit table entry with the former.
- **State-level conventions.** Look at the State's declared
  `conventions` field in the operator-layer node module. For each
  declared convention, decide which value applies. If the code uses a
  value not in the declared options, the operator layer needs an extra
  convention value, not an ad-hoc override — handle it as a substrate
  edit.
- **Algorithmic conventions on producing Operations.** Each Operation
  declares its canonical `algorithmic_conventions` (e.g.
  `symmetry_group`, `broadening_param`, `bte_solver`). For each, decide
  the code's value:
  - `symmetry_group`: most codes use `spglib_auto`. A code with no
    symmetry reduction uses `C1`.
  - `broadening_param`: `stdev` (canonical), `halfwidth`, or a code-
    specific scheme like `adaptive_scaled`.
  - `bte_solver`: `rta`, `direct_inverse`, or a parameterized identity
    realization (e.g. kaldo's `sc` is iterative SCF — same canonical
    `direct_inverse`, different algorithm).
- **Discretization choices.** Diagnostic only — record on the
  `OperationAdapterSpec.discretization_choices` dict. Examples:
  `bz_summation`, `linear_solver`, `delta_cutoff_sigmas`.

### 4. Write the adapter module

Create `omai/thermal_transport/represented/<code>.py` with one
`StateAdapterSpec` per ingested state and one `OperationAdapterSpec` per
algorithmic-convention-bearing operation. Match the existing
`kaldo.py` / `phono3py.py` template:

- File docstring: code's role, links, output-file mapping table.
- One block per spec, named `<CODE>_<STATE>` in upper snake case.
- Notes that cite the specific code API call or file used.
- Notes that name the corresponding kaldo/phono3py file/quantity so a
  reader can cross-check.

### 5. Wire it in

- Re-export in `omai/thermal_transport/represented/__init__.py`.
- Note: `visualize.py` is currently hard-coded for K and P badges; adding
  a third code requires a small refactor to that module to make it
  generic. **Do this last and as a separate step.**

### 6. Validate via `compare()`

Write at least three smoke tests in `tests/test_<code>.py`:

1. **Unit factor**: synthetic identical-physics data in the new code's
   units and a reference's units, after applying the spec-derived factor,
   `compare()` returns `EXPECTED_AGREE`.
2. **Convention factor**: where applicable (e.g. a 2× or 4π factor
   between the new code and the reference), the spec captures it.
3. **HiddenState contraction**: per-element compare returns
   `NOT_COMPARABLE`; sum-contraction returns `EXPECTED_AGREE` on the
   reference data.

If any returns `UNEXPECTED_DISAGREE`, *do not lower rtol*. Find the
missing convention.

## Pitfalls observed during ingestion

These are recurring traps; check each one explicitly while writing specs.

- **Angular vs linear frequency.** rad/ps = angular_THz = 2π × linear_THz.
  Codes that quote frequencies "in THz" rarely state which.
- **Compounding factors.** Watch for cases where a unit *and* a
  convention both differ between two codes. The cross-code factor
  multiplies, and the result can look like a single mystery factor.
  *Worked example:* ShengBTE Linewidth (angular_THz, 2× Im Σ) vs
  phono3py Linewidth (linear_THz, 1× Im Σ) gives a 1/(4π) factor —
  1/(2π) from units and 1/2 from convention. If you write a quick
  cross-code test against a reference and the residual is mysteriously
  off by a factor of "about 0.08" or "about 12.5", that's 1/(4π) or 4π;
  resist the urge to add a fudge factor — there is a convention you
  haven't declared.
- **Linewidth vs scattering rate vs imaginary self-energy.** Three names,
  factors of 1, 2, and possibly 4π apart. Look for the formula
  `Γ = … Im Σ` in the docs or source. Codes that emit "scattering rates
  in ps⁻¹" are typically expressing the same number ShengBTE does (2× Im
  Σ in angular frequency).
- **Per-mode vs integrated quantities.** A code may expose only the
  T-integrated form of an observable that the operator DAG declares
  per-mode. Don't fake the per-mode form. Skip the spec.
- **"Direct inverse" vs "iterative" BTE solvers.** Both can realize the
  canonical `bte_solver=direct_inverse` identity (same fixed point,
  different algorithm). Distinguish on the `OperationAdapterSpec`
  via `discretization_choices`, not as a different state.
- **Default symmetry.** Most codes apply spglib reduction by default;
  kaldo (stable) is the exception. Record explicitly — don't assume.
- **Irreducible wedge vs full grid output.** Affects array shape; record
  on the StateAdapterSpec note.
- **g/mol vs amu for masses, eV/Å² vs Ry/au² for force constants, nm vs
  Å for lattice vectors.** Common cross-code unit traps.
- **Force-constant unit conventions silently differ between codes that
  nominally use the same unit.** Phono3py's `fc3.npy` and ShengBTE's
  `FORCE_CONSTANTS_3RD` are both documented as "eV/Å³", but ingesting
  phono3py's array verbatim into ShengBTE gives κ ≈ 100× too small (the
  characteristic signature of FC3 values ≈ 10× too large, since
  Γ ∝ |V₃|² ∝ fc3² and κ ∝ 1/Γ). The empirical factor 0.1 reconciles
  them; the root cause is a per-distance vs per-displacement scaling
  difference in phono3py's internal representation that we have not yet
  fully traced through the source. **Always verify a freshly-ingested
  code against an already-trusted code on the same material before
  trusting a single-code run** — otherwise convention-mismatch errors of
  this magnitude can hide in plain sight. The Si-Tersoff cross-code
  agreement check in `experiments/silicon_shengbte/` is the worked
  example.

## Worked example: ShengBTE ingestion (2026-05)

For a concrete walkthrough of this procedure on a real code, see
`omai/thermal_transport/represented/shengbte.py` and the companion
tests in `tests/test_shengbte.py`. Notable decisions made during that
ingestion:

- **Skipped HeatCapacity** because ShengBTE exposes only `BTE.cv`
  (volumetric J/m³K), not a per-mode form. Recorded the gap in the
  adapter docstring.
- **Added `KM_PER_S = Unit(...)`** to `units.py` with `to_canonical = 10.0`
  (1 km/s = 10 Å·THz). This kind of one-line additions to `units.py` is
  routine — most codes drop a single new unit.
- **`compute_force_constants_*` is upstream.** ShengBTE reads FC2/FC3
  from files written by another code (phonopy or QE for harmonic,
  thirdorder.py for cubic). The op-adapter `symmetry_group` value
  therefore reflects the upstream code's choice. Note this in the spec.
- **κ_CONV ≠ direct_inverse algorithm, but = direct_inverse canonical.**
  ShengBTE iterates F = F_RTA + correction until κ stops changing;
  phono3py uses a LAPACK pseudo-inverse; kaldo's `inverse` uses
  scipy.linalg.solve. All three converge to the same linearized-BTE
  solution, so they share `bte_solver=direct_inverse`. The distinction
  goes on `discretization_choices.linear_solver`.
- **broadening_param=adaptive_scaled** is a new convention value the
  ShengBTE ingestion needed. (kaldo uses `halfwidth`, phono3py `stdev`;
  ShengBTE's adaptive Gaussian doesn't reduce to either.) If a new
  convention *value* arises, add it as an override on the
  OperationAdapterSpec — no operator-layer change required. If a new
  convention *name* arises, that *is* a operator-layer edit.

## What this skill explicitly does *not* do

- It does not write code that calls the external program. Adapter specs
  describe outputs after the code has run; a separate ingestion
  function takes those outputs and wraps them as `Representation`
  instances.
- It does not modify the operator DAG. New nodes/edges or new
  conventions on existing nodes are substrate work, not adapter work.
- It does not refactor `visualize.py`. That's a known follow-up.
