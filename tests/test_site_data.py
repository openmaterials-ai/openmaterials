from omai.thermal_transport.site_data import build_graph_dict, build_instances


def test_build_graph_dict_shape():
    g = build_graph_dict()
    assert len(g["nodes"]) == 46
    assert len(g["links"]) == 92
    by_id = {n["id"]: n for n in g["nodes"]}
    kappa = by_id["ThermalConductivity[transport_model=wigner]"]
    assert kappa["type"] == "observable"
    assert kappa["layer"] == 10
    for n in g["nodes"]:
        assert set(n) >= {"id", "type", "layer", "kind", "symbol", "formula"}
        assert n["kind"] == "symbolic"
        # every variable has a curated LaTeX symbol, not a bare word
        assert n["symbol"] and n["symbol"] != n["id"], f"no symbol for {n['id']}"
    assert sum(1 for n in g["nodes"] if n["formula"]) >= 40


def test_instances_bundle_valid():
    # The seed ships empty (no invented data); validate any instances that exist.
    insts = build_instances()
    ids = {n["id"] for n in build_graph_dict()["nodes"]}
    required = {"variable", "material", "conditions", "value", "units", "source"}
    for it in insts:
        assert required <= set(it), it
        assert it["variable"] in ids, f"instance points at unknown variable {it['variable']}"
        assert it["source"]["kind"] in ("simulation", "measurement")

