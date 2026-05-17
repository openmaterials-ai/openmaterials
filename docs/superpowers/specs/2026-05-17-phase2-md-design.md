# Phase 2 — MD-based κ paths

**Date**: 2026-05-17
**Scope**: extend `omai.thermal_transport` from a BTE-only domain into a BTE + MD domain. LAMMPS+ASE becomes the Potential / Forces anchor; GPUMD becomes a marquee MD κ reference; new operator states for MD primitives (HeatCurrent, MSD, VAF, Trajectory); new transport_model values on κ (Green-Kubo, NEMD, HNEMD).

## Why

Phase 1 (BTE chain — RTA / direct / Wigner / QHGK / cumulative κ) is consolidated, type-encoded, and verified on Si-Tersoff. The "big map of materials science" framing requires extending beyond BTE: the lattice-thermal-conductivity literature uses MD-based methods (Green-Kubo, NEMD, HNEMD) as the empirically-tested complement to BTE. Without MD κ paths, the operator/representation framework can't claim to span the field.

Phase 2 is decomposed into three sub-projects, decreasing in isolation:

| | Sub-project | What it builds | Why |
|---|---|---|---|
| **P1** | LAMMPS+ASE as the Potential / Forces / FC-derivative anchor | A new `lammps` (or `ase`) adapter that ties `provide_potential` and the FC2/FC3 chain to the ASE calculator interface. Possibly one new operator state, `Forces`, if per-displacement forces need to be type-comparable across codes. | Pins the Potential across kaldo / phono3py / phonopy / shengbte. Anchor for everything downstream. |
| **P2** | MD primitives | New operator states: `Trajectory`, `HeatCurrent`, `VelocityAutocorrelation`, `MeanSquaredDisplacement`. New edges: `run_md`, `compute_heat_current`, `autocorrelate`, `fourier_to_dos`. LAMMPS + GPUMD adapter coverage for the new states. | First-class MD outputs (independent of κ). Used by P3 but also valuable in isolation (DOS-via-VAF cross-check, diffusion observables). |
| **P3** | MD-based κ | New `ThermalConductivity[transport_model=green_kubo \| nemd \| hnemd]` Observables. New edges: `contract_kappa_green_kubo`, `contract_kappa_nemd`, `contract_kappa_hnemd`. LAMMPS + GPUMD adapter coverage. | Closes the cross-code MD-vs-BTE κ comparison. The κ output that's directly comparable to experiment. |

The order is also the dependency order: P3 needs P2 (HeatCurrent / time-series MD outputs); P2 needs P1 (Potential anchor). Doing P1 alone has standalone value (tighter cross-code agreement on the BTE chain).

## Architectural decisions (locked in earlier brainstorm)

The pattern choices from the consolidation discussion still hold:

- **κ parameterisation**: keep two-axis `ThermalConductivity[transport_model=…, bte_solver=…]`. P3's transport_model values (`green_kubo`, `nemd`, `hnemd`) join the existing `lbte`, `wigner`, `qhgk`. Phase 1's `bte_solver` axis only applies to `transport_model=lbte`; MD variants ignore it.
- **MD primitives**: each is its own operator state with its own producing edge. Trajectory at the top (output of `run_md`); HeatCurrent / VAF / MSD downstream contractions.
- **Pattern reuse**: every addition follows the three patterns in `docs/skills/extend_dag.md` (Pattern A for terminals, Pattern B for sibling/converging, Pattern C for shared-output / alternative-producer).

## Spine

The phase-1 spine extension via `experiments/silicon_tersoff/spec_demo.py` continues. P1's deliverable is "all four BTE codes agree on κ on the *same* LAMMPS+ASE-evaluated Tersoff Si Potential." P2's deliverable is cross-code agreement on the MD primitives (HeatCurrent ACF, VAF) between LAMMPS and GPUMD on the same Potential. P3's deliverable is cross-paradigm agreement: `κ_HNEMD (GPUMD) ↔ κ_GK (LAMMPS) ↔ κ_LBTE (kaldo/phono3py/shengbte) ↔ κ_Wigner / κ_QHGK (kaldo)` all on Si-Tersoff at 300 K.

## Out of scope (this spec)

- **Non-Si materials**: polar systems (NaCl, MgO) for NAC verification, alloys, isotope effects beyond what's already in stage 3. Si-Tersoff remains the only fully-verified worked example; polar materials get their own future spec.
- **Quantum corrections to MD κ**: classical-MD-κ vs quantum-BTE-κ comparison has a long literature; we don't try to fold quantum corrections into MD here.
- **Ab-initio MD**: MD with DFT forces (rather than classical potentials). Implementation-wise this is just "different ASE calculator," but real DFT-MD requires HPC resources we don't plan to set up.
- **A second domain** (electronic structure, optical response, etc.). Phase 2 stays within thermal transport.

## Success criteria

- P1: every BTE adapter's `provide_potential` spec cleanly declares LAMMPS+ASE as the implementation; cross-code Si-Tersoff κ comparison reproduces phase-1 agreement (≤ ~15% across all four codes) using the SAME ASE calculator object for force evaluation in every code's pipeline.
- P2: `tests/test_silicon_md.py` (new) verifies HeatCurrent ACF identity between LAMMPS and GPUMD on the same Potential; VAF → DOS Fourier identity holds.
- P3: `tests/test_silicon_consolidation.py` extended with κ_GK / κ_NEMD / κ_HNEMD verification sections (each may skip if the respective MD run hasn't produced data); the three values agree with κ_LBTE within MD's ~20–30% noise band.

## Order and execution

**P1 first.** Lightest, mostly adapter work, deliverable closes a phase-1 hole (the implicit shared-Potential assumption). Spec for P1 will be a separate doc.

P2 and P3 come after P1 and may interleave. Each gets its own spec when scoped.
