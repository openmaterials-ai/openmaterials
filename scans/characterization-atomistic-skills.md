# Characterization and mesoscale (XRD, lobsterpy, fipy) as used by AtomisticSkills: scan report

Scan of the FINAL AtomisticSkills (arXiv 2605.24002) group: X-ray diffraction
(pymatgen `XRDCalculator` plus DARA phase-ID/refinement, the `xrd-agent`),
COHP bonding analysis (`lobsterpy`, `atomate2-agent`), and phase-field evolution
(`fipy`, `phasefield-agent`). Companion catalog:
`scans/characterization-atomistic-skills.json` (12 entries). This is a SCAN: it
catalogs, it does not map code.

Three distinct substrates land here, and the honesty of the scan is in keeping
them apart:

- **XRD is FUNCTION-VALUED** (intensity vs a spectral axis) with scalar
  reductions. The spectrum-layer question owns the pattern; peak positions and
  intensities are the fingerprint the phase-ID skills actually compare.
- **lobsterpy is FITTED/ANALYSIS** (ICOHP integrals, bonding fractions): on the
  representation side of the physics line, a projection of a ground state the
  map already carries.
- **fipy is a DIFFERENT SUBSTRATE** (mesoscale continuum PDE fields): deferred.
  The one map-shaped scalar of the whole group is grain-boundary energy
  gamma_GB (J/m^2), which is NOT a fipy skill.

## Sources and version anchoring

Every quantity claim is anchored to a committed AtomisticSkills `file:line` and,
where importable, to the pip-downloaded package source.

- **pymatgen 2026.5.4** (`pip download --no-deps pymatgen` ->
  `/tmp/pmgsrc/pmg_pkg`): `XRDCalculator` source read directly
  (`pymatgen/analysis/diffraction/xrd.py`).
- **lobsterpy 0.6.1** (`pip download --no-deps lobsterpy` ->
  `/tmp/charsrc/lobster_pkg`): `lobsterpy/coxx/analyze.py` read directly.
- **fipy**: NOT downloaded. fipy is a general finite-volume PDE solver; the
  physical content lives entirely in the skill scripts, so the scan reads the
  scripts that drive it.

Envs: `xrd-agent` (dara-xrd, pymatgen, kaleido<0.3; DARA drives BGMN, Ray for
the parallel phase-search tree); `mat-xrd-calculator` and `mat-xrd-digitizer`
run in `base-agent` (pymatgen only). `atomate2-agent` (lobsterpy, ijson; the
LOBSTER binary from cohp.de on the remote HPC worker, WAVECAR deleted after
projection). `phasefield-agent` (fipy, scipy, numpy, imageio; NO MCP server,
scripts only).

## Graph snapshot (freshness at my end)

`docs/data/graph.json` read at **82 nodes / 198 links** (graph edges live under
the **`links`** key, NOT `edges`: `graph.json` ships `nodes` / `links` /
`tiers`). `map/log.jsonl` at **163 records**. The **amset tail (records
154-163) has FULLY landed**: `ElectricalConductivity[carrier=electronic]`,
`ElectricalConductivity[carrier=ionic]`, `SeebeckCoefficient`,
`ElectronicThermalConductivity`, `CarrierMobility`, `StaticDielectricTensor`
are all graph nodes now, and the 198 links are populated (no longer an empty
edges array). Re-read `graph.json` at encode time.

- **Present, relevant**: `Structure`, `SurfaceEnergy`, `AdsorptionEnergy`,
  `TotalEnergy`, `BandGap`, `PhaseFraction`, `MagneticMoment`.
- **Absent, relevant**: any XRD/diffraction node, grain-boundary energy,
  ICOHP/bond-strength, bonding fractions, phase-field order parameter /
  concentration / interface mobility.

## Entry counts by status (12 entries)

| Status | Count | Entries |
|---|---|---|
| spectrum-layer-candidate | 1 | XRD pattern I(2theta) (function-valued) |
| scalar-reduction-candidate | 2 | peak positions d_hkl, relative intensities |
| representation-only | 5 | refined lattice params, weight-fraction/Rwp, COHP spectrum, ICOHP integral, bonding/antibonding fractions |
| already-mapped | 1 | input Structure |
| new-node-candidate | 1 | grain-boundary energy gamma_GB (J/m^2) |
| deferred | 2 | phase-field order parameter phi, phase-field concentration c |

By code: **XRD 6** (1 spectrum, 2 scalar-reduction, 2 representation-only, 1
already-mapped), **lobsterpy 3** (all representation-only), **fipy 3** (2
deferred continuum fields + 1 new-node-candidate that is NOT fipy but adjacent).

## XRD: the spectrum-layer proposal (this scan owns the deeper look)

The pymatgen scan deferred `xrd-pattern` as a function-valued new-node
candidate; this scan takes the deeper look.

**The function-valued object.** `XRDCalculator.get_pattern` returns a
`DiffractionPattern` with `.x` (2theta, degrees), `.y` (intensity, scaled so
max = 100), `.hkls` (Miller triplets + multiplicity per peak), `.d_hkls`
(d-spacing, Angstrom). This is a LINE spectrum (sparse Bragg peaks), which
`xrd_utils.py` convolves with a Caglioti pseudo-Voigt profile (FWHM^2 = U tan^2
+ V tan + W) into a DENSE curve on `arange(5, 90, bin)`. Both forms are
function-valued (intensity vs a spectral axis), the same family as `PhononDOS`
g(omega) and the amset (doping, T) transport grid: ingest via the
representation/spectrum layer, NOT as a scalar node.

**Spectral axis and the wavelength condition.** 2theta is what the skills serve
and what experiments record, but it is meaningful only WITH the wavelength
(Bragg: 2 d sin theta = lambda). The recommendation: store the pattern on the
wavelength-INDEPENDENT `d_hkl` (Angstrom) or Q = 4 pi sin(theta) / lambda
(Angstrom^-1) as the canonical axis, with 2theta(deg) a derived representation
carrying the **wavelength as a REQUIRED condition**. The wavelength is not an
internal gauge: it changes the observable (2theta positions AND, via the
Lorentz-polarization factor and s = sin(theta)/lambda in the atomic form factor,
the relative intensities). Draw it from a controlled radiation vocabulary (the
pymatgen `WAVELENGTHS` table: CuKa 1.54184, CuKa1 1.54056, CuKa2 1.54439, MoKa
0.71073, CrKa 2.29100, FeKa, CoKa, AgKa, ... in Angstrom) plus a free-float
escape for synchrotron wavelengths.

**What the skills actually compare (scalar reductions).** Phase ID and
refinement do not compare the raw curve pointwise; they compare REDUCTIONS:
(1) **peak positions** d_hkl (Angstrom) / their 2theta, indexed by (hkl): the
fingerprint that identifies a phase (`mat-xrd-phase-analysis` matches
candidate-CIF calculated patterns to the experimental peak set); (2) **relative
intensities** (scaled, max = 100): the second half of the fingerprint;
(3) refined **lattice parameters** a,b,c,alpha,beta,gamma (Rietveld, Structure
metadata); (4) per-phase **weight fractions** (`gewicht`, dimensionless);
(5) the goodness-of-fit **Rwp** (%).

**Proposal (two tiers).** (A) a SPECTRUM-LAYER `XRDPattern` representation,
canonical axis d_hkl / Q, served-as 2theta(deg) with the required wavelength
condition, intensities scaled dimensionless with the kinematic Lorentz-
polarization convention flagged. (B) SCALAR-REDUCTION entries: peak positions
d_hkl (hkl-indexed) and relative intensities as the phase-ID fingerprint;
refined lattice params as Structure metadata; weight fractions parallel to
`PhaseFraction`; Rwp representation-only. The pattern is a PURELY GEOMETRIC
property of the Structure (SKILL.md), so it grounds a Structure representation,
not a per-material physics node in the scalar sense; mint `XRDPattern` only if a
characterization domain opens.

## lobsterpy: the physics-line verdict (FITTED side)

**What LOBSTER produces.** COHP(E) is the crystal orbital Hamilton population, an
ENERGY-resolved projection of the DFT band energy onto atom-pair orbital
overlaps: a SPECTRUM (bonding/antibonding vs E, eV). ICOHP is the integral of
-COHP(E) to the Fermi level: a per-bond SCALAR in eV, a covalent-bond-strength
proxy. `lobsterpy.cohp.analyze.Analysis` condenses this to per cation-anion pair
`{ICOHP_mean (eV), ICOHP_sum (eV), has_antibdg_states_below_Efermi (bool),
number_of_bonds (int)}` plus per-orbital bonding/antibonding INTEGRALS and
PERCENTAGES (dimensionless fractions).

**Verdict: representation-only, on the FITTED side of the physics line.** Three
reasons. (1) COHP/ICOHP is a PROJECTION onto an arbitrarily chosen local
atomic-orbital basis; the number depends on the basis and the projection
(charge spilling, should be < 1-2%), so it is a post-hoc interpretive quantity,
not a gauge-invariant observable. (2) It RE-PARTITIONS a ground state the map
already carries (the DFT band energy / `TotalEnergy`) into bonds; it adds no new
measurable. (3) The bonding/antibonding percentages are analysis constructs
(integrals over an energy window relative to E_Fermi), explicitly
fitted-and-summarized. ICOHP is a candidate DERIVED per-bond scalar (eV,
edge-indexed by atom pair) ONLY if a bonding-analysis domain is ever opened,
kept explicitly on the fitted side. These are NOT new physics nodes.

**Note on the committed script.** The skill's own `analyze_lobster.py` only
PLOTS the COHP curves via `PlainCohpPlotter` (a spectrum plot); it does NOT call
the condensed-bonding summary. The scalar quantities (ICOHP_sum/mean, bonding
fractions) come from `lobsterpy.cohp.analyze.Analysis` / `lobsterpy
automatic-plot`, which the SKILL.md references but the committed code does not
invoke: the scalars are one level deeper than the committed script.

## fipy: the honesty verdict (DEFERRED, different substrate)

**What fipy evolves.** The phase-field skills evolve CONTINUUM PDE FIELDS on a
finite-volume mesh (`fipy.Grid2D` + `CellVariable`): (a) Allen-Cahn evolves a
NON-CONSERVED order parameter phi(r,t) in [0,1] (1 = solid grain, 0 = liquid);
(b) Cahn-Hilliard evolves a CONSERVED concentration field c(r,t) plus its
chemical-potential field mu(r,t). The MODEL PARAMETERS are dimensionless in the
skills as written: mobility M = 1.0, gradient-energy coefficient
epsilon/gamma/kappa, double-well height W/a, mesh dx = dy = 1.0, dt. The OUTPUTS
are a GIF/PNG of the evolving field and, for grain growth, a scalar TIME SERIES
(grain area vs time in grid-unit^2) demonstrating the v = M gamma K curvature
law.

**Honest answer.** A continuum field is a DIFFERENT SUBSTRATE from the map's
per-material scalars: it is a mesoscale spatiotemporal STATE of a microstructure,
not a property OF a material. The AtomisticSkills phase-field skills produce NO
map-shaped per-material scalar as written: the order parameters and
concentration are dimensionless fields, the mobility and gradient-energy
coefficients are dimensionless demonstration constants, and there is no
interface-energy or interface-velocity output in physical units. Verdict:
REPRESENTATION-ONLY / DEFERRED. IF a phase-field model were parameterized from a
real material (interface energy gamma in J/m^2, interface mobility in m^4/(J s),
gradient-energy coefficient in J/m), THOSE would be map-shaped, but the skills
do not compute them.

**The one map-shaped scalar in the neighbourhood: grain-boundary energy.**
`mat-grain-boundary` is listed near the phase-field skills but is NOT a fipy
skill. It computes gamma_GB = (E_GB - N E_bulk)/(2A) in **J/m^2** from
MLIP-relaxed CSL grain-boundary slab supercells, the phase-field/kMC INPUT. This
IS a per-configuration scalar (one gamma_GB per boundary), EXACTLY the
`SurfaceEnergy` construction (energy per area from a slab-bulk difference over
2A), the SAME `ENERGY_PER_LENGTH_SQUARED` dimension `(M=1, L=0, T=-2)`, and the
SAME shape (scalar per interface configuration, config in the conditions not the
index). It is catalogued as this group's single new-node candidate, a sibling of
`SurfaceEnergy`/`AdsorptionEnergy` in the stability domain. The (Sigma,
misorientation angle, rotation axis, GB plane) rides in the instance conditions
and the producing edge scheme, exactly as the facet (hkl) does for
`SurfaceEnergy`.

## Traps found (full list in JSON `traps`)

1. **CuKa is the Ka1/Ka2 WEIGHTED average (1.54184 A), NOT CuKa1 (1.54056)
   alone.** The skills default to `'CuKa'`. A high-resolution monochromated run
   uses CuKa1 only; a lab diffractometer sees the doublet. Record WHICH
   wavelength as the required condition (`xrd.py:23-27`).
2. **pymatgen intensities carry the Lorentz-polarization factor but NO
   absorption, NO preferred orientation, NO Debye-Waller by default.** I_hkl =
   |F_hkl|^2 * (1 + cos^2 2theta)/(sin^2 theta cos theta). Kinematic; not
   experiment-ready. Flag the convention on the representation (`xrd.py:66-97,
   241`).
3. **2theta is wavelength-dependent; d_hkl / Q are not.** Cross-wavelength phase
   matching must compare on d_hkl (Angstrom) or Q (Angstrom^-1) (`xrd.py:207,
   259`).
4. **ICOHP sign convention: NEGATIVE = bonding** (example -1.85 / -11.09 eV).
   LOBSTER plots -COHP (positive = bonding); some reports use -ICOHP (positive =
   strong bond). Any ICOHP value MUST carry its sign (`analyze.py:1284-1285,
   1196-1207`).
5. **|ICOHP_sum| is NOT equal to (bonding - antibonding) integral** (lobsterpy
   warns explicitly; different windows / orbital resolution). Do not derive one
   from the other (`analyze.py:1144-1157`).
6. **COHP/ICOHP are BASIS-DEPENDENT projections**, not gauge-invariant
   observables (charge spilling < 1-2%): this is why they sit on the fitted
   side. Record basis + spilling (`GaAs/README.md:5-11`).
7. **fipy phase-field parameters are DIMENSIONLESS demonstration constants**
   (M=1, epsilon=2, W=1, dx=1), not physical material parameters. No J/m^2
   interface energy or m^2/s mobility output (`run_grain_growth.py:44,57-59`).
8. **mat-grain-boundary is NOT a fipy skill and IS map-shaped** (gamma_GB J/m^2,
   MLIP slab energies, the phase-field/kMC input). Do not misfile it as a
   continuum-field skill (`mat-grain-boundary/SKILL.md:10-19,96-116`).
9. **Refinement weight fraction (gewicht) is NOT the equilibrium
   `PhaseFraction`.** BGMN least-squares fit vs CALPHAD Gibbs minimization: same
   dimension, different provenance. Keep apart.
10. **The lobster skill script only PLOTS COHP**; the scalar summary is a
    separate `Analysis` API one level deeper than the committed code.

## Open questions (full list in JSON `open_questions`)

1. **XRD canonical axis**: d_hkl (Angstrom) or Q (Angstrom^-1), with 2theta(deg)
   served and the wavelength as a required condition. Recommend
   wavelength-independent canonical.
2. **Radiation vocabulary**: register the pymatgen `WAVELENGTHS` table as a
   controlled condition set (CuKa weighted-average vs CuKa1 explicit) + a
   free-float escape.
3. **Peak positions d_hkl**: per-reflection scalar-reduction representation
   (hkl-indexed) vs pure Structure geometry metadata (they are a function of the
   lattice).
4. **XRDPattern node**: mint only if a characterization domain opens; the
   pattern is a geometric function OF the Structure.
5. **ICOHP**: representation-only (recommended) vs a candidate derived per-bond
   scalar on the explicit fitted side if a bonding-analysis domain opens.
6. **grain-boundary energy gamma_GB**: mint as a new stability-domain node
   (ENERGY_PER_LENGTH_SQUARED, sibling of SurfaceEnergy/AdsorptionEnergy)?
   Strong recommend YES.
7. **fipy fields**: confirmed DEFERRED (continuum substrate). Recommend the map
   boundary stays at per-material scalars.
8. **Version pins**: pymatgen 2026.5.4, lobsterpy 0.6.1 (both downloaded); the
   AtomisticSkills envs pin these unversioned; fipy unpinned. Pin before an
   encode relies on the WAVELENGTHS table or the Analysis schema.

## Source anchors

- **Skills**: `mat-xrd-calculator/SKILL.md:1-59`, `scripts/calculate_xrd.py:6-49`,
  `scripts/xrd_utils.py:1-78`; `mat-xrd-phase-analysis/SKILL.md:1-147`,
  `scripts/phase_search.py`, `examples/GeO2-ZnO/.../results_summary.json`
  (best_rwp 12.11); `mat-xrd-refinement/SKILL.md:1-148`, `scripts/refine.py:56-231`,
  `examples/LiFePO4/.../refinement_result.json` (Rwp 32.32, gewicht, lattice);
  `mat-xrd-digitizer/SKILL.md:1-84`; `mat-dft-lobster/SKILL.md:1-76`,
  `scripts/analyze_lobster.py:14-84`, `scripts/generate_inputs.py:5,32-35`,
  `examples/GaAs/README.md:5-13`; `mat-phase-field-conservative/SKILL.md:1-62`,
  `scripts/run_spinodal_decomposition.py:23,51,59-64`;
  `mat-phase-field-non-conservative/SKILL.md:1-64`,
  `scripts/run_grain_growth.py:45-149`, `scripts/run_dendrite_growth.py`;
  `mat-grain-boundary/SKILL.md:1-166`.
- **Package source**: pymatgen 2026.5.4
  `/tmp/pmgsrc/pmg_pkg/pymatgen/analysis/diffraction/xrd.py:23-48` (WAVELENGTHS),
  `:57-98` (docstring: LP yes, Debye-Waller no), `:103-129` (wavelength
  resolution), `:131-280` (get_pattern; `:207` Bragg, `:209-211` s, `:228-231`
  form factor, `:238` F_hkl, `:241` LP, `:244` I=|F|^2, `:259` d_hkl, `:278-279`
  normalize max=100); lobsterpy 0.6.1
  `/tmp/charsrc/lobster_pkg/lobsterpy/coxx/analyze.py:51-82` (Analysis params),
  `:488-560` (get_information_all_bonds), `:658-830` (orbital-resolved
  bonding/antibonding), `:1108-1157` (integral/perc; ICOHP_sum!=b-ab warning),
  `:1278-1315` (ICOHP_mean/sum eV, example -1.85/-11.09), `:1378+`
  (set_condensed_bonding_analysis); `lobsterpy/plotting` PlainCohpPlotter. fipy:
  not downloaded (general PDE solver; model in the skill scripts).
- **Map side**: `docs/data/graph.json` (82 nodes, 198 links, key `links` not
  `edges`); `map/log.jsonl` (163 records);
  `omai/stability/operator/nodes.py:13,98-99,145` (SurfaceEnergy/AdsorptionEnergy,
  ENERGY_PER_LENGTH_SQUARED, scalar, config in conditions not index);
  `omai/operator/dimensions.py:108` (ENERGY_PER_LENGTH_SQUARED (1,0,-2,0,0,0,0));
  `omai/operator/registry.py:84-152` (QUANTITY_TAGS; surface_energy present, no
  xrd/cohp/grain_boundary tag); `scans/pymatgen-atomistic-skills.json`
  (xrd-pattern deferred to this scan).
