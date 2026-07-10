# phonopy and LAMMPS deltas as used by AtomisticSkills: scan report

A **delta / gap analysis** (not a fresh survey) of two codes already deeply
mapped, phonopy (17 space specs on the harmonic rail, 18 nodes in `codes.json`)
and LAMMPS (11 nodes on the thermal rail + `ElasticConstants`/`Pressure` on the
mechanics rail), against what AtomisticSkills (arXiv 2605.24002) actually
exercises. Companion catalog: `scans/phonopy-lammps-delta-atomistic-skills.json`
(15 entries).

Sources (read-only): vendored `phonopy/` @ **3.5.1** (`phonopy/version.py:37`),
vendored `lammps/` @ **30 Mar 2026 Development** (`src/version.h:1-2`),
`AtomisticSkills/.agents/skills/` (126 skills), and matcalc `QHACalc`
(`/tmp/mcsrc/matcalc-0.5.1/src/matcalc/_qha.py`, which wraps `phonopy.PhonopyQHA`).
Every skill-usage claim is anchored to a real `file:line`.

**Graph snapshot at my end:** `docs/data/graph.json` = **74 nodes**, git HEAD
`3874add`. Present and relevant: `Gruneisen` (the MODE `gamma_qnu`, `(q,nu)`
indexed, FC2/FC3-produced), `MolarGibbsEnergy` (CALPHAD, constant-P, per-mole-of-
atoms), the four phonopy `Molar*` constant-V nodes, `ElasticConstants`,
`Pressure`, `Frequency`, `Eigenvectors`, `PhononDOS`. The records 148-153 the
brief warned might land had not landed at scan time.

## What AtomisticSkills actually drives (the whole point of a delta)

phonopy is exercised by **five** skills, LAMMPS by **one**:

| skill | code path | what it drives |
|---|---|---|
| `mat-phonon` | matcalc `PhononCalc` -> phonopy | Frequency, DOS, band structure, the four constant-V Molar* thermodynamics |
| `mat-qha-thermal-expansion` | matcalc `QHACalc` -> `phonopy.PhonopyQHA` | **the QHA cluster** (Gibbs, alpha(T), C_P, thermal-Gruneisen, B(T)) |
| `mat-raman-spectra` | raw `phonopy` (band + IrReps) | **mode irreps / Raman activity**, **Raman intensities** (Born + eigenvectors) |
| `mat-kinetic-monte-carlo` | raw `phonopy` (Gamma mesh) | Gamma frequencies (Vineyard hTST prefactor; imaginary = negative freq) |
| `mat-lattice-thermal-conductivity` | matcalc `Phonon3Calc` -> phono3py | (phono3py, out of phonopy scope; covered by matcalc-ase scan) |
| `mat-lammps-md` | native LAMMPS input scripts | **units metal** NPT/NVT MLIP-MD: T, PE, E_tot, Press, Vol, **Density**, Trajectory, minimize |

The prior `scans/lammps-thermal.json` (30 entries) and
`scans/matcalc-ase-atomistic-skills.json` (13 entries) are NOT re-cataloged here;
this scan records only the delta and cross-references them.

## Honest-coverage verdict on the existing rails

**phonopy rail: HONEST, but scoped to the harmonic constant-V chain that
AtomisticSkills over-runs.** The four confirmed nodes match exactly what the
skills drive, and the docstring correctly hands QHA/anharmonic off. The gap is
not dishonesty: the skills exercise phonopy **beyond** that chain (QHA via
`PhonopyQHA`, mode symmetry via `IrReps`, thermal displacements) and those
outputs have no node. Coverage honest; scope incomplete.

**LAMMPS rail: HONEST for its thermal-transport slice, but that slice is largely
orthogonal to the skills.** The rail (and the `lammps-thermal` scan) center on
the KAPPA heat-flux / Green-Kubo / NEMD-reservoir machinery. **No AtomisticSkills
skill touches any of it.** `mat-lammps-md` runs plain NPT/NVT MLIP-MD (glass
melt/quench, Cu phase transition, adsorption relax) in **units metal**, producing
Temperature / Trajectory / Pressure / TotalEnergy / **Density**. So the rail
honestly covers its own slice, but the skill-relevant delta is small: a `Density`
node and the metal-unit-style default (the rail's LJ/real anchoring is not the
skills' unit style).

## The QHA cluster proposal (the headline)

`mat-qha-thermal-expansion` drives `QHACalc` -> `phonopy.PhonopyQHA`
(`calculate_qha.py:33-41`, `eos='vinet'`, an 11-volume scan `0.95..1.05`). The
result dict emits five quantities with **no node today**:

| candidate node | symbol | unit | PhonopyQHA anchor | matcalc key |
|---|---|---|---|---|
| GibbsFreeEnergy (QHA) | G(T) | kJ/mol | `qha/core.py:312` | `gibbs_free_energies` |
| ThermalExpansion | alpha(T) | 1/K | `qha/core.py:291` | `thermal_expansion_coefficients` |
| HeatCapacityConstantP | C_P(T) | J/(K*mol) | `qha/core.py:337` (polyfit) | `heat_capacity_P` |
| ThermalGruneisen | gamma(T) | dimensionless | `qha/core.py:355` | `gruneisen_parameters` |
| BulkModulus[T] | B(T) | GPa | `qha/core.py:319` | `bulk_modulus_P` |

The `F(V,T)` volume scan (`qha/core.py:298`; 11 scale factors, EOS in {vinet,
birch_murnaghan, murnaghan}) is a matcalc-owned **discretization scheme** on the
QHA operator, carrying MLIP-checkpoint double-provenance, not a node.

### The thermochemistry-guardrail relationship (critical)

The QHA cluster is **constant-PRESSURE** (Gibbs side); the existing phonopy
`Molar*` nodes are **constant-VOLUME** (Helmholtz side). The map **already
encodes exactly this potential distinction**:
`omai/thermochemistry/operator/nodes.py:30-38` gives CALPHAD `MolarGibbsEnergy`
(constant-P, per-mole-of-**atoms**, Gibbs-minimization producer) a **distinct
UID** from phonopy `MolarHelmholtzFreeEnergy` (constant-V, per-mole-of-primitive-
cell, phonon-gas producer) **despite identical field exponent vectors**, on a
`(potential x basis x producer)` key.

The QHA nodes are a **third region** of that same space: constant-P (like CALPHAD)
but per-mole-of-primitive-cell and phonon-gas+EOS producer (like phonopy). Each
must carry `{constraint: constant_pressure, basis: primitive_cell, producer:
qha_eos_scan}` so that:

- **`HeatCapacityConstantP` does NOT alias phonopy `MolarHeatCapacity` (C_V).**
  They share the field exponent vector but differ by
  `C_P - C_V = alpha^2 * B * V * T` and by potential.
- **QHA `GibbsFreeEnergy` does NOT alias CALPHAD `MolarGibbsEnergy`.** Same
  potential (constant-P), different basis and producer.
- **`ThermalGruneisen` does NOT alias the existing MODE `Gruneisen`.** The
  existing node is `gamma_qnu`, `(q,nu)`-indexed, FC3-produced
  (`nodes.py:393-402`). The QHA `gamma(T)` is a single scalar per temperature: the
  heat-capacity-weighted **contraction** of the mode gammas. Honest relationship:
  an edge mode-`Gruneisen` -> `ThermalGruneisen`.

`C_P` ships in two estimators (numerical `core.py:326`, polyfit `core.py:337`;
matcalc defaults polyfit): alternative-producer edges (Pattern C), like fc2's
dual producers already in the graph. `BulkModulus[T]`: recommend indexing the
existing `BulkModulus` node by temperature rather than minting a second node
(parallels the `T(bin)` index open question in the lammps-thermal scan).

## The other phonopy gaps (beyond QHA)

- **PhononIrreps / mode symmetry (NEW, skill-driven).** `mat-raman-spectra`
  calls `phonon.set_irreps(q=[0,0,0])` (`analyze_raman_modes.py:154-183`,
  phonopy `IrReps` at `irreps.py:57`) to tag each Gamma mode with its point-group
  irrep label and a Raman/IR-activity flag. Categorical annotation, not on the
  rail. Non-symmorphic groups return `None` (skill falls back to `Unknown`).
- **RamanIntensity (NEW, skill-driven).** Same skill builds Raman intensities
  from the bond-polarizability model (`:186-277`): `alpha_nu = sum_k (Z*_k .
  e_nu,k)/sqrt(m_k)`, consuming phonopy `Eigenvectors` x VASP `BornCharges` +
  `DielectricTensor` (already mapped). Spectroscopic observable; **only the DFT
  tier yields real intensities** (MLIP tier is equal-weight, no Born charges).
- **ThermalDisplacement / ADP (NEW, capability-only).** phonopy computes
  per-atom mean-square displacements and U_ij ellipsoids
  (`thermal_displacement.py:161,302`) but **no skill drives it today**. The
  harmonic (vibrational) analog of the LAMMPS MSD node; distinct physics (do not
  alias the diffusive MSD). Lower priority.

## Cross-engine EXPECTED_AGREE candidates (now concrete)

The mlip scan's abstract claim, made real by `mat-lammps-md`: the **same MLIP
checkpoint** runs both as an ASE calculator (matcalc/phonopy path) and as a
LAMMPS `pair_style`.

| checkpoint | ase path | lammps pair_style |
|---|---|---|
| MACE | `MACECalculator` | `pair_style mace no_domain_decomposition` (`in.na2si3o7_quench_mace:18-19`) |
| CHGNet | matgl `PESCalculator` | `pair_style mliap python chgnet CHGNet-MPtrj-2023.12.1` (`in.cu_phase_transition_matgl:18`) |
| FairChem UMA | `FAIRChemCalculator` | `pair_style mliap python fairchem uma-s-1p1` (`in.relax_adsorption_fairchem:18`) |

Quantities that must agree to inference precision on identical configs:
**Potential identity, TotalEnergy, Forces, Stress**; downstream
Trajectory/Temperature/Pressure distributions for identical `(ensemble, seed)`.
This is an EXPECTED_AGREE edge between the **ase Potential node and the lammps
Potential node**, keyed on checkpoint identity. **Trap:** the ase side is
eV/A/A^3 (CODATA-mixed per the matcalc scan), the LAMMPS metal side is eV/A/**bar**;
the Stress compare needs the bar <-> eV/A^3 conversion (`nktv2p` metal
`1.6021765e6`). Comparability is to MLIP-inference precision, not bit-exact
(`no_domain_decomposition` vs `mliap-python` bridges differ numerically).

Also: `mat-lammps-md`'s `minimize`-based adsorption components
(`in.relax_adsorption_fairchem:24-29`, `min_style cg` -> relaxed Structure +
`variable E equal pe`) target the **same `AdsorptionEnergy` new-node candidate**
the matcalc-ase scan flagged (via `AdsorptionCalc`); LAMMPS-minimize and ase-relax
are cross-engine producers of it.

## Unit traps

1. **phonopy linear THz CONFIRMED everywhere** (mat-phonon grid, mat-raman
   `*33.3564` THz->cm^-1, mat-kmc mesh). No angular/linear ambiguity in any skill.
2. **phonopy imaginary modes = NEGATIVE frequencies** (sqrt-of-negative);
   mat-kmc filters them (`compute_htst_prefactor.py:87`). A comparator must not
   treat negative freq as an error.
3. **phonopy `Molar*` basis = per mole of PRIMITIVE CELLS**, not atoms; QHA
   Gibbs/C_P inherit it. Cross-code to CALPHAD (per mole of atoms) needs the
   atoms-per-cell divide.
4. **LAMMPS unit style = METAL in ALL three `mat-lammps-md` examples** (eV, bar,
   K, ps, g/cm^3), NOT the LJ of the KAPPA examples nor the hard-coded REAL of the
   old `contract_kappa_nemd` spec. Pressure/stress in **bar** (metal).
5. **QHA result dict mixes bases in one object**: alpha 1/K, Gibbs kJ/mol, B GPa,
   C_P J/(K*mol), gamma dimensionless (`_qha.py:298-302`). Read per-key units.
6. **QHACalc.pressure is GPa** while MDCalc.pressure is eV/A^3 (matcalc-ase trap
   8): the QHA Gibbs pressure axis is GPa.

## Entry counts by status

- **phonopy (11 entries):** existing-confirmed 4 (Frequency, Molar* x4 grouped,
  Eigenvectors, band/DOS), new-candidate 6 (irreps, Raman-intensity, QHA-Gibbs,
  QHA-thermal-expansion, QHA-C_P, QHA-thermal-Gruneisen; + thermal-displacement/ADP
  capability-only), scheme-on-operator 1 (QHA F(V,T) volume scan). The five QHA
  outputs are one cluster; BulkModulus[T] recommended as a T-index on the existing
  node.
- **LAMMPS (4 entries):** existing-confirmed 2 (metal-unit thermo/trajectory;
  minimize -> Structure/TotalEnergy), new-minor 1 (Density), cross-engine
  EXPECTED_AGREE 1 (same-checkpoint ase-vs-pair_style).

## Open questions

1. `BulkModulus[T]`: temperature index on the existing node, or a new node?
   (Recommend: index.)
2. QHA cluster: one new quasi-harmonic domain, or distributed across
   thermal_transport + thermochemistry? The constant-P/constant-V guardrail says
   it straddles both.
3. `PhononIrreps`: a node, or a symmetry annotation/scheme on Frequency? (Labels
   not always resolvable; non-symmorphic -> None.)
4. `RamanIntensity`: ingest a vibrational-spectroscopy domain (Eigenvectors x
   Born x dielectric; DFT-tier-only real intensities; sibling IR node)?
5. `ThermalDisplacement/ADP`: ingest now (capability-only) or defer to a driving
   skill? Vibrational MSD, distinct from diffusive LAMMPS MSD.
6. `Density`: new scalar node or derived contraction of Structure/CellVolume?
7. Cross-engine EXPECTED_AGREE tolerance: what envelope for same-checkpoint
   ase-vs-pair_style, given the bridge-numerics differences? A `compare()` policy
   keyed on checkpoint identity.

**Nothing blocked the scan.** All targeted phonopy modules (`qha/core.py`,
`phonon/irreps.py`, `phonon/thermal_displacement.py`) and LAMMPS input templates
were present in the vendored trees; every QHA attribute was confirmed against
`phonopy.PhonopyQHA` source and the matcalc wrapper.

## Review verdicts (2026-07-10)

Adversarial deep review of commit `65974f1`'s catalog (this scan). Default to
distrust. Every source anchor was re-opened in the vendored trees; the matcalc
wrapper was re-read from `/tmp/mcsrc/matcalc-0.5.1/src/matcalc/_qha.py`; the
guardrail mechanism was checked against the actual node-identity code, not the
prose; every skill input was re-read line by line; the LAMMPS clone was grepped
honestly. Graph checked against `docs/data/graph.json` at HEAD `65974f1`.

**Snapshot correction.** The scan header records `git_head 3874add, node_count 74`.
At review time HEAD is `65974f1` (this delta scan's own commit) and the graph is
STILL 74 nodes. The config-thermo encode (records 148-153) has NOT landed: no
`ThermalExpansion` / `GibbsFreeEnergy` / `Density` / QHA node exists yet;
`BulkModulus` (the T=0 scalar), `Gruneisen`, `MolarGibbsEnergy`,
`MolarHelmholtzFreeEnergy` are all present as the scan claims. The scan's snapshot
holds; only the HEAD hash advanced. Not racing the encode.

**Headline: one physics-mechanism claim was WRONG and is corrected; every unit and
every physics relationship survived.** Verdict tally over the 15 entries: **12
CONFIRMED, 3 CONFIRMED-WITH-CORRECTION** (the guardrail-mechanism restatement, the
LAMMPS pair_style/pair_coeff line conflation, and the basis-wording tightening). No
entry was rejected. No status flipped. The QHA cluster physics is sound.

### The guardrail mechanism: WRONG as stated, corrected (load-bearing)

The scan repeatedly says the map distinguishes `MolarGibbsEnergy` from
`MolarHelmholtzFreeEnergy` on a **"(potential x basis x producer) key"** and that
each QHA node "needs its own UID carrying `{potential, basis, producer}`". **This
is the plausible-but-wrong mechanism.** The actual code:
`omai/operator/space.py:64-70` defines `Space.__hash__`/`__eq__` as **name-based**
(`hash(self.name)`; equality is `self.name == other.name`); the tier comment at
`:62` states outright "Not part of identity: `__hash__`/`__eq__` remain name-based."
The thermochemistry docstring
(`omai/thermochemistry/operator/nodes.py:35-40`) confirms it in words: identity
"keeps them apart **by the quantity tag** (`molar_gibbs_energy` ... never
`molar_helmholtz_free_energy`)" and "the basis (`per_mole_of_atoms`, constant
pressure, SER zero) lives in **the descriptions and the representation notes, not
the dimension**." So: **the distinct uid comes from the distinct node NAME (the
quantity tag). The dimension exponent vector (`ENERGY_PER_MOLE`) is IDENTICAL
across the two nodes and does no separating work. Potential, basis and producer are
documented in `description` prose only; they are NOT the identity key.** A new QHA
node is kept distinct by giving it a fresh NAME (e.g. `HeatCapacityConstantP` vs
`MolarHeatCapacity`), and the constant-pressure / primitive-cell / EOS-scan facts
are recorded in its description. The scan's `(potential x basis x producer) key`
framing must be read as "documented in prose, enforced by distinct names," not as a
composite identity tuple. **Corrected in the JSON entries and the summary.**

### QHA cluster: five outputs, units and PhonopyQHA anchors all CONFIRMED

Opened `phonopy/phonopy/qha/core.py` and `/tmp/mcsrc/.../_qha.py` line by line.

| output | PhonopyQHA property | core.py line | matcalc key | matcalc unit (_qha.py) | verdict |
|---|---|---|---|---|---|
| G(T) | `gibbs_temperature` | 312 | `gibbs_free_energies` | kJ/mol (:299) | CONFIRMED |
| alpha(T) | `thermal_expansion` | 291 | `thermal_expansion_coefficients` | 1/K (:298) | CONFIRMED |
| C_P(T) | `heat_capacity_P_polyfit` | 337 (polyfit); 326 numerical | `heat_capacity_P` | J/(K*mol) (:301) | CONFIRMED |
| gamma(T) | `gruneisen_temperature` | 355 | `gruneisen_parameters` | dimensionless (:302) | CONFIRMED |
| B(T) | `bulk_modulus_temperature` | 319 | `bulk_modulus_P` | GPa (:300) | CONFIRMED |

Every core.py line anchor is exact. The matcalc result-dict keys (`_qha.py:268-272`),
the `_units` dict (`:292-303`), `PhonopyQHA(...)` construction (`:253`), the default
11-volume scan `(0.95..1.05)` (`:82`) and `eos='vinet'` default (`:77`) all match
the scan verbatim. `heat_capacity_P` uses the polyfit estimator (`:271`), confirming
the "matcalc defaults polyfit" claim; the numerical estimator (`core.py:326`) is the
alternative-producer sibling as claimed. `mat-qha-thermal-expansion` drives it at
`scripts/calculate_qha.py:33-44` (`QHACalc(...).calc(atoms)`, `eos`, write paths):
CONFIRMED. Cross-checked against the matcalc scan's verdict
(`matcalc-ase-atomistic-skills.md:289-292`): "WRONGLY UNCONFIRMED, actually driven
(1): `QHACalc` <- `mat-qha-thermal-expansion`", consistent.

**Unit basis correction (per mole of WHAT).** The scan says the QHA thermodynamics
are "per mole of PRIMITIVE CELLS." The precise fact:
`phonopy/phonon/thermal_properties.py:664` labels the output "Thermal properties /
unit cell (natom)"; the per-formula-unit reduction requires `divide_by_Z=True`
(`:514-516,529-530`), whose **default is False**, and matcalc/`PhononCalc` does NOT
set it. So the honest basis is **per mole of the phonopy CELL passed to
PhonopyQHA (its natom), which in the matcalc path is the primitive/unit cell
`PhononCalc` builds**, NOT per formula unit and NOT per mole of atoms. This is the
load-bearing distinction for the CALPHAD cross-code compare (which is per mole of
ATOMS): the atoms-per-cell divide the scan flags is correct in direction. Wording
tightened from "primitive cells" to "phonopy cell (natom), primitivized in the
matcalc path"; the physics is unchanged. PhonopyQHA ingests these in kJ/mol,
J/K/mol (`core.py:230-241`); G(T) is internally eV (`_equiv_energies`) and surfaced
as kJ/mol by matcalc (`_qha.py:299`), the map's user-visible unit is kJ/mol.

### Mode Gruneisen vs thermal gamma(T): aliasing claim CONFIRMED

`omai/thermal_transport/operator/nodes.py:393-402`: the existing `Gruneisen` node is
field `gamma_G`, `DIMENSIONLESS`, indices **`(q, nu)`**, "computed from FC2 and FC3
via the standard Maradudin-Fein expression," tier `Scattering`. (The scan's prose
called the field `gamma_qnu`; the field NAME is `gamma_G` but the INDEX signature is
`(q,nu)` exactly as claimed, cosmetic naming nuance, physics correct.) A scalar
`gamma(T)` is `DIMENSIONLESS` indexed by **T only**, a different index signature,
a different producer (EOS volume scan vs FC3), and it is the heat-capacity-weighted
average of the mode gammas. It CANNOT alias the mode node (name-based identity + a
different index signature); it is a genuine **contraction** of it. The honest
`mode-Gruneisen -> ThermalGruneisen` edge stands. CONFIRMED.

### LAMMPS: unit style, no-KAPPA, nktv2p, minimize, Density

- **units metal, all three examples: CONFIRMED.** `in.na2si3o7_quench_mace:5`,
  `in.cu_phase_transition_matgl:4`, `in.relax_adsorption_fairchem:5`. `timestep
  0.001` in each (`:15/:12/:13`). `thermo_style custom step temp pe etotal press vol
  density` in mace (`:23`) and matgl (`:25`); fairchem is `... press vol` with **no
  density** (`:22`), so the scan correctly limits the Density claim to mace+matgl.
- **pair_style line conflation: CORRECTED.** The scan writes `pair_style mliap
  python chgnet CHGNet-MPtrj-2023.12.1` (`in.cu:18`) and `pair_style mliap python
  fairchem uma-s-1p1` (`in.relax:18`). In the real files line 17 is bare
  `pair_style mliap` and line 18 is the **pair_coeff** line carrying `* * mliap
  python <model> ...`. The `python chgnet/fairchem` tokens live on **pair_coeff**,
  not `pair_style`. The checkpoint string is also fuller than quoted:
  `CHGNet-MPtrj-2023.12.1-2.7M-PES` (not `...2023.12.1`). MACE differs: `pair_style
  mace no_domain_decomposition` (`in.na2si3o7:18`) + `pair_coeff * * ${model_file}
  Na Si O` (`:19`), there the model IS on pair_style. Corrected in the JSON.
- **no skill touches KAPPA/heat-flux/GK: CONFIRMED.** Honest grep across all 126
  skills: no `heat/flux`, `fix thermal/conductivity`, `green-kubo`, `NEMD` in any
  LAMMPS input. `mat-lattice-thermal-conductivity` has ZERO LAMMPS references (it is
  phono3py). The only LAMMPS input files in the whole skill set are the three
  `mat-lammps-md/examples/*/in.*`. The KAPPA machinery the rail centers on is
  untouched by every skill.
- **nktv2p bar<->eV/A^3 chain: CONFIRMED.** `lammps/src/update.cpp:191` (`metal`
  block), `:197` `force->nktv2p = 1.6021765e6`, exactly the scan's value; this is
  the native-stress-to-bar factor for the metal Stress compare.
- **minimize -> Structure/TotalEnergy: CONFIRMED.** `in.relax_adsorption_fairchem`:
  `min_style cg` (`:24`), `minimize 1.0e-8 1.0e-10 2000 10000` (`:25`), `variable E
  equal pe` (`:27`), `print` (`:28`), `write_data` (`:29`). Feeds the
  `AdsorptionEnergy` candidate cross-engine to ase-relax, as claimed.
- **Density the only new-minor candidate: CONFIRMED** for the LAMMPS delta (the
  only thermo column with no node; the others map to Temperature/Pressure/
  TotalEnergy/Trajectory or the CellVolume candidate).

### Cross-engine pair_style verification (duty 5)

`mliap python` bridge is REAL and source-verifiable in the clone
(`src/ML-IAP/mliap_model_python.cpp`, `mliap_unified.cpp`, `_couple.pyx`), so the
chgnet and fairchem runtime-python models are grounded in the vendored source.
**`pair_style mace` / `no_domain_decomposition` is NOT in the vendored clone**:
the only `mace`/`MACE` hit is `PTM/ptm_polar.cpp` (unrelated substring). The MACE
pair_style is an EXTERNAL LAMMPS plugin (built from the MACE-LAMMPS package), not
part of base LAMMPS; it is verifiable only in the skill input, not the clone. This
nuances the scan's duty-5 claim: two of three checkpoints (chgnet, fairchem) are
clone-source-verified; the MACE bridge is external-plugin-only. The EXPECTED_AGREE
edge and the `no_domain_decomposition`-vs-`mliap-python` tolerance caveat stand.

### Em-dash check

Zero U+2014 in both `scans/phonopy-lammps-delta-atomistic-skills.json` and `.md`
(perl `\x{2014}` scan, both files clean). Note: the phonopy source's `Gruneisen`
description uses em-dashes and minus signs (gamma formula), that is upstream
source, not these scan files.

### Orchestrator decisions

1. **QHA domain placement.** The cluster straddles constant-V (Helmholtz/phonon)
   and constant-P (Gibbs) physics. RECOMMEND a dedicated **quasi-harmonic**
   node group rather than splitting across thermal_transport + thermochemistry:
   its producer identity (PhonopyQHA over an EOS volume scan) is a single coherent
   operator, and one group keeps the constant-P/constant-V guardrail legible.
   Enforce the guardrail by DISTINCT NAMES, not a composite key.
2. **BulkModulus[T] topology.** RECOMMEND a **new `BulkModulusTemperature` node**,
   NOT a T-index on the existing `BulkModulus`. The existing node is a name-identity
   scalar reached by `ElasticConstants -> BulkModulus` (`contract_bulk_modulus`, per
   the matcalc scan); adding a T index would change its index signature and its
   producer set in place, muddying that contraction. The QHA `bulk_modulus_P` is a
   distinct producer (EOS fit per T) on the constant-P surface: a sibling node under
   the quasi-harmonic group is cleaner and consistent with name-based identity.
   (This overrides the scan's "index the existing node" recommendation.)
3. **The contraction edge.** ADD `Gruneisen (mode, (q,nu)) -> ThermalGruneisen (T)`
   as a heat-capacity-weighted contraction. Honest, distinct index signatures,
   distinct producers. Approved.
4. **Density.** Admit as a **new minor scalar node `Density` (g/cm^3)**, skill-driven
   (quench densification), with a documented derivation `TotalMass/CellVolume`. Not
   the phonon DOS. Low priority but real.
5. **Cross-engine tolerance policy.** The same-checkpoint ase-vs-`pair_style` compare
   is EXPECTED_AGREE only to **MLIP-inference precision**, not bit-exact:
   `no_domain_decomposition` (MACE) and `mliap-python` (chgnet/fairchem) bridges have
   their own numerical envelopes, and MACE is an external plugin the clone cannot
   pin. Policy: a per-quantity tolerance in `compare()` keyed on checkpoint identity,
   with the Stress compare carrying the metal `nktv2p=1.6021765e6` bar<->eV/A^3
   conversion. Do NOT assert bit-exactness across engines.
