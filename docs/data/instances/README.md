# Instances

Every value on the map is a **lineage instance**: the one construct the whole
project shares. An evidence record here is the same shape as a shareable
lineage record, just minimal: whatever we have of the claim. Nothing is seeded
with invented numbers; the store stays empty until real simulation or measured
values are appended.

To append one, add a JSON file (one record per file) and open a pull request:

```json
{
  "id": "<sha256 of the canonical lineage object>",
  "kind": "simulation",
  "lineage": {
    "node": "ThermalConductivity[transport_model=wigner]",
    "material": "Si",
    "conditions": {"T": 300},
    "values": {"value": 0.0, "units": "W/(m K)"},
    "source": "paper:<slug>"
  },
  "source": {"kind": "simulation", "ref": "paper:<slug>", "detail": "<verbatim quote, page anchor>"}
}
```

- `lineage.node` must be an exact id from `../graph.json`; identity is the
  hash of the `lineage` object alone (`omai.lineages.lineage_id`), and the
  stated `id` must recompute to it.
- `kind` is `simulation` (numerical) or `measurement` (lab).
- `lineage.source` is the namespaced identity-bearing origin, a `scheme:ref`
  string (`paper:`, `doi:`, `zotero:`, `arxiv:` ...). Include it whenever the
  ref has a scheme; a bare code ref (for example `kaldo`) stays only in the
  verbatim `source` block, which always rides OUTSIDE the hash and carries the
  quoted provenance. `uncertainty`, when known, goes inside `values`.
- The node uid pin is injected at build time against the live map, so a value
  follows its node through supersede chains without stranding its identity.

The easiest way to write one correctly is `omai.map_data.record_instance`,
which the paper parser also uses. The build projects every `*.json` here into
the flat `../instances.json` view the site reads (byte-stable across the
lineage refactor):

```bash
CUDA_VISIBLE_DEVICES="" PYTHONPATH=. python -m omai.map_data
```

## Your data stays yours

Appending an instance grants the map a non-exclusive CC BY 4.0 license to
redistribute the record with attribution, and nothing else: no copyright
assignment, no CLA, no claim on the simulation or experiment behind it. The
raw artifacts (trajectories, force sets, lab records) are never ingested;
the record carries a provenance reference and the artifacts stay wherever,
and however, you publish them. Anyone reusing map data must credit the map
version and, through its provenance, your source. The full statement is
GOVERNANCE.md, "Data ownership and fairness".
