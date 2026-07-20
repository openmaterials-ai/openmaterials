# omds: distances between simulations

The lineage record is the encoder. `omds.distance(a, b)` resolves the
`lineage@1` default (a versioned weighted sum over the node, material,
conditions, params, and execution channels, each bounded to [0, 1]);
`omds.divergence(a, b)` returns the per-channel breakdown sorted largest
first, answering where two computations part ways. The node channel is BFS
on the published map graph; the material channel delegates to `omdc`.
Records normalize from lineage records, instance rows, or flat dicts.
Design: `docs/distance/2026-07-20-simulation-distance-design.md`.
