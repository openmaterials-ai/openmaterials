# Phase 2 P2 — MD primitives

**Date**: 2026-05-18
**Parent**: `docs/superpowers/specs/2026-05-17-phase2-md-design.md`
**Scope**: introduce the operator-layer states and edges that describe a classical MD run and its primary contractions (heat current, autocorrelations, MSD). LAMMPS and GPUMD adapter coverage grows to cite the codes' native APIs for each. No κ formulae yet — those land in P3.

## What's new on the operator layer

### New states (5)

| State | Kind | Fields / indices | What it carries |
|---|---|---|---|
| `Trajectory` | **HiddenState** | `r`, `v` with indices `(i, alpha, t)` (atom, Cartesian, timestep) | The per-atom positions and velocities sampled at each MD timestep. Gauge-dependent: ensemble + thermostat + initial conditions all alter the realised trajectory. |
| `HeatCurrent` | **HiddenState** | `J` with indices `(alpha, t)` (Cartesian, timestep) | Instantaneous heat current vector J(t). Gauge-dependent (ensemble noise). |
| `HeatCurrentACF` | **Observable** | `Jcorr` with indices `(alpha, beta, tau)` | ⟨J_α(0) J_β(τ)⟩ — the time-correlation of the heat current. Gauge-invariant after ensemble averaging; the Green-Kubo κ integrand. |
| `VelocityAutocorrelation` | **Observable** | `Cv` with indices `(tau,)` (or `(i, tau)` if per-atom) | ⟨v(0)·v(τ)⟩, the velocity autocorrelation function. Fourier transform gives the phonon DOS (Wiener-Khinchin); already gauge-invariant. |
| `MeanSquaredDisplacement` | **Observable** | `M` with indices `(tau,)` | ⟨|r(t+τ) − r(t)|²⟩ — gauge-invariant, used to read diffusion coefficients (off-topic for κ but a free addition). |

`PhysicsType` gains five values: `TRAJECTORY`, `HEAT_CURRENT`, `HEAT_CURRENT_ACF`, `VELOCITY_AUTOCORRELATION`, `MEAN_SQUARED_DISPLACEMENT`.

Two new dimensions:
- `LENGTH_PER_TIME` (= velocity), for `Trajectory.v` and `VelocityAutocorrelation.Cv`.
- `ENERGY_TIMES_LENGTH_PER_TIME` (= heat-current energy×velocity ~ W·m), for `HeatCurrent.J` and `HeatCurrentACF.Jcorr`.

### New edges (6)

| Edge | Inputs | Output | Notes |
|---|---|---|---|
| `run_md` | `Potential`, `Temperature` | `Trajectory` | `algorithmic_conventions`: `ensemble ∈ {NVE, NVT, NPT, …}`, `thermostat ∈ {berendsen, langevin, nose_hoover, csvr, none}`, `integrator ∈ {velocity_verlet, leapfrog, …}`. `parameters`: `time_step` (in time), `n_steps` (int), `n_equilibration_steps` (int). |
| `compute_heat_current` | `Trajectory` | `HeatCurrent` | algorithmic_conventions: `definition ∈ {hardy, irving_kirkwood, virial}` — Irving-Kirkwood is canonical. Standard MD definition: J_α = (1/V) Σ_i [E_i v_i,α + (1/2) Σ_{j≠i} r_{ij,α} (F_{ij}·v_i)]. |
| `autocorrelate_heat_current` | `HeatCurrent` | `HeatCurrentACF` | algorithmic_conventions: `correlation_method ∈ {direct, fft}` (direct = O(N²) sum, FFT = O(N log N) via Wiener-Khinchin). |
| `compute_velocity_autocorrelation` | `Trajectory` | `VelocityAutocorrelation` | Same `correlation_method` convention. Per-atom: ⟨v_i(0)·v_i(τ)⟩ averaged over atoms. |
| `compute_msd` | `Trajectory` | `MeanSquaredDisplacement` | algorithmic_conventions: `unwrap_pbc ∈ {true, false}` (Δr across PBC must be unwrapped for the diffusion limit to be sensible). |
| `fourier_to_dos` | `VelocityAutocorrelation` | `PhononDOS` | The classical-MD equivalent of compute_dos via the Wiener-Khinchin theorem: g(ω) ∝ ∫ Cv(τ) e^(iωτ) dτ. `dos_broadening` convention inherited. Pattern-C with `compute_dos` (different upstream input states; both produce `PhononDOS`). |

### Sympy formulas

Every edge carries a sympy formula. Sketches:

- `run_md`: `r(t+Δ), v(t+Δ) = VelocityVerlet(r(t), v(t), F(r(t)); Δ, thermostat_params)`. A schematic — the actual stepping is a long iteration; the formula declares the one-step recurrence with thermostat as an auxiliary.
- `compute_heat_current` (Irving-Kirkwood, condensed): `J(t) = (1/V) Σ_i E_i v_i + (1/(2V)) Σ_{i<j} r_{ij} (F_{ij} · v_i)`.
- `autocorrelate_heat_current`: `Jcorr_αβ(τ) = (1/n_lag) Σ_t J_α(t) J_β(t+τ)`.
- `compute_velocity_autocorrelation`: `Cv(τ) = (1/(N · n_lag)) Σ_i Σ_t v_i(t) · v_i(t+τ)`.
- `compute_msd`: `M(τ) = (1/(N · n_lag)) Σ_i Σ_t |r_i(t+τ) − r_i(t)|²`.
- `fourier_to_dos`: `g(ω) = (1/π) ∫₀^∞ Cv(τ) cos(ωτ) dτ` (real-cosine form for VAF DOS).

## Adapter coverage

### `lammps` adapter (extend)

- `LAMMPS_TRAJECTORY` (StateAdapterSpec): code_api references `fix nvt`/`fix nvt langevin`/`run` plus `dump custom` for the on-disk file.
- `LAMMPS_HEAT_CURRENT` (StateAdapterSpec): `compute heat/flux <id> ...`.
- `LAMMPS_HEAT_CURRENT_ACF` (StateAdapterSpec): `fix ave/correlate ... Jx Jy Jz`.
- `LAMMPS_VELOCITY_AUTOCORRELATION` (StateAdapterSpec): `compute vacf <id>` + `fix ave/time`.
- `LAMMPS_MEAN_SQUARED_DISPLACEMENT` (StateAdapterSpec): `compute msd <id>`.
- `LAMMPS_RUN_MD` (OperationAdapterSpec): algorithmic_convention overrides for the ensemble / thermostat choices LAMMPS exposes.
- Similar `LAMMPS_COMPUTE_HEAT_CURRENT`, `LAMMPS_AUTOCORRELATE_HEAT_CURRENT`, `LAMMPS_COMPUTE_VELOCITY_AUTOCORRELATION`, `LAMMPS_COMPUTE_MSD`.
- `fourier_to_dos`: LAMMPS doesn't have a native fix for VAF→DOS; the spec describes user-driven post-processing (numpy FFT). Document as "Not Exposed" if the LAMMPS-internal path doesn't carry it.

### `gpumd` adapter (extend)

- `GPUMD_TRAJECTORY` (StateAdapterSpec): `dump_position`, `dump_velocity` keywords in `run.in`.
- `GPUMD_HEAT_CURRENT` (StateAdapterSpec): `compute heat_current` keyword + the per-atom decomposed form GPUMD exposes for HNEMD.
- `GPUMD_HEAT_CURRENT_ACF` (StateAdapterSpec): GPUMD's `compute_hac` keyword writes `hac.out` directly.
- `GPUMD_VELOCITY_AUTOCORRELATION` (StateAdapterSpec): GPUMD writes mvac.out etc.
- `GPUMD_MEAN_SQUARED_DISPLACEMENT` (StateAdapterSpec): `compute_msd` keyword.
- `GPUMD_RUN_MD` (OperationAdapterSpec): GPUMD ensembles include `ensemble nve`, `ensemble nvt_nhc`, etc.
- Similar coverage for the auto-correlate / VAF / MSD ops.

## Tests (smoke)

- `tests/test_md_primitives.py` (new) — for each new state, assert producing edge identity, inputs, outputs. For each new edge, assert it carries a sympy formula and the algorithmic_conventions are declared per spec.
- `tests/test_lammps_md_coverage.py` and `tests/test_gpumd_md_coverage.py` — assert each new state has a spec from the relevant adapter.
- Update `test_node_count` to 43 and `test_edge_count` to 44 (gain 5 states + 6 edges).

## Substrate doc updates

- Counts: 38/38 → 43/44.
- New bullets in the node and edge lists with one-line summaries.
- Brief paragraph in §"The operator DAG" introducing the MD primitives tier: "On top of the BTE chain, a parallel MD tier captures time-resolved primitives (Trajectory, HeatCurrent, HeatCurrentACF, VAF, MSD) that feed the MD-based κ paths in P3."

## Out of scope (this spec)

- **κ formulae** (`contract_kappa_green_kubo`, `contract_kappa_nemd`, `contract_kappa_hnemd`) — P3.
- **NEMD-specific Trajectory variants** — P3 (folded into `run_md`'s `ensemble=nemd` value).
- **Per-atom decomposed heat currents** (mode-resolved) — possible follow-up; not P2.
- **Quantum corrections to MD VAF / MSD** — not in scope.
- **Phonon dispersion via VAF** beyond the VAF→DOS edge — P3 or later.

## Success criteria

- 5 new operator states + 6 new edges, all sympy-formula-carrying.
- `validate_dag(NODES, EDGES) == []` clean.
- Adapter coverage in `lammps.py` and `gpumd.py` for all five new states (or explicit out-of-scope notes where the code doesn't expose the state cleanly).
- Substrate doc node/edge counts updated to 43/44.
- pytest stays green; total test count rises to ≥ 540.
- `docs/dag.html` regenerates and lays out the new MD tier.

## Order

1. PhysicsType + dimension additions (operator core).
2. New states in `omai/thermal_transport/operator/nodes.py`.
3. New edges in `omai/thermal_transport/operator/edges.py` with sympy formulas.
4. `omai/thermal_transport/operator/__init__.py` exports.
5. Adapter coverage in `lammps.py` and `gpumd.py`.
6. Smoke tests (test_operator.py extension + new test_md_primitives.py).
7. Substrate doc counts and bullets.
8. dag.html regenerate.
9. Single commit; push.
