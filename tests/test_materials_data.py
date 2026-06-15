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


def test_all_domains_and_write(tmp_path):
    from omai import map_data
    assert any(d.name == "thermal_transport" for d in map_data.DOMAINS)
    g = map_data.write_graph(tmp_path / "graph.json")
    assert g.exists()


def test_shared_primitives_reuse_existing_nodes():
    from omai.materials.operator import shared_primitives as sp_mod
    from omai.thermal_transport.operator.nodes import TEMPERATURE_STATE, MEAN_SQUARED_DISPLACEMENT
    assert sp_mod.TEMPERATURE is TEMPERATURE_STATE
    assert sp_mod.MEAN_SQUARED_DISPLACEMENT is MEAN_SQUARED_DISPLACEMENT
    assert sp_mod.STRUCTURE.name == "Structure"


def test_skills_catalog_schema():
    import json
    import pathlib

    catalog = pathlib.Path(__file__).resolve().parents[1] / "omai" / "materials" / "skills_catalog.json"
    cat = json.loads(catalog.read_text())
    assert len(cat) >= 30                      # ~40+ mat-* skills; some are data-only
    for rec in cat:
        assert rec["name"].startswith("mat-")
        assert isinstance(rec["produces"], list)
        for p in rec["produces"]:
            assert {"quantity", "symbol", "units", "gauge"} <= set(p)
            assert p["gauge"] in ("observable", "hidden", "parameter")
        assert isinstance(rec["consumes"], list)
        assert isinstance(rec["operation"], dict) and "kind" in rec["operation"]
        assert isinstance(rec["codes"], list)
        for inst in rec.get("example_instances", []):
            assert isinstance(inst["value"], (int, float))   # real numbers only
