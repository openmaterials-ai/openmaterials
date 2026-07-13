import pytest

from omai.map_data import (
    DOMAINS,
    build_codes as _build_codes,
    build_graph_dict as _build_graph_dict,
    build_instances,
    build_spectra,
    record_instance as _record_instance,
    record_spectrum as _record_spectrum,
)
from omai.thermal_transport.domain import THERMAL_TRANSPORT


def build_codes():
    return _build_codes((THERMAL_TRANSPORT,))


def build_graph_dict():
    return _build_graph_dict((THERMAL_TRANSPORT,))


def record_instance(**kw):
    return _record_instance(domains=DOMAINS, **kw)


def record_spectrum(**kw):
    return _record_spectrum(domains=DOMAINS, **kw)


# A minimal valid PhononDOS spectrum: a linear-THz axis (registered, FREQUENCY)
# and an open-normalization density (units a free string, per the DOS convention).
def _good_spectrum(**over):
    kw = dict(
        variable="PhononDOS", material="Si",
        axis_name="omega", axis_units="linear_THz",
        axis_values=[0.0, 1.0, 2.0, 3.0], values=[0.0, 0.4, 0.9, 0.3],
        units="states/THz", source_kind="simulation", source_ref="phonopy",
        conditions={"normalization": "per cell"},
    )
    kw.update(over)
    return kw


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
    assert len(symbolic) == 52
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
    nodes = map_data.build_graph_dict(map_data.DOMAINS)["nodes"]
    ids = {n["id"] for n in nodes}
    name_to_uid = {n["id"]: n["uid"] for n in nodes}
    required = {"variable", "material", "conditions", "value", "units", "source"}
    for it in insts:
        assert required <= set(it), it
        assert it["variable"] in ids, f"instance points at unknown variable {it['variable']}"
        assert it["source"]["kind"] in ("simulation", "measurement")
        # Each instance is pinned to the live node uid of its variable (P3).
        assert it["node_uid"] == name_to_uid[it["variable"]]


def test_paper_sourced_instances_land_and_pin_the_live_node_uids():
    # The first paper-sourced evidence apply (2026-07-11): 14 signed-off values
    # from three parsed papers. Each carries source.ref "paper:<slug>", is a
    # simulation, and pins the live node uid of its variable.
    from omai import map_data

    insts = build_instances()
    name_to_uid = {n["id"]: n["uid"]
                   for n in map_data.build_graph_dict(map_data.DOMAINS)["nodes"]}
    paper = [it for it in insts if it["source"]["ref"].startswith("paper:")]
    assert len(paper) == 22
    # papers contribute BOTH kinds now: measured kappa lands on the
    # method-neutral node (Balandin graphene, PtSe2 FDTR), computed values on
    # their route-labeled or neutral nodes. Pin the split so drift is loud.
    kinds = [it["source"]["kind"] for it in paper]
    assert kinds.count("simulation") == 20 and kinds.count("measurement") == 2
    for it in paper:
        assert it["node_uid"] == name_to_uid[it["variable"]]
        # Every landed value carries a verbatim, page-located quote in detail.
        assert "(p. " in it["source"]["detail"]

    by_ref = {}
    for it in paper:
        by_ref.setdefault(it["source"]["ref"], []).append(it)
    assert len(by_ref["paper:kaldo-2020-barbalinardo"]) == 8
    assert len(by_ref["paper:qhgk-2019-isaeva"]) == 3
    assert len(by_ref["paper:esfarjani-2011"]) == 3

    # Spot values with their pinned labels.
    def find(ref, variable, value):
        hits = [it for it in paper
                if it["source"]["ref"] == ref
                and it["variable"] == variable and it["value"] == value]
        assert len(hits) == 1, (ref, variable, value)
        return hits[0]

    k147 = find("paper:kaldo-2020-barbalinardo",
                "ThermalConductivity[bte_solver=direct_inverse]", 147.0)
    assert k147["material"] == "Si (diamond)"
    assert k147["units"] == "W/(m K)"

    q027 = find("paper:qhgk-2019-isaeva",
                "ThermalConductivity[transport_model=green_kubo]", 0.027)
    assert q027["material"] == "a-Si"
    assert q027["conditions"]["T"] == 50

    # The a-Si mass density landed on the MassDensity node in g/cm3.
    dens = find("paper:qhgk-2019-isaeva", "MassDensity", 2.3)
    assert dens["units"] == "g/cm3"

    # All three esfarjani kappa values pin to the RTA solver (the paper computes
    # kappa within the relaxation-time approximation), not direct_inverse.
    esf = by_ref["paper:esfarjani-2011"]
    assert {it["value"] for it in esf} == {32.67, 47.2, 166.0}
    for it in esf:
        assert it["variable"] == "ThermalConductivity[bte_solver=rta]"


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


def test_record_instance_carries_optional_configuration(tmp_path):
    """An instance may carry an optional configuration uid (spec section 5);
    material stays the display string and the key survives into the bundle."""
    uid = "a" * 64
    p = record_instance(
        variable="ThermalConductivity[bte_solver=rta]", material="Si",
        value=15.76, units="W/(m K)", source_kind="simulation", source_ref="kaldo",
        conditions={"T": 300}, configuration=uid, instances_dir=tmp_path,
    )
    assert p.exists()
    recs = build_instances(tmp_path)
    assert recs[0]["configuration"] == uid
    assert recs[0]["material"] == "Si"


def test_record_instance_without_configuration_omits_the_key(tmp_path):
    record_instance(
        variable="ThermalConductivity[bte_solver=rta]", material="Si",
        value=1.0, units="W/(m K)", source_kind="simulation", source_ref="kaldo",
        instances_dir=tmp_path,
    )
    recs = build_instances(tmp_path)
    assert "configuration" not in recs[0]


def test_record_instance_rejects_unknown_variable(tmp_path):
    with pytest.raises(ValueError):
        record_instance(
            variable="NotAVariable", material="Si", value=1.0, units="x",
            source_kind="simulation", source_ref="kaldo", instances_dir=tmp_path,
        )


# ---- spectrum layer (function-valued evidence) -----------------------------


def test_record_spectrum_roundtrip(tmp_path):
    p = record_spectrum(spectra_dir=tmp_path, **_good_spectrum())
    assert p.exists()
    recs = build_spectra(tmp_path)
    assert len(recs) == 1
    r = recs[0]
    assert r["variable"] == "PhononDOS"
    assert r["axis"]["name"] == "omega" and r["axis"]["units"] == "linear_THz"
    assert r["values"] == [0.0, 0.4, 0.9, 0.3]
    assert len(r["axis"]["values"]) == len(r["values"])


def test_record_spectrum_pins_node_uid(tmp_path):
    record_spectrum(spectra_dir=tmp_path, **_good_spectrum())
    recs = build_spectra(tmp_path)
    name_to_uid = {n["id"]: n["uid"] for n in _build_graph_dict(DOMAINS)["nodes"]}
    # Bundling pins the record to the live node uid of its variable (P3).
    assert recs[0]["node_uid"] == name_to_uid["PhononDOS"]


def test_record_spectrum_rejects_unknown_variable(tmp_path):
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path, **_good_spectrum(variable="NotAVariable"))


def test_record_spectrum_rejects_unit_mismatch(tmp_path):
    # A THERMAL_CONDUCTIVITY axis unit against a FREQUENCY canonical axis.
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path, **_good_spectrum(axis_units="W_per_m_per_K"))


def test_record_spectrum_rejects_unregistered_axis_unit(tmp_path):
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path, **_good_spectrum(axis_units="not_a_unit"))


def test_record_spectrum_rejects_non_monotonic_axis(tmp_path):
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path,
                        **_good_spectrum(axis_values=[0.0, 2.0, 1.0, 3.0]))


def test_record_spectrum_rejects_length_mismatch(tmp_path):
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path,
                        **_good_spectrum(values=[0.0, 0.4, 0.9]))


def test_record_spectrum_rejects_non_real_values(tmp_path):
    with pytest.raises(ValueError):
        record_spectrum(spectra_dir=tmp_path,
                        **_good_spectrum(values=[0.0, 0.4, "x", 0.3]))


def test_record_spectrum_rejects_non_spectrum_node(tmp_path):
    # ThermalConductivity is a scalar node: no canonical axis declared.
    with pytest.raises(ValueError):
        record_spectrum(
            spectra_dir=tmp_path,
            **_good_spectrum(variable="ThermalConductivity[transport_model=wigner]"))


def test_spectra_bundle_valid():
    # The committed spectra bundle must validate against the unified map and pin
    # each record to its live node uid.
    from omai import map_data

    specs = build_spectra()
    nodes = map_data.build_graph_dict(map_data.DOMAINS)["nodes"]
    name_to_uid = {n["id"]: n["uid"] for n in nodes}
    required = {"variable", "material", "conditions", "axis", "values", "units", "source"}
    for s in specs:
        assert required <= set(s), s
        assert s["variable"] in name_to_uid, s["variable"]
        assert s["node_uid"] == name_to_uid[s["variable"]]
        assert len(s["axis"]["values"]) == len(s["values"])



def test_record_instance_never_silently_overwrites(tmp_path):
    """One paper legitimately reports several values on the same node for the
    same material (the kaldo 2020 apply had five such). The old slug was
    (material, variable, source_ref) only, so the second value silently
    OVERWROTE the first. Now: identical re-records are idempotent (same path
    back); different records get a numeric suffix; a slug_hint gives the
    caller a human-readable disambiguator."""
    common = dict(
        variable="ThermalConductivity[bte_solver=rta]", material="Si",
        units="W/(m K)", source_kind="simulation", source_ref="paper:x",
        instances_dir=tmp_path,
    )
    p1 = record_instance(value=118.0, conditions={"mesh": "7x7x7"}, **common)
    # identical re-record: same path, still one file
    p1b = record_instance(value=118.0, conditions={"mesh": "7x7x7"}, **common)
    assert p1 == p1b
    assert len(list(tmp_path.glob("*.json"))) == 1
    # a DIFFERENT value on the same slug: new suffixed file, first untouched
    p2 = record_instance(value=123.0, conditions={"mesh": "10x10x10"}, **common)
    assert p2 != p1 and p2.exists() and p1.exists()
    recs = build_instances(tmp_path)
    assert sorted(r["value"] for r in recs) == [118.0, 123.0]
    # slug_hint: human-readable disambiguation up front
    p3 = record_instance(value=166.0, slug_hint="extrapolated", **common)
    assert "extrapolated" in p3.name
