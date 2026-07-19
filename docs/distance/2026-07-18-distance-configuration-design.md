# distance-configuration: design

Date: 2026-07-18
Status: draft for review
Scope: the configuration/material distance repo for the openmaterials-ai org.
A companion spec for distance-simulation (lineage as encoder) will follow; this
document defines the contract that repo depends on.

## Context

OpenMaterials already answers "same or different" for atomic configurations:
`canonical_uid` (sha256 of the spglib-standardized primitive cell) plus a
StructureMatcher dedup gate (`omai/configurations.py`). It has no notion of
"how far". This repo supplies the continuous complement: graded distances
between configurations, designed to become the traversal layer for large
archives of simulations (nearest-neighbor retrieval, graded dedup and
trajectory keyframing, novelty scoring against the archive before paying for a
run on MaterialsCodeGraph, archive maps, motif search).

Hard requirements from the product owner:

1. Compare crystals, amorphous cells (the 17k-atom a-Si class), and cells with
   impurities/defects, across chemistries.
2. Ship multiple named distances and default to one.

## Non-goals

- No identity. Identity stays `canonical_uid` and the lineage id in the main
  repo. Everything this repo produces (embeddings, distances, indexes) is
  derived, rebuildable, and never identity-bearing.
- No charged-defect awareness (encoders see geometry and species, not charge
  state). Documented limitation.
- No web UI. This is a library plus batch tools; visualization stays with the
  existing site and MCG.

## Core representation: a structure is a distribution of local environments

Every configuration is encoded as a weighted set of per-atom local-environment
vectors, plus a pooled per-structure vector derived from it:

- Perfect crystal: symmetry-unique environments with multiplicities (diamond
  Si is one environment). Tiny sets, near-free comparison.
- Amorphous cell: farthest-point-sampled subset (default 256 environments)
  with weights normalized to probability masses. Two realizations of the same
  quench protocol are near zero distance; a 4k-atom and a 17k-atom cell of the
  same glass compare as equals.
- Defective crystal: host environments at large weight plus outlier
  environments at small weight. The defect is explicit in the representation.

The pooled vector (mean plus max concatenation, float32, fixed dimension) is
the cheap index key for approximate-nearest-neighbor search; the environment
set is the faithful object that distances rank with.

## The distance registry

A registry of named, versioned distances. Each entry declares machine-readable
metadata: invariances satisfied (rotation, translation, permutation,
supercell, perturbation continuity), whether it is a true metric or a
similarity, cost class, dependency extra, and whether it is ANN-indexable.
The traversal layer reads this metadata to pick prefilter and re-rank stages
automatically.

v1 distances:

| id        | what it is                                                        | deps        | role |
|-----------|-------------------------------------------------------------------|-------------|------|
| `env-ot`  | Optimal transport (Sinkhorn, exact EMD for small sets) between weighted environment sets; environments encoded by the pinned universal MLIP | `[mace]`    | DEFAULT; the trustworthy answer for crystal, amorphous, and defect regimes |
| `latent`  | Cosine over pooled per-structure vectors                          | `[mace]`    | ANN index key; candidate retrieval |
| `comp`    | Element Mover's Distance over modified Pettifor scale             | none        | chemistry-only channel; true metric; deterministic forever |
| `amd`     | Average Minimum Distance vector (Chebyshev), PDD plus EMD for the sharp form | `[amd]`     | geometry-only channel; species-blind; deterministic forever; handles 17k-atom cells in milliseconds |
| `exact`   | pymatgen StructureMatcher RMSD                                    | none        | re-rank of top-k only; never primary |

Channels stay separate: polymorph queries (same chemistry, different geometry)
and isostructural queries (same geometry, different chemistry) are different
axes. No blended composite in v1; the traversal layer composes per query.

### Default semantics (the alias doctrine)

`default` is an alias, currently `env-ot@1`, resolved at call time. Stored or
published results always record the concrete id and version, never the alias.
Bumping the default is a deliberate, versioned act that breaks nothing stored.
Resolving the default without its extra installed raises an error that names
the install command and the always-available deterministic channels; it never
silently falls back to a different distance.

```python
from omdc import distance, embed, DISTANCES

d = distance(s1, s2)                 # resolves default -> env-ot@1
d = distance(s1, s2, metric="amd")   # named channel
DISTANCES                            # the registry, with metadata
```

Inputs are pymatgen Structure or ASE Atoms (adapter), periodic or molecular.

## Encoders

`Encoder.embed(structure) -> EnvironmentSet` where the result carries per-atom
vectors, weights, the pooled vector, and full provenance:
`(encoder_id, version, weights_sha256, hyperparams_hash)`. Embedding records
are cached and content-addressed by `(canonical_uid, encoder_pin)`; a model
upgrade means a batch re-embed job, never a migration and never an identity
change.

- Default encoder: MACE-MP-0 (MIT license, ASE-native), per-atom invariant
  features from the final interaction layer.
- Pluggable alternates: MatterSim (MIT; likely better off-equilibrium and for
  glasses), Orb (Apache-2.0). MACE-OFF is excluded as a default anywhere
  (academic-use license).
- Acceptance benchmark before pinning `env-ot@1`: MACE-MP-0 vs MatterSim on
  the a-Si corpus (realization invariance, size invariance, crystal/amorphous
  separation, defect detectability). The winner becomes the pin.
- The core package has zero torch dependency; learned encoders are extras
  (`pip install omdc[mace]`). `comp` and `amd` always work.

## Motif index (impurity and defect search)

Material-level distance between pristine and dilutely doped cells is small and
that is physically correct. "Find every simulation containing a P dopant in
Si" is a different query. Environments whose distance to their host's dominant
modes exceeds a threshold (a versioned hyperparameter of the motif index, not
a magic number) are indexed per-atom in a separate motif index,
making defect search sublinear and concentration-independent. When a lineage
links a defective cell to a pristine reference, the defect fingerprint comes
from direct comparison; otherwise outlier detection against the cell's own
modes applies.

## Storage and indexes

- Embeddings: parquet, one row per `(canonical_uid, encoder_pin)`, float32.
  Roughly 1 KB pooled plus up to ~256 KB env-set per structure; derived cache,
  rebuildable, lives outside the map (bucket or MCG artifacts, pointer-only),
  consistent with the OpenMaterials light-format doctrine.
- ANN: HNSW (usearch or FAISS) over pooled vectors; index files are disposable
  build products.
- Retrieval pattern: ANN on `latent` for candidates, `env-ot` to rank,
  `exact` only when byte-level confidence is requested.

## Contract with distance-simulation (repo 2)

Repo 2 encodes the lineage record (map node, template, conditions, params,
hyperparameters) and decomposes distance field-wise: graph distance on the
typed map DAG for nodes, dimension-aware numeric distance for conditions,
categorical for template/code. Its `material` leaf delegates to this repo
through one function: `distance(struct_a, struct_b, metric=...)`. Therefore
this repo must stay import-light (no torch in core) and semver-stable on that
call signature and on registry ids.

## Testing gates

Property-based invariance gates, in the spirit of the map's six gates:

1. Rotation, translation, permutation: distance exactly 0 (within float
   tolerance) for every registered distance claiming the invariance.
2. Supercell: pooled vector identical; env-ot 0.
3. Continuity: a 0.01 A rattle moves every continuous distance by a small
   bounded amount.
4. Amorphous: same-protocol different-realization near zero; same glass at
   4k vs 17k atoms near zero.
5. Defect: single vacancy in a large cell is small but nonzero at material
   level and detected by the motif channel; the same defect at a different
   site is near identical.
6. Ordering sanity: d(Si-diamond, Si-strained) < d(Si-diamond, Si-beta-tin)
   < d(Si-diamond, a-Si) on the `env-ot` and `amd` channels; `comp` is 0
   across all Si polymorphs and nonzero for Si:P.
7. Metric axioms (symmetry, triangle inequality) property-tested for every
   entry claiming "true metric".
8. Golden vectors per pinned encoder version as regression tests.

## Repo layout and packaging

- Repo: `openmaterials-ai/distance-configuration`. Package: `omdc` (sibling
  style to `omai`). Python 3.11+, pyproject, MIT.
- Modules: `omdc/registry.py` (distances, alias resolution),
  `omdc/encoders/` (mace and mattersim adapters), `omdc/envset.py`
  (weighted sets, FPS, symmetry collapse), `omdc/metrics/` (ot, cosine, elmd,
  amd, exact), `omdc/store.py` (parquet cache), `omdc/index.py` (ANN, motif),
  `tests/` (gates above).
- Repo 2, `openmaterials-ai/distance-simulation` (package `omds`), follows in
  its own spec and depends on `omdc`.

## Roadmap (explicitly not v1)

- Contrastive calibration head on top of the latent space trained on known
  equivalences (polymorph pairs, MD neighbors, supercells).
- Medium-range-order channel for glasses: smoothed RDF or structure-factor
  distance as a deterministic registry entry.
- REMatch-SOAP as a within-chemistry re-rank distance under a `[soap]` extra.
- Environment-level search UX ("find this motif anywhere") beyond the motif
  index primitive.

## Decisions adopted (flag objections at review)

1. Default distance: `env-ot@1`; default encoder pinned after the MACE-MP-0
   vs MatterSim benchmark on a-Si.
2. Repo names `distance-configuration` and `distance-simulation`; packages
   `omdc` and `omds`.
3. Per-structure pooled vectors and env-sets in v1; motif index in v1 (raised
   from roadmap by the impurity requirement); contrastive calibration in v2.

## Deviations adopted at implementation (2026-07-18)

1. License Apache-2.0, not MIT: org convention (openmaterials LICENSE and
   NOTICE mirrored).
2. `comp` uses the Pettifor scale as shipped by pymatgen (`mendeleev_no`)
   instead of a vendored modified-Pettifor table: same intent, one less stale
   dependency.
3. `env-ot` for sampled sets uses the square root of the energy distance, not
   entropic Sinkhorn: gate 4 exposed the finite-sample floor of empirical
   Wasserstein between independent realizations of the same disordered
   material (0.36 vs a 0.89 reference), and the Sinkhorn divergence does not
   remove it (the self-transport term is zero on identical support). Exact
   EMD remains the estimator for symmetry-exact sets; EnvironmentSet carries
   a `sampled` flag to choose.
4. Gate 6 uses fcc-Si as the distinct polymorph (deterministic construction);
   the strained < polymorph and strained < glass inequalities are asserted,
   and the full chain waits for the real a-Si corpus.
5. REMatch-SOAP moved to roadmap; `exact` is StructureMatcher only.
6. Motif rule: outlier = weight below 0.05 AND cosine distance above 1e-4 to
   the nearest host mode; hist encoder species scalars weighted 20x so a
   substitutional P in Si is visible (3.4e-4) against bulk noise (1e-6).
