from omai.thermal_transport.site_data import build_graph_dict


def test_build_graph_dict_shape():
    g = build_graph_dict()
    assert len(g["nodes"]) == 46
    assert len(g["links"]) == 92
    by_id = {n["id"]: n for n in g["nodes"]}
    kappa = by_id["ThermalConductivity[transport_model=wigner]"]
    assert kappa["type"] == "observable"
    assert kappa["layer"] == 10
    for n in g["nodes"]:
        assert set(n) >= {"id", "type", "layer", "kind", "formula"}
        assert n["kind"] == "symbolic"
    assert sum(1 for n in g["nodes"] if n["formula"]) >= 40
