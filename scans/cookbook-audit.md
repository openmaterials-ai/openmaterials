# Atomistic Cookbook coverage audit

A systematic probe of the COSMO/EPFL Atomistic Cookbook
(https://atomistic-cookbook.org, repo lab-cosmo/atomistic-cookbook,
BSD-3-Clause) against the map's current coverage: 27 code rails
(`docs/data/codes.json`), 98 nodes (`docs/data/graph.json`), 10 domains
(`omai/map_data.py`). Companion catalog: `scans/cookbook-audit.json`.
Statuses: `covered` / `gap-code` / `gap-node` / `gap-edge`.

This is a scan-only pass. It touches no map code.

## What was swept

40 recipe folders under `examples/` (the canonical sphinx-gallery list),
cross-checked against the 41 titles on the site index. The cookbook is not a
DFT or characterization collection: it is an ML-interatomic-potential (MLIP)
plus statistical-sampling collection built around the PET-MAD universal
potential and the metatensor/metatomic stack. Its overlap with the map's
lattice-dynamics core is deliberately thin (one BTE recipe on kALDo, one
phonon-UQ recipe on phonopy, both of which the map already covers). The gap
concentration is elsewhere: **nuclear quantum effects**, **enhanced sampling /
free energy**, and **ML-model quantities** (spectra, tensors, uncertainty).
That is exactly where Giuseppe's missing-nodes worry is justified.

## The code-gap list (axis A)

Cookbook codes absent from the 27 rails, with the encode call:

| Code | What it produces | Call |
|---|---|---|
| **i-PI** | PIMD trajectories, quantum kinetic-energy estimators, quantum heat capacity, instanton rates | **RAIL (top priority).** A Trajectory producer variant; the home of the whole nuclear-quantum-effects layer. |
| **PLUMED** | free-energy surfaces, collective variables, metadynamics bias | **RAIL.** Producer for the biggest missing tier (free energy / PMF). |
| **CP2K** | DFT energies, forces, stress, AIMD frames | **RAIL (medium).** Second first-principles engine; grounds existing DFT nodes. |
| **eOn** | NEB / dimer reaction barriers, saddle geometries | **RAIL (medium).** Second producer for the existing ReactionBarrier[neb_mep] node. |
| **GROMACS** | trajectories, dielectric/dipole response | RAIL (medium-low). MD producer variant; value is soft-matter reach. |
| **metatensor / metatomic** | the calculator interface that delivers ML predictions | REPRESENTATION-ONLY. The MLIP delivery mechanism, not a physics rail; credit owed when PET models land. |
| **torch-pme** | long-range electrostatic energy inside potentials | OUT-OF-SCOPE. An energy contribution internal to a potential, no map-tier observable. |
| **featomic** | SOAP / lambda-SOAP descriptors | OUT-OF-SCOPE. Model internals. |
| **scikit-matter** | FPS/CUR selection, PCovR, convex hulls | OUT-OF-SCOPE. Data-science tooling. |
| **chemiscope** | interactive structure viewer | OUT-OF-SCOPE. Pure visualization, computes no physics. |
| kALDo, LAMMPS, ASE | (already rails) | COVERED. |

License confirmation is the gating item for i-PI and eOn before either rail
is minted (the credits rule blocks an unlicensed rail).

## The new-node candidates (axis B)

Quantities the cookbook computes that have no map node. Every entry carries a
false-merge check against the existing 98.

- **FreeEnergySurface / PMF** (spectrum-layer): F(s) along a collective
  variable. NOT HelmholtzFreeEnergy (that is the harmonic vibrational free
  energy from phonon frequencies; this is configurational free energy along a
  reaction coordinate). Genuinely new; fits the spectrum contract.
- **ElectronicDOS** (spectrum-layer): g(E), Fermi level, gap on an energy
  grid. **Critical false-merge risk with PhononDOS** - both are "DOS" but are
  physically distinct (electronic states in eV vs vibrational modes in THz).
  Must be a separate node. Parent of the existing BandGap.
- **IRAbsorptionSpectrum** (spectrum-layer): n(w)alpha(w) from the dipole
  power spectrum. No existing spectral node beyond PhononDOS. Confirms the
  deferred spectrum-layer hook.
- **QuantumKineticEnergy** (scalar + tensor): PIMD centroid-virial /
  thermodynamic estimator. NOT InternalEnergy (harmonic-oscillator per-mode
  energy) and NOT classical MD kinetic energy.
- **QuantumHeatCapacity** (scalar): PIMD scaled-coordinates estimator of C_V.
  Overlaps the existing HeatCapacity node in quantity but not method (the map's
  HeatCapacity is harmonic-crystalline; this is a fluctuation estimator valid
  for liquids). Best as a method-tagged producer variant, not a new node.
- **PolarizabilityTensor** (rank-2, lambda=0/2): molecular alpha, Raman basis.
  NOT the bulk DielectricTensor (that is a Sources leaf for the NAC
  correction); this is the per-molecule analog for finite systems.
- **NMRShieldingTensor / IsotropicChemicalShift** (ppm): entirely new
  spectroscopy domain, no merge risk.
- **DipoleMoment(t) / DynamicalCharges**: MD dipole time series feeding IR.
  Related to but not a merge with BornCharges (static/provided vs
  produced-along-trajectory).
- **TunnelingRate / InstantonRateConstant**: tunneling-corrected reaction
  rate. NOT ActivationEnergy or ReactionBarrier (those are static barrier
  heights; this is a kinetics rate).
- **ElectronDensity / ChargeDensity** (field-valued): confirms the QE scan's
  deferred charge-density node; exceeds the current scalar+spectrum contract.
- **ModelUncertainty / CommitteeDisagreement**: a property of the MODEL, not
  the material. Recommended as a record-level `uncertainty` attribute (already
  in the instance schema), NOT an evidence node.

## The method/edge gaps (axis C)

- **PIMD as a Trajectory producer variant** - a second producing operator for
  the existing Trajectory node, with quantum estimators attached (mirrors how
  ThermalConductivity carries transport_model tags).
- **Metadynamics as a FreeEnergy producer** - the operator into the new
  FreeEnergySurface node.
- **Thermodynamic integration** - a second free-energy producer.
- **Dipole/polarizability autocorrelation -> spectroscopy** - structurally
  identical to the existing HeatCurrent -> HeatCurrentACF -> Green-Kubo chain,
  reusing the ACF/Fourier machinery for a different current.
- **NEB / saddle-search (eOn)** - a second ReactionBarrier producer.
- **Ring-polymer instanton** - producer for the new TunnelingRate node.

## Top 10 encode candidates (ranked)

Ranked by breadth of field use x fit to the map's existing tiers.

1. **i-PI rail + PIMD Trajectory producer** - ring-polymer sampling of the
   quantum partition function; one rail opens the entire NQE layer.
2. **FreeEnergySurface / PMF node** - F(s) = -kT ln P(s) along a CV; the single
   biggest missing tier, function-valued, fits the spectrum contract.
3. **PLUMED rail** - the metadynamics producer for candidate 2; ubiquitous.
4. **ElectronicDOS node** - g(E), Fermi level, gap; parent of BandGap; guard
   the PhononDOS false-merge.
5. **eOn rail + second NEB/saddle producer** - strengthens ReactionBarrier
   [neb_mep] with a second producer.
6. **IRAbsorptionSpectrum node + dipole-ACF producer** - reuses the existing
   Green-Kubo machinery; classic observable.
7. **QuantumHeatCapacity as a HeatCapacity producer variant** - small
   increment on the i-PI rail; grounds an existing node with a quantum
   estimator.
8. **CP2K rail** - second first-principles engine; nodes already exist, low
   new-node cost.
9. **PolarizabilityTensor node** - molecular optical response; distinct from
   the bulk dielectric tensor.
10. **NMRShieldingTensor node** - new spectroscopy corner with strong
    experimental linkage; ranked low only because it sits far from the map's
    lattice-dynamics core.

## Deferred hooks the cookbook independently confirms

- **NEB barrier**: confirmed by `eon-pet-neb`. The node exists; eOn is a second
  producer.
- **spectrum layer**: confirmed twice over by `water-ir-spectrum` (IR) and
  `pet-mad-dos` (electronic DOS) - both function-valued spectra beyond
  PhononDOS.
- **polarization / dielectric response**: confirmed by `water-pulsed`,
  `polarizability`, and the dynamical-charges discussion in `water-ir-spectrum`.
- **quantum-nuclear effects / isotopes**: strongly confirmed by the whole
  path-integral cluster (`path-integrals`, `heat-capacity`, `pi-metad`).
- **RRHO / molecular thermochemistry**: partially confirmed (the cookbook does
  quantum C_V via PIMD rather than rigid-rotor-harmonic-oscillator).

Hooks this source does NOT confirm (it is a sampling/MLIP collection, not a
characterization one): **RDF** (MD is everywhere but never surfaced as a
headline product), **XRDPattern** (no diffraction recipe), **defects** (no
defect-formation recipe), **thermoelectric evidence** (the transport recipe is
lattice thermal conductivity, already covered by kALDo, not Seebeck/ZT).

## Open questions

Carried verbatim in the JSON `open_questions` field. The load-bearing ones:

1. i-PI and eOn licenses must be confirmed before a rail is minted (credits
   rule).
2. Method-tagged siblings vs standalone nodes for the quantum estimators
   (QuantumHeatCapacity, QuantumKineticEnergy) - a kernel/tiering decision.
3. ModelUncertainty is recommended as a record-level attribute, not a node;
   needs a project decision before any UQ recipe is encoded.
4. ElectronDensity is field-valued and exceeds the current scalar+spectrum
   evidence contract; needs a field-evidence kernel first.
5. Whether the IR spectrum's absorption-vs-frequency axis is expressible under
   the current spectrum canonical-axis registry or needs a new registered
   axis+value unit pair.

## Review verdicts (2026-07-11)

Adversarial deep review of commit `160eb74`'s audit (three axes, top-10 rank).
Default-to-distrust pass. Ground truth re-read at HEAD from
`docs/data/codes.json` (**27 rails**), `docs/data/graph.json` (**98 nodes**),
`omai/map_data.py` (10 domains). Cookbook re-opened by WebFetch of
`atomistic-cookbook.org` and each cited recipe page; licenses pulled from the
five rail repos' own LICENSE files; citations checked against the publishers.
**Em-dash grep over both files: zero.**

### Sweep verification

- **Ground truth CONFIRMED.** 27 rails, 98 nodes. No `i-pi`/`plumed`/`cp2k`/
  `eon`/`gromacs` key exists in `codes.json` (grep-verified): every rail
  candidate is genuinely absent. `PhononDOS` present, no electronic DOS.
  `HelmholtzFreeEnergy`, `MolarHelmholtzFreeEnergy`, `MolarGibbsEnergy`,
  `QHAGibbsEnergy` all present (all scalar). `ReactionBarrier[construction=
  neb_mep]`, `BandGap`, `HOMOLUMOGap`, `DielectricTensor`,
  `StaticDielectricTensor`, `IsotopeAbundances` present. Statuses in the catalog
  are consistent with the current graph.
- **Recipe count CORRECTED: 40 folders vs 41 site titles.** The scan text says
  "40 recipe folders cross-checked against the 41 titles" and the JSON says
  `recipes_swept: 40`. The site index WebFetch returns **41 gallery titles**.
  The delta is a card/folder bookkeeping artifact, not a missed physics recipe:
  some folders back two gallery cards (`sample-selection` -> both "Sample and
  Feature Selection" and "PCA/PCovR Visualization"; the pet-mad family ->
  "Introduction to foundational models" and "The PET-MAD universal potential"),
  and `gaas-map`/`water-md` carry no standalone headline title. Every physics
  theme on the index is present in the swept 40. `site_index_titles: 41` and a
  `sweep_gap_note` are now recorded in the JSON. **No physics gap hides in the
  40-vs-41.**
- **Per-recipe code attributions CONFIRMED (8+ spot-checks).** pi-metad (i-PI +
  PLUMED, FES via `sum_hills`, CVs = O-O distance + coordination difference);
  eon-pet-neb (eOn NEB + dimer, PET-MAD, ~0.9 eV barrier, saddle); heat-capacity
  (i-PI PIMD, scaled-coordinates estimator, **exact formula match** to the JSON:
  `C_V = k_B beta^2 (<eps_v^2> - <eps_v>^2 - <eps_v'>)`); pet-mad-dos (electronic
  g(E) on a 4806-point grid, Fermi level, CNN bandgap); batch-cp2k (CP2K
  `reftraj` single-point DFT energies + forces); polarizability (lambda-SOAP
  equivariant, lambda=0/2 molecular alpha); water-ir-spectrum (**LAMMPS** MD +
  metatomic dipole head -> dipole ACF -> IR; engine is LAMMPS, not i-PI, which is
  consistent with the JSON's "LAMMPS/i-PI" producer); thermal-conductivity-bte
  (kALDo, covered). **The sweep is trustworthy.**

### The credits-readiness table (five rail candidates)

All five licenses verified from primary sources; each JSON entry now carries
`credits_ready: true`. No invented DOIs. Open question 1 is **RESOLVED**.

| Rail | License (verified 2026-07-11) | Canonical citation | DOI |
|---|---|---|---|
| **i-PI** | **dual GPL-2.0 / MIT** (user's choice; `licenses/LICENSE.md`: "distributed under both the GPL and MIT licenses") | Y. Litman, V. Kapil, Y. M. Y. Feldman, et al., i-PI 3.0, J. Chem. Phys. **161**, 062504 (2024) | 10.1063/5.0215869 |
| **PLUMED** | **LGPL-3.0** (`COPYING.LESSER`) | G. A. Tribello, M. Bonomi, D. Branduardi, C. Camilloni, G. Bussi, PLUMED 2, Comput. Phys. Commun. **185**, 604 (2014) | 10.1016/j.cpc.2013.09.018 |
| **CP2K** | **GPL-2.0-or-later** (`LICENSE`) | T. D. Kuhne, M. Iannuzzi, M. Del Ben, et al., CP2K, J. Chem. Phys. **152**, 194103 (2020) | 10.1063/5.0007045 |
| **eOn** | **BSD-3-Clause** (repo `LICENSE`, (c) eOn Development Team 2010-present) | S. T. Chill, M. Welborn, R. Terrell, L. Zhang, J.-C. Berthet, A. Pedersen, H. Jonsson, G. Henkelman, EON, Model. Simul. Mater. Sci. Eng. **22**, 055002 (2014) | 10.1088/0965-0393/22/5/055002 |
| **GROMACS** | **LGPL-2.1-or-later** (gromacs.org; repo on GitLab) | M. J. Abraham, T. Murtola, R. Schulz, et al., GROMACS, SoftwareX **1-2**, 19 (2015) | 10.1016/j.softx.2015.06.001 |

Corrections to the scan's credits: i-PI license was "MIT (GPL components);
confirm" -> **clean dual GPL/MIT (user's choice)**; i-PI lead author "M. Litman"
-> **Y. Litman** (Yair); i-PI article no. 062504 confirmed against pubs.aip.org
(the repo README BibTeX's "062505" is a README typo). eOn license "(confirm)"
-> **CONFIRMED BSD-3-Clause**; eOn title "client-server software..." ->
"EON: software for long time simulations..."; full 8-author list recorded. The
2014 eOn paper mentions GPLv3, but the **current** TheochemUI repo relicenses
under BSD-3, which governs an encode today. metatensor citation (JCP **164**,
064113, 2026; DOI 10.1063/5.0304911) confirmed exact. For a metadynamics FES
encode, PLUMED asks (per its own guidance) that the specific method paper be
cited alongside PLUMED 2; that method DOI is left **UNKNOWN-until-encode**, not
invented.

### Top-10 ranking review (order STANDS, two sharpenings)

- **Candidate 2 (FreeEnergySurface) carries a hidden kernel dependency.** A
  multi-CV FES is a scalar field over CV-space and is **beyond** the current
  1-D spectrum contract; only the **1-CV PMF** fits spectrum-layer today (axis =
  the one CV, values = F). The confirmed pi-metad recipe uses **two** CVs, so
  the general FES is field-valued and shares the same field-kernel gap as
  ElectronDensity. Rank unchanged, but the *encodable slice today* is the 1-CV
  PMF.
- **Candidate 4 (ElectronicDOS) is the single highest false-merge hazard.**
  `ElectronicDOS != PhononDOS`: dimension-distinct (states per **energy/eV** vs
  states per **frequency/THz**), physics-distinct. Must be guarded explicitly at
  encode; never a PhononDOS producer variant.
- **QuantumHeatCapacity (rank 7) re-affirmed as a producer VARIANT, not a
  node.** Same quantity Cv, same dimension as the existing `HeatCapacity`, only
  the method differs (PIMD fluctuation estimator vs harmonic). A new node would
  be a false duplicate. Recommend `HeatCapacity[method=pimd]`.

No candidate is promoted or demoted. The physics-fit ordering is sound.

### Dimensional rigor (recomputed; two added)

- **PolarizabilityTensor (added, two conventions).** SI polarizability
  `alpha = d(dipole)/d(E) = C^2 m^2 J^-1 = A^2 s^4 kg^-1`, exponents
  `(M,L,T,Theta,N,I,J) = (-1, 0, 4, 0, 0, 2, 0)`. Polarizability-**volume**
  (Gaussian/atomic) convention `alpha_vol = alpha_SI/(4*pi*eps0)` has dimension
  of **volume** `L^3`, exponents `(0,3,0,0,0,0,0)`, unit angstrom^3 - the
  convention the cookbook's lambda-SOAP targets use. The two differ by
  `4*pi*eps0` and have **different dimension signatures**; an encode must pin
  which. Distinct from the map's `DielectricTensor`/`StaticDielectricTensor`,
  which are **dimensionless** bulk relative permittivities: dimension-distinct,
  no merge.
- **NMRShieldingTensor / IsotropicChemicalShift (added).** **Dimensionless**,
  exponents `(0,0,0,0,0,0,0)` (a ratio of induced to applied field). "ppm" is a
  `10^-6` dimensionless scaling, **not a unit** - register as dimensionless with
  a ppm serving-scale, do not invent a unit.
- **FreeEnergySurface.** Energy-dimensioned (per mole or per particle), but the
  **argument structure** (a function over collective variables), not the
  dimension, is what separates it from the three scalar free-energy nodes.

### False-merge verdicts (checked against the live graph)

- `FreeEnergySurface / PMF` vs {`MolarHelmholtzFreeEnergy`, `MolarGibbsEnergy`,
  `QHAGibbsEnergy`}: all three existing nodes are **scalar** state-point free
  energies (harmonic-vibrational A(T); CALPHAD G(T,x); quasi-harmonic G(T,p)).
  A PMF/FES is **function-valued over a collective variable**, `F(s) = -kT ln
  P(s)`: same physical dimension (energy), **different argument structure**,
  different basis (configurational along a reaction coordinate). **Dimension-
  equal, family-distinct: must not merge.** That dimension-equality is exactly
  the trap.
- `ElectronicDOS` vs `PhononDOS`: dimension-distinct, physics-distinct. Separate
  node. (Highest hazard.)
- `PolarizabilityTensor` vs `DielectricTensor`: dimension-distinct (L^3 or
  C^2 m^2 J^-1 vs dimensionless). Separate node.
- `TunnelingRate/InstantonRateConstant` vs `ReactionBarrier`/`ActivationEnergy`:
  a rate constant (inverse time) vs a barrier height (energy). Separate node.

### Out-of-scope calls (confirmed sound)

chemiscope (pure viewer), scikit-matter (FPS/CUR/PCovR data-science artifacts),
torch-pme (long-range energy contribution internal to a potential, no
standalone map-tier observable), featomic (descriptors = model internals): all
four out-of-scope calls state their reasoning and it is **sound**.
`ModelUncertainty` correctly routed to a **record-level uncertainty attribute**
(the instance schema already carries the field), not an evidence node. Agreed.

### Orchestrator decisions and RECOMMENDED ENCODE ORDER

Full list in the JSON `orchestrator_decisions`. Load-bearing outcomes:

1. **Rails credits-clear now.** All five rail candidate licenses + citations are
   verified and recorded; the credits rule no longer blocks any of them.
2. **Kernel gate.** Multi-CV FES and ElectronDensity both need a field / multi-
   axis evidence kernel that does not exist yet. The 1-CV PMF is encodable under
   the current spectrum contract; the multi-CV FES is not.
3. **Variants not nodes.** `QuantumHeatCapacity = HeatCapacity[method=pimd]`
   variant; `QuantumKineticEnergy` = a genuinely new scalar/tensor node (no
   dimensional twin); `CollectiveVariable` = axis descriptor;
   `ModelUncertainty` = record uncertainty attribute.
4. **False-merge guards** (above) must be encoded explicitly.

**RECOMMENDED ENCODE ORDER (after the already-queued kaldo delta):**

- **The kaldo delta lands first.** It is a same-family increment on the existing
  thermal-transport DAG; the cookbook slices open a **new** layer and should not
  preempt it.
- **Slice 1: i-PI rail + PIMD Trajectory producer + QuantumKineticEnergy node +
  QuantumHeatCapacity[method=pimd] producer variant.** One credits-clear rail
  (dual GPL/MIT) unlocks the entire nuclear-quantum-effects layer, grounds an
  existing node (HeatCapacity) with a new estimator, and adds exactly one clean
  new node (QuantumKineticEnergy) with no false-merge and no kernel dependency.
  Highest value-per-encode, zero kernel blockers, adjacent to the MD/thermo core
  the kaldo delta just touched.
- **Slice 2: PLUMED rail + 1-CV PMF node** (FreeEnergySurface restricted to one
  collective variable). Biggest missing tier, credits-clear (LGPL-3.0); the
  1-CV restriction keeps it inside the current spectrum contract, so no kernel
  work is needed first. Defer multi-CV FES to the field kernel.
- **Slice 3: ElectronicDOS node** (spectrum-layer), PhononDOS false-merge
  guarded explicitly; parent of the existing BandGap; no new rail required (any
  DFT engine or PET-MAD-DOS produces it).
- **Then** (all credits-ready, ranked, kernel-permitting): eOn + second NEB
  producer, IRAbsorptionSpectrum + dipole-ACF, CP2K, PolarizabilityTensor,
  NMRShieldingTensor. **ElectronDensity and multi-CV FES wait on the field
  kernel.**
