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
