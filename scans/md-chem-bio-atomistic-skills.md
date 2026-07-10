# The MD/chem/bio family as used by AtomisticSkills

Scan of the classical-MD, molecular-informatics, and structural-biology tooling
the AtomisticSkills (arXiv 2605.24002) drug-* and chem-* skills drive:
**openmm, mdanalysis, rdkit, sella, vina, pdbfixer** (plus openbabel as a
documented CLI conversion step in two skills, and biopython, checked and found
entirely unused). Companion catalog:
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

**biopython is used by NO skill** (grep clean across `.agents/skills/`: zero
`import Bio`, zero CLI). Structure I/O and prep are served by pdbfixer +
openmm.app + MDAnalysis, not biopython. **openbabel is NOT imported in any
Python, but the `obabel` CLI IS invoked as a documented format-conversion step**
in two skills: `drug-pose-validation/SKILL.md:26,105` (a REQUIRED
PDBQT->SDF conversion before `validate_poses.py`) and
`drug-binding-site-definition/SKILL.md:188` (an OPTIONAL "if needed"
troubleshooting suggestion). So openbabel has a real, if peripheral, workflow
path (a CLI utility, not a linked library); it produces no map quantity
(catalog-only tooling), but the earlier "no openbabel path / used by no skill"
claim was wrong and is corrected here. biopython alone is truly unused.

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
- **openbabel (2 skills, CLI only):** `obabel` PDBQT->SDF conversion in
  drug-pose-validation (required step) and drug-binding-site-definition (optional).
  A format-conversion utility, no map quantity. NOT a Python import anywhere.
- **biopython:** used by NO skill (zero import, zero CLI).

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

**Truncation trap:** chem-bond-dissociation hardcodes BOTH molar factors
truncated: `EV_TO_KJ_MOL = 96.485` (`calculate_bde.py:57`, from 96.48533212331)
AND `EV_TO_KCAL_MOL = 23.0605` (`:58`, from 23.060547830619). Sub-1e-4 relative
error on each; record the exact factors on the encode side.

## Unit / provenance traps

1. **OpenMM (nm, fs, kJ/mol) vs MDAnalysis (Angstrom, ps, kJ/mol):** the energy
   base matches but LENGTH and TIME bases differ across the handoff. RMSD/RMSF/MSD
   come out in Angstrom / Angstrom^2 with a ps time axis; the OpenMM trajectory was
   written in nm with fs timesteps.
2. **OpenMM energy zero:** the potential energy is a classical force-field number
   on a force-field-defined zero (kJ/mol, large negative for a solvated box). It
   must NOT be subtracted against MLIP or DFT totals. FOUR incompatible energy
   ZEROS now coexist: (a) MM force-field zero (OpenMM), (b) MLIP per-element
   `atom_refs` zero (fairchem, the MLIP scan's line 165-167 caveat), (c)
   DFT-pseudopotential zero (QE/VASP), (d) DFT-all-electron/ECP zero (ORCA). This
   is CONSISTENT WITH, and a superset of, the ORCA scan's zero enumeration (ORCA
   all-electron/ECP zero is NOT the QE/VASP pseudopotential zero, "never subtract
   ORCA vs periodic totals", orca scan lines 111-112,185-186). NOTE this is a
   separate axis from the ORCA scan's "four BASES" (per-molecule / per-cell /
   per-mole-of-atoms / per-mole-of-cells): that is an extensivity/counting axis,
   NOT an energy-zero axis. The two catalogs do not contradict: bases and zeros
   are orthogonal labels, both required.
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
10. **Snapshot drift (scanner misread corrected):** the scanner logged
    "77 nodes, empty edges." The "empty edges" was a MISREAD: `graph.json` has
    NO `edges` key at all; its edges live under the `links` key. At review
    (HEAD `2c787b7`) `graph.json` carries **82 nodes and 198 links**, 12 tiers;
    `map/log.jsonl` is at **163 records**. The QHA encode may land records
    164-174 while this runs (do not race). Re-read `graph.json` at encode time.
    The family's candidate nodes (ReactionBarrier, BondDissociationEnergy,
    BindingFreeEnergy, Density, RadialDistributionFunction, CoordinationNumber)
    are still ABSENT at 82 nodes; ActivationEnergy, MeanSquaredDisplacement,
    Diffusivity, ReactionEnergy, Trajectory, Temperature, Pressure, TotalEnergy,
    Forces, Structure, Frequency are all PRESENT.

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
- **sella:** `chem-ts-optimization/scripts/optimize_ts_sella.py:75 (import Sella),
  94-102 (Sella ctor kwargs, order:1 at :98), 102 (Sella(atoms,**kwargs)),
  111 (optimizer.run), 135-142 (imag_modes + is_first_order_saddle==1 at :142)`;
  `chem-irc-verification/scripts/verify_irc_sella.py`; `chem-ts-optimization/SKILL.md:15,93`.
- **neb barrier:** `chem-neb-barrier/scripts/calculate_barrier.py:10 (from ase.mep
  import NEBTools,NEB), 126-127 (NEBTools(images).get_barrier()[0]), 144
  (results['barrier_eV'])`.
- **bde:** `chem-bond-dissociation/scripts/calculate_bde.py:8,58,220,486-490`.
- **vina:** `drug-docking-vina/scripts/run_docking.py:39,82-84,143,153,161,212-216`.
- **pdbfixer:** `drug-protein-prep/scripts/prepare_protein.py:31,166,215,242,269`.
- **solution_md:** `chem-solution-md/scripts/analyze_solution_md.py:33,127-176,177-213,215-284`;
  `chem-solution-md/SKILL.md:11,121,132-133,137,140-142,174`.
- **map side:** `omai/operator/registry.py:98,133,134,137,138` (verified:
  :98 adsorption_energy, :133 mean_squared_displacement, :134 diffusivity =
  Einstein relation, :137 reaction_energy = balanced solid-state, :138
  activation_energy = Arrhenius slope of diffusivity);
  `docs/data/graph.json` (HEAD `2c787b7`, 82 nodes, 198 links under the `links`
  key; there is no `edges` key: the scanner's "empty edges" was a misread).
- **border scans:** `scans/matcalc-ase-atomistic-skills.md` (NEB barrier deferred
  to this task); `scans/orca-atomistic-skills.json` (`orca-transition-state-energy`,
  molecular-Frequency mode-index proposal); `scans/orca-atomistic-skills.md`
  (energy-zero language, cross-checked consistent, lines 111-118,185-186);
  `scans/mlip-family-atomistic-skills.md:165-167` (MLIP `atom_refs` energy zero).
- **openbabel/biopython (negative-claim evidence):** `obabel` CLI at
  `drug-pose-validation/SKILL.md:26,105` and `drug-binding-site-definition/SKILL.md:188`
  (openbabel HAS a CLI path, correction); biopython: zero `import Bio`, zero CLI
  anywhere under `.agents/skills/` (truly unused).

## Review verdicts (2026-07-10)

Adversarial deep-review, default-distrust. All source anchors re-opened at review
HEAD `2c787b7`. The MDAnalysis 2.10.0 wheel base-unit table was re-read from
`/tmp/mdsrc/mda_extract/MDAnalysis/units.py`; the molar-energy factor set was
recomputed from CODATA-2018 (`e=1.602176634e-19`, `N_A=6.02214076e23`, thermochemical
`kcal=4184 J`) and the Hartree cross-check from `scipy.constants`. `graph.json`
re-read (82 nodes / 198 links / 12 tiers); `map/log.jsonl` at 163 records.

**Negative-claim outcomes (the load-bearing ones).**

- **biopython: CONFIRMED unused.** Zero `import Bio`, zero `from Bio`, zero CLI
  across all 126 skills. Structure I/O is pdbfixer + openmm.app + MDAnalysis.
- **openbabel: the claim was WRONG, CORRECTED.** No Python import anywhere, but the
  `obabel` CLI IS a documented workflow step in two skills
  (`drug-pose-validation/SKILL.md:26,105` required PDBQT->SDF;
  `drug-binding-site-definition/SKILL.md:188` optional). The catalog's "no
  openbabel path / used by no skill" was false; openbabel is now recorded as a
  catalog-only CLI format-conversion utility (no map quantity).

**Barrier-family verification (all VERIFIED, minor anchor drift fixed).**

- **chem-neb-barrier** drives `ase.mep NEBTools(images).get_barrier()[0]` at
  `calculate_barrier.py:126-127` (scanner said :117; corrected), stored as
  `results["barrier_eV"]` at `:144` (scanner said :143; corrected). CI-NEB, idpp
  interpolation, MLIP calculator, eV. THE matcalc-deferred route. VERIFIED.
- **chem-ts-optimization** drives `Sella(atoms, order=1)` (`optimize_ts_sella.py:102`,
  `order:1` in the kwargs dict at :98) and validates the saddle by
  `is_first_order_saddle = n_imag_below_cutoff == 1` at `:142` (EXACTLY as claimed).
  Frequencies are signed cm^-1 (imaginary negative, :55-57). VERIFIED.
- **sella emits NO barrier scalar: CONFIRMED.** The script outputs geometry,
  signed frequencies, saddle order (`:160-162`) only. `SKILL.md:93` ("use the same
  backend/model/head across reactant/product/TS optimization") confirms the barrier
  is a DOWNSTREAM reactant/product/TS MLIP-energy difference, not a sella output.
- **Distinctness vs Arrhenius `ActivationEnergy`: CONFIRMED.** `registry.py:138`
  reads verbatim "Arrhenius activation energy from the temperature dependence of
  diffusivity" (a diffusivity slope, NOT a PES barrier). The `ReactionBarrier`
  candidate is genuinely distinct from `ActivationEnergy`; the name collision is a
  trap, correctly flagged.

**Factor confirmations (all EXACT to catalog precision).**

- `1 eV = 96.48533212331 kJ/mol` and `= 23.060547830619 kcal/mol`: recomputed
  96.48533212331002 and 23.06054783061903. EXACT.
- `1 kcal/mol = 4.184 kJ/mol` (thermochemical): EXACT.
- Reciprocals 0.0433641042, 0.0103642697, 0.2390057361: match (10-sig-fig rounds).
- Hartree cross-check (scipy): `2625.499639479 kJ/mol` matches;
  `627.5094740631 kcal/mol` and `27.211386245988 eV` agree to CODATA last-digit
  rounding. All CONFIRMED.
- **MDAnalysis base units (from the wheel): CONFIRMED** length Å, time ps, energy
  kJ/mol, force kJ/(mol·Å), speed Å/ps. The OpenMM(nm,fs) / MDAnalysis(Å,ps)
  length+time base mismatch on a shared kJ/mol energy base is real.
- **OpenMM internal units (from `run_md.py` source): CONFIRMED** kJ/mol (:44,190),
  kelvin (:43,148), nanometer positions (:95-97), femtosecond timestep (:147),
  atmosphere pressure (:234). Two temperature definitions confirmed: hand-rolled
  `2*KE/(3N*R)` (:39-43, no dof correction) vs StateDataReporter dof-corrected
  (:217,252,308).
- **BDE truncation trap: SHARPENED.** BOTH factors are truncated in-script:
  `EV_TO_KJ_MOL=96.485` (:57) and `EV_TO_KCAL_MOL=23.0605` (:58). The .md
  previously named only the kcal one; corrected to match the JSON.

**Four-energy-zeros trap: stated precisely and CONSISTENT with ORCA.** The four
ZEROS (MM force-field, MLIP `atom_refs`, DFT-pseudopotential, DFT-all-electron/ORCA)
are an energy-reference axis, orthogonal to the ORCA scan's four BASES
(per-molecule / per-cell / per-mole-atoms / per-mole-cells, an extensivity axis).
The MD catalog's zeros are a superset that incorporates the ORCA scan's
all-electron-vs-pseudopotential split (orca .md 111-112,185-186) and the MLIP
scan's `atom_refs` zero (mlip .md 165-167). No contradiction. Sharpened in trap 2.

**Positive-usage anchors (all VERIFIED at file:line).** vina
(`run_docking.py:39 from vina import Vina, :143 v.energies(), :153
affinity_kcal_mol, :83 AD4 neg_intra`), rdkit (`ETKDGv3 :76, EmbedMultipleConfs
:81, MLIP get_potential_energy :154`; build_solvation_box MMFFOptimizeMolecule
:61; analyze_docking Crippen cLogP :67 + TPSA :70), mdanalysis (`import MDAnalysis
:31-32, rms.RMSD :79, align.AverageStructure :163`), pdbfixer (`from pdbfixer
import PDBFixer :31, openmm.app.Modeller :32, handle_missing_residues :166`),
mmgbsa (`dG=E_complex-E_receptor-E_ligand :8, "relative ranking rather than
absolute" :11, GBn2 :133`), build_complex (`amber/ff14SB :97, openff-2.2.0 :96,
tip3p default :98, water map :111-115, PME :186`). All CONFIRMED. Minor line-anchor
drift throughout (source files edited since scan HEAD `2c9e1ac`); facts intact.

**Per-entry verdicts (19 entries).**

- `openmm-md-trajectory` (already-mapped): VERIFIED. openmm is a fourth
  Trajectory engine; thermostatted/barostatted frames; nm->Å handoff real.
- `openmm-temperature` (already-mapped): VERIFIED. Two T definitions confirmed.
- `openmm-potential-energy` (new-node-candidate): VERIFIED. kJ/mol per-cell on the
  MM force-field zero; equilibration diagnostic; label forbids cross-substrate
  subtraction.
- `openmm-pressure-density` (already-mapped): VERIFIED. Barostat setpoint (atm) to
  Pressure; density g/cm^3 a diagnostic.
- `openmm-forcefield-provenance` (representation-only): VERIFIED. The
  (protein_ff, ligand_ff, water_model, nonbondedMethod) tuple is the MM checkpoint
  analog; water map and PME confirmed at source.
- `mdanalysis-rmsd-rmsf-com` (catalog-only-bio-prep): VERIFIED. Å deviation-from-
  reference, not MSD; no operator path.
- `mdanalysis-hbonds-contacts` (catalog-only-bio-prep): VERIFIED. Cutoff-defined
  occupancies, dimensionless.
- `chem-solution-md-msd` (already-mapped): VERIFIED. Grounds
  MeanSquaredDisplacement; NO Diffusivity fit in-script (confirmed absent).
- `chem-solution-md-rdf-coordination` (representation-only): VERIFIED. Home-rolled
  g(r) + coordination number; curve + derived scalar, no map node today.
- `chem-solution-md-density` (representation-only): VERIFIED. Equilibration
  diagnostic; Density = mass/CellVolume.
- `sella-transition-state-geometry` (already-mapped): VERIFIED. TS Structure +
  Forces + saddle-order label; no barrier scalar (see barrier-family above).
- `reaction-barrier-energy` (new-node-candidate): VERIFIED. One ReactionBarrier
  node fed by NEB + sella + ORCA, kept apart from Arrhenius ActivationEnergy by a
  construction label. Distinctness and NEB anchors confirmed.
- `bond-dissociation-energy` (new-node-candidate): VERIFIED. MLIP energy difference
  (`bde_eV=e_frag1+e_frag2-intact_energy :486`); rdkit only fragments; sibling of
  ReactionEnergy on per_molecule basis (registry.py:137 confirms ReactionEnergy is
  solid-state). Both molar factors truncated.
- `mmgbsa-binding-free-energy` (new-node-candidate): VERIFIED. Force-field physics
  (GBn2 implicit solvent), but skill states ranking-only (:11); kcal/mol; label
  must forbid absolute-affinity reading.
- `vina-docking-score` (catalog-only-informatics): VERIFIED. Empirical fitted
  scoring function, kcal/mol nominal not a free energy; AD4 neg_intra confirmed.
- `rdkit-conformers` (catalog-only-informatics): VERIFIED. ETKDG sampler + MMFF;
  the map-worthy output is the downstream MLIP relaxation, not rdkit.
- `rdkit-fingerprints-similarity` (catalog-only-informatics): VERIFIED.
  Dimensionless identity representation; clearest catalog-only case.
- `rdkit-descriptors-logp-admet` (catalog-only-informatics): VERIFIED. cLogP is a
  Crippen group-contribution regression, not a computed partition free energy.
- `pdbfixer-protein-preparation` (catalog-only-bio-prep): VERIFIED. Input
  conditioning, no observable. (openbabel would sit alongside as CLI prep;
  biopython genuinely absent.)

Count: **19/19 entries VERIFIED**; statuses unchanged (5 already-mapped, 4
new-node-candidate, 4 catalog-only-informatics, 3 catalog-only-bio-prep, 3
representation-only). One negative claim corrected (openbabel), one snapshot
misread corrected (77->82 nodes, edges live under `links`), one truncation note
sharpened, one four-zeros statement sharpened. No status changed; no physics claim
overturned.

**Orchestrator decisions.**

1. **ReactionBarrier: MINT one node, three engine routes.** ENERGY, eV.
   Construction label `{neb_mep, static_ts_mlip, static_ts_dft}`. Topology: fed by
   `chem-neb-barrier` (NEB, the matcalc-deferred route), `chem-ts-optimization`
   (sella static-TS, downstream energy difference), and `orca-transition-state-energy`
   (the ORCA scan's molecular-DFT node, an OVERLAP not a duplicate). DISTINCT from
   `ActivationEnergy` (registry.py:138 Arrhenius diffusivity-slope). Cross-engine
   numeric comparison FORBIDDEN by the energy-zero split (eV MLIP vs Hartree->eV
   all-electron). RECOMMENDED.
2. **MM `TotalEnergy` labeling: label, do not mint a parallel node.**
   `TotalEnergy(basis=per_cell, engine=openmm, potential_class=classical_forcefield)`,
   mirroring the ORCA-scan per-molecule/per-cell basis-label recommendation. The
   label's load-bearing job is to forbid MM-vs-MLIP-vs-DFT subtraction (four zeros).
   Capability-level for now (skills use PE only as an equilibration diagnostic).
3. **BDE: MINT `BondDissociationEnergy`**, a labeled sibling of `ReactionEnergy`
   (`cleavage_type in {homolytic, heterolytic}`, basis=per_molecule). Do NOT overload
   solid-state `ReactionEnergy` (registry.py:137 = balanced solid-state from per-atom
   formation energies; different basis). rdkit is catalog-only (fragmentation only);
   the physics is the MLIP energy difference. Record EXACT factors (script truncates).
4. **MM-GBSA: MINT `BindingFreeEnergy` as a labeled ranking-only candidate**
   (`method=mmgbsa|mmpbsa, endpoint, single_trajectory, implicit_solvent=GBn2`) OR
   defer the protein-ligand thermodynamics domain. It IS force-field physics (unlike
   Vina), but the skill itself targets relative ranking (:11). Label must forbid
   absolute-affinity reading. ORCHESTRATOR CHOICE (mint-labeled recommended).
5. **Liquid-structure descriptors: representation-only for now.** g(r) (curve node
   like PhononDOS), coordination number (derived scalar), Density (=mass/CellVolume)
   are real physics but currently only equilibration diagnostics with no operator.
   Candidate curve/scalar nodes if the map ingests liquid-structure descriptors.
6. **Diffusivity-from-solution-MSD gap: NOTED, not closed here.**
   `chem-solution-md` grounds `MeanSquaredDisplacement` but fits NO Einstein slope
   (no `D=MSD/6t`/polyfit in `analyze_solution_md.py`). The map's `Diffusivity`
   (registry.py:134, Einstein relation) is produced elsewhere (agent step or
   downstream skill), and if fit here would re-enter the ionic-conductivity
   Nernst-Einstein route already in the graph (registry.py:135). Encode-side
   decision.
7. **Molecular-Frequency mode index:** the single molecular-Frequency variant the
   ORCA scan proposed (index kind `mode`, imaginary count as label) absorbs the
   sella signed-cm^-1 frequencies too; do NOT mint a second molecular-frequency
   node. CONFIRMED consistent with the sella output.
8. **openbabel/biopython provenance:** neither enters map provenance. openbabel is
   a CLI format-conversion utility (catalog-only); biopython is unused. Confirmed.
