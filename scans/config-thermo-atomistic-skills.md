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

`docs/data/graph.json` had **67 nodes** at scan time (git HEAD `f16f913`).
**Review re-read (2026-07-09, HEAD `1675cde`): the graph is now 73 nodes.** The
thermochemistry (pycalphad) encode LANDED while this catalog waited (commits
`cd83b1e` CALPHAD domain, `89b2283` records 134-144, `1675cde` data+index regen).
Statuses below are re-stated against the live 73-node graph.

- **Present** (the mapped diffusion slice, unchanged): `Diffusivity`,
  `ActivationEnergy`, `MeanSquaredDisplacement`. `registry.py` carries
  `diffusivity`, `activation_energy`, `mean_squared_displacement`.
- **Still absent** (73-node graph): `IonicConductivity`, `ChargeDiffusivity`,
  `HavenRatio`, `ProbabilityDensity`, `ReactionEnergy`, `ClusterExpansion`.
- **Now present** (landed since scan, the pycalphad encode + mp-api rail):
  `ChemicalPotential` (`ENERGY_PER_MOLE`, J/mol, per mole of atoms,
  `omai/thermochemistry/operator/nodes.py:121`), `MolarGibbsEnergy`,
  `PhaseFraction`, `TransitionTemperature`, plus `EnergyAboveHull` and `Voltage`.
  The scan's original "VERIFIED absent: ChemicalPotential, MolarGibbsEnergy"
  is **stale**: they are live. The per-atom-eV vs per-mole-J/mol chemical-potential
  reconciliation is now a LIVE cross-domain question, not an in-flight one.
- The `omai/thermochemistry/{operator,representation}/` dirs are **no longer
  empty**: the `compute_chemical_potentials` edge (`edges.py:117`) maps
  `MolarGibbsEnergy -> ChemicalPotential`.

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

**Dimension (verified by hand, twice).** Electrical conductivity is S/m =
`A^2 s^3 kg^-1 m^-3`. In the map's `(M, L, T, Theta, N, I, J)` base-exponent
convention (`omai/operator/dimensions.py`):

```
IonicConductivity = (M=-1, L=-3, T=3, Theta=0, N=0, I=2, J=0)   [VERIFIED]
```

Two derivations agree: (1) Nernst-Einstein term-by-term, `(n/V)[L^-3] *
z^2 e^2 [I^2 T^2] * D [L^2 T^-1] / (k_B T) [M L^2 T^-2] = M^-1 L^-3 T^3 I^2`;
(2) S/m first-principles, `S = A/V = A^2/W = I^2 T/(M L^2 T^-2) =
M^-1 L^-2 T^3 I^2`, so `S/m = M^-1 L^-3 T^3 I^2`. It carries the **electric-current
axis I=2**, which **no current diffusion-slice node has**.

**Correction (review):** the scan's claim that this "opens the electric-current
base axis on the materials side for the first time" is **wrong**. The map has
already opened that axis: `Voltage = (1,2,-3,0,0,-1,0)`, `I=-1`, and
`dimensions.py:130-131` explicitly calls Voltage "the map's first use of the
electric-current base axis." IonicConductivity is the first `I=+2` node and the
first I-axis node **in the diffusion slice**, not the materials side's first
I-node. It remains **emphatically NOT the map's ThermalConductivity**
`(1,1,-3,-1,0,0,0)`: different sign of L and T, a Theta axis instead of an I
axis. Ionic and thermal conductivity share only the English word "conductivity".

**Units**: mS/cm (skill reports sigma_RT at 300 K, `calculate_activation_energy.
py:241,107`). `1 S/m = 10 mS/cm`, so the registration factor mS/cm -> S/m is
**x0.1** (verified). `N_A*e = F = 96485.33212331` C/mol (SI-exact);
`R = 8.31446261815324` J/mol/K (CODATA, `= N_A * k_B`, verified to full precision,
consistent with the `k_B = 8.617333262145e-5` eV/K the Arrhenius plot uses at
`:59,209`). The Nernst-Einstein sigma here uses the **tracer** diffusivity times
conv_factor, i.e. assumes Haven ratio 1 (`analyzer.py:338`; the charge diffusivity
gives `chg_conductivity` at `:340`).

**Verdict**: `IonicConductivity` is a genuine NEW node (dimension **VERIFIED
CORRECT**), a companion to the already-mapped `Diffusivity` (they differ only by
the conversion factor). It opens the electric-current axis **in the diffusion
slice** (Voltage already opened it on the materials side); it is the first `I=+2`
node.

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
2. **Per-atom eV vs per-mole J/mol chemical potential** (now a LIVE trap): smol
   semigrand mu and rxn open-element mu are per-ATOM eV (`N=0`); the **now-live**
   `ChemicalPotential` node (`omai/thermochemistry`, `ENERGY_PER_MOLE`, `N=-1`,
   per mole of atoms) is per-MOLE J/mol. Factor `1 eV/atom = 96485.33212331 J/mol`
   (= Faraday, SI-exact, verified). The live node must carry the basis or the
   three false-merge. This is no longer hypothetical: the node landed.
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
   open-element mu (per-atom eV), and the **now-live** pycalphad `ChemicalPotential`
   (per-mole J/mol): one node with a basis label or separate nodes? The
   thermochemistry domain is no longer empty; this decision spans a live node.
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
10. **Snapshot drift** (resolved at review): the graph was 67 nodes at scan time
    (HEAD f16f913); the review re-read at HEAD `1675cde` finds **73 nodes** (the
    pycalphad encode landed). Statuses are snapshot-dated and MUST be re-read from
    graph.json at encode time; the ChemicalPotential / PhaseFraction / MolarGibbs
    candidates now overlap LIVE nodes, not in-flight ones.

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
  DIFFUSIVITY); `omai/operator/dimensions.py:130-132` (Voltage, I=-1, the map's
  first electric-current axis); `omai/operator/registry.py:125-127`;
  `omai/thermal_transport/operator/nodes.py:55` (Potential, OPAQUE);
  `omai/thermochemistry/operator/nodes.py:121` (ChemicalPotential, ENERGY_PER_MOLE,
  now live); `docs/data/graph.json` (67 nodes at scan HEAD f16f913; 73 at review
  HEAD 1675cde).

## Review verdicts (2026-07-09)

Adversarial deep review of commit `92a94b7`'s catalog (17 entries). Sources
re-opened from `/tmp/cfgsrc`: `smol-0.5.7` sdist, `reaction_network-8.3.0` wheel,
`pymatgen_analysis_diffusion-2025.11.15` wheel. Every AtomisticSkills anchor
opened in-repo. Map side read from `omai/operator/dimensions.py`,
`omai/thermochemistry/operator/{nodes,edges}.py`, and `docs/data/graph.json`
(re-read at HEAD `1675cde`, **73 nodes**). Constants recomputed from SI-exact
scipy values. **Em-dash grep over both files: zero.**

### The load-bearing dimension: IonicConductivity

**DIMENSION VERIFIED CORRECT.** `(M=-1, L=-3, T=3, Theta=0, N=0, I=2, J=0)`,
confirmed by two independent hand derivations (Nernst-Einstein product and S/m
first-principles). `get_conversion_factor` at `analyzer.py:846-869` matches the
scan's formula **exactly** (`1000 * n/(vol_cm3 * N_A) * z^2 * (N_A*e)^2/(R*T)`,
`z` from oxidation state else valence-electron count at `:864`, `vol *= 1e-24`
cm^3 at `:868`); `self.conductivity = self.diffusivity * conv_factor` at `:338`.
Serving unit **mS/cm** confirmed; registration factor to S/m is **x0.1** (verified).
The Nernst-Einstein sigma uses the **tracer** diffusivity (Haven ratio 1 assumed);
input D in **cm^2/s** confirmed. Constants verified to full precision:
`F = N_A*e = 96485.33212331` C/mol, `R = N_A*k_B = 8.31446261815324`,
`k_B = 8.617333262145e-5` eV/K.

### Physics-changing / status-changing corrections

- **"First electric-current axis" overclaim: CORRECTED.** The scan said
  IonicConductivity "opens the electric-current base axis on the materials side
  for the first time." Wrong: `Voltage = (1,2,-3,0,0,-1,0)` (`I=-1`) already
  opened it (`dimensions.py:130-131` says so verbatim). IonicConductivity is the
  first `I=+2` node and the first I-axis node **in the diffusion slice**. Fixed
  in the dimension_check, the verdict, and the entry (JSON + here).
- **ChemicalPotential / MolarGibbsEnergy "VERIFIED absent": STALE, CORRECTED.**
  The pycalphad thermochemistry encode LANDED between scan (HEAD f16f913, 67
  nodes) and review (HEAD `1675cde`, 73 nodes). `ChemicalPotential`
  (`ENERGY_PER_MOLE`, J/mol, per mole of atoms, `nodes.py:121`), `MolarGibbsEnergy`,
  `PhaseFraction`, `TransitionTemperature` are now **live**. The per-atom-eV vs
  per-mole-J/mol reconciliation is now a live cross-domain question. Fixed
  throughout.
- **smol ensemble line anchors: CORRECTED.** `ChemicalPotentialManager` is the
  class at `ensemble.py:22-99` (not `111-134`; line 111 is only the descriptor
  binding). The `E - sum(mu*N)` generalized-enthalpy construction is
  `compute_feature_vector` at `312-340`, phrase "a generalized enthalpy" at line
  317, `natural_parameter = -1.0` at line 25. The per-atom-eV unit is a **skill
  convention** (SKILL.md:61), not annotated in smol source.

### Per-entry verdicts

- **smol-cluster-expansion-model: CONFIRMED (representation-only, Potential
  analog).** `expansion.py:288` `return np.dot(self.coefs, corrs)` exact; `:159`
  `self.coefs = coefficients` exact; ECI division at `:182` (strips external
  terms at `:179-181` first). `MSONable` `as_dict`/`from_dict` at `:511`/`:486`.
  Fitting is **external** (sklearn `LassoCV`, sparselm SGL); smol carries no
  solver. Potential-analog verdict stands.
- **smol-ce-predicted-energy: CONFIRMED (new-node-candidate).** Three energy bases
  verified: per-supercell (feature vector x `self.size`, `processor/expansion.py:180`,
  "correlation vector x system size" at `ensemble.py:320-321`), per-prim
  (`normalized=True`, `expansion.py:259-288`), per-atom (skill divides by sites,
  `run_gcmc_sweep.py:153`). ENERGY dimension; not TotalEnergy, not FormationEnergy.
- **smol-mc-composition-and-occupancy: CONFIRMED (new-node-candidate).**
  Dimensionless mole fraction (`element_count/total_sites`). Cousin `PhaseFraction`
  is now live but a phase fraction is not a mole fraction: companion, not equate.
- **smol-semigrand-chemical-potential: CONFIRMED (new-node-candidate), anchors
  corrected.** Per-atom eV (skill convention); sibling of the now-live per-mole
  J/mol ChemicalPotential.
- **smol-mc-phase-diagram: CONFIRMED (representation-only).** `plot_phase_diagram`
  (`91-158`), `plot_contour_phase_diagram` (`161-226`) verified.
- **smol-mc-temperature-condition: CONFIRMED (representation-only).**
  `constants.py` `kB = 8.617333262145e-5` eV/K exact; `beta = 1/(kB*T)` at
  `kernel/base.py:398` and `metropolis.py:166` exact.
- **rxn-reaction-energy-per-atom: CONFIRMED (new-node-candidate).**
  `base.py:37-38` "The energy of this reaction in total eV." exact;
  `computed.py:114` sum over reduced-composition entry energies x coefficients;
  `energy_per_atom = energy/num_atoms` at `:122`; `num_atoms` sums product-side
  atoms x coefficients (`basic.py:322-324`) so the basis is **per reaction-atom**,
  confirmed.
- **rxn-gibbs-entry-formation-energy: CONFIRMED (new-node-candidate, cousin of
  FormationEnergy).** SISSO `dGf(T) - dHf(298 K)` at `gibbs.py:94-100`; range
  `[300,2000] K` enforced via `raise ValueError` at `:84-85` (not an assert); the
  `~50 meV/atom MAD` is a **real source comment** on `uncertainty = 0.05 *
  num_atoms` at `gibbs.py:97` (0.05 eV = 50 meV, not invented). Finite-T Gibbs vs
  0 K/298 K DFT: cousin, never a naive equate.
- **rxn-open-element-chemical-potential: CONFIRMED (new-node-candidate).**
  `minimize.py:218-222` `mu`, `chempots = {open_elem: mu}`. Grand-potential
  subtraction `energy - sum(mu*n_open)` is delegated to pymatgen's
  `GrandPotPDEntry` (`open.py:55-63,143`), not spelled out in rxn; mu is a bare
  float (per-atom eV by pymatgen convention). Sibling of the live ChemicalPotential.
- **rxn-pathway-cost: CONFIRMED (representation-only, dimensionless).**
  `Softplus._softplus = log(1 + (273/t)*exp(x))` at `functions.py:74-77`, `x =
  dot(param values, weights)`, default param `["energy_per_atom"]`, weight `[1.0]`.
  `273` and `t=self.temp` (default 300) are constants, not the reaction T. Cost is
  dimensionless by construction (log of a squashed eV/atom).
- **rxn-reaction-network-graph: CONFIRMED (representation-only).** Combinatorial
  substrate. (Minor unrelated defect: `find_pathways.py:181` references an
  undefined `logger` in an except branch, would `NameError` if hit; not a catalog
  claim.)
- **rxn-synthesis-temperature-condition: CONFIRMED (representation-only).**
  Feeds both the Gibbs energetics and the Softplus cost scale.
- **diffusion-diffusivity / activation-energy / mean-squared-displacement:
  CONFIRMED (already-mapped).** Wheel-verified cm^2/s, eV, A^2 vs fs held. Haven
  ratio + charge diffusivity remain unmapped low-priority candidates.
- **diffusion-ionic-conductivity: CONFIRMED (new-node-candidate), dimension
  verified, "first materials I-axis" claim corrected (see above).**
- **diffusion-probability-density: CONFIRMED (representation-only).** Volumetric
  CHGCAR field, Angstrom grid, `to_chgcar` at `pathway.py:242`.

### Orchestrator decisions

1. **Mint IonicConductivity.** Dimension `(-1,-3,3,0,0,2,0)` verified; serving
   unit mS/cm, registration factor **x0.1** to S/m. Companion to Diffusivity
   (differ only by conv_factor). It is the first `I=+2` node and the first I-axis
   node in the diffusion slice (NOT the materials side's first: Voltage precedes
   it). Charge diffusivity + Haven ratio: **defer** (the two skill scripts do not
   print them).
2. **ConfigurationalEnergy question.** smol CE-predicted energy is ENERGY-
   dimensioned but fixed-lattice, training-referenced, three-basis (supercell /
   prim / atom): mint a `ConfigurationalEnergy` node with a basis+reference label
   rather than routing through TotalEnergy or FormationEnergy. Recommended: **new
   node**, given the distinct physics (lattice-model Hamiltonian, not a relaxed-
   structure PES call).
3. **Chemical-potential family topology.** ChemicalPotential is **now live**
   (per-mole J/mol, ENERGY_PER_MOLE). smol semigrand mu and rxn open-element mu
   are per-atom eV. Recommended: **one ChemicalPotential node carrying a basis
   label** (per-atom eV vs per-mole J/mol, factor 96485.33212331 = Faraday), not
   three nodes. The encode agent that landed the per-mole node must add the basis
   field before the eV siblings attach.
4. **dGf(T)-vs-FormationEnergy cousin ruling.** rxn GibbsEntry `dGf(T)` shares the
   dimension AND per-atom basis of FormationEnergy but is finite-T SISSO-Gibbs
   (300-2000 K, ~50 meV/atom MAD, MP-derived) vs 0 K/298 K DFT. Recommended:
   **cousin, not equate**; encode as `FormationEnergy[source=sisso, T=...]` variant
   or a distinct node, never a naive merge. Record MP provenance + SISSO T + the
   0.05*num_atoms descriptor uncertainty on any instance.
5. **Snapshot reconciliation.** Statuses re-read at HEAD `1675cde` (73 nodes); the
   ChemicalPotential / MolarGibbsEnergy / PhaseFraction candidates now overlap
   LIVE nodes. Re-read graph.json at encode time.
