# Phase 2 P3 — MD-based κ paths

**Date**: 2026-05-18
**Parent**: `docs/superpowers/specs/2026-05-17-phase2-md-design.md`
**Scope**: close the MD half of the κ map by adding the three canonical MD-based κ paths — Green-Kubo (from HeatCurrentACF), NEMD (direct / Müller-Plathe), and HNEMD (homogeneous-NEMD driving force) — as Pattern-A `transport_model` variants of `ThermalConductivity`. LAMMPS adapter spec for Green-Kubo and NEMD; GPUMD adapter spec for Green-Kubo and HNEMD.

## What's new on the operator layer

### New states (3)

| State | Kind | Producing edge | Notes |
|---|---|---|---|
| `ThermalConductivity[transport_model=green_kubo]` | **Observable** | `contract_kappa_green_kubo` | Green-Kubo κ from time-integrated heat-flux autocorrelation. Gauge-invariant (a time-correlation of a tensor observable, integrated to a steady state). |
| `ThermalConductivity[transport_model=nemd]` | **Observable** | `contract_kappa_nemd` | Non-equilibrium MD κ from imposed temperature gradient (or imposed heat flux à la Müller-Plathe). Steady-state observable; gauge-invariant once finite-size and ensemble corrections converge. |
| `ThermalConductivity[transport_model=hnemd]` | **Observable** | `contract_kappa_hnemd` | Homogeneous-NEMD κ from imposed driving force F_e applied uniformly across the cell. Gauge-invariant in the linear-response limit (small F_e). |

All three are **Pattern A** terminals on the `transport_model` axis: same `physics_type=THERMAL_CONDUCTIVITY`, same field signature `kappa[alpha, beta]`, different `type_parameters={"transport_model": "..."}`.

### New edges (3)

| Edge | Inputs | Output | Notes |
|---|---|---|---|
| `contract_kappa_green_kubo` | `HeatCurrentACF`, `Temperature` | `ThermalConductivity[transport_model=green_kubo]` | Classical Green-Kubo: κ_αβ = V/(k_B T²) ∫₀^∞ Jcorr_αβ(τ) dτ. Parameters: `tau_max` (integration upper bound, in time), `tau_min` (lower bound, optional — often 0). |
| `contract_kappa_nemd` | `HeatCurrent`, `Temperature` | `ThermalConductivity[transport_model=nemd]` | NEMD: κ = J_z / (dT/dz). `algorithmic_conventions`: `nemd_method ∈ {direct_two_reservoir, muller_plathe, ehex}`. Parameters: `imposed_flux` (Müller-Plathe variant) or `imposed_gradient` (direct method). |
| `contract_kappa_hnemd` | `HeatCurrent`, `Temperature` | `ThermalConductivity[transport_model=hnemd]` | HNEMD: κ_αβ = ⟨J_α⟩ / (T·V·F_e^β) in the linear-response limit. Parameters: `driving_force_magnitude`, `driving_direction` (β). |

### Sympy formulas

Each edge carries a sympy formula matching the output field's `(α,β)` indices:

- `contract_kappa_green_kubo`:
  `κ[α,β] = V/(k_B T²) · ∫₀^{τ_max} Jcorr[α,β,τ] dτ`
- `contract_kappa_nemd`:
  `κ[α,β] = -⟨J[α]⟩ / ∂_β T  (schematic; β-direction encoded by the imposed gradient axis)`
- `contract_kappa_hnemd`:
  `κ[α,β] = ⟨J[α]⟩ / (T · V · F_e[β])`

## Adapter coverage

### `lammps` adapter (extend)

- `LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO` (StateAdapterSpec): output is the κ tensor read from `fix ave/correlate`'s integrated output (or post-processed offline from the dumped J(t)).
- `LAMMPS_CONTRACT_KAPPA_GREEN_KUBO` (OperationAdapterSpec): drives the integration; LAMMPS exposes the autocorrelate machinery but the time integral is usually post-processed (numpy.trapz on `hac.out`-equivalent).
- `LAMMPS_THERMAL_CONDUCTIVITY_NEMD` (StateAdapterSpec): output of a Müller-Plathe run, post-processed from the binned temperature profile and the swap-rate-derived flux.
- `LAMMPS_CONTRACT_KAPPA_NEMD` (OperationAdapterSpec): `fix thermal/conductivity` (Müller-Plathe) drives the simulation; κ is computed offline from the resulting steady state.
- HNEMD: not native to LAMMPS — declare as **Not Exposed** in the LAMMPS module (with an explanation; the canonical HNEMD code is GPUMD).

### `gpumd` adapter (extend)

- `GPUMD_THERMAL_CONDUCTIVITY_GREEN_KUBO` (StateAdapterSpec): produced by post-integrating `hac.out` (which GPUMD also writes as `kappa.out` in the running average via the `compute_hac` keyword's accumulated thermal conductivity column).
- `GPUMD_CONTRACT_KAPPA_GREEN_KUBO` (OperationAdapterSpec): wraps the implicit κ time integration GPUMD performs while writing `hac.out`.
- `GPUMD_THERMAL_CONDUCTIVITY_HNEMD` (StateAdapterSpec): the cornerstone of GPUMD's thermal-transport work. Output is `kappa.out` from `compute_hnemd`.
- `GPUMD_CONTRACT_KAPPA_HNEMD` (OperationAdapterSpec): `compute_hnemd <output_interval> <Fe_x> <Fe_y> <Fe_z>` keyword; driving force is applied homogeneously.
- NEMD: GPUMD doesn't have a canonical NEMD fix in the LAMMPS sense — declare as **Not Exposed** in the GPUMD module (with a pointer to using HNEMD or LAMMPS for the same observable).

## Tests (smoke)

- `tests/test_md_kappa_paths.py` (new) — for each of the three new states, assert producing edge identity, inputs, output. For each new edge, assert it carries a sympy formula with the right LHS index count (2: α, β) and the declared parameters / algorithmic conventions are present.
- Cross-code: assert that `ThermalConductivity[transport_model=...]` exists for *all five* transport_model values (lbte, wigner, qhgk, green_kubo, nemd, hnemd) — actually six counting all of them.
- Adapter coverage: assert LAMMPS has specs for green_kubo + nemd; GPUMD has specs for green_kubo + hnemd; both have **Not Exposed** comments for the missing third.
- Update `test_node_count` to 46 and `test_edge_count` to 47 (gain 3 states + 3 edges).

## Substrate doc updates

- Counts: 43/44 → 46/47.
- Extend the "MD-primitive tier" paragraph in §"The operator DAG" to note: "and from this tier the three MD-based κ contractions (Green-Kubo from HeatCurrentACF, NEMD and HNEMD from time-averaged HeatCurrent) close the cross-paradigm κ map."
- Add three bullets in the edge list:
  - `contract_kappa_green_kubo` — V/(k_B T²) ∫₀^∞ Jcorr_αβ(τ) dτ; parameters `tau_max`, `tau_min`.
  - `contract_kappa_nemd` — κ = J_z/(dT/dz); `nemd_method` convention selects direct two-reservoir vs. Müller-Plathe.
  - `contract_kappa_hnemd` — κ_αβ = ⟨J_α⟩/(T·V·F_e^β); the GPUMD signature method.
- The κ-distribution section gets a one-line cross-reference: "Cumulative κ (P1) is currently defined only on the BTE side; MD-side cumulative κ via the cross-correlation cumulant is out of scope for P3."

## Out of scope (this spec)

- **NEMD finite-size scaling** (κ ∝ 1/(1/N + 1/N₀)) — a real correction the user must apply to make NEMD κ comparable to bulk κ; modelled as a downstream Phase-3 capability.
- **Spectrally-resolved κ** (κ(ω) via the heat-current spectrum, GPUMD's `compute_shc`) — a related but distinct observable.
- **Per-atom / per-mode κ decompositions** — a future axis.
- **Cross-paradigm κ comparison test** on Si-Tersoff — requires actual LAMMPS + GPUMD runs to be wired into a fixture, deferred to a worked-example pass.
- **Quantum corrections** to MD κ.

## Success criteria

- 3 new operator states + 3 new edges, all sympy-formula-carrying.
- `validate_dag(NODES, EDGES) == []` clean.
- LAMMPS adapter has specs for green_kubo + nemd (HNEMD documented as not-exposed with one-paragraph rationale).
- GPUMD adapter has specs for green_kubo + hnemd (NEMD documented as not-exposed similarly).
- Substrate doc node/edge counts updated to 46/47.
- pytest stays green; total test count rises by ≥ 10.
- `docs/dag.html` regenerates and lays out the three new κ Observables at the bottom of the MD tier.

## Order

1. PhysicsType already has THERMAL_CONDUCTIVITY (re-used; no new enum value).
2. New states in `omai/thermal_transport/operator/nodes.py` (3 Pattern-A variants).
3. New edges in `omai/thermal_transport/operator/edges.py` (3 contractions with sympy formulas).
4. `omai/thermal_transport/operator/__init__.py` exports.
5. Validator vocabulary: extend `_STATE_SYMBOLS` for the three new state-name strings, and `_PERMITTED_CONSTANTS` for any new MD-κ-specific symbols (`F_e^\beta`, `\partial_\beta T`).
6. Adapter coverage in `lammps.py` (green_kubo + nemd) and `gpumd.py` (green_kubo + hnemd); not-exposed entries for the missing third in each.
7. Smoke tests (`tests/test_md_kappa_paths.py`).
8. Substrate doc counts and bullets.
9. dag.html regenerate.
10. Single commit.
