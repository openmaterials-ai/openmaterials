# pycalphad (CALPHAD) as used by AtomisticSkills: scan report

Scan of **pycalphad** (`pycalphad.Database` / `equilibrium` / `binplot`) as the
AtomisticSkills (arXiv 2605.24002) `calphad-agent` skills actually use it.
Companion catalog: `scans/pycalphad-atomistic-skills.json` (13 entries).

This is the queue's **first genuinely new physics domain**: phase thermodynamics
from assessed Gibbs-energy databases (macroscopic CALPHAD), not atomistics. Every
prior scan (QE, LAMMPS, pymatgen, mp-api) grounded quantities in an ab-initio or
MLIP calculation of a specific structure. CALPHAD instead minimizes a **Gibbs
energy assembled from pre-fitted, human-assessed models** read from a TDB
(Thermodynamic DataBase) file. The producing operator is a Gibbs minimization
over assessed models, the analog of `solve_ground_state` but over a
finite-temperature free energy rather than a 0 K potential.

## Sources and version anchoring

Sources: the two calphad-agent skill directories
`AtomisticSkills/.agents/skills/mat-calphad-phase-diagram/` and
`mat-calphad-property-diagram/` (`plot_phase_diagram.py`,
`plot_phase_fractions.py`, `SKILL.md`, `examples/Al-Zn/alzn_mey.tdb`), plus
`AtomisticSkills/conda-envs/calphad-agent/core_env.yaml` (which pins pycalphad
via `pip`).

**pycalphad is NOT importable in the miniconda base env** (`No module named
pycalphad`) and the `calphad-agent` conda env is **not created** on this machine.
API and unit anchors were read from the pip-downloaded wheel:
`pip download --no-deps --dest /tmp/pcsrc pycalphad` ->
`pycalphad-0.11.2-cp312-cp312-macosx_11_0_arm64.whl`, unzipped to
`/tmp/pcsrc/wheel` and read from source. The unit declarations
(`pycalphad/property_framework/units.py`, `pycalphad/variables.py`) are the
load-bearing anchors and are stable across recent 0.10-0.11 releases; `core_env.yaml`
pins pycalphad with **no version**, so a live install could differ (open question).

## What pycalphad IS in this software: a Gibbs-minimization engine over assessed models

Three load-bearing calls:

1. **`Database(tdb)`** loads the assessed Gibbs-energy functions: the SGTE
   `GHSER*` lattice-stability polynomials (`a + b·T + c·T·ln(T) + Σ d_n·T^n +
   e·T^-1`, J per mole of atoms), Redlich-Kister excess parameters, and
   magnetic / Einstein contributions. `alzn_mey.tdb` defines `GHSERAL`,
   `GHSERZN`, `GALLIQ`, `GZNLIQ` this way (NIMS 2009; parameters from S. an Mey,
   *Z. Metallkd.* 84 (1993) 451-455). The TDB **is the model**: the CALPHAD
   analog of the MLIP checkpoint or the DFT pseudopotential.
2. **`equilibrium(dbf, comps, phases, conds)`** minimizes G at fixed
   `{v.N, v.P, v.T, v.X}` and returns an xarray Dataset of `GM` (molar Gibbs
   energy, J/mol), `MU` (chemical potentials, J/mol), `NP` (phase fractions,
   dimensionless), `Phase` (stable phase names), `X` (phase compositions), `Y`
   (sublattice site fractions).
3. **`binplot(dbf, comps, phases, conds)`** sweeps the minimization over a (T, X)
   grid to draw the T-x phase-diagram boundaries (liquidus / solidus / solvus /
   invariant reactions).

The property-diagram skill consumes `eq.NP` + `eq.Phase`; the phase-diagram skill
consumes the `binplot` boundary set.

## Entry counts by status (13 entries)

- **already-mapped: 2** (as cross-code COUSINS with a normalization/basis caveat,
  never a naive equate): **molar-entropy** (`MolarEntropy`, same dimension) and
  **molar-heat-capacity** (`MolarHeatCapacity`, same dimension, C_P-vs-C_V +
  basis mismatch). The dimension-level match is all that holds: these share the
  exponent vector with the map's phonon `Molar*` nodes but are a **different
  physics** (assessed Gibbs vs harmonic Helmholtz), **different basis** (mole of
  atoms vs mole of primitive cells), **different producer**.
- **new-node-candidate: 6**: molar-gibbs-energy, molar-enthalpy,
  chemical-potential, phase-fraction, activity, transition-temperature. (The two
  already-mapped molar entries would ALSO become candidates if the encode
  decision mints source/basis-labeled variants rather than reusing the phonon
  nodes.)
- **representation-only: 5**: site-fraction (Y, sublattice model coordinate),
  phase-diagram (binplot/ternplot product), tdb-assessed-database (the model
  artifact), molar-mass-density-context, and system-moles-condition (pycalphad's
  normalization machinery).

## The J/mol vs eV/atom factor (exact)

**1 eV/atom = 96485.33212331 J/mol** (= `e · N_A`, and since both `e` and `N_A`
are SI-exact since the 2019 redefinition, this factor is **exact**; it is
numerically identical to the Faraday constant `F = e·N_A`).

- Derivation: 1 eV/atom is `e` joule per atom; times Avogadro is
  `1.602176634e-19 · 6.02214076e23 = 96485.33212331` J/mol.
- Inverse: 1 J/mol = `1.0364269656262175e-05` eV/atom = `0.010364269656262174`
  meV/atom.
- Verified with `scipy.constants`: `Avogadro · e = 96485.33212331001`.

**Why it matters for the exponent vectors.** The map's dimension convention is
`(M, L, T, Theta, N, I, J)` with the **fifth slot N the amount-of-substance
(mole) axis**. The map's DFT stability nodes (FormationEnergy, EnergyAboveHull)
are eV/atom with **N = 0** (plain `ENERGY`). CALPHAD's molar energies are J/mol
with **N = -1** (`ENERGY_PER_MOLE = (1,2,-2,0,-1,0,0)`). A CALPHAD molar quantity
therefore CANNOT map to a DFT per-atom node without both this factor **and** a
per-atom-vs-per-formula-unit basis check; the mole axis must be present in the
CALPHAD exponent vectors.

## The molar-basis triple ambiguity

Three different "moles" all called molar:

1. **pycalphad `GM` / `HM` / `SM` / `CPM` with `v.N: 1`**: per mole of **ATOMS**
   (system-moles normalization; `units.py:29-45` declares J/mol, J/mol/K;
   `model.py:484` `energy = GM` normalized per mole atoms by
   `_site_ratio_normalization`; pint defines `atom = mol/N_A` at `units.py:14`
   and the molar mass is built in `g/mol-atom` at `units.py:67`).
2. **pycalphad `G` / `H` = `formulaenergy`**: per mole of **FORMULA UNITS**
   (`model.py:485` `G = ast · _site_ratio_normalization`, `units.py:32` J
   extensive). Differs from (1) by atoms-per-formula-unit.
3. **the map's `Molar*` nodes**: per mole of **PRIMITIVE UNIT CELLS** (phonopy
   convention, `nodes.py:210-241`, emitted kJ/mol). Differs from (1) by
   atoms-per-cell **and** by kJ vs J (factor 1000).

## CALPHAD stability is NOT the DFT hull (mandatory distinctions)

The map already carries FormationEnergy and EnergyAboveHull on the DFT/MLIP side.
CALPHAD's Gibbs energies are the **assessed-thermodynamics** side of the same
physics (which phase is stable). Five axes keep them apart:

1. **Reference state.** DFT FormationEnergy references composition-weighted
   **elemental DFT total energies** (MP elemental refs in the committed li2o
   example). CALPHAD references the **SER** (Stable Element Reference: stable
   structure of each pure element at 298.15 K, 1 bar), encoded as the `GHSER*`
   functions. Different energy zero: not the same number.
2. **Finite temperature.** The DFT hull is a **0 K, athermal** convex hull of
   formation energies (no entropy). The CALPHAD hull is a **finite-T** hull of
   molar Gibbs energies `G(T) = H - TS`, with configurational + vibrational +
   magnetic entropy baked into the assessed polynomials. CALPHAD stability is
   T-dependent (the whole point of a T-x diagram); the DFT hull is not.
3. **Assessed vs computed.** DFT energies are **computed** ab initio for the
   specific structure. CALPHAD energies are **assessed**: fitted by a human to
   reproduce experiment + first-principles data, then frozen into a TDB. The TDB
   + its citation is the model, the analog of the MLIP checkpoint.
4. **Gibbs vs Helmholtz + the molar-node trap.** The map's `Molar*` nodes are
   **harmonic-phonon Helmholtz** quantities (constant volume) per mole of
   primitive cells. CALPHAD `GM/HM/SM/CPM` are **assessed Gibbs** quantities
   (constant pressure) per mole of atoms. Same dimension vectors, different
   thermodynamic potential, different basis, different producer. `CPM` (C_P) is
   NOT the map's `MolarHeatCapacity` (C_V): `C_P - C_V = T V α² / κ_T`.
5. **Phase fraction / diagram / activity / site fraction are new.** NP
   (dimensionless phase amount), transition temperatures (K), activity, and
   site fractions Y have no analog on the current map; they are the distinctive
   Gibbs-minimization outputs that define the new domain.

## Proposed new domain: `thermochemistry`

Modeled on `omai/stability/domain.py` (a clean single-tier `Domain` descriptor)
and `omai/thermal_transport/domain.py` (multi-tier). Reuses existing dimensions
`ENERGY_PER_MOLE` and `ENERGY_PER_TEMPERATURE_PER_MOLE`. Proposed tiers:

| Tier | Description | Candidate nodes |
|---|---|---|
| **Assessed models** | The TDB artifact + per-phase assessed Gibbs energies (SER-referenced GHSER* + Redlich-Kister excess + magnetic/Einstein). The domain's Sources tier. | `TDBDatabase` (model artifact), `MolarGibbsEnergy` (per phase, J/mol-atoms) |
| **Molar thermodynamics** | T-derivative potentials of the assessed Gibbs energy, all per mole of atoms (J/mol family). Analog of thermal_transport "Thermodynamics" but Gibbs/assessed not Helmholtz/phonon. | `MolarEnthalpy`, `MolarEntropy[source=calphad]`, `MolarHeatCapacity[ensemble=constant_p,source=calphad]`, `ChemicalPotential`, `Activity` |
| **Equilibrium** | Outputs of the Gibbs minimization at fixed (N,P,T,x): which phases coexist and in what amount. No phonon/DFT analog. | `PhaseFraction` (NP, dimensionless), `SiteFraction` (Y, representation coord) |
| **Phase diagram** | Swept-equilibrium products: transition temperatures and the T-x / isothermal diagrams. Aggregate representations. | `TransitionTemperature` (liquidus/solidus/solvus/invariant, K), `PhaseDiagram` (binplot/ternplot product, representation-only) |

**Identity guardrails (mandatory).** Because CALPHAD molar quantities share
dimension vectors with the phonon `Molar*` nodes, node identity must be
disambiguated by (a) a source/producer label (calphad vs phonopy), (b) a basis
label (per_mole_of_atoms vs per_mole_of_primitive_cells), and (c) for heat
capacity an ensemble label (constant_p vs constant_v). Otherwise a CALPHAD `SM`
and a phonopy `MolarEntropy` false-merge, exactly the failure the quantity-tag
registry exists to prevent.

## Unit convention traps found

1. **J/mol vs eV/atom, factor 96485.33212331** (= e·N_A, SI-exact = Faraday). The
   mole axis N must appear in CALPHAD exponent vectors.
2. **Molar basis triple ambiguity**: per mole of atoms (pycalphad default) vs per
   mole of formula units (pycalphad `G`) vs per mole of primitive cells (map
   `Molar*`).
3. **Gibbs vs Helmholtz**: CALPHAD is constant-P Gibbs; the map's molar nodes are
   constant-V Helmholtz harmonic phonons. `C_P != C_V`.
4. **Per-mode `HeatCapacity` vs molar `CPM`**: the per-mode node is
   `ENERGY_PER_TEMPERATURE` (no mole axis, indexed (q,ν)); CALPHAD `CPM` is
   `ENERGY_PER_TEMPERATURE_PER_MOLE` (mole axis, scalar). Different dimension AND
   kind. Never equate.
5. **R = 8.3145 hardcoded** (`variables.py:939`), a 5-sig-fig truncation of CODATA
   `8.31446261815324` J/mol/K. Every ideal-mixing (`-R T Σ x ln x`) and
   Einstein/two-state term uses it.
6. **Elements uppercase + `VA` vacancy** must be explicitly in `comps`
   (`plot_phase_diagram.py:48,53-54`), or the sublattice models break.
7. **Pressure baked in**: `conds` set `v.P: 101325` Pa (1 atm); `GM` is the
   constant-P Gibbs energy at this pressure. Record P.
8. **`binplot` returns a matplotlib Axes**, not a data table: transition
   temperatures are drawn, not returned as labeled scalars; extracting them for
   instances needs the Workspace/mapping API.
9. **phonopy kJ/mol vs pycalphad J/mol**: factor 1000 on top of the basis
   difference when bridging to the map's `Molar*` nodes.

## Source anchors (read from the wheel)

- `pycalphad/property_framework/units.py:29-45`: `GM/HM = 'J / mol'`,
  `SM/CPM = 'J / mol / K'`, `G/H = 'J'` (extensive); `:14` `atom = mol/N_A`;
  `:48-91` the per-mole<->per-mass g/mol context (`molar_weight` in g/mol-atom).
- `pycalphad/variables.py`: `:412-417` `SiteFraction` ('fraction'), `:488-505`
  `PhaseFraction` NP ('fraction'), `:528-534` `MoleFraction` v.X, `:830-836`
  `ChemicalPotential` MU ('J / mol'), `:901-915` Temperature/Pressure
  ('kelvin'/'pascal'), `:922-925` `SystemMolesType` v.N ('mol'), `:937-939`
  MU/NP aliases + `R = Float(8.3145)`.
- `pycalphad/model.py`: `:484` `energy = GM`, `:485` `formulaenergy = G`, `:486`
  `entropy = SM = -GM.diff(T)`, `:487` `enthalpy = HM`, `:489`
  `heat_capacity = CPM`, `:410-461` sublattice `moles`/`site_ratios`, `:957`
  ideal-mixing uses v.R.
- `pycalphad/core/equilibrium.py:15,49,72,81`: `equilibrium` signature; GM/MU are
  base outputs; `pycalphad/core/calculate.py:194,212` output-by-name; `binplot` /
  `ternplot` at `pycalphad/mapping/compat_api.py:6-42,65-105`.
- Skills: `plot_phase_diagram.py:15-16,48,51,57,62-67,76`;
  `plot_phase_fractions.py:15,58,60-61,65,68,73-92`;
  `examples/Al-Zn/alzn_mey.tdb:1-19` (assessment provenance).

## Open questions (full list in JSON `open_questions`)

1. pycalphad not importable in base and the calphad-agent env not created; anchors
   read from the pip wheel 0.11.2 (core_env.yaml pins no version). Pin at encode.
2. **Encode decision (mirrors the pymatgen per-cell-vs-per-atom decision)**:
   separate CALPHAD molar nodes vs labels on the phonon `Molar*` nodes? Review
   leans separate: different potential (G vs F), basis (atoms vs cells), producer.
3. The map has `MolarHelmholtzFreeEnergy` and `MolarInternalEnergy` but NO
   `MolarGibbsEnergy` and NO `MolarEnthalpy`; CALPHAD supplies exactly the missing
   Gibbs-side pair. Confirm ADD rather than relabel.
4. `phase_fraction` (NP) and `transition_temperature` are arrays/spectra (vs T or
   x), like `si-frequency-qe.json`; confirm they enter via the representation
   layer, not as scalar instances. Invariant points (eutectic (T,x)) ARE scalars.
5. `activity` is not read by either skill (they consume NP/Phase and the binplot
   boundaries) but is reachable from the equilibrium MU via `ReferenceState`.
   Open the node now or defer?
6. `TransitionTemperature` is an OUTPUT temperature; the map's `Temperature` is an
   INPUT Source. Confirm a distinct node.
7. `SiteFraction` Y: representation coordinate (this scan's verdict) or node?
8. TDB assessment provenance is the MLIP-checkpoint analog; confirm the instance
   schema records `{tdb_file, assessment_citation, comps, phases, v.N, v.P, v.T,
   v.X}` as conditions. This scan does not touch `omai/` or `docs/data`.
9. `ternplot` (ternary isotherms) exists in the API but the skill implements only
   `binplot` (SKILL.md: ternary "not yet implemented"). Anchor the ternary node to
   the API, flag it is not exercised.
