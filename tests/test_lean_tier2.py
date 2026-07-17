"""Lean Tier 2 (identities) and the units bridge. The generated files compile
against physlib/Mathlib (verified on a machine with a toolchain via
`lake build OpenMaterialsIdentities`); CI has none, so here we re-check the
generators structurally so a regression fails fast even without a toolchain:
the composition theorems stay non-reflexive, every `law` theorem's output symbol
and cleared-denominator statement is consistent with the map's formula, and the
emitted-plus-skipped operators account for every equational operator in the map.
"""
import re

import sympy as sp

from omai.lean_identities import (
    _all_edges, _flatten_indexed, _lean_expr, _lean_var, build_identities,
    build_index,
)
from omai.lean_units import build_units


def _equational_ops():
    return [op for op in _all_edges()
            if isinstance(getattr(op, "formula", None), sp.Equality)]


def test_identities_are_non_reflexive_and_grow_past_the_two_compositions():
    src, stats = build_identities()
    # Both original compositions survive, plus at least one standalone law: the
    # count strictly increases past the historical 2.
    assert stats["compositions"] == 2
    assert stats["laws"] >= 1
    assert stats["theorems"] == stats["compositions"] + stats["laws"] > 2
    # No theorem is a reflexive X = X (that carries no algebraic content).
    for m in re.finditer(r":\n    (.+?) = (.+?) := by", src):
        assert m.group(1).strip() != m.group(2).strip(), "reflexive theorem emitted"
    # The ZT and C_P compositions are still present and still substitute.
    assert "identity_contract_zt" in src
    assert "identity_contract_heat_capacity_p_identity" in src
    assert "subst" in src


def test_emitted_plus_skipped_account_for_every_equational_operator():
    _, stats = build_identities()
    emitted_ops = {t["op"] for t in build_index_items()}
    skipped_ops = {op for op, _ in stats["skipped"]}
    eq_ops = {op.name for op in _equational_ops()}
    # Every equational operator is either emitted or skipped, with no overlap.
    assert emitted_ops.isdisjoint(skipped_ops)
    assert eq_ops <= (emitted_ops | skipped_ops)
    # Coverage is honest: skip reasons are non-empty strings.
    assert all(isinstance(r, str) and r for _, r in stats["skipped"])


def build_index_items():
    return [{"op": op, **v} for op, v in build_index().items()]


def _law_symmap(lhs, rhs):
    """Reproduce the generator's symbol -> Lean identifier map (with the same
    collision-dedup) so the test renders the formula exactly as the generator."""
    all_syms = sorted({lhs} | rhs.free_symbols, key=str)
    symmap = {str(x): _lean_var(str(x)) for x in all_syms}
    used = {}
    for k in list(symmap):
        v = symmap[k]
        if v in used.values():
            n = 2
            while f"{v}_{n}" in used.values():
                n += 1
            symmap[k] = f"{v}_{n}"
        used[k] = symmap[k]
    return symmap


def test_every_law_theorem_is_consistent_with_the_map_formula():
    """The fail-fast structural check: for each `law` theorem, re-derive the
    output symbol Y and the single-fraction numerator/denominator N/D from the
    map formula exactly as the generator does, and confirm the emitted Lean
    states precisely `h : Y = N / D`, requires `D ≠ 0`, and asserts the cleared
    form `Y * D = N` proved by `subst` then `div_mul_cancel₀`. A drift between
    the map formula and the emitted theorem fails here."""
    idx = build_index()
    by_op = {op.name: op for op in _all_edges()}
    laws = {op: v for op, v in idx.items() if v["kind"] == "law"}
    assert laws, "expected at least one law theorem"
    for op_name, entry in laws.items():
        f = by_op[op_name].formula
        lhs = _flatten_indexed(f.lhs)
        rhs = _flatten_indexed(f.rhs)
        assert lhs.is_Symbol
        num, den = sp.fraction(sp.together(rhs))
        # a law always has a real denominator to clear, fraction-free N and D
        assert not (den == 1 or den.is_number), \
            f"{op_name}: law emitted for a denominator-free formula"
        symmap = _law_symmap(lhs, rhs)
        yv = symmap[str(lhs)]
        num_lean = _lean_expr(num, symmap)
        den_lean = _lean_expr(den, symmap)
        lean = entry["lean"]
        assert f"(h_{yv} : {yv} = ({num_lean}) / ({den_lean}))" in lean, \
            f"{op_name}: hypothesis N/D does not match the map formula"
        assert f"(hd0 : ({den_lean}) ≠ 0)" in lean, \
            f"{op_name}: denominator hypothesis mismatch"
        assert f"{yv} * ({den_lean}) = ({num_lean})" in lean, \
            f"{op_name}: cleared-denominator goal mismatch"
        assert f"subst h_{yv}" in lean
        assert "div_mul_cancel₀ _ hd0" in lean


def test_every_law_requires_exactly_one_denominator_hypothesis():
    """Combining to a single fraction means each `law` clears exactly one
    denominator: exactly one `≠ 0` binder, so no spurious hypothesis is emitted
    (which would trip the unused-variable linter in Lean)."""
    idx = build_index()
    for op_name, entry in idx.items():
        if entry["kind"] != "law":
            continue
        den_hyps = re.findall(r"\(hd\d+ : (.+?) ≠ 0\)", entry["lean"])
        assert len(den_hyps) == 1, \
            f"{op_name}: expected exactly one denominator hypothesis, got {den_hyps}"


def test_identity_index_for_frontend():
    idx = build_index()
    assert idx, "index is non-empty"
    assert all("lean" in v and v["kind"] in ("composition", "law")
               for v in idx.values())
    # both kinds are represented
    kinds = {v["kind"] for v in idx.values()}
    assert kinds == {"composition", "law"}


def test_units_bridge_anchors_si_and_transitivity():
    src, stats = build_units()
    assert stats["theorems"] == 3 and stats["canonical_units"] > 10
    assert "canonical_is_identity" in src
    assert "conversions_compose" in src
    assert "dimScale_transitive" in src  # proved by PhysLean's own lemma
