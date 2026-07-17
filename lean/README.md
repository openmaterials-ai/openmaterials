# Lean export (physlib)

`lean/` is a standalone lake package (`openmaterials`, library `OpenMaterials`)
holding the map's generated proof layer. It depends on
[physlib](https://github.com/leanprover-community/physlib) (the successor of
PhysLean), pinned by rev in `lakefile.toml`, on toolchain
`leanprover/lean4:v4.31.0` (`lean-toolchain`). Mathlib comes in transitively
through physlib and is fetched from the mathlib build cache.

Generated modules (do not edit by hand; regenerate with
`python -m omai.map_data`, or the individual exporters):

- `OpenMaterials.lean` (Tier 1, `omai.physlean_export`): each node is a physlib
  `Dimension`; each theorem states that an edge's output dimension equals the
  product of its input dimensions, proved by extensionality plus `simp` with
  physlib's `*_mul` lemmas.
- `OpenMaterialsDimensions.lean` (Tier 1 companion, `omai.physlean_export`):
  the map's full seven-base dimension vector (`Dimension7`: M, L, T, Th, N, I,
  J) with its own ext lemma and Mul instance, covering exactly the nodes the
  physlib bridge omits, Mathlib only.
- `OpenMaterialsIdentities.lean` (Tier 2, `omai.lean_identities`): the
  executable identities as real-valued composition theorems, Mathlib only
  (`ring` / `field_simp`).
- `OpenMaterialsUnits.lean` (`omai.lean_units`): the units bridge, anchoring
  the map's SI-canonical convention against physlib's `UnitChoices.dimScale`.

**Verified.** The package builds against physlib with zero errors and zero
sorries. `tests/test_physlean_export.py` re-checks every Tier 1 identity in
Python so a regression fails fast even without a Lean toolchain.

To build:

```
cd lean
lake exe cache get   # fetch the mathlib build cache (first build only)
lake build
```

or `bash lean/check.sh` (pass `--no-cache` to skip the cache fetch, e.g. in CI
with a warm `.lake`).

Scope (Tier 1): the dimensional layer only. Nodes whose dimension uses
amount-of-substance (mole), current, or luminous intensity are omitted from
the physlib bridge, since physlib's `Dimension` has five bases (length, time,
mass, charge, temperature) and no mole base; extending it upstream is a later
tier. Those omitted nodes are covered by the Mathlib-only seven-base module
`OpenMaterialsDimensions.lean` instead.
