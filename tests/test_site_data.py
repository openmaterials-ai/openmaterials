import pytest

from omai.thermal_transport.site_data import (
    build_codes,
    build_graph_dict,
    build_instances,
    record_instance,
)


def test_build_codes_maps_real_variables():
    codes = build_codes()
    assert "kaldo" in codes and "phono3py" in codes
    ids = {n["id"] for n in build_graph_dict()["nodes"]}
    for code, mapping in codes.items():
        assert mapping, f"{code} maps nothing"
        for var in mapping:
            assert var in ids, f"{code} maps unknown variable {var}"
    # kaldo maps a broad swath including the phonon frequency
    assert "Frequency" in codes["kaldo"]


def test_build_graph_dict_shape():
    g = build_graph_dict()
    symbolic = [n for n in g["nodes"] if n["type"] in ("observable", "hidden")]
    assert len(symbolic) == 46
    assert {n["id"] for n in g["nodes"] if n["type"] == "parameter"} == {
        "CellVolume", "AtomicMass", "AtomCount",
    }
    assert len(g["links"]) >= 92
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
    # Instances live in one shared dir and may belong to any domain, so validate
    # their variables against the unified map (all domains), not thermal-only.
    from omai import map_data

    insts = build_instances()
    ids = {n["id"] for n in map_data.build_graph_dict(map_data.DOMAINS)["nodes"]}
    required = {"variable", "material", "conditions", "value", "units", "source"}
    for it in insts:
        assert required <= set(it), it
        assert it["variable"] in ids, f"instance points at unknown variable {it['variable']}"
        assert it["source"]["kind"] in ("simulation", "measurement")


def test_record_instance_roundtrip(tmp_path):
    p = record_instance(
        variable="ThermalConductivity[bte_solver=rta]", material="Si",
        value=15.76, units="W/(m K)", source_kind="simulation", source_ref="kaldo",
        conditions={"T": 300, "mesh": "8x8x8"}, detail="Tersoff, RTA",
        instances_dir=tmp_path,
    )
    assert p.exists()
    recs = build_instances(tmp_path)
    assert len(recs) == 1
    assert recs[0]["value"] == 15.76
    assert recs[0]["source"]["ref"] == "kaldo"


def test_record_instance_rejects_unknown_variable(tmp_path):
    with pytest.raises(ValueError):
        record_instance(
            variable="NotAVariable", material="Si", value=1.0, units="x",
            source_kind="simulation", source_ref="kaldo", instances_dir=tmp_path,
        )

