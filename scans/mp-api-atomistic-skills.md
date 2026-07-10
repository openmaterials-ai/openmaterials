# mp-api / Materials Project as used by AtomisticSkills: scan report

Scan of **mp-api** (`mp_api.client.MPRester`) and the **Materials Project**
document models (`emmet-core`) as the AtomisticSkills (arXiv 2605.24002) `mat-*`
skills actually query them. Companion catalog:
`scans/mp-api-atomistic-skills.json` (18 entries). Sources: the MP-querying
scripts under `AtomisticSkills/.agents/skills/` (mat-db-mp `query_mp.py` /
`get_elasticity.py` / `get_magnetism.py` / `get_structure_by_id.py` /
`find_similar_structures.py`, plus `mat-stability/query_mp_hull.py`,
`mat-electronic-structure/get_mp_electronic_structure.py`,
`mat-phonon/get_mp_phonon.py`, and the phase-diagram / elemental-energies /
novelty / substitution scripts). The MP document models were read directly from
the miniconda base env: **mp-api 0.41.2, emmet-core 0.85.1**
(`/Users/juicy/miniconda3/lib/python3.12/site-packages/{mp_api/client,
emmet/core}`); field units are quoted from `emmet/core/summary.py`,
`elasticity.py`, `magnetism.py`, `electrode.py`, `structure.py`, `thermo.py`,
and `types/enums.py`. All MPRester routes the skills use (summary, thermo,
elasticity, magnetism, phonon, electronic_structure_bandstructure /
electronic_structure_dos, tasks, insertion_electrodes) are verified present in
`mp_api/client/mprester.py`.

## What Materials Project IS in this software: a DATABASE, not an engine

This scan target is conceptually special. QE, VASP, LAMMPS, MLIPs are ENGINES:
you run them and they produce a value. MP is a **DATABASE**: a representation
whose artifacts are database **records** carrying **already-computed** values for
mapped quantities. Those values were themselves computed by VASP DFT workflows
(MP's provenance is the atomate2/VASP stack the `atomate2-vasp` scan catalogs),
so **the VASP catalog's conventions apply to MP fields**: MP energies are a VASP
`e_0_energy`-family variant with MP2020 corrections, MP stress (trajectory
endpoint) is kbar, and MP elastic / magnetic values are pymatgen post-processing
outputs. MP fills two distinct roles for the map:

1. **A RETRIEVAL representation** of quantities the map already has: `Structure`,
   `ElasticConstants` / `BulkModulus` / `ShearModulus`, `ForceConstants[order=2]`,
   `Frequency` / `PhononDOS`, `DielectricTensor`, per-atom energetics.
2. **An INSTANCE SOURCE**: each `(material_id, value)` record is a piece of
   evidence (kind `simulation`, `ref` `materials-project` + mp-id) with the MP
   functional / mixing-scheme as conditions provenance. This is MP's highest
   value to the project, and the dedicated design section below specifies it.

AtomisticSkills reaches MP through `MPRester.materials.<endpoint>.search` /
`.get_*_by_id`; the API key is `MP_API_KEY`.

## Entry counts by status (18 entries)

These counts were CORRECTED in deep review (2026-07-09). The original scanner
reported 9 / 7 / 2, computed against an earlier graph snapshot. Re-checking every
status against the current `docs/data/graph.json` (66 nodes) found seven nodes the
scanner had called candidates now PRESENT (FormationEnergy, EnergyAboveHull,
YoungsModulus, PoissonRatio, MagneticMoment, SurfaceEnergy, Voltage), six of them
with committed instance records. Corrected live counts: **14 already-mapped, 2
new-node-candidate, 2 representation-only**. See "Review verdicts (2026-07-09)".

- **already-mapped: 14**: mp-structure-record (`Structure`),
  mp-cell-volume-and-density (`CellVolume` / `AtomCount`),
  mp-total-energy-and-per-atom (`TotalEnergy`, per-cell trajectory route only),
  mp-formation-energy (`FormationEnergy`, node now present),
  mp-energy-above-hull (`EnergyAboveHull`, node now present),
  mp-bulk-modulus (`BulkModulus`), mp-shear-modulus (`ShearModulus`),
  mp-elastic-tensor (`ElasticConstants`),
  mp-youngs-modulus-and-poisson (`YoungsModulus` / `PoissonRatio`, nodes now
  present; `universal_anisotropy` still tagless),
  mp-magnetic-moment (`MagneticMoment`, per-site, node now present),
  mp-phonon-bandstructure-dos-forceconstants (`Frequency` / `PhononDOS` /
  `ForceConstants[order=2]`), mp-surface-energy (`SurfaceEnergy`, node now
  present; Wulff-weighted aggregate, MP-has-it-but-unused),
  mp-intercalation-voltage (`Voltage`, node now present; MP-has-it-but-unused),
  mp-dielectric-constants (`DielectricTensor`, electronic part).
- **new-node-candidate: 2**: mp-band-gap-and-electronic-structure (NO tag, no
  node; new domain), mp-mass-density (NO tag; derivable). (Plus
  `universal_anisotropy` inside mp-youngs-modulus-and-poisson: no tag, no node.)
- **representation-only: 2**: mp-material-provenance (the
  functional/mixing-scheme + mp-id provenance layer, MP's analog of the VASP
  scan's atomate2-workflow-framework), mp-structure-similarity (CrystalNN /
  StructureMatcher retrieval, same verdict as the pymatgen scan).

## Which in-flight pymatgen encode nodes MP grounds directly

The pymatgen encode set in flight (FormationEnergy, EnergyAboveHull,
SurfaceEnergy, Voltage, MagneticMoment, YoungsModulus, PoissonRatio) is largely
**served directly by MP fields**, in most cases with no in-skill computation:

| in-flight node | MP field (endpoint) | units MP serves | trap |
|---|---|---|---|
| FormationEnergy | `SummaryDoc.formation_energy_per_atom` (summary) | eV/atom | MP-fitted refs + MP2020 corrections (distinct reference state from MLIP route) |
| EnergyAboveHull | `SummaryDoc.energy_above_hull` (summary/thermo) | eV/atom | provenance is the WHOLE hull at one thermo_type |
| BulkModulus | `ElasticityDoc.bulk_modulus.vrh` (elasticity) | **GPa directly** | NOT eV/A^3; do not apply *160.2176634 |
| ShearModulus | `ElasticityDoc.shear_modulus.vrh` (elasticity) | **GPa directly** | same |
| YoungsModulus | `ElasticityDoc.young_modulus` (elasticity) | **SI Pa** | DIVIDE by 1e9 for GPa |
| PoissonRatio | `ElasticityDoc.homogeneous_poisson` (elasticity) | dimensionless | (none) |
| MagneticMoment (per-site) | `MagnetismDoc.magmoms` (magnetism) | mu_B per site | do NOT use per-cell `total_magnetization` |
| Voltage | `InsertionElectrodeDoc.average_voltage` (insertion_electrodes) | V | MP-has-it-but-unused by the skills |
| SurfaceEnergy | `SummaryDoc.weighted_surface_energy` (summary) | J/m^2 (and eV/A^2) | Wulff-WEIGHTED aggregate, not one (hkl) facet; MP-has-it-but-unused |

MP is thus the DFT-database sibling of the MLIP records already in the store:
`cu-bulkmodulus-atomisticskills-mat-elasticity-cu.json` and
`cu-shearmodulus-...` are exactly the (BulkModulus/ShearModulus, GPa, VRH) shape
an MP record would take, differing only in provenance (DFT database vs MACE-OMAT
MLIP). That makes MP records natural **EXPECTED_AGREE** witnesses.

## Normalization and unit traps found (the precision duty)

1. **Elasticity is GPa, not eV/A^3 (headline).** MP serves `bulk_modulus.vrh`,
   `shear_modulus.vrh`, and `elastic_tensor.{raw, ieee_format}` (Voigt 6x6) all
   in **GPa** (`elasticity.py:24-58`), because emmet's ElasticityDoc pipeline
   post-processes pymatgen's elastic tensor into GPa. A consumer must **not**
   apply the `160.2176634` eV/A^3 -> GPa factor that the raw-pymatgen MLIP route
   needs (pymatgen scan). This is the opposite trap direction from raw pymatgen.

2. **Young's modulus is SI Pascal, not GPa.** `ElasticityDoc.young_modulus`
   carries pymatgen's `y_mod` (the `9.0e9` factor), served in **Pa**
   (`elasticity.py:188-189`, and the in-source comment `:706` "note it is in Pa,
   not GPa"). DIVIDE by 1e9 for the map's GPa convention. Same 1e9 mismatch the
   pymatgen scan flagged in pymatgen's `y_mod`, but here MP actually **serves**
   the Pa value. Two different unit conventions inside one elasticity document.

3. **Magnetization normalizations (headline for magnetism).**
   `total_magnetization` is **TOTAL mu_B (per cell)** and is `abs()`-ed
   (`magnetism.py:57-59, 81-82`), so **the sign is lost**. The per-formula-unit
   value is the SEPARATE field `total_magnetization_normalized_formula_units`
   (mu_B/f.u.); the per-volume value is `total_magnetization_normalized_vol`
   (mu_B/A^3). The registry's `magnetic_moment` tag is **per-site**, matched by
   MP's `magmoms` (per-site list). Do not feed per-cell `total_magnetization` to
   a per-site MagneticMoment node. (The task brief's "total_magnetization mu_B
   per formula unit" is precisely the trap: the primary field is per-cell total;
   per-f.u. is a distinct normalized field.)

4. **Three energy quantities + the MP2020 correction.** MP exposes
   `uncorrected_energy_per_atom` (raw DFT eV/atom), `energy_per_atom`
   (MP2020-corrected eV/atom), and the trajectory-endpoint `e_wo_entrp` (raw
   per-cell eV). Only the PER-CELL trajectory `e_wo_entrp` maps to the map's
   per-cell `TotalEnergy`; the per-atom fields belong to the FormationEnergy /
   per-atom-energy family. `e_wo_entrp` is a DIFFERENT VASP variant than the VASP
   scan's `e_0_energy` (pymatgen `final_energy`). AtomisticSkills deliberately
   harvests raw trajectory `e_wo_entrp` for MLIP training to avoid the MP2020
   corrections baked into `energy_per_atom` (`query_mp.py:141-142`).

5. **Functional / mixing-scheme provenance.** `thermo_type` is one of
   `{GGA_GGA+U, GGA_GGA+U_R2SCAN, R2SCAN}` (`types/enums.py:154-159`).
   `GGA_GGA+U_R2SCAN` is a **mixing** scheme (r2SCAN energies referenced onto the
   GGA/GGA+U hull). A GGA hull and an R2SCAN hull give different
   `energy_above_hull` for the same material, so every MP-as-instance record must
   carry `thermo_type` in conditions.

6. **`density_atomic` impl/doc mismatch.** emmet populates
   `SummaryDoc.density_atomic` as `volume/num_sites` = A^3/atom
   (`structure.py:157`) but its description string says "atoms per cm^3"
   (`structure.py:74`). Trust the implementation if ever ingested.

## Quantities the map lacks entirely (new-domain candidates)

- **band_gap (eV)**: no registry tag; the single most-used MP electronic field
  (`mat-db-mp`, `mat-electronic-structure`). Same candidate the pymatgen + VASP
  scans flagged; MP is the DFT-database retrieval producer. Opens the electronic
  domain.
- **universal_anisotropy (A_U, dimensionless)**: no tag; a genuine elastic-
  anisotropy new-node candidate.
- **density (g/cm^3)**: no tag but derivable from CellVolume + AtomicMass +
  AtomCount (contract-tier, low priority).
- Further no-analog MP fields: `e_ionic` / `e_total` (dielectric), refractive
  index `n`, electrode capacity/energy-density (mAh/g, mAh/cc, Wh/kg, Wh/l).

## Instance-source design (how MP records enter as evidence)

Full spec in the JSON `instance_source_design` object; summary:

- **kind**: always `simulation` (MP values are DFT), never `measurement`.
- **source.ref**: DEEP-REVIEW CORRECTION. The scanner recommended
  `ref="materials-project"` with the mp-id in `source.detail`, claiming it matched
  the `qe` / `atomisticskills-*` convention. It does NOT. The two real MP-provenance
  records already committed (`li2o-mp-1960-formationenergy...`,
  `li2o-mp-1960-energyabovehull...`) put the **mp-id in the `material` field**
  (`"Li2O (mp-1960)"`), set `source.ref` to the **skill** name
  (`"atomisticskills-mat-phase-diagram-Li2O"`), and use `source.detail` for a
  physics note plus the example path. No committed record uses `"materials-project"`
  as `ref`. For a pure-MP direct-ingest record (MP as producer, no skill),
  `ref="materials-project"` is a plausible but not-yet-adopted alternative; the
  encode-stage schema owner (Appendix C of `docs/openmaterials.tex`) decides. This
  scan does not touch `omai/` or `docs/data`.
- **conditions** (free-form; confirmed by the committed records, which carry keys
  `thermo`, `polymorph`, `references`, `hull`, `site`, `cell`, `from`, `reference`,
  `working_ion`) carry the MP calculation provenance, mirroring
  `si-totalenergy-qe.json` `{pseudo, ecutwfc, k_mesh, code}` and
  `cu-bulkmodulus...` `{average: VRH, model}`. For MP, conditions should carry:
  (1) the functional / mixing-scheme (the committed pattern uses key `thermo` with
  value `GGA+U`, NOT key `functional` with the enum literal `GGA_GGA+U`; align at
  encode time); (2) for energetics, the MP2020 correction state (corrected vs
  uncorrected); (3) the averaging / orientation scheme where relevant
  (`average: VRH`, IEEE vs structure orientation).
- **value / units per field**: `formation_energy_per_atom` eV/atom;
  `energy_above_hull` eV/atom; `bulk_modulus.vrh` / `shear_modulus.vrh` GPa;
  `young_modulus / 1e9` GPa; `homogeneous_poisson` dimensionless; `magmoms[i]`
  mu_B (per-site); `volume` angstrom^3; trajectory `e_wo_entrp` eV (per-cell);
  `average_voltage` V; `e_electronic` dimensionless. See the JSON
  `per_field_mapping`.
- **uncertainty**: typically `null`. MP does not serve a per-value stochastic
  uncertainty for these DFT fields; systematic functional error is captured by
  `thermo_type` in conditions, not by the uncertainty field (unlike the MLIP MD
  records such as `lgps-activationenergy...` which carry a fit uncertainty).
- **Not ingested as instances**: Structure (not a scalar), phonon spectra / force
  constants (enter via the representation layer like `si-frequency-qe.json`, not
  as a scalar value), and full elastic / dielectric TENSORS. Scalar reductions
  (VRH moduli, band gap, formation energy, e_above_hull, average voltage,
  e_electronic) are the instance-friendly fields.
- **EXPECTED_AGREE partners**: MP DFT records vs the AtomisticSkills MLIP records
  already in the store (MP BulkModulus vs `cu-bulkmodulus` MACE-OMAT; MP
  FormationEnergy / EnergyAboveHull vs `mat-stability` MLIP; MP Voltage vs
  `mat-intercalation-voltage` MLIP). Cross-source agreement is what makes MP a
  valuable independent DFT-database witness alongside the MLIP and QE/VASP
  producers.

## MP-has-it-but-unused

MP serves several fields AtomisticSkills does **not** query but which ground
in-flight / registry nodes, so they are ready DFT-database instance sources
(and EXPECTED_AGREE partners) even though the skills compute the same quantities
via MLIP: `average_voltage` (V, insertion_electrodes) -> registry `voltage`;
`weighted_surface_energy` (J/m^2 and eV/A^2) -> registry `surface_energy`;
`e_electronic` (dimensionless) -> `DielectricTensor`. These are cataloged so the
encode stage knows MP can back-fill DFT evidence for the whole in-flight set.

## Open questions (full list in JSON `open_questions`)

1. **Magnetization normalization** (headline): per-site `magmoms` -> per-site
   MagneticMoment; per-cell `total_magnetization` is abs()-ed (sign lost) and is
   NOT per-f.u. Decide whether per-site / per-f.u. / per-cell magnetization are
   distinct map nodes.
2. **Elasticity units** (headline): MP is GPa directly (no 160x); `young_modulus`
   is SI Pa (divide by 1e9). Two conventions in one document.
3. **Energy variant + correction**: `uncorrected_energy_per_atom` vs
   `energy_per_atom` (MP2020) vs trajectory `e_wo_entrp` (per-cell, raw); match
   the same variant + correction state in any cross-code EXPECTED_AGREE.
4. **Functional / mixing-scheme**: `thermo_type` (GGA_GGA+U / GGA_GGA+U_R2SCAN /
   R2SCAN / **UNKNOWN**, four members; the scanner omitted UNKNOWN) must enter
   conditions on every MP record. The committed records store it under key
   `thermo` with value `GGA+U`, not `thermo_type`/`GGA_GGA+U`.
5. **MP-has-it-but-unused**: `average_voltage`, `weighted_surface_energy`,
   `e_electronic` ground in-flight/registry nodes though the skills do not query
   them.
6. **Quantities with no tag**: `band_gap`, `universal_anisotropy` (new domains);
   `density` (derivable); dielectric `e_ionic`/`e_total`, refractive index,
   electrode capacities have no map analog.
7. **`density_atomic`** impl (A^3/atom) contradicts its "atoms per cm^3"
   description; trust the impl.
8. **source.ref convention** (CORRECTED): the committed MP records put the mp-id
   in the `material` field and set `ref` to the skill, NOT `ref="materials-project"`
   with mp-id in `detail`. The scanner's recommendation is a not-yet-adopted option
   for pure-MP direct ingest; the encode-stage schema owner decides.
9. **emmet-core version**: field names/units read from mp-api 0.41.2 /
   emmet-core 0.85.1; pin emmet-core when an encode relies on a field's units, as
   a future emmet could re-normalize a default.

## Review verdicts (2026-07-09)

Adversarial deep review of commit cdf2594's catalog (18 entries). Every emmet /
pymatgen document field opened and read from the installed source
(`/Users/juicy/miniconda3/lib/python3.12/site-packages/{emmet/core,pymatgen}`,
emmet-core 0.85.1); every AtomisticSkills usage anchor opened in the real script;
every status re-checked against the current `docs/data/graph.json` (66 nodes),
`omai/operator/registry.py`, and the committed `docs/data/instances/*.json`; every
dimension vector recomputed. Default was distrust. The two load-bearing unit
claims (GPa moduli, Pa Young's modulus) were verified beyond docstrings, in the
emmet builder / pymatgen math, not just field descriptions.

### Corrections that changed physics or classification (not typos)

- **STATUS FLIPS (the headline finding), 7 entries.** The scanner ran against an
  earlier graph snapshot and marked `FormationEnergy`, `EnergyAboveHull`,
  `YoungsModulus`, `PoissonRatio`, `MagneticMoment`, `SurfaceEnergy` as
  new-node-candidate and `Voltage` with `node: null`. All seven nodes are PRESENT
  in the current `docs/data/graph.json`, and SIX already have committed instance
  records (`li2o-mp-1960-formationenergy`, `li2o-mp-1960-energyabovehull`,
  `cu-youngsmodulus`, `cu-poissonratio`, `fe-bcc-magneticmoment`,
  `cu-{100,110,111}-surfaceenergy`, `lifepo4-voltage`). Reclassified all seven to
  already-mapped with `node` populated; live counts corrected 9/7/2 -> 14/2/2.
  The sibling pymatgen scan (same date) still calls these candidates; that is a
  cross-scan inconsistency for the orchestrator to reconcile (its snapshot
  predates the nodes landing).
- **INSTANCE-DESIGN source.ref recommendation, CORRECTED.** The scanner's
  `ref="materials-project"` + mp-id-in-`detail` proposal is FALSELY claimed to
  match the existing convention. The two committed MP-provenance records put the
  mp-id in the **`material`** field (`"Li2O (mp-1960)"`), set `ref` to the
  **skill** (`atomisticskills-mat-phase-diagram-Li2O`), and use `detail` for a
  physics note. Grep confirms NO committed record uses `ref="materials-project"`.
  Corrected in the JSON `instance_source_design` (DEEP_REVIEW_SCHEMA_FIT +
  source_ref_format) and here; kept the scanner proposal only as a flagged,
  not-yet-adopted option for pure-MP direct ingest.
- **conditions key names, CORRECTED.** The committed records use conditions key
  `thermo` with value `GGA+U`, not `functional`/`thermo_type` with the enum
  literal `GGA_GGA+U`. conditions IS free-form (confirmed: keys `thermo`,
  `polymorph`, `references`, `hull`, `site`, `cell`, ...), so thermo_type /
  functional / average / correction all fit; the per_field_mapping condition
  examples are design suggestions, not implemented key names.
- **ThermoType enum, CORRECTED (incomplete).** The scanner listed 3 members and
  cited `types/enums.py:154-159`; the enum has a FOURTH member `UNKNOWN="UNKNOWN"`
  on line 160. Fixed in mp-material-provenance and the open questions.
- **query_mp.py energy/trajectory anchors, CORRECTED (~100-line drift).** The
  scanner cited `:141-142` / `:146-159` / `:209` for the e_wo_entrp comment /
  get_trajectory / per-atom division; the real lines are `:260-261` / `:265` +
  `:272-277` / `:328`. The physics and units claims are correct; only the line
  numbers were wrong. Also added the served-in-kbar + `KBAR_TO_EV_A3` stress
  conversion (query_mp.py:203, :285) the scanner did not anchor.

### Load-bearing unit verification (GPa moduli, Pa Young's modulus)

- **Bulk / shear moduli are GPa: CONFIRMED beyond docstring.** Field descriptions
  say GPa (`elasticity.py:45-58`), AND the builder feeds Cauchy stresses whose
  documented expected unit is GPa (`elasticity.py:248` "Expected units: GPa"), so
  the fitted `elastic_tensor` and its VRH averages are GPa by construction; the
  compliance is `*1000` to TPa^-1 "assuming elastic tensor in units of GPa"
  (`elasticity.py:315-318`). The `160.2176634` eV/A^3 -> GPa factor must NOT be
  applied to MP fields. Trap holds.
- **Young's modulus is SI Pa: CONFIRMED beyond docstring.** `young_modulus` is
  populated from pymatgen `prop_dict["y_mod"]` (`elasticity.py:625`), and
  pymatgen `elastic.py:199-204` computes `y_mod = 9.0e9 * k_vrh * g_vrh /
  (3*k_vrh + g_vrh)` with `k_vrh`/`g_vrh` in GPa, so the `9.0e9` factor carries
  GPa -> Pa: the served value is Pascal. Corroborated by the in-source comment
  `elasticity.py:706` "young's modulus (note it is in Pa, not GPa)". DIVIDE by 1e9
  for the map's GPa. Trap holds.

### abs()-ed total_magnetization (sign loss)

- **CONFIRMED in emmet source.** `magnetism.py:81-83`:
  `total_magnetization = abs(total_magnetization)` with the in-source comment
  "not necessarily == sum(magmoms)". The sign is destroyed at populate time, so
  ferrimagnetic / antiferromagnetic sign structure CANNOT be recovered from
  `total_magnetization` (nor from the two normalized variants, which divide the
  same abs'd value). It must come from the per-site `magmoms` list. Added the
  further caveat that MP `magmoms` are `CollinearMagneticStructureAnalyzer`-rounded
  (`round_magmoms=True`, `magnetism.py:84-88`) and the per-cell total need not
  equal their sum. The catalog now states this in mp-magnetic-moment and the
  magnetization open question.

### Energy variant (e_wo_entrp vs e_0_energy)

- **CONFIRMED.** The skill harvests the trajectory `frame["e_wo_entrp"][-1]`
  (energy without entropy, raw per-cell VASP eV) deliberately, to avoid the MP2020
  corrections in summary `energy_per_atom` (comment `query_mp.py:260-261`). This is
  a DIFFERENT VASP smearing variant than the atomate2-vasp scan's `e_0_energy`
  (the sigma->0 extrapolated energy = pymatgen `final_energy`). The catalog keeps
  the three energy quantities cleanly distinct: `uncorrected_energy_per_atom` (raw
  DFT eV/atom), `energy_per_atom` (MP2020-corrected eV/atom), trajectory
  `e_wo_entrp` (raw per-cell eV); only the per-cell `e_wo_entrp` maps to the
  per-cell `TotalEnergy` node, and a cross-code EXPECTED_AGREE must match BOTH the
  variant and the correction state.

### Per-entry verdicts

- mp-structure-record: CONFIRMED. `summary.py:422-426` structure field; get_structure_by_id.py:43; node `Structure` present.
- mp-cell-volume-and-density: CONFIRMED. volume A^3 (`structure.py:61-64`), density g/cm^3 (`:67-69`), density_atomic impl A^3/atom (`:157`) vs "atoms per cm^3" description (`:74`) mismatch verified. Nodes `CellVolume` / `AtomCount` present.
- mp-total-energy-and-per-atom: CONFIRMED (physics) + anchors CORRECTED. Three-energy distinction sound; `TotalEnergy` present (per-cell trajectory route only). query_mp.py line numbers fixed.
- mp-formation-energy: RECLASSIFIED new-node-candidate -> already-mapped. `summary.py:167-170` eV/atom; node `FormationEnergy` present; committed instance li2o-mp-1960-formationenergy. Reference-state/MP2020 trap unchanged.
- mp-energy-above-hull: RECLASSIFIED -> already-mapped. `summary.py:172-175` eV/Atom; node `EnergyAboveHull` present; committed instance li2o-mp-1960-energyabovehull. Whole-hull provenance caveat kept.
- mp-bulk-modulus: CONFIRMED already-mapped. GPa verified beyond docstring (see above). `BulkModulus` present; MLIP sibling cu-bulkmodulus.
- mp-shear-modulus: CONFIRMED already-mapped. GPa; `ShearModulus` present; MLIP sibling cu-shearmodulus.
- mp-elastic-tensor: CONFIRMED already-mapped. raw/ieee 6x6 GPa (`elasticity.py:24-31`), compliance TPa^-1 (`:34-42`). `ElasticConstants` present. Tensor, not an instance scalar.
- mp-youngs-modulus-and-poisson: RECLASSIFIED -> already-mapped (two moduli). Pa Young's verified beyond docstring. `YoungsModulus`/`PoissonRatio` present; committed cu-youngsmodulus / cu-poissonratio. `universal_anisotropy` STILL tagless/absent (genuine candidate).
- mp-magnetic-moment: RECLASSIFIED -> already-mapped (per-site). abs() sign-loss + round_magmoms verified. `MagneticMoment` present; committed fe-bcc-magneticmoment (conditions carry a `site` key, confirming free-form per-site).
- mp-band-gap-and-electronic-structure: CONFIRMED new-node-candidate. `band_gap` eV (`summary.py:209-211`); NO registry tag, NO node. electronic-structure anchors (get_mp_electronic_structure.py:57-84) verified.
- mp-phonon-bandstructure-dos-forceconstants: CONFIRMED already-mapped. Linear THz (settled, no 2pi), eV/A^2 force constants. `Frequency`/`PhononDOS`/`ForceConstants[order=2]` present. phonon anchors (get_mp_phonon.py:62-76) verified.
- mp-mass-density: CONFIRMED new-node-candidate. g/cm^3 (`structure.py:67-69`); NO tag, NO node; derivable (contract-tier).
- mp-surface-energy: RECLASSIFIED -> already-mapped. J/m^2 (`summary.py:370-373`) + eV/A^2 (`:365-368`). `SurfaceEnergy` present; committed cu-{100,110,111}-surfaceenergy. MP value is Wulff-WEIGHTED aggregate, NOT a single (hkl) facet, so not a direct EXPECTED_AGREE with the per-facet records. MP-has-it-but-unused.
- mp-intercalation-voltage: CONFIRMED already-mapped, node upgraded null -> `Voltage`. `average_voltage` V (`electrode.py:62-64`). committed lifepo4-voltage. MP-has-it-but-unused; EXPECTED_AGREE with the MLIP record.
- mp-dielectric-constants: CONFIRMED already-mapped. e_total/e_ionic/e_electronic/n dimensionless (`summary.py:338-356`). `DielectricTensor` present (electronic part only; e_total/e_ionic are distinct).
- mp-material-provenance: CONFIRMED representation-only + ThermoType UNKNOWN member added. thermo_type enum (`types/enums.py:154-160`), MP2020 correction toggle.
- mp-structure-similarity: CONFIRMED representation-only. CrystalNN / StructureMatcher retrieval over MP; same verdict as the pymatgen scan.

No entry was KILLED. No anchor for the emmet/pymatgen SOURCE fields failed (only
query_mp.py's usage line numbers drifted, now fixed). All dimension vectors
recomputed correct (moduli {M:1,L:-1,T:-2}; voltage {M:1,L:2,T:-3,I:-1}; per-atom
energy {M:1,L:2,T:-2}; density {M:1,L:-3}; surface energy {M:1,L:0,T:-2}).

### Decisions for the orchestrator (not for the reviewer)

1. **Cross-scan status reconciliation (highest priority).** This review flipped 7
   entries to already-mapped because the nodes are live in graph.json; the sibling
   pymatgen scan still lists FormationEnergy / EnergyAboveHull / YoungsModulus /
   PoissonRatio / Voltage / SurfaceEnergy as new-node-candidate. Decide the
   canonical status and re-sync the pymatgen scan, or record that scans are
   snapshot-dated and statuses are read from graph.json at encode time.
2. **MP source.ref / material convention for pure-MP records.** The committed
   convention (mp-id in `material`, ref = skill) is skill-mediated. For a direct
   MP ingest with no skill, adopt (a) ref = ingestion path with mp-id in
   `material`, or (b) ref = `materials-project`. Not settled.
3. **conditions key vocabulary.** Standardize `thermo` vs `functional`/`thermo_type`
   and the value form (`GGA+U` vs enum `GGA_GGA+U`) so MP records and the existing
   li2o records share keys.
4. **Magnetization node topology.** Per-site `magmoms` -> MagneticMoment (present).
   Decide whether per-cell / per-f.u. / per-vol magnetization warrant their own
   nodes, and record that `total_magnetization` is sign-stripped (magmoms are the
   only sign-bearing source).
5. **Which remaining candidates to open.** band_gap (electronic domain),
   universal_anisotropy (elastic-anisotropy), density (derivable, low priority)
   are the only genuinely unmapped MP quantities left after the status flips.
