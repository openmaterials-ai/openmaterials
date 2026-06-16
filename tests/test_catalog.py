def test_build_catalog_has_grounding_fields():
    from omai.map_data import build_catalog, DOMAINS
    cat = build_catalog(DOMAINS)
    assert isinstance(cat, list)
    by_id = {c["id"]: c for c in cat}
    assert "Temperature" in by_id
    t = by_id["Temperature"]
    assert set(t) >= {"id", "symbol", "type", "dimension", "description"}
    assert t["symbol"] == "T"
    assert t["type"] in ("observable", "hidden", "parameter")
    assert by_id["ThermalConductivity[transport_model=wigner]"]["description"]
    assert "Diffusivity" in by_id

    # Fix 1: single-field node has correct non-null dimension
    assert by_id["Temperature"]["dimension"] == "temperature"

    # Fix 2: promoted-parameter nodes now carry grounded dimensions
    assert by_id["CellVolume"]["dimension"] == "volume"

    # Fix 1: multi-field node captures all distinct field dimensions
    traj_dim = by_id["Trajectory"]["dimension"]
    assert "length" in traj_dim
    assert "length_per_time" in traj_dim
