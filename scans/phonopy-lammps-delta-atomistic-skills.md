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
