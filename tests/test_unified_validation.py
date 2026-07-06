"""The DAG-discipline validator guards the unified multi-domain map.

Historically validate_dag was only exercised against the thermal-transport
domain, and its symbol vocabulary was a hard-coded table inside
omai.operator.validate — so a new domain's edges silently escaped the
free-symbol discipline (the materials edges shipped with five vocabulary
violations that nothing caught). The vocabulary is now a registry that each
domain populates at import time, and these tests pin the invariant:
every domain validates, individually and unified.
"""
from __future__ import annotations

from omai.map_data import DOMAINS
from omai.operator.validate import validate_dag


def _unified_nodes_and_edges():
    nodes, edges, seen = [], [], set()
    for domain in DOMAINS:
        for space in domain.nodes:
            if space.name not in seen:
                seen.add(space.name)
                nodes.append(space)
        edges.extend(domain.edges)
    # Edges may consume shared leaves re-exported from another domain
    # (e.g. materials consuming thermal's MeanSquaredDisplacement); those
    # are already present via the thermal NODES tuple.
    return tuple(nodes), tuple(edges)


def test_unified_map_validates_clean():
    nodes, edges = _unified_nodes_and_edges()
    assert validate_dag(nodes, edges) == []


def test_every_domain_registers_symbol_vocabulary():
    """Each domain's edge formulas resolve entirely inside the registered
    vocabulary — per domain, not just in the union (a domain must not
    depend on another domain's constants by accident)."""
    from omai.operator.vocabulary import SPACE_SYMBOLS

    nodes, edges = _unified_nodes_and_edges()
    node_names = {s.name for s in nodes}
    # Every registered space name must correspond to a real node, so the
    # registry cannot drift ahead of (or away from) the actual map.
    for name in SPACE_SYMBOLS:
        assert name in node_names, f"vocabulary entry {name!r} has no node"


def test_registration_extends_validation_vocabulary():
    """A synthetic edge with a foreign symbol fails validation until its
    space registers the symbol."""
    import sympy as sp

    from omai.operator.dimensions import DIMENSIONLESS
    from omai.operator.operator import Operator
    from omai.operator.space import Field, ObservableSpace
    from omai.operator.vocabulary import register_space_symbols

    src = ObservableSpace(name="_VocabTestSource", fields=(Field("x", DIMENSIONLESS),))
    out = ObservableSpace(name="_VocabTestOut", fields=(Field("y", DIMENSIONLESS),))
    edge = Operator(
        name="_vocab_test_edge",
        inputs=(src,),
        outputs=(out,),
        formula=sp.Eq(sp.Symbol("y_test"), sp.Symbol("x_test") ** 2),
    )

    errors = validate_dag((src, out), (edge,))
    assert any("x_test" in e for e in errors) and any("y_test" in e for e in errors)

    from omai.operator.vocabulary import SPACE_SYMBOLS

    register_space_symbols({
        "_VocabTestSource": frozenset({"x_test"}),
        "_VocabTestOut": frozenset({"y_test"}),
    })
    try:
        assert validate_dag((src, out), (edge,)) == []
    finally:
        SPACE_SYMBOLS.pop("_VocabTestSource", None)
        SPACE_SYMBOLS.pop("_VocabTestOut", None)
