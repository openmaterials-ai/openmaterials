"""Tiers: authored physics-stage grouping on Spaces, exported to graph.json."""
from __future__ import annotations

from omai.operator.space import ObservableSpace, Field
from omai.operator.dimensions import DIMENSIONLESS


def test_space_carries_tier_default_empty():
    s = ObservableSpace(name="X", fields=(Field("x", DIMENSIONLESS),))
    assert s.tier == ""


def test_space_tier_settable():
    s = ObservableSpace(name="X", fields=(Field("x", DIMENSIONLESS),), tier="Sources")
    assert s.tier == "Sources"


def test_domain_carries_tiers_default_empty():
    from omai.map_data import Domain
    from omai.thermal_transport import representation as tt_rep
    d = Domain(name="d", nodes=(), edges=(), symbols={}, param_promotions=(),
               representation_package=tt_rep)
    assert d.tiers == ()


def test_all_thermal_nodes_tiered():
    from omai.thermal_transport.operator import NODES
    untiered = [n.name for n in NODES if not n.tier]
    assert untiered == [], f"untiered thermal nodes: {untiered}"


def test_all_materials_nodes_tiered():
    from omai.materials.operator import NODES
    untiered = [n.name for n in NODES if not n.tier]
    assert untiered == [], f"untiered materials nodes: {untiered}"


def test_thermal_domain_has_ordered_tiers():
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    names = [t[0] for t in THERMAL_TRANSPORT.tiers]
    assert names == ["Sources", "Harmonic", "Thermodynamics",
                     "Scattering", "Transport", "Molecular dynamics"]
    # every tier used by a node is declared in the manifest
    used = {n.tier for n in THERMAL_TRANSPORT.nodes}
    assert used <= set(names)


def test_materials_domain_declares_diffusion_tier():
    from omai.materials.domain import MATERIALS
    names = [t[0] for t in MATERIALS.tiers]
    assert "Diffusion" in names
    used = {n.tier for n in MATERIALS.nodes}
    assert used <= set(names)


def test_graph_dict_exports_tier_per_node_and_manifest():
    from omai.map_data import DOMAINS, build_graph_dict
    g = build_graph_dict(DOMAINS)
    # manifest present and ordered
    assert "tiers" in g and g["tiers"], "graph.tiers missing"
    orders = [t["order"] for t in g["tiers"]]
    assert orders == sorted(orders), "tiers not in ascending order"
    names = [t["name"] for t in g["tiers"]]
    assert names[:6] == ["Sources", "Harmonic", "Thermodynamics",
                         "Scattering", "Transport", "Molecular dynamics"]
    assert "Diffusion" in names
    # every non-parameter node has a tier that is in the manifest
    manifest = set(names)
    for n in g["nodes"]:
        assert "tier" in n
        if n["type"] != "parameter":
            assert n["tier"] in manifest, f"{n['id']} tier {n['tier']!r} not in manifest"


def test_parameter_nodes_tier_is_sources():
    from omai.map_data import DOMAINS, build_graph_dict
    g = build_graph_dict(DOMAINS)
    params = [n for n in g["nodes"] if n["type"] == "parameter"]
    assert params, "expected promoted-parameter nodes"
    for n in params:
        assert n["tier"] == "Sources"
