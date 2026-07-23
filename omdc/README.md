# omdc: the distance layer

Graded distances between atomic configurations. The OpenMaterials hash
answers "same or different"; `omdc` answers "how far".

[OpenMaterials](https://github.com/openmaterials-ai/openmaterials-ai) gives every
configuration a content-addressed identity (`canonical_uid`) and every
computation a lineage. This library adds the continuous complement: named,
versioned distance metrics over configurations, built to traverse large
archives of simulations: nearest-neighbor retrieval, graded deduplication and
trajectory keyframing, novelty scoring before paying for a run, archive maps,
and defect search.

## Install

```bash
pip install -e ".[distance]"        # comp, exact, env-ot and latent on the hist encoder
pip install -e ".[distance,mace]"   # the default traversal encoder (MACE-MP-0)
pip install -e ".[distance,amd]"    # the amd geometry channel
```

## Quickstart

```python
from pymatgen.core import Lattice, Structure
import omdc

diamond = Structure.from_spacegroup("Fd-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
other = diamond.copy()
other.apply_strain(0.01)

omdc.distance(diamond, other)                  # default: resolves to env-ot@1
omdc.distance(diamond, other, metric="comp")   # a named channel
omdc.embed(diamond)                            # the pinned environment set
omdc.DISTANCES                                 # the registry, with metadata
```

`examples/quickstart.py` prints every channel across a small zoo of Si cells
(hist encoder, so it runs without extras):

```
             env-ot    latent    comp    amd     exact
strained 1%  0.1019    0.0052    0.0     0.0803  0.0000
fcc          0.7993    0.3194    0.0     1.1774  inf
glass        0.7663    0.1292    0.0     0.7259  inf
vacancy      0.0052    0.0001    0.0     0.2502  inf
```

## The registry

Multiple distances, one default. Every distance has a stable versioned id and
machine-readable metadata (invariances, metric axioms, cost class,
ANN-indexability), so a traversal layer can pick prefilter and re-rank stages
automatically.

| id       | what it is                                                    | needs        | role |
|----------|---------------------------------------------------------------|--------------|------|
| `env-ot` | transport distance between weighted local-environment sets    | `[mace]`*    | default; the trustworthy answer for crystals, glasses, and defects |
| `latent` | cosine over pooled environment vectors                        | `[mace]`*    | the ANN index key; candidate retrieval |
| `comp`   | Element Mover's Distance on the Pettifor scale                | nothing      | chemistry only; a true metric; deterministic forever |
| `amd`    | Average Minimum Distance (Chebyshev)                          | `[amd]`      | geometry only, species-blind; deterministic forever |
| `exact`  | pymatgen StructureMatcher RMSD (inf when cells do not match)  | nothing      | re-rank of top-k only |
| `latent-lb` | euclidean between weighted-mean environment vectors        | `[mace]`*    | certified lower bound of `env-ot` on symmetry-exact sets; powers `funnel_search` |
| `spectrum` | Wasserstein-1 between 1D mass distributions                 | nothing      | DOS and spectra, mass-normalized; input is `(x, y)` |
| `curve`  | symmetric relative L2 between property curves                 | nothing      | function-valued curves like kappa(T); input is `(x, y)` |
| `traj-ot` | sqrt energy distance between trajectories                    | `[mace]`*    | trajectory identity, dedup, and `keyframes()` thinning; input is a frame sequence |

*these run on the dependency-free `hist` reference encoder too:
`omdc.distance(a, b, metric="env-ot", encoder="hist")`.

`omdc.funnel_search(query, entries, k)` returns exact env-ot nearest neighbors
while pruning with the certified `latent-lb` bound (no false dismissals on
symmetry-exact sets); the `lower_bounds` field in the registry is what makes
that funnel assemblable mechanically.

### The alias doctrine

`default` is an alias, resolved at call time (today: `env-ot@1`). Anything
stored or published records the concrete id and version, never the alias, so
bumping the default later breaks nothing. If the default's dependency is
missing the call raises `MissingExtraError` naming the fix; it never silently
falls back to a weaker distance.

## How a structure is represented

A structure is a weighted set of per-atom local-environment vectors:

- a perfect crystal collapses to its symmetry-unique environments with
  multiplicity weights (diamond Si is one environment),
- a disordered or large cell is subsampled by deterministic farthest-point
  sampling (256 environments) with nearest-assignment weights,
- a defective crystal is host environments at large weight plus outlier
  environments at small weight: the defect is explicit, not washed out.

`env-ot` compares these sets with exact EMD when both are symmetry-exact and
with the square root of the energy distance when either is sampled, so two
independent realizations of the same glass read as the same material instead
of inheriting the finite-sample floor of empirical Wasserstein. Environments
come from pluggable encoders carrying full provenance pins
(encoder id, version, weights sha256, hyperparameters hash); embeddings are
derived data, cached by (structure key, encoder pin), rebuildable, and never
identity-bearing.

For impurity and defect search, `omdc.index.MotifIndex` indexes outlier
environments (dilute and different from the host modes) per atom, so
"find every P dopant in Si" stays sublinear and concentration-independent.
`omdc.index.PooledIndex` serves nearest-neighbor retrieval over pooled
vectors; `omdc.store` persists embeddings to parquet.

## Phonon distance

`phonon-ot@1` compares two mode populations: each mode is a point in
(frequency, velocity magnitude, bandwidth) space, heat-capacity weighted
when available, z-scored jointly, compared by the sampled-regime estimator
(sqrt energy distance). It sees "same kappa, different mechanism":
boundary-limited and anharmonicity-limited transport differ loudly here
while agreeing in the scalar. `ModeSet.from_kaldo(folder)` reads a kaldo
output folder directly; `ModeSet.from_arrays` takes any code's arrays.
Harmonic-only runs (no bandwidth) compare on the shared axes for both
sides.

## Scale profiles

Distance is also a function of scale: `omdc.scale_profile(a, b)` returns
env-ot at a ladder of interaction radii (2.5, 5, 10 A by default), so the
answer becomes "far at which scale". A strained crystal is near locally and
far at long range; two realizations of one glass stay near at every rung;
missing medium-range order appears at 10 A and not before.
`omdc.layer_profile` gives the same ladder from MACE receptive fields
(mace extra), and `omdc.metrics.amdmetric.amd_profile` exposes the AMD
vector's k index as nested lower bounds of the full amd distance (amd
extra). Every rung mints its own encoder hyperparameter hash, so embeddings
at different scales never mix in the cache.

## The encoder benchmark

`PYTHONPATH=. python -m omdc.benchmark --encoders hist,mace` scores
encoders on a deterministic corpus with identical structures and
estimators per encoder; only the environment vectors differ. Lower is
better on the four criteria; separation is the same-glass vs
glass-crystal margin, higher is better. Gate: realization < 0.5,
size < 0.5, defect and polymorph in (0, 1). Measured 2026-07-20 (rep=3):

| encoder | realization | size | defect | polymorph | separation | pass |
|---|---|---|---|---|---|---|
| `hist@1` | 0.099 | 0.080 | 0.0068 | 0.127 | 10.1 | yes |
| `mace-mp-0-small@1` | 0.076 | 0.112 | 0.0097 | 0.041 | 13.2 | yes |

MACE separates the regimes more sharply (separation 13.2 vs 10.1,
polymorph 0.041 vs 0.127); hist is marginally better on size invariance.
Both pass, so `mace-mp-0-small@1` remains the pinned default traversal
encoder, now with measured backing. Open before the pin is final: rerun
on the real a-Si corpus, and a MatterSim adapter (it joins by encoder
name; unknown names fail loudly rather than skipping).

## Limitations

- Charge states of defects are invisible to every encoder here.
- Molecules need a vacuum box (inputs are periodic pymatgen Structures or ASE
  Atoms).
- `hist` is a reference and CI encoder: chemistry-aware only through atomic
  number. The traversal-quality space is the MACE encoder; MatterSim lands
  behind the same pin mechanism after the encoder benchmark on the a-Si
  corpus.

## Relation to the rest of OpenMaterials

Identity and lineage live in
[openmaterials](https://github.com/openmaterials-ai/openmaterials-ai); heavy
artifacts live on [MaterialsCodeGraph](https://materialscodegraph.com/) by
pointer. The upcoming simulation-distance layer (`omds`) encodes lineage records
and delegates its material leaf to this package.

Apache-2.0.

Part of the OpenMaterials-AI initiative.
