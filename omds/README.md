# omds: distances between simulations

The lineage record is the encoder. omdc answers how far apart two
configurations are; omds answers how far apart two computations are, and
`divergence(a, b)` answers where they part ways (the per-channel breakdown
sorted largest first: not a distance, the localization tool).

Distance decomposes over the typed lineage fields, each channel bounded to
[0, 1] and deterministic:

- **node**: BFS shortest path on the published map graph
  (`docs/data/graph.json`, read-only), capped at 6 hops and normalized;
  ids sharing a base name differ by at most the 0.15 qualifier penalty;
  off-map ids compare as strings. The map is the encoder for "what
  quantity": two quantities are near when few operators separate them.
- **material**: delegated to omdc's comp channel (Element Mover's
  Distance), squashed by the versioned scale 25. The material-name parser
  is the same strict rule as the site mirror: a capitalized word must
  tokenize fully into element symbols, so a-Si parses to Si and SWCNT
  refuses (the pymatgen isotope aliases D and T are excluded, otherwise
  SWCNT would parse as S+W+C+N+T). Unparseable names compare as strings.
- **conditions** and **params**: bounded relative difference over the
  union of keys; a key present on one side only counts 1. params merges
  params, hyperparameters, and setup values, mirroring the identity hash.
- **execution**: categorical over code and template; deliberately lowest
  weight, since execution sits outside the identity hash.

`lineage@1`, the default, is the weighted sum (node 0.35, material 0.30,
conditions 0.15, params 0.10, execution 0.10; versioned, sums to 1). Every
channel is also registered individually (`lineage-node@1` and so on) with
`input="lineage"` in the shared omdc `DistanceSpec` shape, and the alias
doctrine is omdc's: `default` resolves at call time, stored results record
concrete ids. Records normalize from lineage records, instance rows
(variable, material, conditions), or flat dicts; nothing is inferred.

Scoping, stated here because it is the contract: metric knowledge lives in
this layer, READING the map, never writing it. Promoting per-node metric
ids into the map schema is a governance change that waits for its own
review. Composing omds with omdc (config-close and lineage-far queries,
artifact-backed divergence localization along the DAG) is follow-up work.
