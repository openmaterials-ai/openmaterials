# index: the source registry

The index is the source registry that lives beside the map. Entries are
organized by source; each pins that source's coverage to a specific element
hash at a specific map version.

- `codes/`: one file per code representation, present now. Each
  `codes/<rep>.json` is `{representation, map_version, covers}`, where `covers`
  lists the nodes the code maps, each carrying the node uid, the code's API
  name, and its declared unit, sorted by node, and `map_version` is the frozen
  genesis hash from `map/GENESIS`.
- `papers/` and `experiments/` arrive with their first entries later.

Files here are generated, never hand-edited: run `python -m omai.index_data`.
