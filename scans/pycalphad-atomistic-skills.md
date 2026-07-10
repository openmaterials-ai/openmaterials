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
   `model.py:484` `energy = GM = self.ast` is bare `ast`, but every energy
   contribution is divided by `_site_ratio_normalization` (`model.py:931,957,
   979,...`) as it enters `ast`, and `_site_ratio_normalization` (`:627-638`) =
   Σ site_ratio·(atoms·site_fraction) = atoms per formula unit, so `GM` is
   per-mole-of-atoms while `G = formulaenergy = ast·_site_ratio_normalization`
   (`:485`) is per-formula-unit; pint defines `atom = mol/N_A` at `units.py:14`
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
5. **R = 8.3145 hardcoded** (`variables.py:939`), a 5-sig-fig **rounding**
   (round-up, not truncation) of CODATA `8.31446261815324` J/mol/K. Relative
   error `4.496e-06 = 0.00045%` high, **negligible at CALPHAD precision** (the
   assessed parameters it multiplies carry far larger uncertainty). Every
   ideal-mixing (`-R T Σ x ln x`) and Einstein/two-state term uses it.
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

## Review verdicts (2026-07-09)

Adversarial deep review of commit 1850a0f's catalog (13 entries). Every anchor
opened against source: pycalphad 0.11.2 from the re-downloaded wheel
(`/Users/juicy/miniconda3/bin/pip download --no-deps --dest /tmp/pcsrc pycalphad`
-> `pycalphad-0.11.2-cp312-cp312-macosx_11_0_arm64.whl`, unzipped to
`/tmp/pcsrc/wheel`), the two calphad-agent skill scripts read in-repo at
`AtomisticSkills/.agents/skills/mat-calphad-{phase,property}-diagram/scripts/`,
the map side read from `omai/thermal_transport/operator/nodes.py`,
`omai/operator/registry.py`, `omai/operator/dimensions.py`, and
`docs/data/graph.json` (66 nodes, current). Every factor recomputed from SI-exact
constants (scipy). Em-dash grep over both files: **zero** (the em-dash grep
exits 1 on both).

### Corrections that changed a stated number (not physics-changing, but wrong)

- **R relative error: CORRECTED.** The scan called `v.R = 8.3145` a "truncation"
  of CODATA `8.31446261815324` that is "0.0001% high". Two errors: (1) it is a
  **rounding up**, not a truncation (a truncation would give 8.3144). (2) The
  relative error recomputes to `(8.3145 - 8.31446261815324)/8.31446261815324 =
  4.496e-06 = 0.00045%`, ~4.5x the stated 0.0001%. Fixed in the JSON `value`,
  the JSON `traps`, and unit-trap #5 here. Added the honest note: **negligible at
  CALPHAD precision** (the assessed TDB parameters and the ideal-mixing term it
  multiplies carry uncertainties orders of magnitude larger). `variables.py:939`
  `si_gas_constant = R = Float(8.3145)` confirmed exact.
- **GM normalization mechanism: CLARIFIED.** The scan attributed GM's
  per-mole-of-atoms basis to "`model.py:484` normalized by
  `_site_ratio_normalization`". But `model.py:484` is bare `energy = GM =
  property(lambda self: self.ast)`. The per-mole-of-atoms basis is real but
  arises one level down: each contribution (`reference_energy` :931,
  `ideal_mixing_energy` :957, `excess_mixing_energy` :979, magnetic/einstein/
  volume/order :999-1189) is divided by `_site_ratio_normalization` as it enters
  `ast`; `G = formulaenergy = ast * _site_ratio_normalization` (:485) multiplies
  it back out. VERIFIED `_site_ratio_normalization` (:627-638) sums
  `site_ratio * (number_of_atoms * site_fraction)` = atoms per formula unit, so
  the "mole" in GM's J/mol is genuinely mole-of-atoms. Physics unchanged;
  mechanism wording fixed in JSON + the triple-ambiguity item.
- **Stray line ref: CORRECTED.** JSON system-moles `source` cited `:834` for
  Pressure; `:834` is inside the ChemicalPotential docstring. PressureType is at
  `variables.py:912-915`. Fixed.

### Per-entry verdicts

- **molar-gibbs-energy: CONFIRMED (new-node-candidate).** `units.py:29-31`
  GM='J / mol' name 'Gibbs Energy'; `model.py:484` `energy = GM`. Dimension
  ENERGY_PER_MOLE (1,2,-2,0,-1,0,0) matches `dimensions.py:106`. Map genuinely
  lacks a molar-Gibbs node (registry has no `molar_gibbs_energy`; graph.json has
  no MolarGibbsEnergy). Per-mole-of-atoms basis clarified (above). Headline new
  node stands.
- **molar-enthalpy: CONFIRMED (new-node-candidate).** `units.py:35-40` HM=GM
  units, name 'Enthalpy', H='J' extensive; `model.py:487` `enthalpy = HM = GM -
  T·GM.diff(T)`. `HM_MIX` at :492 confirmed. Map lacks `molar_enthalpy` in both
  registry and graph.json. Stands.
- **molar-entropy: CONFIRMED (already-mapped, cousin).** `units.py:41-42`
  SM='J / mol / K' name 'Entropy'; `model.py:486` `entropy = SM = -GM.diff(T)`;
  ideal-mixing uses `v.R` at `:957`. Map's `MolarEntropy` (nodes.py:221-230,
  registry `molar_entropy`) VERIFIED as "entropy per mole of **primitive unit
  cells**", phonon (`S_mol = (N_A/N_q) Σ s_qν`). Same dimension
  ENERGY_PER_TEMPERATURE_PER_MOLE, DIFFERENT basis (atoms vs cells) and physics
  (assessed Gibbs vs harmonic phonon). Cousin verdict correct; never a naive
  equate.
- **molar-heat-capacity: CONFIRMED (already-mapped, cousin).** `units.py:44-45`
  CPM='J / mol / K' name 'Heat Capacity'; `model.py:489` `heat_capacity = CPM =
  -T·GM.diff(T,T)`. Map's `MolarHeatCapacity` (nodes.py:156-166) VERIFIED: field
  is literally named **`C_V_mol`** with description "per mole of **primitive unit
  cells**", `C_V_mol = (N_A/N_q) Σ c_qν`. So the map node IS constant-volume
  C_V; CALPHAD CPM is constant-pressure C_P. `C_P != C_V` verdict is
  source-backed on both sides. The per-mode `HeatCapacity` node
  (nodes.py:140, ENERGY_PER_TEMPERATURE, indexed (q,ν)) is a different dimension
  and kind, as the scan says. Cousin verdict correct.
- **chemical-potential: CONFIRMED (new-node-candidate).** `variables.py:830-836`
  ChemicalPotential 'J / mol', display_name property; `:937` `MU =
  ChemicalPotential`; `:941` `CONDITIONS_REQUIRING_HESSIANS = {ChemicalPotential,
  PhaseFraction}` VERIFIED. `equilibrium.py:81` `chemical_potentials =
  properties.MU[index]`. No map node. Stands.
- **phase-fraction: CONFIRMED (new-node-candidate).** `variables.py:488-505`
  PhaseFraction 'fraction', varname 'NP_'+phase, `result += compset.NP`; `:938`
  `NP = PhaseFraction`. Skill usage `plot_phase_fractions.py:73-92` (`eq.NP`
  indexed `[0,0,temp_idx,0,idx]`, threshold `>1e-3`) and `:96` ylabel 'Phase
  Fraction' VERIFIED verbatim. Dimensionless, no map analog. Stands.
- **site-fraction: CONFIRMED (representation-only).** `variables.py:412-417`
  SiteFraction 'fraction'; `:482-485` `Y(phase,subl,species)` repr VERIFIED.
  `model.py:410-461` moles/site_ratios confirmed. Internal CEF DOF, not an
  observable. Verdict holds.
- **activity: CONFIRMED (new-node-candidate).** `metaproperties.py:232`
  `class ReferenceState` VERIFIED (the reference-plane-shift mechanism activity
  is built on). Not a hardcoded StateVariable; derived dimensionless
  `exp((μ-μ_ref)/RT)`. Not read by either skill (correctly flagged). Stands.
- **transition-temperature: CONFIRMED (new-node-candidate).**
  `variables.py:901-904` TemperatureType 'kelvin'; skill `plot_phase_diagram.py:
  62-67` conds, `:76` binplot, `:80-81` axes VERIFIED. Al-Zn README numbers
  (liquidus ~933K->692K, eutectoid ~550K, FCC miscibility gap) VERIFIED in
  `examples/Al-Zn/README.md`. Output-temperature-vs-input-Temperature distinction
  correct. Stands.
- **phase-diagram: CONFIRMED (representation-only).** `compat_api.py:6` binplot
  (binary isobaric), `:65` ternplot VERIFIED; SKILL.md line 43 "Ternary isotherms
  require a separate script not yet implemented" VERIFIED verbatim.
  Product/artifact, not a Space. Holds.
- **tdb-assessed-database: CONFIRMED (representation-only).** `Database` /
  `binplot` imports and `plot_phase_diagram.py:51,57` VERIFIED. TDB header
  `examples/Al-Zn/alzn_mey.tdb` VERIFIED: Copyright NIMS 2009, "PARAMETERS ARE
  TAKEN FROM Reevaluation of the Al-Zn System, Sabine an Mey, Z.Metallkd., 84
  (1993) 451-455". Model artifact, MLIP-checkpoint analog. Holds.
- **molar-mass-density-context: CONFIRMED (representation-only).** `units.py:67`
  `molar_weight = 0.0 # g/mol-atom`, `:73` `Q_(molar_weight, 'g/mol')`, `:14`
  `atom = 1/avogadro_number * mol` all VERIFIED verbatim. Direct evidence GM's
  'mol' is mole-of-atoms. Internal machinery, not a node. Holds.
- **system-moles-condition: CONFIRMED (representation-only).**
  `variables.py:922-925` SystemMolesType 'mol' 'No. Moles'; skill
  `plot_phase_diagram.py:62-67` / `plot_phase_fractions.py:65` set
  `{v.N:1, v.P:101325, v.T:(...), v.X(...)}` VERIFIED. The v.N:1 knob pins the
  per-mole-of-atoms basis. Normalization condition, not an observable. Holds.

### Freshness check vs the current 66-node graph

`docs/data/graph.json` has **66 nodes** (matches the task's stated current
graph). The 2 already-mapped entries (`molar_entropy`, `molar_heat_capacity`)
still exist in registry.py and graph.json; the 6 new-node-candidate quantities
(`molar_gibbs_energy`, `molar_enthalpy`, `chemical_potential`, `phase_fraction`,
`activity`, `transition_temperature`) are still absent from registry + graph;
the map still lacks MolarGibbsEnergy and MolarEnthalpy. No status is stale as of
this review. `ENERGY_PER_MOLE` and `ENERGY_PER_TEMPERATURE_PER_MOLE` both present
in `dimensions.py`.

### The Molar* false-merge guardrail (load-bearing): map side VERIFIED

The scan states the **map side** correctly, not just the pycalphad side. Read
from `omai/thermal_transport/operator/nodes.py`:

- `MolarHeatCapacity` (:156-166): field `C_V_mol`, ENERGY_PER_TEMPERATURE_PER_MOLE,
  "per mole of **primitive unit cells**", `C_V_mol = (N_A/N_q) Σ c_qν`. It is
  **constant-volume C_V, harmonic phonon, per mole of cells**, exactly the
  basis the scan claims for the map node. CALPHAD CPM (constant-pressure C_P,
  per mole of atoms, assessed) genuinely differs.
- `MolarHelmholtzFreeEnergy` (:210-218): `F_mol`, "per mole of primitive unit
  cells", phonopy kJ/mol. **Helmholtz (constant V)**, confirms the Gibbs-vs-
  Helmholtz split.
- `MolarEntropy` (:221-230) and `MolarInternalEnergy` (:232-241): both "per mole
  of primitive unit cells", phonon.

`registry.py:105-111` describes all four as "per mole of primitive unit cells"
and has **no** `molar_gibbs_energy` / `molar_enthalpy`. The guardrail (source +
basis + ensemble labels to prevent a CALPHAD SM/CPM false-merging with a phonopy
MolarEntropy/MolarHeatCapacity) is justified: the two sides share the exponent
vector but differ in basis (atoms vs cells), potential (G vs F), ensemble
(const-P vs const-V), and producer.

### Verified factor set

- 1 eV/atom = **96485.33212331** J/mol (= e·N_A; scipy `e*Avogadro =
  96485.33212331001`; SI-exact since 2019 = Faraday constant). CONFIRMED.
- Inverse: 1 J/mol = **1.0364269656262175e-05** eV/atom = **0.010364269656262174**
  meV/atom. CONFIRMED (both digits exact).
- R: pycalphad `8.3145` vs CODATA `8.31446261815324`; rel err **4.496e-06 =
  0.00045%** high (round-up). Negligible at CALPHAD precision. (Scan's earlier
  "0.0001%" CORRECTED.)
- k_B = 8.617333262e-5 eV/K CONFIRMED (matches map's activation-energy anchor).
- phonopy kJ/mol vs pycalphad J/mol: factor 1000, on top of the atoms-vs-cells
  basis difference. CONFIRMED.

### Decisions for the orchestrator (not for the reviewer)

1. **Separate CALPHAD molar nodes vs labels on the phonon `Molar*` nodes
   (highest priority).** Review strongly leans **separate nodes**. Verified on
   both sides: the map's `MolarHeatCapacity` field is literally `C_V_mol` (const
   V, per mole of cells, phonon); CALPHAD CPM is const-P, per mole of atoms,
   assessed. A shared node would false-merge two physically distinct heat
   capacities / entropies. Mint `MolarGibbsEnergy`, `MolarEnthalpy`, and
   source/basis/ensemble-labeled `MolarEntropy[source=calphad]` /
   `MolarHeatCapacity[ensemble=constant_p,source=calphad]` variants. Add
   `molar_gibbs_energy` and `molar_enthalpy` tags (both currently absent) rather
   than relabel the Helmholtz/internal nodes.
2. **Array-valued phase-fraction and transition-temperature ingestion.** `NP(T)`
   and the liquidus/solidus/solvus curves `T(x)` are spectra/arrays (like
   `si-frequency-qe.json`), NOT scalar instances; **invariant points**
   (eutectic/eutectoid `(T,x)`) ARE scalars. Decide the spectrum-layer vs
   scalar-instance ingestion per quantity. Note `binplot` returns a matplotlib
   Axes, not a data table (unit-trap #8): extracting boundary loci for instances
   needs the Workspace/mapping API, not the plot.
3. **activity node now or defer.** Not read by either skill (they consume
   NP/Phase and binplot boundaries); reachable from the same equilibrium MU via
   `ReferenceState` (metaproperties.py:232). Low priority; defer unless a skill
   uses it.
4. **TransitionTemperature as a distinct node vs reusing the Temperature Source.**
   The map's `Temperature` is an INPUT Source; a transition temperature is a
   COMPUTED output locus. Review leans distinct node (`transition_temperature`).
5. **SiteFraction Y: representation coordinate (this review's verdict) vs node.**
   CEF internal DOF, analogous to the pymatgen scan's Voigt-packing / symmetry
   representation-only verdicts. Keep representation-only.
6. **TDB provenance schema.** Confirm the instance schema records
   `{tdb_file, assessment_citation, comps, phases, v.N, v.P, v.T, v.X}` as
   conditions (the TDB is the MLIP-checkpoint analog). Out of this scan's scope
   (does not touch `omai/` or `docs/data` writes).
7. **Version pinning.** `core_env.yaml` pins pycalphad with no version; anchors
   are 0.11.2 from the wheel (base env still lacks pycalphad; calphad-agent env
   not created on this machine). Pin the version at encode time.

### UNVERIFIED

None. pycalphad is not importable in base and the calphad-agent env is not
created here, but every anchor was resolved against the downloaded 0.11.2 wheel
and the in-repo skill scripts. Line numbers in the JSON `source` lists are exact
in every case checked (a rarity), except the one stray `:834` Pressure ref, now
corrected. No entry was KILLED; no anchor failed to support its claim.
