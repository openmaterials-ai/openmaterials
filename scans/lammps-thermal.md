# LAMMPS thermal-transport / MD-observable scan

Slice: `thermal-md` · Source: vendored `lammps/` @ **30 Mar 2026 (Development)** (`src/version.h`) ·
Catalog: `scans/lammps-thermal.json` (30 entries, every entry source-anchored to `src/*.cpp` lines,
doc `.rst` lines as secondary anchors).

## Coverage

| Area | Entries | Notes |
|---|---|---|
| Heat-flux / Green–Kubo pipeline | 9 | `compute heat/flux` (+ centroid + TALLY variants), `ke/atom`, `pe/atom`, `stress/atom`, `centroid/stress/atom`, `fix ave/correlate`, `fix ave/time`, GK-κ in-script workflow |
| NEMD κ | 7 | `fix thermal/conductivity` (Müller-Plathe), `fix heat`, `fix ehex`, `fix langevin tally`, chunked T(z) profile, `compute temp/region`, NEMD-κ workflow |
| Trajectory & correlation observables | 6 | `dump custom`, `dump atom`, `compute msd`, `compute vacf`, `compute rdf`, diffusivity workflows (DIFFUSE) |
| Ensembles/thermostats (scheme) | 1 | consolidated `nve/nvt/npt/langevin` entry — gauge concern, deliberately unmapped |
| Mechanical/materials overlap | 4 | `compute pressure`, ELASTIC C_ij workflow, `voronoi/atom` (note-only), `cna/atom` (note-only) |
| Thermo stdout | 3 | `temp`; `pe/ke/etotal/enthalpy`; `vol` |

Mapping outcome: **14 entries ground existing catalog nodes**, **13 are new-node candidates**,
**3 are deliberately unmapped machinery/schemes** (`fix ave/time`, ensembles, `cna/atom`).

Canonical workflows read end-to-end: all five `examples/KAPPA` scripts (langevin, heat, ehex, mp,
heatflux — mutually agreeing at κ ≈ 3.29–3.88 on the Evans 1986 LJ state point), `examples/DIFFUSE`
(MSD-slope and VACF-integral D), `examples/ELASTIC` (Si-SW C_ij vs Cowley 1988).

## The most consequential convention traps

1. **`compute heat/flux` emits J·V, not J** (`compute_heat_flux.cpp:114-117`: "normalization by
   volume is not included"). Everything downstream must divide by V exactly once:
   κ = 1/(V·k_B·T²)·∫⟨(JV)(0)(JV)(t)⟩dt on the raw `c_flux` products. Cross-code (e.g. vs GPUMD,
   which quotes intensive quantities) this is a guaranteed factor-V mystery. Sign/unit chain:
   `stress/atom` returns S = −(virial+ke) in **pressure·volume** units (`-force->nktv2p`,
   `compute_stress_atom.cpp:328`); `heat/flux` applies `jv -= S·v` then `jv /= nktv2p`
   (`compute_heat_flux.cpp:166-181`), netting +virial·v in energy·velocity units.

2. **Per-atom stress sign + stress·volume + double-count trio**
   (`compute_stress_atom.cpp:328`, doc `compute_stress_atom.rst:193-206`):
   (a) S is the **negative** of the per-atom pressure tensor — Σ diag(S)/(dV) = −P, opposite sign
   to `compute pressure`; (b) it is stress **times an undefined per-atom volume** (bar·Å³ in metal),
   never a stress; (c) the **default includes the kinetic term** — the canonical GK script must pass
   `stress/atom NULL virial` or kinetic transport is double-counted against the convective e_i·v_i
   term. Additionally, plain `stress/atom` gives **unphysical J** for angle/dihedral/improper/rigid
   contributions — `centroid/stress/atom` (9 asymmetric components, `pressatomflag=2`) is the
   physical choice there, and the two decompositions differ per-atom (a gauge) while summing to the
   same global virial.

3. **Wrapped-by-default coordinates, and `dump atom` is fractional**
   (`dump_atom.cpp:39,76-83`; `dump_custom.cpp:2655`): `dump custom x y z` are wrapped into the box;
   MSD/diffusion post-processing needs `xu yu zu` (image-flag unwrapping `x + image·prd`) or
   `x y z + ix iy iz`. `dump atom`'s **default columns are scaled fractional `xs ys zs`** — treating
   them as lengths is silently wrong by a box factor. `compute msd` unwraps internally via image
   flags (`compute_msd.cpp:196-201`), so image-flag integrity (`set image`, npt box changes) is a
   correctness precondition.

4. **Unit-style dependence is total, and lj adds a stealth normalization.** Every factor in the
   pipeline (`boltz`, `mvv2e`, `nktv2p`, dt) is set per `units` style (`update.cpp:150-302`: lj all
   1.0; real kcal/mol·fs·atm; metal eV·ps·bar). Two derived traps: (a) the GK scale in the canonical
   lj script omits k_B because k_B=1 — porting to metal/real without inserting `boltz` is wrong by
   ~10⁴; (b) **thermo pe/ke/etotal/enthalpy print per-atom by default in lj units only**
   (`thermo.cpp:194-200`) while compute outputs stay extensive. The existing
   `LAMMPS_CONTRACT_KAPPA_NEMD` spec hard-codes real-unit parameter units — flagged for repair.

5. **Single-time-origin correlation estimators.** `compute msd` and `compute vacf` correlate against
   state stored **at compute creation** (`compute_msd.cpp:82-86`, `compute_vacf.cpp:56-63`) — no
   sliding time-origin average, unlike the catalog nodes' ⟨·⟩_{t₀} definitions. `fix ave/correlate`
   *does* average over origins, with the lag axis in **timesteps** (`i*Nevery`,
   `fix_ave_correlate.cpp:489`), unnormalized raw products, and `type auto` yielding only the
   diagonal αα components.

## What LAMMPS grounds beyond the current 8-variable MD tier in `lammps.py`

The existing spec covers Potential, Trajectory, HeatCurrent, HeatCurrentACF, VACF, MSD, κ_GK, κ_NEMD
(+ operator specs). This scan adds grounding for:

- **Temperature** — as an MD *output*: `compute temp` with the dof = dN−d COM convention
  (`compute_temp.cpp:58-68`), region-scoped `temp/region`, and crucially the **spatially indexed
  T(z) chunk profile** (`fix ave/chunk` → `profile.*` files) that the NEMD gradient is measured from.
- **Diffusivity** — natively in-script: `slope()`/`trap()` variable functions over `fix vector`
  series (DIFFUSE examples), Einstein 2d·D·t and VACF-integral routes.
- **CellVolume** — thermo `vol` keyword; consumed live by the GK scale variable (fluctuating under
  npt — a note the parameter-tier node should carry).
- **HeatCurrent** — a second, independent realization (`TALLY` package per-pair tally) that
  cross-checks the stress-decomposition route for pair potentials.

Corrections to existing spec text found while cross-reading:
- `LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO` says the κ integral is post-processed and LAMMPS emits no
  running κ — but `examples/KAPPA/in.heatflux:68-72` computes the running κ **natively in-script**
  via `trap()` and prints it in thermo output. (True part: there is no dedicated κ *file*.)
- `LAMMPS_TRAJECTORY` says unwrapping "is set via `dump_modify` (use `xu yu zu`)" — `xu yu zu` are
  dump **column keywords**, not `dump_modify` options.
- `LAMMPS_CONTRACT_KAPPA_NEMD` `parameter_units` hard-code real units; the canonical examples are lj.
- `nemd_method` scheme should enumerate more than `muller_plathe`/`direct_two_reservoir`: LAMMPS
  ships `fix heat`, `fix ehex`, and `fix langevin tally` reservoir variants (all five agree in
  `examples/KAPPA`).

## Genuinely NEW node candidates (13 entries)

| Candidate node | Entries | Why |
|---|---|---|
| PerAtomKineticEnergy / PerAtomPotentialEnergy | `ke-atom`, `pe-atom` | HeatCurrent inputs; per-atom PE partition is itself a gauge |
| PerAtomStress (stress·volume, hidden) | `stress-atom`, `centroid-stress-atom` | the virial half of HeatCurrent; materials overlap; centroid = scheme value |
| ExchangedReservoirEnergy (imposed vs measured scheme) | `muller-plathe-exchanged-energy`, `fix-heat-imposed-rate`, `fix-ehex-imposed-rate`, `langevin-reservoir-energy` | the numerator of κ_NEMD; today only an operator parameter |
| RadialDistributionFunction | `rdf` | structure-tier sibling of MSD; default extent = pair cutoff (trap) |
| Pressure | `pressure` | materials overlap: barostat setpoint, enthalpy, ELASTIC readout; sign-opposite to PerAtomStress |
| ElasticConstants (stiffness tensor, Voigt) | `elastic-constants-workflow` | T=0 finite-strain −ΔP/Δε with cfac unit chain; Si-SW reference values |
| MD TotalEnergy/Enthalpy family | `thermo-energies` | must NOT be conflated with per-phonon-mode InternalEnergy/Entropy nodes |
| (note-only) per-atom Voronoi volume | `voronoi-atom-volume` | the canonical denominator turning stress·V into stress |

Deliberately unmapped (not quantities): `fix ave/time` (averaging/IO machinery),
ensemble/integrator/thermostat declaration (Trajectory gauge; scheme on `run_md` — one consolidated
entry as requested), `cna/atom` (categorical diagnostic label).

## Open questions (full list in JSON `open_questions`)

1. Is T(bin) an index on the existing Temperature node or a new ProfileTemperature node? The NEMD
   gradient edge needs one of the two declared.
2. Should J·V-vs-J (extensive vs intensive HeatCurrent) become a named normalization in
   `normalizations.py`? It is a guaranteed cross-code factor-V.
3. stress/atom vs centroid/stress/atom heat-flux decompositions: scheme on `compute_heat_current`
   or two edges? (They coincide for pair potentials, differ for bonded/many-body.)
4. Single-origin (LAMMPS msd/vacf) vs time-origin-averaged (catalog) estimators: normalization
   declaration or tolerance policy in `compare()`?
5. Per-unit-style parameter tables (or a `unit_style` scheme on the whole LAMMPS representation)
   to fix the hard-coded real-unit `parameter_units`.

**Nothing blocked the scan.** All targeted sources were present in the vendored tree; the only
scoped-out items (USER-PHONON, fix phonon, SMD variants) match the exclusions already declared in
`omai/thermal_transport/representation/lammps.py`.
