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

- **already-mapped: 9** — mp-structure-record (`Structure`),
  mp-cell-volume-and-density (`CellVolume` / `AtomCount`),
  mp-total-energy-and-per-atom (`TotalEnergy`, per-cell trajectory route only),
  mp-bulk-modulus (`BulkModulus`), mp-shear-modulus (`ShearModulus`),
  mp-elastic-tensor (`ElasticConstants`),
  mp-phonon-bandstructure-dos-forceconstants (`Frequency` / `PhononDOS` /
  `ForceConstants[order=2]`), mp-intercalation-voltage (registry `voltage` tag;
  MP-has-it-but-unused), mp-dielectric-constants (`DielectricTensor`, electronic
  part).
- **new-node-candidate: 7** — mp-formation-energy (registry `formation_energy`
  tag), mp-energy-above-hull (registry `energy_above_hull` tag),
  mp-youngs-modulus-and-poisson (registry `youngs_modulus` / `poisson_ratio`;
  plus `universal_anisotropy` with no tag), mp-magnetic-moment (registry
  `magnetic_moment` tag), mp-band-gap-and-electronic-structure (NO tag; new
  domain), mp-mass-density (NO tag; derivable), mp-surface-energy (registry
  `surface_energy` tag; MP-has-it-but-unused).
- **representation-only: 2** — mp-material-provenance (the
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
| PoissonRatio | `ElasticityDoc.homogeneous_poisson` (elasticity) | dimensionless | — |
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

- **band_gap (eV)** — no registry tag; the single most-used MP electronic field
  (`mat-db-mp`, `mat-electronic-structure`). Same candidate the pymatgen + VASP
  scans flagged; MP is the DFT-database retrieval producer. Opens the electronic
  domain.
- **universal_anisotropy (A_U, dimensionless)** — no tag; a genuine elastic-
  anisotropy new-node candidate.
- **density (g/cm^3)** — no tag but derivable from CellVolume + AtomicMass +
  AtomCount (contract-tier, low priority).
- Further no-analog MP fields: `e_ionic` / `e_total` (dielectric), refractive
  index `n`, electrode capacity/energy-density (mAh/g, mAh/cc, Wh/kg, Wh/l).

## Instance-source design (how MP records enter as evidence)

Full spec in the JSON `instance_source_design` object; summary:

- **kind**: always `simulation` (MP values are DFT), never `measurement`.
- **source.ref**: `"materials-project"` (a stable code identifier, matching the
  existing `qe` / `atomisticskills-mat-elasticity-Cu` refs), with the **mp-id in
  `source.detail`**, e.g. `"mp-149 elasticity (R2SCAN)"`. Recommendation, to be
  confirmed by the encode-stage instance-schema owner (Appendix C of
  `docs/openmaterials.tex`); this scan does not touch `omai/` or `docs/data`.
- **conditions** carry the MP calculation provenance, mirroring
  `si-totalenergy-qe.json` `{pseudo, ecutwfc, k_mesh, code}` and
  `cu-bulkmodulus...` `{average: VRH, model}`. For MP conditions **must** carry:
  (1) the functional / mixing-scheme = `thermo_type`; (2) for energetics, the
  MP2020 correction state (corrected vs uncorrected); (3) the averaging /
  orientation scheme where relevant (`average: VRH`, IEEE vs structure
  orientation). Example: `{"functional": "R2SCAN", "average": "VRH"}` for a bulk
  modulus.
- **value / units per field**: `formation_energy_per_atom` eV/atom;
  `energy_above_hull` eV/atom; `bulk_modulus.vrh` / `shear_modulus.vrh` GPa;
  `young_modulus / 1e9` GPa; `homogeneous_poisson` dimensionless; `magmoms[i]`
  mu_B (per-site); `volume` angstrom^3; trajectory `e_wo_entrp` eV (per-cell);
  `average_voltage` V; `e_electronic` dimensionless. See the JSON
  `per_field_mapping`.
- **uncertainty**: typically `null` — MP does not serve a per-value stochastic
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
   R2SCAN) must enter conditions on every MP record.
5. **MP-has-it-but-unused**: `average_voltage`, `weighted_surface_energy`,
   `e_electronic` ground in-flight/registry nodes though the skills do not query
   them.
6. **Quantities with no tag**: `band_gap`, `universal_anisotropy` (new domains);
   `density` (derivable); dielectric `e_ionic`/`e_total`, refractive index,
   electrode capacities have no map analog.
7. **`density_atomic`** impl (A^3/atom) contradicts its "atoms per cm^3"
   description; trust the impl.
8. **source.ref convention**: `materials-project` + mp-id in `detail`;
   confirm with the encode-stage instance-schema owner.
9. **emmet-core version**: field names/units read from mp-api 0.41.2 /
   emmet-core 0.85.1; pin emmet-core when an encode relies on a field's units, as
   a future emmet could re-normalize a default.
