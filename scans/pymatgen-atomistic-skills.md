# pymatgen as used by AtomisticSkills: scan report

Scan of pymatgen (version 2025.6.14, importable in the miniconda base env at
`/Users/juicy/miniconda3/lib/python3.12/site-packages/pymatgen`) as the `mat-*`
skills of AtomisticSkills (arXiv 2605.24002) actually use it. Companion catalog:
`scans/pymatgen-atomistic-skills.json` (26 entries). Sources: the 54
`AtomisticSkills/.agents/skills/mat-*/` skill directories (SKILL.md +
`scripts/*.py`) and the pymatgen source tree. MP-served example documents in the
repo carry `pymatgen_version` 2024.11.13; the two add-on distributions
(`pymatgen-analysis-diffusion`, `pymatgen-analysis-defects`, imported under the
`pymatgen.analysis.*` namespace) are not present in base, so their APIs are
anchored to skill usage plus canonical docstrings rather than a read source line.

## What pymatgen IS in this software

pymatgen is the structure/analysis workhorse. It is almost never the thing that
computes an energy or a force: those come from an MLIP calculator (MACE,
FairChem, MatGL via `matcalc`) or from VASP/QE. pymatgen owns four things:

1. **The crystal-structure object.** `pymatgen.core.Structure` (lattice +
   species + fractional positions, angstrom throughout) is the currency every
   `mat-*` skill passes around. `pymatgen.io.ase.AseAtomsAdaptor` is the bridge
   that lets the ASE-native MLIP calculators act on it, and is the single
   most-called pymatgen API in the MD-based skills.

2. **File I/O.** CIF (`io.cif.CifWriter`, `Structure.from_file`), VASP
   (`io.vasp.Vasprun`, `BSVasprun`, `Outcar`, `Chgcar`), LOBSTER
   (`io.lobster.Cohpcar`), and the ASE round-trip.

3. **Symmetry.** `symmetry.analyzer.SpacegroupAnalyzer` (spglib-backed):
   space/point group, and primitive/conventional cell standardization that
   nearly every skill runs before computing.

4. **A set of pure-python physics analyses** that turn calculator outputs into
   named quantities: elastic-tensor algebra, XRD kinematics, phase-diagram
   convex hull, the diffusion Einstein relation, the Wulff construction, and the
   Born/dielectric contraction behind Raman intensities.

## The clusters of physics pymatgen touches

- **Symmetry / structure** (pervasive): `SpacegroupAnalyzer`,
  `StructureMatcher`, `Lattice.volume`, `Composition.weight`, the ASE/CIF
  bridge. These ground the map's existing `Structure`, `CellVolume`,
  `AtomicMass`, `AtomCount` nodes, or are representation-only.
- **Elasticity / mechanics** (`mat-elasticity`, `mat-equation-of-state`):
  `analysis.elasticity.ElasticTensor` (`.voigt`, `.k_vrh`, `.g_vrh`) and the BM
  equation of state. Grounds `ElasticConstants`, `BulkModulus`, `ShearModulus`.
- **Thermodynamics / phase diagrams** (`mat-stability`, `mat-phase-diagram`,
  `mat-db-mp`, `mat-defect-energy`, `mat-intercalation-voltage`,
  `mat-surface-energy`): `entries.ComputedEntry`, `analysis.phase_diagram`
  convex hull, and a family of energy-difference observables (energy above hull,
  formation, surface, GB, defect, voltage) all built from MLIP `TotalEnergy`.
- **Diffusion** (`mat-diffusion-analysis`, `mat-md-probability-density`):
  `analysis.diffusion.DiffusionAnalyzer` -> `Diffusivity`, `ActivationEnergy`,
  `MeanSquaredDisplacement`.
- **Phonons / spectroscopy** (`mat-phonon`, `mat-raman-spectra`,
  `mat-dielectric-response`): `phonon.*` band structure / DOS
  (representation/retrieval), and `io.vasp.Outcar.born` / `.dielectric_tensor`
  feeding Raman tensors -> grounds `Frequency`, `PhononDOS`, `ForceConstants`,
  `BornCharges`, `DielectricTensor`.
- **Electronic structure** (`mat-electronic-structure`, `mat-dft-lobster`,
  `mat-magnetic-density`): band gap, Fermi level, COHP, magnetic moment. Below
  the current map's floor; representation-only or new-domain candidates.
- **Diffraction** (`mat-xrd-*`): `analysis.diffraction.xrd.XRDCalculator`.

## Quantity count by status

- **already-mapped: 14** (crystal-structure, cell-volume, atomic-mass,
  atom-count, elastic-stiffness-tensor, bulk-modulus-vrh, shear-modulus-vrh,
  birch-murnaghan-eos, total-energy, stress-tensor, diffusivity,
  activation-energy, mean-squared-displacement, phonon-band-structure-and-dos,
  force-constants-representation, born-charges-and-dielectric). Grounds 18
  distinct existing nodes: Structure, CellVolume, AtomicMass, AtomCount,
  ElasticConstants, BulkModulus, ShearModulus, TotalEnergy, Stress, Diffusivity,
  ActivationEnergy, MeanSquaredDisplacement, Frequency, PhononDOS,
  ForceConstants[order=2], BornCharges, DielectricTensor.
- **new-node-candidate: 8** (energy-above-hull, xrd-pattern, raman-intensity,
  surface-energy-and-wulff, grain-boundary-energy, intercalation-voltage,
  defect-formation-energy, magnetic-moment; plus youngs-modulus/poisson and
  band-gap as lower-priority candidates).
- **representation-only: 4** (space-group-and-symmetry,
  structure-match-and-novelty, cohp-bonding, ase-structure-bridge).

(The JSON has 26 entries; some cover two tags, e.g. born-charges+dielectric and
frequency+DOS, hence the node count exceeds the entry count.)

## Top 8 encode candidates, ranked

1. **energy-above-hull (E_hull)**: thermodynamic stability, eV/atom (reported
   meV/atom). The single most-used output across `mat-stability`,
   `mat-phase-diagram`, `mat-db-mp`, `mat-structure-novelty`. Convex-hull
   distance over a whole `ComputedEntry` set. `PhaseDiagram.get_e_above_hull`.
2. **surface-energy (gamma_hkl)**: energy per facet area, J/m^2. `SlabGenerator`
   + `WulffShape`; gamma = (E_slab - N E_bulk)/(2 A). Whole surface/interface
   domain hangs off this.
3. **xrd-pattern I(2theta)**: kinematic powder diffraction, 2theta(deg) /
   d_hkl(angstrom) / scaled intensity. `XRDCalculator.get_pattern`. Anchor of
   the four `mat-xrd-*` skills (calculate, phase-analysis, refinement,
   digitizer).
4. **defect-formation-energy (E_f)**: point-defect energetics, eV. Vacancy /
   substitution / interstitial generators + E_f = E_defect - E_pristine + sum
   dn_i mu_i. Chemical-potential-referenced.
5. **intercalation-voltage (V_avg)**: electrode voltage, volts. Energy
   difference of full/empty/metal cells over ions; eV/e = V. Battery domain.
6. **magnetic-moment (m_i, M_total)**: per-site / total, Bohr magnetons, plus
   FM/AFM ordering label. `analysis.magnetism.Ordering`. Magnetism domain.
7. **grain-boundary-energy (gamma_gb)**: J/m^2, same defect-energetics family
   as surface energy. `core.interface.GrainBoundaryGenerator`. Microstructure
   domain.
8. **raman-intensity I_Raman(omega)**: a.u. vs cm^-1, from Born-charge-
   contracted mode displacements with point-group selection rules. Downstream of
   BornCharges + DielectricTensor + Eigenvectors. Spectroscopy domain.

Lower priority (derivable or hidden): youngs-modulus / poisson (deterministic
functions of K and G), band-gap (eV, hidden electronic intermediate), COHP
(bonding diagnostic).

## Unit convention traps found

1. **eV/A^3 vs GPa in elasticity (factor 160.2176634).** pymatgen's
   `ElasticTensor` and its `k_vrh`/`g_vrh` are stored in **eV/A^3**
   (`elastic.py:130-136`, `:163-196`), NOT GPa. `mat-elasticity` multiplies by
   `EV_PER_A3_TO_GPA = 160.2176634`. Verified exact:
   `Unit('GPa').get_conversion_factor(Unit('eV ang^-3')) = 0.006241509074460764`,
   inverse `= 160.21766339999996` (`elastic.py:52`). A consumer that reads
   `.voigt` and treats it as GPa is off by 160x.

2. **eV/atom vs eV/cell in the thermodynamics stack.** The registry defines
   `total_energy` "per simulation cell", but every stability / phase-diagram /
   voltage flow runs **per atom** (`ComputedEntry.energy_per_atom`,
   `formation_energy_per_atom`, `get_e_above_hull` in eV/atom, then `*1000` to
   meV/atom in `compute_ehull.py:181`). This is the highest-risk trap: naive
   equating of a per-cell TotalEnergy with a per-atom hull energy is wrong by the
   atom count.

3. **Voigt packing (not just a reshape).** `.voigt` uses the fixed reverse map
   `[[0,5,4],[5,1,3],[4,3,2]]` (`tensors.py:381`) and a `_vscale` factor. For the
   stiffness C_ij the 6x6 is used directly by `k_voigt = voigt[:3,:3].mean()` and
   `g_voigt` (`elastic.py:163-172`), so the 160x factor is the only conversion;
   but the `_vscale` factor-2/4 on shear off-diagonals bites if the compliance
   S = C^-1 is ever round-tripped.

4. **VASP stress sign/units in the elastic fit.**
   `ElasticTensor.from_independent_strains(vasp=True)` applies `c_ij *= -0.1`
   (`elastic.py:519`) to convert VASP kbar-with-opposite-sign stress to GPa. The
   MLIP path used by AtomisticSkills feeds eV/A^3 and does NOT take this branch,
   so the two routes to C_ij carry different raw-stress conventions.

5. **Linear THz vs angular omega, and THz vs cm^-1 for phonons.** pymatgen/MP
   `PhononBandStructure`/`PhononDos` store **linear THz**, while the registry
   describes `frequency` as "angular frequencies omega_qnu" (factor 2pi apart).
   `mat-raman` converts THz -> cm^-1 with 1 THz = 33.35641 cm^-1. Same
   linear-frequency situation flagged in the QE scan.

6. **Diffusivity in cm^2/s.** `DiffusionAnalyzer.diffusivity` returns **cm^2/s**
   (not A^2/ps, not SI m^2/s); MSD is A^2, `analyzer.dt` is fs (skill divides by
   1000 for ps). 1 cm^2/s = 1e16 A^2/s.

7. **eV/A^2 is two different quantities.** Surface/GB energy (energy per area,
   `M T^-2`) and force constants (force per length, also `M T^-2`) share the
   eV/A^2 dimension but are physically distinct; the surface conversion
   1 eV/A^2 = 16.0218 J/m^2 (`calculate_surface_energy.py:114`) must not be
   confused with the FC2 48.5829 eV/A^2 per Ry/bohr^2 factor from the QE scan.

8. **Young's modulus units mismatch.** pymatgen `ElasticTensor.y_mod` returns SI
   **Pa** (`9.0e9 * ...`, `elastic.py:198-204`), but `mat-elasticity` recomputes
   E in **GPa** from GPa moduli. A node equating the two is off by 1e9.

## Open questions (a reviewer must check)

Carried verbatim in the JSON `open_questions`:

1. Diffusion and defects add-ons are not in the base env; DiffusionAnalyzer
   units (cm^2/s, MSD A^2, dt fs) and the defect generators are anchored to
   usage + docstrings, not a read source line.
2. TotalEnergy per-cell vs per-atom: decide on a `per_atom` label or a separate
   FormationEnergy/EnergyAboveHull node before ingesting `mat-stability`.
3. Frequency angular-vs-linear: confirm the map's intended convention before an
   EXPECTED_AGREE with MP phonons (factor 2pi and 33.35641 cm^-1/THz).
4. `Tensor.voigt` `_vscale` handling for compliance (S = C^-1) if elastic
   compliance is ever ingested (factor-2/4 on off-diagonals).
5. matcalc `ElasticityCalc`/`EOSCalc` internals: confirm matcalc hands raw
   eV/A^3 to the skill (the skill's *160.2176634 assumes it), and does not take
   the vasp=True -0.1 branch on the MLIP stress path.
6. Whether surface / GB / defect / voltage energies want dedicated nodes or
   contract edges over a generic TotalEnergy + Structure (an encode-stage
   modeling decision). Exact closed forms are recorded in the JSON.
7. XRD intensity model omits absorption / preferred orientation / Debye-Waller
   (unless passed); `mat-xrd-refinement` would need those scheme flags.
8. `GrainBoundaryGenerator` import path moved
   (`analysis.gb.grain` -> `core.interface`) across pymatgen versions; pin the
   version when anchoring the GB node.
