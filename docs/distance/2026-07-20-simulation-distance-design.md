# omds: simulation distance, the lineage record as the encoder

Date: 2026-07-20. Companion to the configuration-distance and multiscale
designs in this directory.

## Contract

omdc answers how far apart two configurations are; omds answers how far
apart two computations are. The encoder is the typed lineage record itself
(omai/lineages.py): identity there is the hash of the lineage, so distance
here decomposes over exactly the fields that mint identity, plus execution.

Channels, each bounded to [0, 1], each deterministic:

- node: BFS shortest path on the published map graph (docs/data/graph.json,
  read-only), capped at 6 hops and normalized; ids sharing a base name
  differ by at most the qualifier penalty (0.15); off-map ids compare as
  strings. The map is the encoder for "what quantity": two quantities are
  near when few operators separate them.
- material: delegated to omdc's comp channel (Element Mover's Distance),
  squashed by the versioned scale 25; the material-name parser is the same
  strict rule as the site mirror (a-Si parses to Si, SWCNT refuses; the
  pymatgen isotope aliases D and T are excluded so refusal actually
  happens). Unparseable names compare as plain strings.
- conditions and params: bounded relative difference over the union of
  keys; a key present on one side only counts 1. params merges params,
  hyperparameters, and setup values, mirroring the identity hash.
- execution: categorical over code and template (outside the identity hash,
  deliberately lowest weight).

lineage@1, the default, is the weighted sum (node 0.35, material 0.30,
conditions 0.15, params 0.10, execution 0.10; versioned, sums to 1). Every
channel is registered individually (lineage-node@1 and so on) with
input="lineage" in the shared omdc DistanceSpec shape. divergence(a, b)
returns the per-channel breakdown sorted largest first: not a distance but
the localization tool, "where do two simulations part ways". Records
normalize from the lineage shape, from instance rows (variable, material,
conditions), or from flat dicts; nothing is inferred.

## Scoping decisions

- The metrized-map idea (each map node declaring its own metric id in the
  map schema) is implemented conservatively: metric knowledge lives HERE,
  reading the map, never writing it. Promoting metric ids into the map
  schema itself is a governance change and waits for its own review.
- The 2x2 queries this unlocks with omdc: config-close and lineage-far
  (same material, different workflow), lineage-close and config-far (same
  workflow, different material).
- Cross-code divergence localization at result level (comparing the mode
  populations or curves two codes produced, node by node along the DAG)
  composes omds with omdc's spectrum, curve, and phonon channels; the
  wiring of artifact-backed comparisons is follow-up work with the MCG
  plumbing.
