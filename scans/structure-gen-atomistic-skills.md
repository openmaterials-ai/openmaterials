# Structure generation (pyxtal, smact, mattergen, diffcsp) as used by AtomisticSkills: scan report

A **fresh survey** of the structure-generation family AtomisticSkills (arXiv
2605.24002) exercises, cataloging how generative / random / screening operators
enter a map whose `Structure` node is today a pure SOURCE with **no producing
edge**. Companion catalog: `scans/structure-gen-atomistic-skills.json` (8
entries). This is a SCAN, not map code.

**Graph snapshot at my end:** `docs/data/graph.json` = **77 nodes**, git HEAD
`7c6ff1d`. The config-thermo encode the brief warned about (records 148-153) had
NOT landed; node count is 77 (was 74 at the phonopy-lammps review). Not racing
that encode.

> **Review correction (2026-07-10):** the scan text above originally said "0
> edges in graph.json". That is wrong: the edges live under the key `links` (D3
> convention), not `edges`. `docs/data/graph.json` at HEAD `7c6ff1d` carries
> **179 links**. The load-bearing conclusion survives and is *better* supported:
> `Structure` is the `target` of **0** of those 179 links and the `source` of
> **15** (`Structure -> {TotalEnergy, Forces, Stress, ForceConstants[order=2],
> MagneticMoment, BandGap, ElasticConstants, BulkModulus, FormationEnergy,
> EnergyAboveHull, SurfaceEnergy, Voltage, AdsorptionEnergy,
> ElectricalConductivity[carrier=ionic], ConfigurationalEnergy}`). Structure is a
> pure source: consumed by 15 operators, produced by none.

**`Structure` is a pure source, confirmed.** The quantity tag `structure`
(`omai/operator/registry.py:86`) reads "Atomic structure: cell, species, and
positions (opaque in Phase 1)." No edge produces `Structure`; every operator on
the map (relax, solve_ground_state, phonon, MD) CONSUMES it. **A generative
producer would be the first edge ever pointing INTO Structure** - the exact
topology inversion the brief flags.

## The family is not four producers: it is three output types

| code | what it actually is | outputs | driven by a skill? |
|---|---|---|---|
| **mattergen** | diffusion generator (conditioned/unconditional) | Structures (CIF) | YES |
| **diffcsp** (DiffCSP++) | diffusion CSP, space-group + Wyckoff constrained | Structures (CIF) | YES |
| **pyxtal** | **symmetry lookup helper** (Wyckoff operator tables) | nothing on the map | only as an internal table inside diffcsp |
| **smact** | **composition-validity FILTER**, dimension-free | boolean per composition | **NO - env dependency only, zero call sites** |

Two **corrections to the brief's framing** sit at the center of this scan:

1. **pyxtal does NOT generate structures here.** Its `from_random`
   (symmetry-constrained random structures) capability is **unused**. pyxtal
   appears only as `from pyxtal.symmetry import Group` inside
   `diffcsp_wrapper.py:591` to fetch Wyckoff affine matrices. The AIRSS-style
   "random symmetric structures" the brief attributes to pyxtal actually come
   from **pymatgen** (`mat-random-structure-search`, using
   `Structure.from_spacegroup` / `SpaceGroup.from_int_number`,
   `generate_random_structures.py:26-27,179`).

2. **smact is never called by a skill.** It is an installed dependency of
   `diffcsp-agent`, `adit-agent`, and `mattergen-agent`
   (`core_env.yaml:21`, `example_full_env.yaml:188` SMACT==3.2.0), but a grep for
   `smact` across `.agents/skills/` returns **zero functional call sites**. The
   charge-balance screening that DOES run (`mat-ionic-substitution`) uses
   **pymatgen** `AutoOxiStateDecorationTransformation`, not smact.

## What each code actually outputs

- **mattergen**: novel inorganic crystal Structures sampled from a diffusion
  model, `p_theta(S)` (unconditional) or `p_theta(S | c)` where `c` is a
  chemical system or a scalar property (`dft_mag_density`). CIF out.
  `mattergen_wrapper.py:130-145`, `mattergen_server.py:35-100`. **CSP mode (exact
  composition) needs non-public checkpoints**; public models are Gen/conditioned
  only.
- **diffcsp (DiffCSP++)**: predicted Structures with **exact composition control**
  from space group + Wyckoff letters + atom types
  (`generate_structures_with_symmetry`, `diffcsp_server.py:54-107`), or
  unconditional Gen (`unconditional_generate.py`). CIF out.
- **pyxtal**: `Group(SG)[letter].ops` -> Wyckoff affine matrices. Produces
  **nothing** on the map; pure symmetry bookkeeping inside diffcsp.
- **smact**: `valid(composition) in {True, False}` - charge-neutral +
  electronegativity-ordered verdicts. A **dimension-free FILTER**, not a
  structure producer, not a physical quantity.

## The generative-operator proposal (the headline)

**The question.** `Structure` is a pure source with no producing edge. A
`generate_structure` edge producing `Structure` would invert that topology. Does
the map want generative producers as **edges into Structure**, or as
**representation-only provenance on Structure instances**?

**Recommendation: representation-only provenance, NOT a producing edge (Phase 1).**
A generated structure is EVIDENCE of a `Structure` whose SOURCE is the generator;
the generator identity is provenance metadata on the instance, parallel to how
mp-api structures enter as sourced instances.

**The facts gathered (all anchored):**

1. **Generated structures are INPUT artifacts, never evaluated outputs.** In every
   skill and the halide workflow the generated CIF is immediately **relaxed** by
   an MLIP, then `E_hull`-screened (`mat-stability`), then DFT-refined, then MD'd
   (`generative-halide-discovery.md:20-25`; `mat-random-structure-search`
   SKILL.md step 2). The generator's raw output is never itself a physics result:
   it is the seed of a downstream evaluation chain.
2. **The physics content is UNVERIFIED at birth.** Every generative SKILL warns
   the output has "varying levels of stability" and MUST be validated by
   relaxation + stability (`mattergen SKILL.md:154`, `adit SKILL.md:103`,
   `random-search SKILL.md:81-85`). A map node carries defined-identity physics; a
   raw generated structure carries only a proposal.
3. **Structure is OPAQUE in Phase 1** (`registry.py:86`). A `generate_structure`
   operator would produce an opaque token - encoding provenance, not physics.
4. **Conditioning is a training/steering target, not a consumed field.** In
   `p(S|c)`, `c` (chemical_system, dft_mag_density, guidance_scale) STEERS the
   diffusion; it is not an evaluated input field the way `Structure` feeds
   `solve_ground_state`. An edge FROM a property node would falsely claim the
   property is computed-then-consumed.
5. **The precedent inverts.** `solve_ground_state` / `relax` CONSUME `Structure`
   and PRODUCE definite-identity quantities. A generator has no physics input to
   consume (unconditional) or only a steering label (conditioned): categorically
   different from relax.

**The provenance model.** Attach a generation-provenance record to the
`Structure` instance: `{generator_code, checkpoint/model_name, conditioning
(chemical_system | property | spacegroup+wyckoff | none), sampler_scheme
(guidance_scale | step_lr | cfg_scale), seed}`. Parallel to a database (mp-id)
provenance and a relaxation provenance. `Structure` stays a source node; the
generator is a source ANNOTATION.

**If Phase 2 wants an edge:** the honest edge is `generator -> Structure` with the
generator an operator whose "input" is a stochastic seed + optional conditioning
LABEL and whose scheme carries (checkpoint, guidance, seed). It would still NOT be
an edge from a property NODE. This inverts the current source topology and should
be a deliberate kernel decision, not an ingest side effect.

## New-node candidates: NONE as physics nodes

Every generative-side quantity is a dimensionless score or a categorical label:
representation-only.

- **Space group / Wyckoff**: categorical annotation (int in [1,230] + Wyckoff
  letters). An INPUT constraint to diffcsp, an EMERGENT property after relaxation
  elsewhere. A symmetry label on a Structure instance, not a node.
- **smact validity**: dimension-free boolean over compositions. A filter verdict,
  not a physics quantity. Representation-only if ever surfaced.
- **Novelty metric** (`mat-structure-novelty`): matched/novel vs MP+ICSD via
  `StructureMatcher` (ltol=0.2, stol=0.3, angle_tol=5.0,
  `mat-structure-novelty/SKILL.md:64`). A dimensionless categorical verdict from a
  downstream FILTER. A novelty flag on a Structure instance, not a node.
- **Stability gates**: `energy_above_hull` / `formation_energy` already exist
  (`registry.py:95-96`); the pipeline CONSUMES them - no new node.

## Traps

0. **(brief) pyxtal does not generate here** - Wyckoff-table helper only; AIRSS
   random search is pymatgen.
1. **(brief) smact is env-only** - zero skill call sites; charge balance that runs
   is pymatgen.
2. **Fractional vs cartesian**: `generate_random_structures.py` uses
   `coords_are_cartesian=False` (random fractional); all generators emit CIF
   (fractional). Do not assume cartesian.
3. **P1 vs symmetric cell**: AIRSS random structures are P1 (symmetry only after
   relaxation, `SKILL.md:82`); diffcsp INJECTS symmetry via Wyckoff ops. Two
   generators disagree on whether the pre-relaxation cell carries symmetry. Do not
   assume a standardized setting.
4. **smact charge-balance rules**: requires BOTH charge neutrality AND
   electronegativity ordering per oxidation states; a composition can be
   charge-balanced yet smact-invalid, or vice versa. Distinct from the pymatgen
   neutrality-only check in `mat-ionic-substitution`.
5. **chemical_system != stoichiometry** (mattergen): controls ELEMENTS, may omit
   an element; mandatory post-filter of CIFs by exact elements (`SKILL.md:131-145`).
6. **CSP vs Gen models**: diffcsp CSP models require `atom_types`; Gen models do
   not. Public mattergen is Gen/conditioned only - true CSP needs non-public
   checkpoints (`SKILL.md:141-146`).
7. **Sampler knobs are not physics**: `guidance_scale`, `step_lr`, `cfg_scale`
   belong in the generation scheme/provenance, never as physical fields.
8. **None of the four import locally**; mattergen/diffcsp are git-only (repos at
   `/home/bdeng/...`). All map-relevant facts are anchored to committed
   AtomisticSkills usage.

## Entry counts by status per code

- **mattergen (2):** producer-of-Structure 2 (unconditional + conditioned).
- **diffcsp (2):** producer-of-Structure 2 (symmetry-constrained CSP + Gen).
- **pyxtal (1):** not-a-producer, internal Wyckoff-table helper.
- **smact (1):** not-driven, dimension-free composition-validity filter.
- **family extras (2):** adit (sibling diffusion producer, crystals+molecules),
  AIRSS random search (pymatgen, not pyxtal).
- **grand total: 8 entries.**

## Open questions

1. **Provenance vs edge**: source annotation on Structure instances (recommended)
   or a first-class `generator -> Structure` edge that inverts the source
   topology? A kernel decision.
2. **Provenance schema**: `{generator_code, checkpoint, conditioning,
   sampler_scheme, seed}`? Parallel to mp-id and relaxation provenance.
3. **Space group as annotation vs node**: keep it a categorical representation
   label (recommended). One symmetry-annotation slot on Structure that both
   diffcsp-input and post-relaxation-emergent can write?
4. **Novelty flag placement**: a representation flag on a Structure instance
   (recommended), or a Structure-to-Structure MATCHES comparator relation (akin to
   an EXPECTED_AGREE)?
5. **smact**: ingest at all? Recommend NOT - dimension-free, not skill-driven; if
   ever wanted, a label on a Composition (itself not yet a map node).
6. **Molecule branch** (adit molecules): out of Phase-1 crystalline scope; future
   non-periodic Structure sibling only.
7. **Cross-generator diversity**: workflows deliberately run mattergen + diffcsp +
   adit for DIVERSITY. Unlike MLIP EXPECTED_AGREE, generators are meant to
   DISAGREE. An EXPECTED-DISAGREE / diversity relation worth modeling? Likely
   representation-only, but noted.

**Nothing blocked the scan.** The four packages do not import locally and
mattergen/diffcsp are git-only, but all functional usage lives in vendored
AtomisticSkills skills, wrappers, servers, and env docs, every claim anchored to a
real `file:line`. pyxtal/smact were not pip-downloaded because they are env-only
here (pyxtal: one Wyckoff-table call; smact: zero call sites).

## Review verdicts (2026-07-10)

Adversarial deep review of commit `671b092`'s catalog (8 entries), independent of
the scanner. Both brief-corrections re-verified by exhaustive grep across all
**126** skills. `smact-4.0.0` wheel re-opened from `/tmp/gensrc`. Map side read
from `omai/operator/registry.py`, `docs/data/graph.json` (re-read at HEAD
`7c6ff1d`, **77 nodes / 179 links**), and a committed instance
(`docs/data/instances/li2s-mp-1153-formationenergy-atomisticskills-mat-db-mp.json`).
**Em-dash grep over both files: zero.**

**Verdict: 8/8 entries VERIFIED.** No status changed. One factual correction
(graph `edges` -> `links`, above). Every file:line anchor spot-checked accurate.

### The two load-bearing brief-corrections both hold

- **pyxtal is env-only, one Wyckoff-table call. VERIFIED exactly.**
  `grep -rn pyxtal AtomisticSkills/` over all 126 skills returns ONE functional
  call: `from pyxtal.symmetry import Group` at `diffcsp_wrapper.py:591`. Every
  other hit is a doc/env mention (`mcp-environments.md:21`,
  `ml-generative-diffcsp/SKILL.md:106`, `batch_generate.py:29`,
  `unconditional_generate.py:15`, two READMEs). The adversarial
  `grep from_random|from_seed|pyxtal(` returns **nothing** (exit 1); `grep pyxtal.`
  returns only the `591` import. **No `from_random` anywhere.** pyxtal produces
  nothing on the map.
- **smact has zero skill call sites. VERIFIED exactly.**
  `grep -rn smact|SMACT AtomisticSkills/` returns SIX hits, all env docs
  (`adit-agent/README.md:37`, `diffcsp-agent/README.md:28`,
  `diffcsp-agent/core_env.yaml:21`, `mattergen-agent/INSTALL_BLACKWELL.md:136,249`,
  `mattergen-agent/example_full_env.yaml:188` SMACT==3.2.0). No `.py` hit in any
  skill or `src/`. The charge screening that DOES run is pymatgen's
  `AutoOxiStateDecorationTransformation` (`propose_substitutions.py:25,60`,
  `SKILL.md:98`), not smact.

### smact source check (TRAP 4)

`pip download smact-4.0.0` into `/tmp/gensrc`. `screening.py` confirms the trap:
`smact_validity` (`:577`) requires charge neutrality **AND** (default
`use_pauling_test=True`) the Pauling electronegativity-ordering test;
`smact_filter` (`:379`) "applies the charge neutrality and electronegativity
tests"; `pauling_test` (`:167`) enforces "positive ions should be of lower
electronegativity". A composition can be charge-balanced yet smact-invalid on EN
order. (AtomisticSkills pins `3.2.0`; the two-gate validity logic is stable across
`3.x`/`4.0`.) TRAP 4 accurate.

### The provenance-record shape (open question 2), against the implemented schema

A committed map instance is `{variable, material, conditions{}, value, units,
uncertainty, source{kind, ref, detail}}`. The mp-id precedent lives in TWO places
at once: `material = "Li2S (mp-1153)"` (formula + parenthesized source id) **and**
`source = {kind:"simulation", ref:"atomisticskills-mat-db-mp", detail:"...retrieved
by the AtomisticSkills mat-db-mp query_mp skill..."}`.

So a generated-structure provenance record, under the committed conventions, would
look like: `material = "Li2ZrCl6 (mattergen:chemical_system)"` (generator tag
paralleling `(mp-123)`) and `source = {kind:"simulation",
ref:"atomisticskills-ml-generative-mattergen", detail:"MatterGen chemical_system
model, guidance_scale=1.0, chemical_system=Li-Zr-Cl, seed=..., CIF then relaxed
by ..."}`. The scan's proposed 5-key dict `{generator_code, checkpoint,
conditioning, sampler_scheme, seed}` all lands inside `source.ref` (generator_code
-> the skill ref) and `source.detail` (the rest, as prose), exactly as mat-db-mp
folds its retrieval provenance into `source.detail` today.

**No contradiction with the implemented schema.** "Representation-only provenance,
no producing edge" is fully expressible: the committed database-sourced instances
already carry `source` + a material-string tag and introduce **no** inbound edge.
A generator is just `source.kind="simulation"` with a generator ref/detail,
parallel to mat-db-mp. **One refinement:** the scan presents the provenance as a
flat 5-key dict, but the implemented schema has no dedicated structured provenance
sub-object; those keys would live as prose in `source.detail` plus the material
tag. Making them machine-readable is a schema EXTENSION (`source.generation`
sub-object), not a fix to this scan. **Caveat:** Structure is a symbolic source
node with no Structure-valued instances committed yet (all 32 instances are scalar
quantities on mp-sourced materials), so this shape is inferred from the closest
committed analog, not yet exercised for a Structure-valued instance.

### Orchestrator decisions

1. **ACCEPT both brief-corrections** as findings; the brief's framing of pyxtal as
   a random-structure generator and smact as an active screener is wrong for
   AtomisticSkills.
2. **ADOPT representation-only provenance** for generative producers in Phase 1:
   keep `Structure` a pure source, no inbound `generate_structure` edge. Matches
   how mp-sourced structures already enter.
3. **DECIDE provenance granularity:** prose-in-`source.detail` (zero schema change,
   matches today's instances) vs a structured `source.generation` sub-object
   (machine-readable, small extension). Recommend prose-first now. Not blocking.
4. **DO NOT ingest smact** as a node (dimension-free, not skill-driven).
5. **DO NOT create** space-group/Wyckoff or novelty as physics nodes: categorical/
   dimensionless representation-only labels. `energy_above_hull` /
   `formation_energy` already exist (`registry.py:95-96`) as the real gates.
6. **IF Phase 2 makes generators first-class edges,** treat it as a deliberate
   kernel decision (it inverts the source topology); the honest edge is
   `generator -> Structure` with conditioning as a LABEL, never from a property
   node.
7. **adit molecule branch and cross-generator diversity relations** stay out of
   Phase-1 crystalline scope; noted, not actioned.
