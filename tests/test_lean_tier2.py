"""Lean Tier 2 (identities) and the units bridge. The generated files compile
against PhysLean/Mathlib (verified on a machine with a toolchain, 2026-07-12);
CI has none, so here we check the generators produce the expected structure."""
from omai.lean_identities import build_identities, build_index
from omai.lean_units import build_units


def test_identities_are_compositions_not_reflexive():
    src, stats = build_identities()
    # only genuine compositions are emitted (chained identities); single-edge
    # definitions are skipped rather than emitted as reflexive X = X.
    assert stats["compositions"] == stats["theorems"] >= 2
    # each theorem has distinct LHS and RHS (non-trivial content)
    import re
    for m in re.finditer(r":\n    (.+?) = (.+?) := by", src):
        assert m.group(1).strip() != m.group(2).strip(), "reflexive theorem emitted"
    # the ZT and C_P compositions are present
    assert "identity_contract_zt" in src
    assert "subst" in src  # proofs substitute the upstream identities


def test_identity_index_for_frontend():
    idx = build_index()
    assert all("lean" in v and v["kind"] == "composition" for v in idx.values())


def test_units_bridge_anchors_si_and_transitivity():
    src, stats = build_units()
    assert stats["theorems"] == 3 and stats["canonical_units"] > 10
    assert "canonical_is_identity" in src
    assert "conversions_compose" in src
    assert "dimScale_transitive" in src  # proved by PhysLean's own lemma
