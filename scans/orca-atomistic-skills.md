# ORCA (molecular quantum chemistry) as used by AtomisticSkills: scan report

Scan of **ORCA** as the AtomisticSkills (arXiv 2605.24002) `orca-agent` skills
actually use it. This is the map's **FIRST molecular code**. Every quantity claim
is anchored to a committed `file:line` in `AtomisticSkills/.agents/skills/` (the
three `chem-dft-orca-*` skills, the shared `src/utils/dft/orca_utils.py`, and the
pure-regex `parse_orca_output.py` that reads ORCA `.out` files). ORCA itself is a
proprietary binary (not pip-installable), so quantity claims anchor to the
parsers, not to a captured output file.

Companion catalog: `scans/orca-atomistic-skills.json` (18 entries).

The honesty question the task poses is carried per-entry: which quantities are the
**same physics** as the periodic DFT slice (total energies, forces, frequencies)
and which are **genuinely molecular-domain** (thermochemistry corrections,
solvation, NMR/EPR, HOMO-LUMO). Answered in `physics_vs_periodic` per entry and
summarized below.

## Sources and version anchoring

ORCA is driven two ways:

1. **Through SCINE** (`chem-dft-orca-singlepoint`, `chem-dft-orca-optimization`):
   `su.core.get_calculator("dft", "orca")` generates ORCA input, parses output,
   and returns `su.Property.{Energy,Gradients,Hessian}`. SCINE ReaDuct drives
   geometry / single-ended TS optimization.
2. **Raw binary + regex** (`chem-dft-orca-advanced-calculation`): writes a custom
   `.inp`, runs the ORCA binary via `subprocess`, then `parse_orca_output.py`
   regex-parses the `.out` for energy, orbitals/HOMO-LUMO, frequencies+IR,
   thermochemistry. This parser is the **authoritative quantity list**.

- **Env** `orca-agent`: **no MCP server, scripts only**, requires
  `ORCA_BINARY_PATH`. `core_env.yaml`: `scine-utilities-python`,
  `scine-readuct-python`, `ase`, `numpy<2` (x86_64 only, no aarch64).
  `example_full_env.yaml` pins `scine-utilities==10.1.0`, `scine-readuct==6.1.0`,
  `ase==3.28.0`. **ORCA version 6.1** (advanced skill links the 6.1 tutorials; not
  pinned in any env, it is whatever the binary is).
- One downstream consumer: `chem-spectrum-matcher` uses an ORCA frequency run as
  one route to a predicted **IR spectrum** (SKILL.md:53,112-115), adding no new
  parsed quantity beyond the freq/IR the parser already exposes.
- **Not ORCA-based**: `chem-nmr-analysis` and `chem-nmr-predict` are EMPIRICAL
  (Wasserstein 1H-spectrum deconvolution, SPINUS prediction); they do not consume
  ORCA output. `chem-thermochemistry`, `chem-vibration`, `chem-bond-dissociation`,
  `chem-ts-optimization`, `chem-neb-barrier`, `chem-irc-verification` contain no
  orca/scine reference (they run on MLIP/ASE, the matcalc scan's domain).

## Graph snapshot (freshness at my end)

`docs/data/graph.json` had **77 nodes** at scan time (git HEAD `671b092`), with an
**empty `edges` array**. The **amset encode is landing while I run**:
`ElectricalConductivity[carrier=ionic]` is already a graph node, and
`registry.py` `QUANTITY_TAGS` already carry `seebeck_coefficient`,
`electronic_thermal_conductivity`, `carrier_mobility`,
`static_dielectric_tensor` (records ~154-163), but those four are **not yet graph
nodes** at this HEAD. **Re-read `graph.json` at encode time**; the node count and
the amset tail will have moved.

> **Review correction (2026-07-10):** two snapshot errors. (1) The "**empty
> `edges` array**" is a misreading: `graph.json` has **no `edges` key at all**;
> edges live under the `links` key (D3 convention), never empty. This is the same
> misreading a prior reviewer already fixed on the structure-gen scan. (2) The
> HEAD is stale: the amset encode **has landed**. Re-read at current HEAD
> `36104c1`, `graph.json` now carries **82 nodes / 198 links / 12 tiers**. The
> registry-vs-graph discrepancy the scanner flagged has **resolved**:
> `SeebeckCoefficient`, `ElectronicThermalConductivity`, `CarrierMobility`,
> `StaticDielectricTensor` are all now graph nodes. Every ORCA-relevant node
> below is re-confirmed present, and every absent candidate
> (`DipoleMoment`, `HOMOLUMOGap`, `NMRShift`, `ZeroPointEnergy`, `ReactionBarrier`,
> `SolvationFreeEnergy`) remains absent, so all candidate/deferral statuses stand.

- **Present, relevant to this scan**: `TotalEnergy`, `Forces`, `Stress`,
  `BandGap`, `Frequency`, `MagneticMoment`, `FormationEnergy`, `ReactionEnergy`,
  `ActivationEnergy`, `MolarGibbsEnergy`, `ChemicalPotential`.
- **Absent, relevant**: `DipoleMoment`, `SolvationFreeEnergy`, `ReactionBarrier`,
  `HOMOLUMOGap`, `NMRShift`, `OrbitalEnergy`, molecular `GibbsFreeEnergy`,
  `ZeroPointEnergy`, `IRIntensity`, `ExcitationEnergy`.

## Entry counts by status (18 entries)

| Status | Count | Entries |
|---|---|---|
| already-mapped, same physics | 2 | forces, temperature |
| already-mapped, basis question | 2 | final single-point energy (TotalEnergy), vibrational frequencies (Frequency) |
| molecular-sibling candidate | 2 | HOMO-LUMO gap (vs BandGap), TS energy / reaction barrier (vs ActivationEnergy + deferred NEB) |
| new-node candidate | 6 | Hessian, ZPE, enthalpy, Gibbs, entropy correction, solvation free energy |
| representation-only | 4 | energy components, imaginary-mode count, IR intensities, orbital energies |
| not surfaced by skills | 2 | dipole moment, NMR shift |

(2 + 2 + 2 + 6 + 4 + 2 = 18.)

> **Review correction (2026-07-10):** the scan originally said "19 entries" here
> and in the companion line above. The `entries` array holds **18** objects. The
> phantom 19th came from double-counting `orca-total-energy-component`: it was
> listed under "same physics" AND under "representation-only" (its true status).
> The same-physics bucket is 2 (forces, temperature), not 3; the JSON
> `entry_counts_by_status` is corrected to total 18.

## The per-molecule basis proposal (the crux)

The map's `TotalEnergy` is defined as **"extensive: one scalar per simulation
CELL"** (`dft_ground_state/operator/nodes.py:78-88`). A molecular total energy is
**"one scalar per MOLECULE"**. Both are extensive `ENERGY` scalars with an empty
index tuple `()`. **The observable shape is identical**; only the substrate
differs (finite molecule, no PBC vs periodic cell).

**Recommendation: same `TotalEnergy` node + a required basis/provenance label**,
not a parallel molecular node hierarchy. The label records `(basis =
per_molecule | per_cell, code = orca | qe | vasp, electron_treatment =
all_electron | ecp | pseudopotential, functional, basis_set, dispersion,
solvation)`. The load-bearing job of the label is to **forbid cross-substrate
subtraction**: an ORCA all-electron molecular total energy and a QE
pseudopotential cell energy sit on **different absolute energy-zero scales** and
must never be differenced. This mirrors how the map already lets `BandGap` ride
`Potential` provenance and keeps same-typed quantities apart by labels, not by
dimension.

Four distinct bases now coexist in the ENERGY family: **per-molecule** (ORCA,
Hartree, N=0), **per-cell** (map `TotalEnergy`), **per-mole-of-atoms** (CALPHAD
`MolarGibbsEnergy`/`ChemicalPotential`, ENERGY_PER_MOLE, N=-1), **per-mole-of-
cells** (phonon `Molar*`). A label must carry which.

## The molecular-vs-periodic node questions

**TotalEnergy**: SAME node + mandatory basis label (above). Identical dimension
and shape; the difference (no PBC, all-electron vs pseudopotential energy-zero) is
provenance metadata that blocks cross-code subtraction. Do NOT mint a separate
`MolecularEnergy` node.

**Forces**: SAME node, no question. Hellmann-Feynman `-dE/dR`, per-atom
`(i, alpha)`, identical to the periodic `Forces` node
(`dft_ground_state/operator/nodes.py:91-93`). ORCA gives analytic gradients; the
`force = -gradient` sign flip and Hartree/Bohr -> eV/Angstrom conversion are
representation-layer (`run_singlepoint.py:135-143`).

**Frequency**: SAME quantity tag `frequency`, BUT the **index signature does not
fit**. The map's `Frequency` is `omega_{q,nu}` indexed `(q, nu)` = (qpoint,
branch) (`thermal_transport/operator/nodes.py:133-134`). A molecule has **no
qpoint and no branch**, only 3N-6 discrete modes. Recommend a molecular
`Frequency` variant with a **NEW index kind `mode`** (the map's first non-periodic
frequency axis), served in **cm^-1** (a spectroscopic wavenumber), with the
imaginary-mode count as a derived label (0 = minimum, 1 = TS). A molecular normal
mode IS a gamma-point phonon of a hypothetical isolated cell.

**HOMO-LUMO gap vs BandGap**: **COUSINS, not the same node**. Same `ENERGY`
dimension, same KS-eigenvalue-gap family, same caveats (both KS-not-quasiparticle,
both underestimated by semilocal functionals). BUT `BandGap` is VBM-to-CBM over
the Brillouin zone (`nodes.py:134-151`); HOMO-LUMO is between two **discrete
frontier MOs** of a finite system with **no bands**. Recommend a distinct
molecular `HOMOLUMOGap` node: calling it `BandGap` is a category error (a molecule
has no band structure). This mirrors the per-cell/per-molecule `TotalEnergy`
split.

## The exact conversion-factor set

- **Hartree -> eV**: `HARTREE_TO_EV = 27.211386245988` (hardcoded
  `parse_orca_output.py:32`; literal `27.211386245988` inline at
  `run_orca_input.py:93`; `su.EV_PER_HARTREE` in `orca_utils.py:27`). ORCA reports
  **Hartree (Eh) natively for ALL energies** (SCF, orbital, ZPE, enthalpy, Gibbs,
  entropy correction). The map serves eV. **This is the unit trap of the day.**
- **Bohr -> Angstrom**: `BOHR_PER_ANGSTROM = su.BOHR_PER_ANGSTROM` (~1.8897259886,
  `orca_utils.py:28`). Forces: `Hartree/Bohr * HARTREE_TO_EV * BOHR_PER_ANGSTROM
  -> eV/Angstrom` (`run_singlepoint.py:137`). Hessian: `* HARTREE_TO_EV *
  BOHR_PER_ANGSTROM^2 -> eV/Angstrom^2` (`:147`).
- **cm^-1 (wavenumber) -> angular frequency**: `omega[rad/s] = 2*pi*c*nu_tilde`,
  `c = 2.99792458e10 cm/s`. Same `FREQUENCY` dimension after the bridge, different
  unit. Imaginary modes are **negative cm^-1**.
- **kcal/mol and kJ/mol** (the chemist's thermochemistry, NOT parsed by any
  AtomisticSkills path): `1 Hartree = 627.5094740631 kcal/mol = 2625.499639479
  kJ/mol`; `1 kcal/mol = 4.184 kJ/mol` (thermochemical calorie, exact); `1 eV =
  23.060547830619 kcal/mol`. These are **per-mole-of-MOLECULES** (N=-1, dimension
  ENERGY_PER_MOLE), a **different basis** from the CALPHAD **per-mole-of-ATOMS**
  ENERGY_PER_MOLE nodes. Faraday bridge for eV<->per-mole: `1 eV/particle =
  96.48533212331 kJ/mol`.
- **Dipole** (not parsed): `1 Debye = 3.33564e-30 C*m`; `1 a.u. (e*a0) = 2.541746
  Debye`.
- **IR intensity**: km/mol; **NMR shift**: ppm (dimensionless).

## Traps found

1. **Hartree everywhere**: every ORCA energy is Hartree; convert with
   `27.211386245988`.
2. **Four ENERGY bases**: per-molecule (ORCA, N=0) vs per-cell (map TotalEnergy)
   vs per-mole-of-atoms (CALPHAD, N=-1) vs per-mole-of-cells (phonon Molar*). A
   label must carry which.
3. **Energy-zero reference differs**: ORCA all-electron/ECP Gaussian-basis energy
   zero is NOT the pseudopotential zero of QE/VASP. Never subtract ORCA vs
   periodic totals across codes.
4. **cm^-1 is a wavenumber**, not angular frequency (bridge `2*pi*c`). Imaginary
   frequencies are printed **negative**; `n_imaginary` = 0 (min) / 1 (TS)
   (`run_optimization.py:240-247`).
5. **Entropy correction is parsed as the `T*S` product in Hartree** (energy), NOT
   the entropy `S`. Divide by `temperature_K` for `S` in ENERGY_PER_TEMPERATURE
   (`parse_orca_output.py:145-151`).
6. **Basis-set provenance is the checkpoint analog**: the `def2-SVP`/`PBE`
   defaults are low-accuracy; results ride on `(functional, basis_set, dispersion,
   solvation, special_option)`. `wB97M-V` needs a documented hack for any
   hyphenated functional (`--functional '' --dispersion '' --special_option
   wB97M-V`, `SKILL.md:98-101`). Record the full method string.
7. **Frozen-core / DLPNO**: `DLPNO-CCSD(T)` runs through the SAME single-point
   skill and its correlated energy is labeled `final_energy` identically to a DFT
   energy (`SKILL.md:119-134`). A CCSD(T) total and a DFT total share the key but
   are different physics; the frozen-core default and DLPNO thresholds are
   uncaptured provenance.
8. **Dispersion** is folded into the method string
   (`method = f"{functional}-{dispersion}"`, `orca_utils.py:160-161`) AND parsed
   separately (`dispersion_correction_hartree`); it is part of the reported total,
   not additive on top.
9. **Solvation**: `--solvation` requires `--solvent` (`orca_utils.py:146-150`).
   The solvated single point returns the ordinary energy tagged with
   solvation/solvent; **no G_solv difference is computed**. Do not read a
   solvation free energy off a single run.

## Open questions (full list in JSON `open_questions`)

1. **TotalEnergy basis label**: required provenance label with cross-substrate
   subtraction forbidden? (Recommended: yes, same node + label.)
2. **Molecular Frequency**: new index kind `mode` (no qpoint, no branch), served
   cm^-1, `n_imaginary` as label? (Recommended.)
3. **HOMOLUMOGap**: distinct molecular node (recommended) vs `BandGap` + basis
   label? A molecule has no bands, so a distinct node avoids a category error.
4. **Molecular thermochemistry family**: mint a per-molecule gas-phase RRHO
   bundle (`ZeroPointEnergy`, `MolecularEnthalpy`, `MolecularGibbsEnergy`, entropy
   correction), kept apart from the CALPHAD per-mole-of-atoms and phonon
   per-mole-of-cells nodes by basis label?
5. **ReactionBarrier / TS energy**: the TS energy grounds a labeled `TotalEnergy`
   (saddle-point, 1 imaginary mode); the barrier delta is agent-level. Unify with
   the **deferred NEB barrier** and Arrhenius `ActivationEnergy` under one family
   kept apart by construction label (static-TS vs NEB-MEP vs Arrhenius-slope)?
6. **SolvationFreeEnergy**: NOT surfaced (skills tag solvation on/off, do not
   compute G_solv). Encode solvated runs as labeled `TotalEnergy` for now.
7. **Molecular Hessian**: representation-only intermediate (recommended) or a node
   feeding a gamma-point-only `ForceConstants` variant?
8. **DipoleMoment** (Debye, new dimension charge*length, I=1 L=1) and **NMRShift**
   (ppm): genuinely molecular-domain but NOT surfaced by any ORCA parser (agent
   reads `.property.txt` manually). Defer both.
9. **Snapshot drift**: scanned HEAD `671b092`, 77 nodes, empty edges,
   amset tail partly landed. Re-read `graph.json` at encode time.

## Source anchors

- **Skills**: `chem-dft-orca-singlepoint/SKILL.md:1-168`,
  `scripts/run_singlepoint.py:32-155`;
  `chem-dft-orca-optimization/scripts/run_optimization.py:130-249`;
  `chem-dft-orca-advanced-calculation/SKILL.md:1-170`,
  `scripts/parse_orca_output.py:32-205` (authoritative parsed-quantity list),
  `scripts/run_orca_input.py:33-106`;
  `chem-spectrum-matcher/SKILL.md:53,112-115,168,180,206-208`;
  `src/utils/dft/orca_utils.py:27-28,58-71,103-217`;
  `conda-envs/orca-agent/{core_env,example_full_env}.yaml`.
- **Map side**: `omai/dft_ground_state/operator/nodes.py:78-89` (TotalEnergy,
  extensive per cell), `:91-103` (Forces), `:134-151` (BandGap, KS gap);
  `omai/thermal_transport/operator/nodes.py:133-134` (Frequency, indices q,nu);
  `omai/operator/dimensions.py:96,91,106,114,108` (ENERGY, FREQUENCY,
  ENERGY_PER_MOLE, FORCE, ENERGY_PER_LENGTH_SQUARED);
  `omai/operator/registry.py:84-152` (QUANTITY_TAGS);
  `docs/data/graph.json` (HEAD `671b092`, 77 nodes, empty edges).

## Review verdicts (2026-07-10)

Adversarial deep review of commit `9c8add9`'s catalog (18 entries), independent of
the scanner. The three-skill ORCA surface re-grepped over all **126** skills; the
parser (`parse_orca_output.py`) opened and every parsed quantity re-derived with
line numbers; all conversion factors recomputed against `scipy.constants`
(CODATA-2022); map side read from `omai/operator/{registry,dimensions}.py`,
`omai/dft_ground_state/operator/nodes.py`, `omai/thermal_transport/operator/nodes.py`,
and `docs/data/graph.json` re-read at current HEAD `36104c1` (**82 nodes / 198
links / 12 tiers**). **Em-dash grep over both scan files: zero.**

**Verdict: 18/18 entries VERIFIED. No status changed.** Every file:line anchor
spot-checked accurate. Two corrections applied (both recorded inline above): the
graph-snapshot `edges`->`links` misreading plus the stale HEAD, and the
entry-count arithmetic (18, not 19: the scanner double-counted
`orca-total-energy-component` under both "same physics" and "representation-only").

### Three-skill ORCA surface: CONFIRMED

Only `chem-dft-orca-{singlepoint,optimization,advanced-calculation}` invoke ORCA
(singlepoint/optimization through SCINE `su.core.get_calculator("dft","orca")`;
advanced through a raw `ORCA_BINARY_PATH` `subprocess` + the regex parser).
`chem-spectrum-matcher` is a downstream consumer of an ORCA IR run and adds no new
parsed quantity. The two extra case-insensitive `orca` grep hits are **substring
false positives**: `resorcarene` (a COD paper title in
`mat-db-optimade/examples/query-cod/results.json`) and `Oscillator`
(`mat-solid-free-energy` `HarmonicOscillatorCalculator`). All negative claims
re-verified: `chem-nmr-analysis`, `chem-nmr-predict`, `chem-thermochemistry`,
`chem-vibration`, `chem-neb-barrier`, `chem-bond-dissociation`,
`chem-ts-optimization`, `chem-irc-verification`, `chem-react-ot`,
`chem-conformer-search` carry **zero** orca/scine/readuct references.

### The four flagged parser claims: all CONFIRMED

1. **T\*S-product-not-S**: `parse_orca_output.py:145-147` captures `Total entropy
   correction ... Eh` (energy), the `-T*S` term, **not** the entropy `S`. No `S`
   in J/(mol K) is ever parsed. `S = entropy_correction / temperature_K`.
2. **Imaginary-frequencies-printed-negative**: the regex parser flags `f < 0` as
   imaginary (`:106`); the SCINE path flags `n < -1e-6` (`run_optimization.py:234`,
   a numerical-tolerance variant). TS wants exactly 1, min wants 0.
3. **`final_energy` DLPNO/DFT collision**: the `FINAL SINGLE POINT ENERGY` regex
   (`:39`, `run_orca_input.py:33`) is method-blind. ORCA writes that header for
   DFT, DLPNO-CCSD(T), and CASSCF alike, all keyed `final_energy`; a correlated
   CCSD(T) total and a DFT total share the key but are different physics.
4. **Hardcoded `27.211386245988`**: confirmed at `parse_orca_output.py:32` and
   inline at `run_orca_input.py:93`. It is the CODATA-2018 value; `scipy` 1.16
   (CODATA-2022) gives `27.211386245981` (last two digits differ, within CODATA
   uncertainty). "Exact match to the eV working unit" is essentially correct.

### Conversion factors: all recomputed against scipy CODATA, all confirmed

| factor | claimed | scipy (CODATA-2022) |
|---|---|---|
| Hartree -> eV | 27.211386245988 | 27.211386245981 (within uncertainty) |
| Hartree -> kcal/mol | 627.5094740631 | 627.5094740629 |
| Hartree -> kJ/mol | 2625.499639479 | 2625.499639479 |
| eV -> kcal/mol | 23.060547830619 | 23.060547830619 (exact) |
| eV/particle -> kJ/mol | 96.48533212331 | 96.48533212331 (exact) |
| kcal/mol -> kJ/mol | 4.184 | 4.184 (exact, thermochem calorie) |
| Debye | 3.33564e-30 C\*m | 3.33564095e-30 |
| a.u. dipole (e\*a0) | 2.541746 D | 2.5417465 D |

### Basis-proposal FACTS: all CONFIRMED

- `TotalEnergy` per-cell: `nodes.py:82-88` "Extensive: one scalar per simulation
  cell" (verbatim).
- `Frequency` `(q, nu)` signature: `thermal_transport/nodes.py:135`
  `indices=("q","nu")`; a molecule has no qpoint/branch.
- `BandGap` VBM-CBM: `nodes.py:136-151` "valence-band maximum and the
  conduction-band minimum", "KS gap, NOT the fundamental (quasiparticle) gap",
  "rides with the `Potential` provenance".
- Four ENERGY bases confirmed in `registry.py`: per-cell (`:87`), per-mole-of-cells
  (`:114-120`, "per mole of primitive unit cells"), per-mole-of-atoms (`:143-144`,
  "per mole of atoms ... SER reference"), per-molecule (ORCA, N=0).

### Orchestrator decisions

- **TotalEnergy**: same node + a required provenance label (`basis`, `code`,
  `electron_treatment`, `functional`, `basis_set`, `dispersion`, `solvation`); the
  label forbids cross-substrate subtraction. No separate `MolecularEnergy` node.
- **Molecular Frequency**: mint a new index kind `mode` (no qpoint, no branch),
  same `frequency` tag, served cm^-1, `n_imaginary` a derived label (0=min, 1=TS).
- **HOMOLUMOGap**: mint a distinct molecular node (not `BandGap`+label): a molecule
  has no bands, so equating with `BandGap` is a category error. Cousin, not same.
- **TS / barrier family**: one `ReactionBarrier`/`ActivationEnergy` family kept
  apart by a construction label (static-TS vs NEB-MEP vs Arrhenius-slope). TS
  energy grounds a labeled `TotalEnergy` (saddle-point, 1 imaginary mode); mint
  `ReactionBarrier` only when a skill computes the delta.
- **Thermochemistry bundle**: mint a molecular-RRHO family (`ZeroPointEnergy`,
  `MolecularEnthalpy`, `MolecularGibbsEnergy`, entropy correction) with a
  construction label, kept apart from CALPHAD per-mole-of-atoms and phonon
  per-mole-of-cells nodes. The entropy member is stored as `T*S` (energy), not `S`.
- **Dipole / NMR**: defer both (not surfaced by any parser; the agent reads
  `.property.txt` manually).
- **Solvation**: encode solvated single points as a labeled `TotalEnergy` for now;
  mint `SolvationFreeEnergy` only when a skill computes gas-minus-solvated.
- **Molecular Hessian**: representation-only intermediate; the skills surface the
  derived wavenumbers, not the raw Hessian.
