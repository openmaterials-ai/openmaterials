# The MD/chem/bio family as used by AtomisticSkills

Scan of the classical-MD, molecular-informatics, and structural-biology tooling
the AtomisticSkills (arXiv 2605.24002) drug-* and chem-* skills drive:
**openmm, mdanalysis, rdkit, sella, vina, pdbfixer** (and, checked and found
unused, openbabel and biopython). Companion catalog:
`scans/md-chem-bio-atomistic-skills.json` (19 entries). Every claim anchors to a
committed `file:line` in `AtomisticSkills/.agents/skills/`.

Honest scoping is the whole task. Encode what carries map-relevant physics (the
MM-MD Trajectory and its thermodynamic observables, the barrier/BDE energies,
the MSD). Catalog-only, with a crisp reason, for informatics (SMILES,
fingerprints, descriptors, logP, conformers, docking scores) and bio-prep
(RMSD/RMSF/hbonds, protein preparation). Scan only: catalog, not map code.

## Sources and importability

None of openmm, MDAnalysis, rdkit, sella, vina, pdbfixer are importable in the
miniconda base env (`/Users/juicy/miniconda3/bin/python`). MDAnalysis 2.10.0 was
pip-downloaded as a wheel to `/tmp/mdsrc` and its `units.py` base-unit table read
directly. Every engine / quantity / unit claim below anchors to the vendored skill
scripts, not to a captured output file.

**openbabel and biopython are used by NO skill** (grep clean across
`.agents/skills/`). Structure I/O and prep are served by pdbfixer + openmm.app +
MDAnalysis, not biopython; there is no openbabel path. Cataloged as unused.

**Two engine classes, not one.** The chem-* MD (chem-solution-md, chem-neb-barrier,
chem-ts-optimization, chem-bond-dissociation) runs on **MLIPs through ASE**
(`get_potential_energy`/`get_forces`, eV/Angstrom): its physics rides the existing
MLIP `Potential` rail, the matcalc-scan domain. The drug-* MD
(drug-protein-ligand-md, drug-mmpbsa-gbsa) runs on **classical force fields through
OpenMM** (kJ/mol, kelvin, atm): a NEW engine class with a NEW checkpoint analog
(the force-field set), on a fourth energy zero distinct from the MLIP PES.

## Entry counts by status (19 entries)

| Status | Count | Entries |
|---|---|---|
| already-mapped | 5 | openmm-md-trajectory (`Trajectory`), openmm-temperature (`Temperature`), openmm-pressure-density (`Pressure`), chem-solution-md-msd (`MeanSquaredDisplacement`), sella-transition-state-geometry (`Structure`/`Forces`/molecular-Frequency label) |
| new-node-candidate | 4 | openmm-potential-energy (MM `TotalEnergy`, labeled), reaction-barrier-energy (the deferred NEB + sella + ORCA overlap), bond-dissociation-energy (BDE), mmgbsa-binding-free-energy (labeled endpoint) |
| representation-only | 3 | openmm-forcefield-provenance (the MM checkpoint analog), chem-solution-md-rdf-coordination (g(r) + CN), chem-solution-md-density |
| catalog-only-informatics | 4 | vina-docking-score, rdkit-conformers, rdkit-fingerprints-similarity, rdkit-descriptors-logp-admet |
| catalog-only-bio-prep | 3 | mdanalysis-rmsd-rmsf-com, mdanalysis-hbonds-contacts, pdbfixer-protein-preparation |

## Entry counts by package (drivers)

- **openmm (4 skills):** drug-protein-ligand-md (full MM-MD), drug-complex-system-builder
  (System + force field), drug-protein-prep (Modeller), drug-mmpbsa-gbsa (endpoint energies).
  Produces: `Trajectory` (already-mapped), `Temperature`, `Pressure`, MM `TotalEnergy`
  (candidate), FF provenance (rep-only), MM-GBSA dG (candidate).
- **mdanalysis (4+ skills):** drug-trajectory-analysis (RMSD/RMSF/COM/hbonds/contacts),
  drug-mmpbsa-gbsa, drug-pocket-detection, drug-binding-site-definition. Produces:
  bio-descriptors only (all catalog-only-bio-prep). NOTE: the RDF/MSD in chem-solution-md
  is home-rolled, NOT MDAnalysis.
- **rdkit (many skills):** conformers (ETKDG), fingerprints (Morgan/Tanimoto), descriptors
  (MW/cLogP/TPSA/QED), BDE fragmentation, SMILES->3D. All catalog-only-informatics EXCEPT
  where it merely feeds an MLIP relaxation (that relaxation is the MLIP's already-mapped
  contribution, not rdkit's).
- **sella (2 skills):** chem-ts-optimization, chem-irc-verification. Produces: TS `Structure`
  + `Forces` + saddle-order (already-mapped/labeled); FEEDS the barrier candidate.
- **vina (5 skills):** drug-docking-vina + 4 consumers. Produces: docking score
  (catalog-only, empirical fitted function).
- **pdbfixer (1 skill):** drug-protein-prep. Produces: prepared topology (catalog-only-bio-prep).
- **openbabel, biopython:** used by NO skill.

## The barrier-energy proposal (sella + ase.mep NEB + ORCA static-TS overlap)

This is the node the **matcalc verdict explicitly deferred to this task**
(`scans/matcalc-ase-atomistic-skills.md`: chem-neb-barrier drives raw `ase.mep`,
not matcalc `NEBCalc`). Three producer routes converge on ONE barrier-energy node:

1. **CI-NEB minimum-energy-path barrier** (the deferred one): `chem-neb-barrier`
   `calculate_barrier.py:117` `NEBTools(images).get_barrier()[0]` ->
   `results["barrier_eV"]` (`:143`). idpp interpolation, 7 images default,
   FIRE/BFGS, MLIP calculator. eV.
2. **Static saddle-point barrier from sella**: `chem-ts-optimization`
   `optimize_ts_sella.py:96-102` `Sella(atoms, order=1)` produces the TS
   *geometry* (validated by exactly 1 imaginary mode, `:142`); the barrier is a
   downstream reactant/product/TS MLIP-energy difference (same backend/model/head,
   `SKILL.md:93`). eV.
3. **Static saddle from ORCA molecular DFT**: the ORCA scan's
   `orca-transition-state-energy` entry (Hartree -> eV). **Do NOT duplicate**: that
   entry is the molecular-DFT producer of the SAME barrier family; this scan
   records the MLIP/ASE producers (NEB + sella) and the overlap.

**Recommendation: ONE `ReactionBarrier` node (ENERGY, eV), fed by all three
routes, kept apart by a construction label {neb_mep, static_ts_mlip,
static_ts_dft}.** It is DISTINCT from the map's existing `ActivationEnergy`, which
`registry.py:138` defines as the Arrhenius activation energy from the temperature
dependence of diffusivity (a slope, not a PES barrier) despite the tempting name
collision. Cross-engine numeric comparison is forbidden by the same energy-zero
split the ORCA scan flagged (MLIP eV vs ORCA all-electron Hartree->eV).

## The honest catalog-only reasons (crisply)

- **vina docking score:** the value of an EMPIRICAL scoring function (Vina/Vinardo/
  AD4 term weights regressed against experimental affinity), reported in kcal/mol
  units but NOT a computed free energy. Fitted-model output, like logP. AD4 even
  carries a `-intra` bookkeeping column (`run_docking.py:82-84`).
- **rdkit conformers:** ETKDG is a knowledge-based distance-geometry SAMPLER;
  MMFF/UFF are cheap empirical FFs to clean embeddings. In these skills the rdkit
  conformer is a STARTING geometry then relaxed by an MLIP; the map-worthy output
  is the MLIP-relaxed `Structure` + eV energy (the MLIP's contribution), not the
  rdkit conformer or its MMFF energy.
- **rdkit fingerprints / Tanimoto:** representation of molecular identity (which
  substructures are present) and a set-overlap similarity. Dimensionless, no
  physics. The clearest catalog-only case.
- **rdkit descriptors / logP / ADMET:** cLogP (Crippen) is an EMPIRICAL
  group-contribution regression, NOT a computed partition free energy; QED, TPSA,
  ADMET endpoints are likewise fitted/counting descriptors. The logP-is-empirical
  case the task named.
- **mdanalysis RMSD/RMSF/COM, hbonds/contacts:** bio-structural descriptors of a
  single macromolecule's conformational stability (Angstrom deviations,
  cutoff-defined occupancies). Well-defined geometrically, but semantically outside
  the materials-physics map, no operator path. (RMSD/RMSF are NOT MSD.)
- **pdbfixer protein prep:** structure-preparation tooling (missing atoms, pH
  protonation, nonstandard-residue swaps) that conditions MD input; no physical
  observable produced. biopython/openbabel would live here too but are unused.

## The molar-energy factor set (the day's trap)

This family adds a THIRD and FOURTH molar-energy convention to the ledger.
**OpenMM AND MDAnalysis both work in kJ/mol**; **Vina, MM-GBSA, and BDE report
kcal/mol**; the **MLIP/ASE routes stay in eV**. Exact factors (CODATA-2018
`e = 1.602176634e-19`, `N_A = 6.02214076e23`):

- `1 eV = 96.48533212331 kJ/mol = 23.060547830619 kcal/mol`
- `1 kcal/mol = 4.184 kJ/mol` (exact, thermochemical calorie)
- `1 kcal/mol = 0.0433641042 eV`; `1 kJ/mol = 0.0103642697 eV`;
  `1 kJ/mol = 0.2390057361 kcal/mol`
- cross-check to the ORCA/molecular ledger:
  `1 Hartree = 2625.499639479 kJ/mol = 627.5094740631 kcal/mol = 27.211386245988 eV`

kJ/mol and kcal/mol here are **per-mole-of-MOLECULES** (dimension ENERGY_PER_MOLE),
distinct from CALPHAD per-mole-of-atoms and phonon per-mole-of-cells. An OpenMM PE
in kJ/mol for a solvated box is **per-simulation-cell** (extensive); reading it as
a molar energy needs the same basis label the ORCA scan flagged.

**Truncation trap:** chem-bond-dissociation hardcodes `EV_TO_KCAL_MOL = 23.0605`
(`calculate_bde.py:58`, truncated from 23.060547830619). Sub-1e-4 relative error;
record the exact factors on the encode side.

## Unit / provenance traps

1. **OpenMM (nm, fs, kJ/mol) vs MDAnalysis (Angstrom, ps, kJ/mol):** the energy
   base matches but LENGTH and TIME bases differ across the handoff. RMSD/RMSF/MSD
   come out in Angstrom / Angstrom^2 with a ps time axis; the OpenMM trajectory was
   written in nm with fs timesteps.
2. **OpenMM energy zero:** the potential energy is a classical force-field number
   on a force-field-defined zero (kJ/mol, large negative for a solvated box). It
   must NOT be subtracted against MLIP or DFT totals. FOUR incompatible energy
   zeros now coexist: MM force-field, MLIP, DFT-pseudopotential, DFT-all-electron
   (ORCA).
3. **Vina "affinity" is not a free energy** despite the kcal/mol label. MM-GBSA dG
   IS force-field physics but is a single-trajectory endpoint estimate for RANKING,
   not an absolute affinity (`compute_mmgbsa.py:11`).
4. **Water model as provenance:** tip3p (default) vs tip3pfb/tip4pew/opc/spce
   (`build_complex.py:110-117`) changes every downstream number; a method knob, not
   a system property. Ligand FF (openff-2.2.0 vs gaff-2.11) + protein FF
   (amber/ff14SB) complete the MM checkpoint analog.
5. **MSD present, Diffusivity absent:** chem-solution-md computes MSD (Angstrom^2),
   RDF g(r), coordination number, and density, but does NOT fit a Diffusivity slope
   (no `D = MSD/6t` anywhere in `analyze_solution_md.py`). `MeanSquaredDisplacement`
   is grounded; `Diffusivity` is not produced by this skill despite being adjacent.
6. **RMSD/RMSF are NOT MSD:** deviation-from-reference (Angstrom) vs diffusive
   spread (Angstrom^2). Different physics, different dimension.
7. **sella emits geometry + frequencies, not a barrier:** the TS `Structure`,
   signed cm^-1 frequencies (imaginary negative), and saddle-order; the barrier is a
   downstream energy difference. The signed-cm^-1 convention matches the ORCA scan's
   molecular-Frequency mode-index proposal.
8. **Temperature has two definitions in run_md.py:** the hand-rolled
   `2*KE/(3N*R)` (`:42`, no dof correction) vs the StateDataReporter dof-corrected
   T (`:213`). Small-system bias.

## The MM checkpoint analog (openmmforcefields)

The `(protein_ff, ligand_ff, water_model, nonbondedMethod)` tuple
(`build_complex.py:97-117,133,186`, default `amber/ff14SB` + `openff-2.2.0` +
`tip3p` + PME) is to an OpenMM run exactly what a checkpoint is to an MLIP run and
a `(functional, basis_set, pseudopotential)` is to a DFT run: the method
provenance every derived Trajectory/energy/force rides on. `openmmforcefields`
(SystemGenerator, SMIRNOFF/GAFF) is the provenance registry. Encoded as a
representation-only gauge on the openmm nodes, NOT a node itself.

## Open questions

1. **ReactionBarrier node** fed by the deferred NEB + sella + ORCA static-TS
   routes, one node, three engine labels, kept apart from Arrhenius
   `ActivationEnergy`? (Recommended; cross-checked against the ORCA scan to avoid
   duplicating `orca-transition-state-energy`.)
2. **MM potential energy:** labeled `TotalEnergy` (basis=per_cell, engine=openmm,
   potential_class=classical_forcefield) or capability-only (the skills use it only
   as an equilibration diagnostic)?
3. **Force-field-set provenance** on every openmm node (the MM checkpoint analog).
4. **BondDissociationEnergy:** a molecular ENERGY node (labeled sibling of
   solid-state `ReactionEnergy`, cleavage_type, basis=per_molecule) fed by
   chem-bond-dissociation via MLIP energy differences? rdkit is catalog-only.
5. **BindingFreeEnergy (MM-GBSA):** ingest as labeled ranking-only candidate or
   defer the protein-ligand thermodynamics domain? It IS force-field physics
   (unlike Vina).
6. **Liquid-structure descriptors:** does the map ingest RDF g(r) (curve node like
   PhononDOS), coordination number, and Density? Currently rep-only diagnostics.
7. **Diffusivity from solution MD:** chem-solution-md grounds MSD but does not fit
   the Einstein slope. Where is `Diffusivity` produced, and does it re-enter the
   ionic-conductivity Nernst-Einstein route already in the graph?
8. **Molecular-Frequency mode index:** confirm the single molecular-Frequency
   variant (index kind `mode`, imaginary count as label) the ORCA scan proposed
   absorbs the sella frequencies too (no second molecular-frequency node).
9. **Catalog-only confirmation:** rdkit (conformers/fingerprints/descriptors/logP),
   Vina score, ligand efficiency, RMSD/RMSF/hbonds/contacts, pdbfixer prep all
   catalog-only with stated reasons; openbabel + biopython unused. Confirm none
   enter provenance.
10. **Snapshot drift:** scanned HEAD `2c9e1ac`, 77 nodes, empty edges. Re-read
    `graph.json` at encode time.

## Source anchors

- **openmm:** `drug-protein-ligand-md/scripts/run_md.py:24-49,177,202,213-220,234,277,298-319,343`;
  `drug-complex-system-builder/scripts/build_complex.py:49-63,97-117,133,186`;
  `drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py:8,123,314-350,444`.
- **mdanalysis:** `drug-trajectory-analysis/scripts/analyze_trajectory.py:31-32,79-97,101-131,163-176,192-247,250-295`;
  `/tmp/mdsrc` MDAnalysis-2.10.0 `units.py` `MDANALYSIS_BASE_UNITS`.
- **rdkit:** `chem-conformer-search/scripts/conformer_search.py:76,81,154`;
  `chem-solution-md/scripts/build_solvation_box.py:49-61`;
  `chem-bond-dissociation/scripts/calculate_bde.py:69,233,276`;
  `drug-docking-analysis/scripts/analyze_docking.py:50-70`.
- **sella:** `chem-ts-optimization/scripts/optimize_ts_sella.py:76,96-102,111,128-142`;
  `chem-irc-verification/scripts/verify_irc_sella.py`; `chem-ts-optimization/SKILL.md:15,93`.
- **neb barrier:** `chem-neb-barrier/scripts/calculate_barrier.py:10,103-117,143`.
- **bde:** `chem-bond-dissociation/scripts/calculate_bde.py:8,58,220,486-490`.
- **vina:** `drug-docking-vina/scripts/run_docking.py:39,82-84,143,153,161,212-216`.
- **pdbfixer:** `drug-protein-prep/scripts/prepare_protein.py:31,166,215,242,269`.
- **solution_md:** `chem-solution-md/scripts/analyze_solution_md.py:33,127-176,177-213,215-284`;
  `chem-solution-md/SKILL.md:11,121,132-133,137,140-142,174`.
- **map side:** `omai/operator/registry.py:98,133,134,137,138`;
  `docs/data/graph.json` (HEAD `2c9e1ac`, 77 nodes, empty edges).
- **border scans:** `scans/matcalc-ase-atomistic-skills.md` (NEB barrier deferred
  to this task); `scans/orca-atomistic-skills.json` (`orca-transition-state-energy`,
  molecular-Frequency mode-index proposal).
