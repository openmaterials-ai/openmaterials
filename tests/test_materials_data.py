def test_materials_package_imports_empty_registries():
    from omai.materials.operator import NODES, EDGES
    assert isinstance(NODES, tuple)
    assert isinstance(EDGES, tuple)


def test_thermal_domain_descriptor():
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    from omai.map_data import Domain
    assert isinstance(THERMAL_TRANSPORT, Domain)
    assert len(THERMAL_TRANSPORT.nodes) == 46          # current thermal node count
    assert THERMAL_TRANSPORT.symbols["Temperature"] == "T"
    assert any(p[0] == "CellVolume" for p in THERMAL_TRANSPORT.param_promotions)


def test_unified_build_equals_thermal_when_materials_empty():
    from omai import map_data
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    g = map_data.build_graph_dict((THERMAL_TRANSPORT,))
    ids = {n["id"] for n in g["nodes"]}
    assert "Temperature" in ids
    assert "CellVolume" in ids               # promoted parameter
    assert any(n["type"] == "parameter" for n in g["nodes"])
    assert len(g["links"]) >= 92
