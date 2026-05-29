# Dimensional reconciliation — automatic unit-bridge in the executor

**Date**: 2026-05-29
**Scope**: make the operator layer dimensionally coherent. When the executor contracts operator-form inputs whose canonical units don't form an SI-coherent system (Å, THz mixed with J/K, W/m·K), it must automatically reconcile the result against the output space's declared canonical unit — eliminating the hidden power-of-ten factors that currently must be applied by hand (κ's 1e22, volumetric Cv's 1e30).

## Why

The validation engine (spec `2026-05-20-validation-engine-design.md`) surfaced a systemic bug. Each `Unit` carries a `to_operator` multiplier *within its dimension*, and each dimension has a canonical unit (the one with `to_operator=1.0`). But those canonical choices are not mutually consistent under the operator formulas:

- `contract_kappa_direct`: `κ[α,β] = (1/(N_q·V_cell)) Σ_qν c[q,ν]·v[α,q,ν]·F[β,q,ν]`. Canonical inputs are c [J/K], v [Å·THz], F [Å], V_cell [Å³]. Their product is `(J/K)(Å·THz)(Å)/Å³ = J·THz/(K·Å) = 1e22 W/(m·K)`, but `ThermalConductivity`'s declared canonical unit is `W/(m·K)` (`to_operator=1.0`). So the executor emits a number that is 1e22× off from what its declared output unit claims. Example B patches this with a hand-applied `×1e22`.
- `contract_volumetric_heat_capacity`: `Σ c / (V_cell·N_q)` with c [J/K], V_cell [Å³] → `J/(K·Å³) = 1e30 J/(m³·K)` vs declared canonical `J/(m³·K)`. Same disease, latent (no test exercises it against a physical value).

The fix: give the operator layer a notion of each canonical unit's *absolute SI scale*, so the executor can derive the dimensional bridge from the contraction's input/parameter/output canonical units automatically. No hand-computed constants anywhere.

## Architecture

The operator layer stays unit-free at the *dimension* level; the SI scale lives on the representation-layer `Unit` (where physical scale already lives). The executor gains a bridge step: after computing the raw contraction number (in whatever the input canonical units multiply to), multiply by `bridge = (net SI scale of the summand's input/parameter canonical units) / (SI scale of the output's canonical unit)`.

Dimensional consistency is *assumed* (the operator formulas are dimensionally correct by construction); the bridge is a pure number that rescales the canonical-unit result into the output's declared canonical unit. This makes the operator layer a dimensionally-coherent theory — the foundation a future strict dimensional-exponent system (deferred) would build on.

## Components

### A. `si_scale` on canonical units (`omai/representation/units.py`)

Add a field to `Unit`: `si_scale: float | None = None` — the absolute SI value of this unit *when it is the canonical unit for its dimension*. Populate it on each dimension's canonical unit:

| Dimension | Canonical unit | `si_scale` (SI) | Reasoning |
|---|---|---|---|
| frequency | linear_THz | 1e12 | THz = 1e12 s⁻¹ |
| length | angstrom (NEW) | 1e-10 | Å = 1e-10 m |
| length_times_frequency | angstrom_linear_THz | 1e2 | Å·THz = 1e-10·1e12 = 1e2 m/s |
| energy_per_temperature | J_per_K | 1.0 | J/K is SI |
| energy_per_temperature_per_volume | J_per_m3_per_K | 1.0 | SI |
| energy_per_temperature_per_mole | J_per_K_per_mol | 1.0 | SI |
| thermal_conductivity | W_per_m_per_K | 1.0 | SI |
| volume | angstrom_cubed (NEW) | 1e-30 | Å³ = 1e-30 m³ |
| energy_per_mole | J_per_mol | 1.0 | SI |
| energy_per_length_cubed | eV_per_A3 | (see note) | not needed for the bridge unless an executable edge contracts it; set when first required |
| dimensionless | dimensionless | 1.0 | — |

Non-canonical units (angular_THz, eV_per_K, km_per_s, kJ_per_mol) keep `si_scale=None` — only the canonical unit per dimension needs it. A helper `dimension_si_scale(dim: Dimension) -> float` finds the dimension's canonical unit (the registered unit with `to_operator == 1.0`) and returns its `si_scale`, raising a clear error if the dimension has no canonical unit or no `si_scale` set.

### B. New typed quantities (`omai/operator/dimensions.py`, `omai/representation/units.py`)

- Add `LENGTH` canonical unit `angstrom` (dimension `length`, `to_operator=1.0`, `si_scale=1e-10`). (`length` dimension already exists; it had no unit.)
- Add a `VOLUME` dimension (`omai/operator/dimensions.py`) and canonical unit `angstrom_cubed` (`to_operator=1.0`, `si_scale=1e-30`).

### C. Type `V_cell` as a Parameter (`omai/thermal_transport/operator/edges.py`)

Declare `Parameter("V_cell", VOLUME)` on `contract_kappa_direct` and on `contract_volumetric_heat_capacity` (the two operators whose formulas reference `V_{cell}`). The caller still supplies the value through the existing `constants={"V_{cell}": <value in Å³>}` dict (Task 5's channel, unchanged). The executor maps the formula symbol `V_{cell}` to the declared Parameter to obtain its dimension → canonical unit → SI scale for the bridge. The symbol-name↔parameter-name mapping mirrors the existing LaTeX↔python conventions in the codebase (the Parameter is named `V_cell`; the formula symbol prints `V_{cell}`; the executor already sanitizes such names).

### D. The bridge, in `apply_edge` (`omai/representation/executor.py`)

**The bridge applies only to *pure-monomial contraction* edges**, and is a no-op (1.0) for everything else. This discriminator is the heart of the design's correctness — it cleanly separates the edges that multiply raw canonical-unit arrays (which need the bridge) from closed-form edges whose unit conversion is already done by physics constants (which must not be re-bridged).

**Applicability test.** Examine the RHS, treating each `Sum` as transparent to its summand (summing over a dimensionless index does not change units, so a base inside a Sum keeps power 1). The bridge applies iff the RHS is a **monomial** in the input Indexed-bases and declared-Parameter symbols: every such factor appears as a multiplicative term raised to an integer power (positive or negative), with no input/parameter wrapped in a transcendental function (`sin`, `sinh`, `exp`, `log`, …) and none appearing additively. Dimensionless counters (`N_q`, `N`) and physics constants (`ℏ`, `k_B`, `N_A`) are *excluded* from the monomial test and from the bridge — they are bound numerically and already carry their values in the result. If the RHS is not such a monomial, **bridge = 1.0**.

**Why this is correct per edge:**
- `contract_kappa_direct` — RHS is `c·v·F/(N_q·V_cell)`, a monomial in {c, v, F, V_cell} (N_q dimensionless, excluded). Bridge applies → 1e22.
- `contract_volumetric_heat_capacity` — RHS is `c/(V_cell·N_q)`, monomial in {c, V_cell}. Bridge applies → 1e30.
- `contract_molar_heat_capacity` — RHS is `N_A·c/N_q`, monomial in {c} (N_A, N_q excluded). Bridge applies, computes `dimension_si_scale(J/K)=1.0 / dimension_si_scale(J/(K·mol))=1.0 = 1.0`. No-op, correct (all inputs already SI).
- `identity_dm`, `sum_linewidths`, `combine_kappa_wigner` — same dimension in/out (and the linewidth/wigner ones are *sums*, not monomials). Bridge = 1.0.
- `compute_heat_capacity`, `compute_free_energy`, `compute_entropy`, `compute_internal_energy` — ω appears inside `sinh`/`log`/`exp`, and ℏ_eff/k_B (which carry the THz→SI conversion) are in the formula. Not a monomial in the inputs → bridge = 1.0. Correct: these are already SI because the constants did the bridging.

**Algorithm when the bridge applies:**
1. For each input space, take its field's dimension; for each declared Parameter referenced in the RHS, take its dimension.
2. Extract each factor's net integer power from the monomial (sympy: `sp.degree`/`as_powers_dict` on the RHS with the Sum replaced by its summand; positive for numerator, negative for denominator factors).
3. `input_si = ∏ dimension_si_scale(dim) ** power` over input/parameter factors.
4. `bridge = input_si / dimension_si_scale(output_field_dimension)`.
5. `result_arr = result_arr * bridge`.

> **Design note — the load-bearing distinction.** Closed-form edges (`compute_heat_capacity` et al.) already produce SI-correct output because the executor binds `ℏ_eff = h·1e12 J/(linear-THz)` and `k_B` in J/K — the *constants* absorb the THz→SI bridge inside the formula. Contraction edges (κ, volumetric/molar Cv) instead multiply raw canonical-unit arrays with no unit-absorbing constants, so they need the bridge. The monomial discriminator is exactly what separates the two cases structurally, and it lands on bridge=1.0 for every closed-form/identity/sum edge — which the pre-existing `tests/test_executor.py` enforces as the regression guard. If the monomial test ever misclassifies an edge (e.g. a future closed-form edge that happens to be a bare monomial but relies on a unit-bearing constant), the regression test for that edge fails loudly rather than silently rescaling.

## Data flow

```
apply_edge contracts inputs (canonical-unit arrays) → raw result (in input-canonical-unit product)
  → compute bridge = (∏ input/param canonical-unit SI^power) / (output canonical-unit SI)
  → result × bridge  (now in output's declared canonical unit)
  → wrap as operator-form Representation
```

## Error handling

- A dimension that appears in an executable contraction but has no canonical unit / no `si_scale` → `dimension_si_scale` raises a clear error naming the dimension and which unit/scale to add. (This is how we discovered `length` had no unit.)
- A formula symbol that is neither an input, a declared Parameter, a physics constant, a counter, nor dimensionless → the existing leftover-symbol check already raises; the bridge step runs after binding, so any un-dimensioned factor is caught.
- A closed-form/identity edge yielding bridge ≠ 1.0 → surfaces a real latent inconsistency; the implementation should make this loud (a failing regression test), not silent.

## Testing

- **Unit (no data files):**
  - `contract_kappa_direct` bridge == 1e22; full κ contraction on synthetic c/v/F/V_cell yields W/(m·K) matching `np.einsum(...)/(N_q·V_cell)·1e22` with NO caller-side factor.
  - `contract_volumetric_heat_capacity` bridge == 1e30; yields J/(m³·K) on synthetic c/V_cell.
  - `dimension_si_scale` returns the right scale per dimension; raises on a dimension with no canonical unit.
  - **Regression**: every edge in the pre-existing `tests/test_executor.py` (identity_dm, sum_linewidths, combine_kappa_wigner, contract_molar_heat_capacity, compute_heat_capacity, compute_free_energy, compute_entropy, compute_internal_energy) yields bridge=1.0 and unchanged results. This is the central guard.
- **Integration:** Example B (`tests/test_validation_engine_silicon.py`) drops its manual `×1e22`; the framework κ now equals kaldo's emitted κ directly. The `run_validation.py` example drops the `×1e22` too.

## Out of scope

- **Full dimensional-exponent system** (pint/astropy-style base-dimension vectors). The `si_scale` field is the foundation it would build on; deferred until the Lean work demands strict dimensional typing.
- **Promoting the `constants` channel to a typed value+unit supply** — V_cell is typed via a declared Parameter, but the supply dict stays raw (value in canonical Å³). Typed supply with unit validation is a future hardening.
- **`compute_dos` DiracDelta executability** — separate followup; not a dimensional issue.
- **`energy_per_length_cubed` (FC3) SI scale** — set only if/when an executable edge contracts FC3; not needed for κ or Cv.

## Success criteria

- `Unit` has an `si_scale`; canonical units for frequency, length, length_times_frequency, energy_per_temperature(+per_volume/per_mole), thermal_conductivity, volume, energy_per_mole, dimensionless carry it.
- `length` has a canonical unit; `volume` dimension + canonical unit exist.
- `V_cell` is a declared `Parameter(VOLUME)` on the two contraction edges; supplied via the unchanged `constants` dict.
- The executor applies the automatic bridge; κ → 1e22 and volumetric Cv → 1e30 emerge with no hand constants.
- Every closed-form/identity/per-mode edge yields bridge=1.0 (pre-existing `test_executor.py` unchanged and green).
- Example B passes with the `×1e22` removed.
- Full suite green.

## Order

1. `si_scale` field on `Unit` + `dimension_si_scale` helper; register `angstrom` (length) and `angstrom_cubed` (volume) units + `VOLUME` dimension; populate si_scale on canonical units. Unit tests for `dimension_si_scale`.
2. Declare `Parameter("V_cell", VOLUME)` on `contract_kappa_direct` and `contract_volumetric_heat_capacity`.
3. Bridge computation in `apply_edge` (power extraction from the summand; bridge=1.0 for closed-form/identity). Regression-guard against `test_executor.py` first, then the κ / volumetric-Cv bridge tests.
4. Drop the manual `×1e22` from Example B's test and `run_validation.py`; confirm κ matches kaldo directly.
5. Full suite; substrate-doc note that the operator layer is now dimensionally reconciled; commit.
