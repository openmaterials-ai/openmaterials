# smol, rxn_network, pymatgen-analysis-diffusion as used by AtomisticSkills: scan report

Scan of the **configurational-thermodynamics trio** as the AtomisticSkills
(arXiv 2605.24002) skills actually use them:

- **smol** (`smol.cofe`, `smol.moca`): cluster expansion + lattice Monte Carlo.
- **rxn_network** (`reaction-network`): reaction energetics + synthesis pathways.
- **pymatgen-analysis-diffusion** (`pymatgen.analysis.diffusion`): MSD /
  diffusivity / ionic conductivity, extending the already-mapped diffusion slice.

Companion catalog: `scans/config-thermo-atomistic-skills.json` (17 entries).

A previous scanner falsely claimed AtomisticSkills was absent. It is vendored at
`AtomisticSkills/.agents/skills/` (126 skills); every usage claim below is
anchored to a real `file:line` in that tree, and every unit/API claim to a real
`file:line` in the pip-downloaded package source.

## Sources and version anchoring

**None of the three import in the miniconda base env** (`No module named smol` /
`rxn_network` / `pymatgen.analysis.diffusion`). Anchors read from pip-downloaded
artifacts (`/Users/juicy/miniconda3/bin/pip download --no-deps --dest
/tmp/cfgsrc smol reaction-network pymatgen-analysis-diffusion`):

- `smol-0.5.7.tar.gz` (sdist, read from source under `/tmp/cfgsrc/smol_src/`)
- `reaction_network-8.3.0-py3-none-any.whl` (unzipped to `/tmp/cfgsrc/rxn/`)
- `pymatgen_analysis_diffusion-2025.11.15-py3-none-any.whl` (`/tmp/cfgsrc/diff/`)

Environments: smol lives in `conda-envs/smol-agent` (`python=3.10`, pins `smol`,
`pymatgen`, no versions); rxn_network + pymatgen-analysis-diffusion live in
`conda-envs/base-agent` (pins `reaction-network`, `pymatgen-analysis-diffusion`,
no versions). Pin versions at encode.

**mp-api scan honoured**: it wheel-verified `DiffusionAnalyzer` diffusivity in
cm^2/s, MSD in A^2, dt in fs. This scan BUILDS on that (same wheel version,
2025.11.15) and does not contradict it; it adds the ionic-conductivity and
AIMD-pathway family that scan did not reach.

## Graph snapshot (freshness at my end)

`docs/data/graph.json` has **67 nodes** at scan time, at git HEAD `f16f913` (the
mp-api database-rail regeneration). The map has moved PAST the 66-node snapshot
the pycalphad and mp-api scans recorded (the mp-api BandGap/vasp rail landed).

- **Present** (the mapped diffusion slice): `Diffusivity`, `ActivationEnergy`,
  `MeanSquaredDisplacement`. `registry.py` carries `diffusivity`,
  `activation_energy`, `mean_squared_displacement`.
- **Absent**: `IonicConductivity`, `ChargeDiffusivity`, `HavenRatio`,
  `ProbabilityDensity`, `ChemicalPotential`, `ReactionEnergy`,
  `ClusterExpansion`, `MolarGibbsEnergy`.
- The `omai/thermochemistry/{operator,representation}/` dirs from the pycalphad
  scan's proposed domain **exist but are EMPTY**: that encode has not landed, so
  the configurational/phase-thermo candidates the pycalphad scan opened
  (ChemicalPotential, PhaseFraction, etc.) are still not live nodes.

## Entry counts by status (17 entries)

| Package | already-mapped | new-node-candidate | representation-only |
|---|---|---|---|
| **smol** | 0 | 3 | 3 |
| **rxn_network** | 0 | 3 | 3 |
| **pymatgen-analysis-diffusion** | 3 | 1 | 1 |
| **total** | **3** | **7** | **7** |

- **smol new-node-candidates**: `smol-ce-predicted-energy` (configurational
  energy, eV/atom), `smol-mc-composition-and-occupancy` (dimensionless
  equilibrium x), `smol-semigrand-chemical-potential` (per-atom eV mu).
- **smol representation-only**: `smol-cluster-expansion-model` (Potential-analog
  parameter-state), `smol-mc-phase-diagram` (T-x/T-mu plot product),
  `smol-mc-temperature-condition` (input Source).
- **rxn_network new-node-candidates**: `rxn-reaction-energy-per-atom` (dG,
  eV/atom), `rxn-gibbs-entry-formation-energy` (SISSO-Gibbs dGf(T), eV/atom,
  cousin of FormationEnergy), `rxn-open-element-chemical-potential` (per-atom
  eV).
- **rxn_network representation-only**: `rxn-pathway-cost` (dimensionless Softplus
  score), `rxn-reaction-network-graph` (combinatorial substrate),
  `rxn-synthesis-temperature-condition` (input Source).
- **diffusion already-mapped**: `diffusion-diffusivity` (-> Diffusivity),
  `diffusion-activation-energy` (-> ActivationEnergy),
  `diffusion-mean-squared-displacement` (-> MeanSquaredDisplacement).
- **diffusion new-node-candidate**: `diffusion-ionic-conductivity` (the
  headline: IonicConductivity, mS/cm).
- **diffusion representation-only**: `diffusion-probability-density` (volumetric
  CHGCAR field).

## smol's cluster expansion IS a fitted Potential-representation analog

The task asked whether the CE is a Potential-representation analog. **Yes.** A
`ClusterExpansion` is a `ClusterSubspace` (the cluster/orbit basis) plus a
coefficient vector `coefs` (`smol/cofe/expansion.py:159`); the ECI are
`coefs / function_total_multiplicities` (`:172-183`). Predicting an energy is
`np.dot(self.coefs, corrs)` (`:288`), exactly how an MLIP evaluates a checkpoint
on a structure. The CE is serialized to `cluster_expansion.json`
(`ClusterExpansion.load`/`.save`) and re-loaded to drive MC
(`mat-grand-canonical-mc/SKILL.md:32-34`; `run_gcmc_sweep.py:38,245`), the way an
MLIP checkpoint file is loaded to drive MD. It is FITTED to DFT/MLIP-labelled
ordered structures via LassoCV / Sparse-Group-Lasso (`ml-cluster-expansion
SKILL.md:104-119`; `iterative_ce_training.py:382-386`), targeting LOOCV < 10
meV/atom (`SKILL.md:169`).

So the CE object is a **parameter-state**, the configurational-energetics analog
of the map's opaque `Potential` node (`omai/thermal_transport/operator/
nodes.py:55`, `OPAQUE`, tier "Sources"): representation-only. What it PRODUCES is
what carries dimensions:

- **Energy**: `processor.compute_property(occu) = dot(coefs, feature_vector)`,
  extensive per supercell (the feature vector is "correlation vector x system
  size", `moca/processor/expansion.py:162-166,180`). `predict(normalized=True)`
  is per-primitive-cell (`expansion.py:259-267`). The GCMC skill divides by site
  count to report **eV/atom** (`run_gcmc_sweep.py:153`). CV-RMSE is reported in
  **eV/prim** (`iterative_ce_training.py:393`). Three energy bases coexist
  (supercell / prim / atom): a unit trap.
- **MC observables**: sublattice occupancy encodings -> structures; mole-fraction
  compositions x (`run_gcmc_sweep.py:145-149`) with equilibrium fluctuations; and
  swept **phase-transition observables**: T-x / T-mu phase diagrams, miscibility
  gaps, spinodal inflection points, from the **semigrand (flip) ensemble** where
  composition fluctuates under a controlled Delta-mu (eV, `SKILL.md:142-149`).

The pycalphad scan's guardrail carries over: smol's CE Gibbs/free energies are
computed lattice-model quantities, not assessed databases; and smol's per-atom eV
chemical potential is not CALPHAD's per-mole J/mol MU (see traps).

## The Nernst-Einstein ionic-conductivity dimension check (headline new node)

`mat-diffusion-analysis/scripts/calculate_activation_energy.py:236` calls
`get_extrapolated_conductivity`, which computes **ionic (electrical)
conductivity** via Nernst-Einstein. The conversion factor
(`analyzer.py:846-869`):

```
sigma[mS/cm] = convf * D[cm^2/s]
convf = 1000 * n/(vol_cm3 * N_A) * z^2 * (N_A*e)^2 / (R*T)
```

This is `sigma = (n/V) z^2 e^2 D / (k_B T)`: number density, squared ionic charge
`z^2` (oxidation state, else valence-electron count, `analyzer.py:864`), electron
charge, over thermal energy. `self.conductivity = self.diffusivity * conv_factor`
(`:338`).

**Dimension (verified by hand).** Electrical conductivity is S/m =
`A^2 s^3 kg^-1 m^-3`. In the map's `(M, L, T, Theta, N, I, J)` base-exponent
convention (`omai/operator/dimensions.py`):

```
IonicConductivity = (M=-1, L=-3, T=3, Theta=0, N=0, I=2, J=0)
```

checked term-by-term: `(n/V)[L^-3] * z^2 e^2 [I^2 T^2] * D [L^2 T^-1] /
(k_B T) [M L^2 T^-2] = M^-1 L^-3 T^3 I^2`. It carries the **electric-current axis
I=2**, which **no current diffusion-slice node has** (the nearest map node with
an I axis, Voltage, is `(1,2,-3,0,0,-1,0)`, `I=-1`). It is **emphatically NOT the
map's ThermalConductivity** `(1,1,-3,-1,0,0,0)`: different sign of L and T, a
Theta axis instead of an I axis. Ionic conductivity and thermal conductivity
share only the English word "conductivity".

**Units**: mS/cm (skill reports sigma_RT at 300 K, `calculate_activation_energy.
py:241,107`). `1 S/m = 10 mS/cm`. `N_A*e = F = 96485.33212331` C/mol (SI-exact);
`R = 8.31446261815324` J/mol/K (CODATA, `= N_A * k_B`, consistent with the
`k_B = 8.617333262e-5` eV/K the Arrhenius plot uses at `:59,209`).

**Verdict**: `IonicConductivity` is a genuine NEW node, opening the
electric-current base axis on the materials diffusion slice, a companion to the
already-mapped `Diffusivity` (they differ only by the conversion factor).

## Where each package sits versus the map

- **Diffusion trio already-mapped, unchanged.** `Diffusivity` (cm^2/s),
  `ActivationEnergy` (eV), `MeanSquaredDisplacement` (A^2 vs fs) map directly to
  the `mat-diffusion-analysis` rail + pymatgen representation. Wheel-verified
  units held.
- **Diffusion extension**: `IonicConductivity` (new, mS/cm, above). Charge
  diffusivity (cm^2/s, collective vs tracer), the Haven ratio (dimensionless,
  `diffusivity/chg_diffusivity`), and the probability-density CHGCAR field are
  further quantities the code exposes; H_r + charge diffusivity are unmapped
  low-priority candidates (the two skill scripts do not print them), and the
  probability density is representation-only.
- **smol** is a new configurational-energetics producer: its CE is a Potential
  analog; its per-atom eV energy, dimensionless MC composition, and per-atom eV
  semigrand mu are candidates; its T-x/T-mu diagrams and MC temperature are
  representation.
- **rxn_network** consumes MP energies (as the mp-api scan noted) through the
  Bartel-SISSO Gibbs descriptor. Its dimensioned outputs are reaction energies
  (eV/atom, total eV) and per-entry SISSO-Gibbs dGf(T) (eV/atom); its costs and
  network are dimensionless graph artifacts.

## Unit convention traps found

1. **smol energy basis triple**: extensive per-supercell (default), per-prim
   (`normalized=True`, CV-RMSE eV/prim), per-atom (eV/atom, GCMC report). Record
   the basis on any CE-energy instance.
2. **Per-atom eV vs per-mole J/mol chemical potential**: smol semigrand mu and
   rxn open-element mu are per-ATOM eV (`N=0`); CALPHAD MU is per-MOLE J/mol
   (`N=-1`). Factor `1 eV/atom = 96485.33212331 J/mol` (= Faraday, SI-exact). A
   shared ChemicalPotential node must carry the basis or the three false-merge.
3. **rxn reaction energy dual normalization**: `ComputedReaction.energy` is TOTAL
   eV for the as-balanced reaction (`reactions/base.py:37-38`); `energy_per_atom
   = energy/num_atoms` eV/atom (`computed.py:117-122`). Skills print eV/atom.
4. **rxn GibbsEntry dGf(T) is finite-T SISSO-Gibbs**, not the map's 0 K/298 K DFT
   FormationEnergy: 300-2000 K, ~50 meV/atom MAD (`entries/gibbs.py:97`),
   MP-derived. Same dimension + per-atom basis, different physics: cousin, never
   a naive equate. Solids only.
5. **rxn pathway cost is dimensionless**: `Softplus = log(1 + (273/T)
   exp(dG_per_atom))` (`costs/functions.py:75-77`) squashes eV/atom to a unitless
   score. Graph-algorithm artifact, not a thermodynamic observable.
6. **Ionic conductivity is NOT thermal conductivity**: `(M=-1,L=-3,T=3,I=2)` vs
   `(1,1,-3,-1)`. Shared word only. Never merge.
7. **Diffusivity is cm^2/s** (wheel-verified), not A^2/ps and not SI m^2/s
   (`1 cm^2/s = 1e16 A^2/s`); MSD is A^2 vs dt in fs; conductivity is mS/cm.
8. **Haven ratio / charge diffusivity vs tracer diffusivity**: the
   Nernst-Einstein sigma here multiplies the TRACER diffusivity by conv_factor,
   i.e. assumes Haven ratio 1; do not silently equate self-diffusivity and charge
   diffusivity when reasoning about conductivity.
9. **smol CE energies are fixed-lattice, fixed-cell** (`relax_cell=False`,
   `ml-cluster-expansion SKILL.md:67-68`): configurational lattice-model energies,
   not relaxed-structure DFT/MLIP totals; reference set by the training data
   (total vs formation energy, `SKILL.md:162`).

## Open questions (full list in JSON `open_questions`)

1. **IonicConductivity** (mS/cm, I=2 axis): confirm minting it on the diffusion
   slice as a Diffusivity companion (introduces the electric-current base axis).
   Charge diffusivity + Haven ratio: open now or defer?
2. **smol CE energy**: mint a ConfigurationalEnergy node (fixed-lattice,
   training-referenced) vs route through the energy family with a basis/reference
   label. Not TotalEnergy, not FormationEnergy despite the shared ENERGY
   dimension.
3. **ClusterExpansion** as a Potential-analog parameter-state: instance schema
   `{ce_file, cutoffs, fit_method, LOOCV eV/prim, training-energy convention}`.
4. **Three chemical potentials**: smol semigrand mu (per-atom eV), rxn
   open-element mu (per-atom eV), pycalphad MU (per-mole J/mol): one node with a
   basis label or separate nodes? Spans the in-flight (empty) thermochemistry
   domain.
5. **rxn reaction energy**: mint ReactionEnergy (eV/atom, per-reaction-atom)? Is
   GibbsEntry dGf(T) a `FormationEnergy[source=sisso,T=...]` cousin or a distinct
   node?
6. **rxn consumes MP energies**: a reaction-energy instance should record MP
   provenance (thermo_type / functional) plus the SISSO temperature and ~50
   meV/atom descriptor error.
7. **smol MC composition x** (dimensionless) is the lattice companion of the
   in-flight thermochemistry PhaseFraction/SiteFraction; scalar-per-(T,mu) vs
   spectrum ingestion. T-x/T-mu diagrams are representation-only.
8. **probability-density CHGCAR** field: confirm representation-only (volumetric,
   not scalar), like the phonon spectra / tensors the map ingests via the
   representation layer.
9. **Version pinning**: smol 0.5.7, reaction-network 8.3.0,
   pymatgen-analysis-diffusion 2025.11.15 (conda-env yamls pin no version).
10. **Snapshot drift**: the graph moved to 67 nodes (HEAD f16f913) past the
    66-node snapshot the pycalphad/mp-api scans recorded. Statuses here read
    against the 67-node graph; record that scan statuses are snapshot-dated and
    re-read from graph.json at encode time (the cross-scan reconciliation the
    mp-api review flagged).

## Source anchors (read from the packages)

- **smol 0.5.7**: `smol/cofe/expansion.py:159,172-183,259-288` (coefs, ECI,
  predict); `smol/moca/processor/base.py:155-164` +
  `processor/expansion.py:162-166,180` (extensive feature vector);
  `smol/moca/ensemble.py:111-134,304-340` (chemical potentials, semigrand
  generalized enthalpy); `smol/constants.py` (`kB = 8.617333262145e-5` eV/K);
  `smol/moca/kernel/base.py:398`, `metropolis.py:166` (beta = 1/(kB T)).
- **reaction-network 8.3.0**: `rxn_network/reactions/base.py:37-38` (energy total
  eV); `reactions/computed.py:104-145` (energy, energy_per_atom, uncertainty);
  `entries/gibbs.py:27-118` (SISSO-Gibbs dGf(T), 300-2000 K, ~50 meV/atom MAD);
  `costs/functions.py:15-77` (Softplus, dimensionless); `enumerators/minimize.
  py:221`, `reactions/open.py:32,52` (open-element chempot).
- **pymatgen-analysis-diffusion 2025.11.15**: `analyzer.py:55` (diffusivity
  cm^2/s), `:96,118,134,276,446` (mscd, Haven ratio), `:338,846-869,1003`
  (Nernst-Einstein conductivity mS/cm), `:877-897` (fit_arrhenius eV);
  `aimd/pathway.py:22-158,242` (ProbabilityDensityAnalysis, Angstrom grid,
  to_chgcar).
- **Skills**: `ml-cluster-expansion/SKILL.md:18,89-95,151-169`,
  `scripts/extract_mc_structures.py:5,70-72,95-100,138`;
  `mat-grand-canonical-mc/SKILL.md:32-35,142-155`,
  `scripts/run_gcmc_sweep.py:38,80-91,93-94,145-153,254-255,296`,
  `scripts/analyze_gcmc_results.py:91-226`;
  `mat-disorder/scripts/iterative_ce_training.py:304-305,160,382-386,393`;
  `mat-reaction-network/scripts/enumerate_reactions.py:36-39,80-89,104-118,132-164`,
  `scripts/find_pathways.py:57-61,104-118,120-206,230-241`;
  `mat-diffusion-analysis/scripts/analyze_diffusion.py:123-135,143-157,175`,
  `scripts/calculate_activation_energy.py:24,59,197-245`;
  `mat-md-probability-density/scripts/calculate_probability_density.py:6,43-60`,
  `SKILL.md:9-24`.
- **Map side**: `omai/materials/operator/nodes.py:7-26` (Diffusivity,
  ActivationEnergy); `omai/materials/representation/mat_diffusion_analysis.py:7-21`
  (D cm^2/s, E_a eV rail); `omai/materials/representation/pymatgen.py:13,69-71`
  (MSD A^2 vs fs); `omai/operator/dimensions.py:115,129` (ThermalConductivity vs
  DIFFUSIVITY); `omai/operator/registry.py:125-127`;
  `omai/thermal_transport/operator/nodes.py:55` (Potential, OPAQUE);
  `docs/data/graph.json` (67 nodes, HEAD f16f913).
