"""The PhysLean export (Tier 1): the map's dimensional layer as Lean.

We cannot run a Lean toolchain in CI (no lake/Mathlib), so we verify the two
things that make the generated file correct: (1) every node's PhysLean
Dimension has the right shared-base exponents, and (2) every emitted lemma
states a dimensional identity that ACTUALLY HOLDS, which is exactly what
Lean's `decide` checks. A false lemma would fail `decide` in Lean; here it
fails this test first. The real `lake build` against PhysLean is the honest
remaining step, run outside CI."""
import re

from omai.map_data import DOMAINS
from omai.physlean_export import (
    _PHYSLEAN_FIELD, _dimension_expr, _node_dimensions, build_export,
)


def _node_exps():
    return {name: exps for name, (exps, _) in _node_dimensions().items()}


def test_shared_base_dimensions_translate_correctly():
    # energy = M L^2 T^-2 -> PhysLean <length=2, time=-2, mass=1, charge=0, temp=0>
    exps = _node_exps()["TotalEnergy"] if "TotalEnergy" in _node_exps() else _node_exps()["ActivationEnergy"]
    expr = _dimension_expr(exps)
    assert expr == "⟨2, (-2 : ℚ), 1, 0, 0⟩"


def test_mole_and_luminous_nodes_are_omitted_not_mangled():
    # a molar node uses the N base PhysLean lacks: it must produce None, not a
    # wrong 5-field literal.
    exps = _node_exps().get("MolarHeatCapacity")
    assert exps is not None
    assert _dimension_expr(exps) is None


def test_every_emitted_lemma_is_a_true_dimensional_identity():
    src, stats = build_export()
    node_exps = _node_exps()
    # rebuild the id->name map the same way the exporter does
    from omai.physlean_export import _lean_ident
    ident_to_exps = {}
    for name, exps in node_exps.items():
        ident_to_exps[_lean_ident(name)] = exps

    lemma_re = re.compile(r"theorem \S+ : (\w+) = (.+) := by decide")
    checked = 0
    for line in src.splitlines():
        m = lemma_re.match(line.strip())
        if not m:
            continue
        target, prod = m.group(1), m.group(2)
        factors = [f.strip() for f in prod.split("*")]
        acc = [0] * len(node_exps[next(iter(node_exps))] and list(ident_to_exps.values())[0])
        for f in factors:
            fe = ident_to_exps[f]
            acc = [a + b for a, b in zip(acc, fe)]
        assert tuple(acc) == tuple(ident_to_exps[target]), \
            f"lemma would FAIL decide: {target} != product of {factors}"
        checked += 1
    assert checked == stats["lemmas"] and checked >= 1


def test_export_pins_the_map_version():
    src, stats = build_export()
    assert stats["map_version"] and stats["map_version"] in src
    assert stats["nodes_exported"] > 50
    assert stats["nodes_omitted"] >= 1  # the honest boundary is real
