# Conformance targets

A **conformance target** is a pinned expectation: one committed lineage plus the
number a code is expected to reproduce for it, within a stated tolerance. It is
the check side of the map. A target does not invent its lineage; it POINTS at an
existing value on the map by carrying that value's lineage verbatim, so the two
share one identity and no target can claim a computation that was never asked.

To append one, add a JSON file (one target per file) and open a pull request:

```json
{
  "id": "<sha256 of the lineage object, identical to the evidence instance's id>",
  "lineage": { ...copied byte-for-byte from the evidence instance... },
  "code": "materialscodegraph",
  "expected": {"value": 1.2452, "units": "W/(m K)"},
  "tolerance": {"value": 0.001, "kind": "absolute"},
  "evidence": "<the evidence instance's filename>.json",
  "note": "<optional: how the tolerance was chosen, or any pin provenance>"
}
```

- The identity rule is cryptographic, not asserted: a target's `lineage` block
  EQUALS its evidence instance's lineage byte-for-byte, so
  `lineage_id(target.lineage) == instance.id` and the two ids coincide. You do
  not retype the lineage; you copy `rec["lineage"]` and `rec["id"]` from the
  committed instance. This is a not-invented proof: a target can only cite a
  computation the map already holds, because a changed condition would mint a
  different id and break the match.
- `expected` is the value the code should reproduce, and it must equal the
  instance's `lineage.values` (same value, same units): the target expects the
  map's own recorded number.
- `tolerance` is `{value, kind}`; `kind` is `absolute` or `relative`, and the
  value is stated in `expected`'s units (an absolute thermal-conductivity
  tolerance is in W/(m K), a reaction-energy tolerance in eV). Where the source
  eval pins a tolerance in another unit, convert it and record the conversion in
  `note`.
- `code` is the engine's key in `../codes.json`, and the target's node (the
  `lineage.node`) must be a node that `code` covers there: `codes[code]` maps
  the node. A target whose code does not represent the node is a bug, not a gap.
- Conditions vs hyperparameters is identity-bearing, exactly as on an instance:
  the temperature, pressure, and phase that define WHICH computation was asked
  live in `lineage.conditions` (inside the hash), never as loose setup dials.
- The `evidence` filename is a convenience pointer to the committed instance
  under `../instances/`; it stays outside the hash and never changes identity.
  A target derived from the literature rather than a committed instance carries
  no `evidence` file: instead its lineage names a `doi:` (or other `scheme:ref`)
  source in-hash, and the check accepts that branch (the source is the citation,
  the instance is optional).

The easiest way to write one correctly is in Python: load the evidence instance,
copy its `lineage` and `id` verbatim, then add `code`, `expected` (mirroring
`lineage.values`), and `tolerance`. Never retype the lineage.

## Your data stays yours

Appending a target grants the map the same non-exclusive CC BY 4.0 license the
instances carry, and nothing else. The target references an evidence instance and
a code; it ingests no raw artifacts. The full statement is GOVERNANCE.md,
"Data ownership and fairness".
