"""Cross-code agreement: the same-conditions comparison groups the map holds.

Two halves, mirroring the data-layer tests: real-data assertions that pin the
five genuine groups in docs/data/instances.json, and synthetic negative guards
that prove the honesty rule refuses apples-to-oranges pairs. The rule under test
is stated in omai.cross_code: two instances compare only when their BASE variable
(the [label] stripped), material, and PHYSICAL conditions (conditions minus the
estimator keys method/scattering and minus the variable [label]) all match, and
a group needs >= 2 members spanning >= 2 distinct estimators.
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.cross_code import agreement_groups, build_agreement

_DOCS = Path(__file__).resolve().parents[1] / "docs"


def _real_groups():
    return agreement_groups()


def _group_for(groups, material, observable="ThermalConductivity"):
    hits = [g for g in groups
            if g["material"] == material and g["observable"] == observable]
    assert len(hits) == 1, (
        f"expected exactly one {observable} group for {material!r}, got {len(hits)}")
    return hits[0]


def _values(group):
    return sorted(m["value"] for m in group["members"])


# ---------------------------------------------------------------------------
# Real data: exactly the five genuine same-condition comparison groups.
# ---------------------------------------------------------------------------

def test_real_data_yields_exactly_five_groups():
    groups = _real_groups()
    # If the real data does not yield exactly five groups, the rule (or the data)
    # moved: fail loudly rather than let the count drift silently.
    assert len(groups) == 5, (
        "expected exactly 5 same-condition groups; got "
        + str([(g["observable"], g["material"], len(g["members"])) for g in groups]))
    # Every real group is on the thermal conductivity node.
    assert all(g["observable"] == "ThermalConductivity" for g in groups)


def test_si_tersoff_group_is_the_cross_code_crown_jewel():
    groups = _real_groups()
    # Two Si groups exist; the Tersoff one is the 8x8x8 mesh with four members.
    si_tersoff = next(
        g for g in groups
        if g["material"] == "Si" and g["conditions"].get("potential") == "Si.tersoff")
    assert si_tersoff["conditions"] == {"T": 300, "mesh": "8x8x8", "potential": "Si.tersoff"}
    assert len(si_tersoff["members"]) == 4
    assert _values(si_tersoff) == [16.735, 19.46, 24.301, 26.908]
    # Spans both codes and both methods.
    refs = {m["ref"] for m in si_tersoff["members"]}
    ests = {m["estimator"] for m in si_tersoff["members"]}
    assert refs == {"kaldo", "phono3py"}
    assert ests == {"bte_solver=direct_inverse", "bte_solver=rta"}
    # The same method run by two codes on the same inputs: cross-code true.
    assert si_tersoff["has_cross_code"] is True
    assert si_tersoff["has_measurement"] is False


def test_ge_tersoff_group_is_direct_inverse_vs_rta():
    ge = _group_for(_real_groups(), "Ge")
    assert ge["conditions"] == {
        "T": 300, "mesh": "8x8x8", "potential": "Ge.tersoff",
        "supercell_fc2": "4x4x4", "supercell_fc3": "3x3x3"}
    assert _values(ge) == [13.332, 15.276]
    assert {m["estimator"] for m in ge["members"]} == {
        "bte_solver=direct_inverse", "bte_solver=rta"}
    # One code (kaldo), two solvers: cross-method but not cross-code.
    assert ge["has_cross_code"] is False
    assert ge["has_measurement"] is False


def test_ptse2_group_is_measurement_vs_simulation():
    ptse2 = _group_for(_real_groups(), "PtSe2 (bulk)")
    # In-plane only: the cross-plane 2.84 value is a different physical question.
    assert ptse2["conditions"] == {"T": "room temperature", "direction": "in-plane"}
    assert _values(ptse2) == [39.0, 41.4]
    assert ptse2["has_measurement"] is True
    kinds = {m["kind"] for m in ptse2["members"]}
    assert kinds == {"simulation", "measurement"}


def test_si_dfpt_quantum_group_is_147_vs_140():
    groups = _real_groups()
    si_dfpt_q = _group_for(groups, "Si (diamond)")
    assert si_dfpt_q["conditions"] == {
        "T": 300, "statistics": "quantum",
        "q-grid": "19x19x19", "potential": "DFPT LDA"}
    assert _values(si_dfpt_q) == [140.0, 147.0]
    # direct_inverse over-predicts RTA (full inversion vs relaxation time).
    hi = max(si_dfpt_q["members"], key=lambda m: m["value"])
    lo = min(si_dfpt_q["members"], key=lambda m: m["value"])
    assert hi["value"] == 147.0 and "direct_inverse" in hi["estimator"]
    assert lo["value"] == 140.0 and "rta" in lo["estimator"]


def test_si_dfpt_classical_group_is_123_vs_118():
    groups = _real_groups()
    # The second Si group is the DFPT LDA classical case (no q-grid, no mesh).
    si_dfpt_c = next(
        g for g in groups
        if g["material"] == "Si"
        and g["conditions"].get("potential") == "DFPT LDA")
    assert si_dfpt_c["conditions"] == {
        "T": 300, "statistics": "classical", "potential": "DFPT LDA"}
    assert _values(si_dfpt_c) == [118.0, 123.0]


def test_groups_sorted_by_estimator_count_then_spread():
    groups = _real_groups()
    keys = [(g["n_estimators"], g["spread"]) for g in groups]
    assert keys == sorted(keys, key=lambda k: (-k[0], -k[1]))


# ---------------------------------------------------------------------------
# Negative guards: instances that must NOT be grouped together. Each builds a
# minimal synthetic pair that differs only in a PHYSICAL condition (or nothing),
# proving the rule refuses to compare across it.
# ---------------------------------------------------------------------------

def _inst(variable, material, value, conditions, ref="codeA", kind="simulation",
          units="W/(m K)"):
    return {
        "variable": variable, "material": material, "value": value,
        "units": units, "conditions": conditions,
        "source": {"kind": kind, "ref": ref},
    }


def test_guard_different_direction_does_not_compare():
    # PtSe2 in-plane (39.0) vs cross-plane (2.84): same base, same material, same
    # method, but direction is a physical condition -> not comparable.
    insts = [
        _inst("ThermalConductivity", "PtSe2 (bulk)", 39.0,
              {"T": "room temperature", "direction": "in-plane", "method": "BTE"}),
        _inst("ThermalConductivity", "PtSe2 (bulk)", 2.84,
              {"T": "room temperature", "direction": "cross-plane", "method": "RTA"}),
    ]
    assert agreement_groups(insts) == []


def test_guard_different_system_size_does_not_compare():
    # a-Si Green-Kubo 0.25 (13824-atom) vs 0.027 (1728-atom): same solver label,
    # but the model size lives in conditions and is physical -> not comparable.
    insts = [
        _inst("ThermalConductivity[transport_model=green_kubo]", "a-Si", 0.25,
              {"T": 50, "system": "13824-atom model"}),
        _inst("ThermalConductivity[transport_model=green_kubo]", "a-Si", 0.027,
              {"T": 50, "system": "1728-atom model"}),
    ]
    assert agreement_groups(insts) == []


def test_guard_different_temperature_does_not_compare():
    # ZT 1.9 (1200 K) vs 1.0 (700 K): same base, same material, but T differs.
    insts = [
        _inst("ZT", "Si0.5Ge0.5", 1.9, {"T": "1200 K", "disorder": "1/r correlation"},
              units="dimensionless"),
        _inst("ZT", "Si0.5Ge0.5", 1.0, {"T": "700 K", "disorder": "1/r correlation"},
              units="dimensionless"),
    ]
    assert agreement_groups(insts) == []


def test_guard_different_elastic_component_does_not_compare():
    # ElasticConstants C11 / C12 / C44: same base, same material, same method,
    # but the tensor component is a physical condition -> three separate questions.
    insts = [
        _inst("ElasticConstants", "Si (diamond)", 133.6,
              {"T": "300 K", "method": "PIMD+TDEP", "component": "C11"}, units="GPa"),
        _inst("ElasticConstants", "Si (diamond)", 59.4,
              {"T": "300 K", "method": "PIMD+TDEP", "component": "C12"}, units="GPa"),
        _inst("ElasticConstants", "Si (diamond)", 64.3,
              {"T": "300 K", "method": "PIMD+TDEP", "component": "C44"}, units="GPa"),
    ]
    assert agreement_groups(insts) == []


def test_guard_same_estimator_alone_does_not_form_a_group():
    # Two identical-estimator values under identical conditions do NOT span two
    # estimators, so no group forms (this is the "different codes, same everything"
    # cross-code case only when the estimator axis or a second method is present;
    # here both are the same solver with no method key, so nothing to compare).
    insts = [
        _inst("ThermalConductivity[bte_solver=rta]", "Si", 19.46,
              {"T": 300, "mesh": "8x8x8", "potential": "Si.tersoff"}, ref="kaldo"),
        _inst("ThermalConductivity[bte_solver=rta]", "Si", 16.735,
              {"T": 300, "mesh": "8x8x8", "potential": "Si.tersoff"}, ref="phono3py"),
    ]
    assert agreement_groups(insts) == []


def test_guard_different_material_does_not_compare():
    # Same solver labels and conditions, different material string -> two
    # different questions, no group.
    insts = [
        _inst("ThermalConductivity[bte_solver=direct_inverse]", "Si", 26.908,
              {"T": 300, "mesh": "8x8x8"}),
        _inst("ThermalConductivity[bte_solver=rta]", "Ge", 13.332,
              {"T": 300, "mesh": "8x8x8"}),
    ]
    assert agreement_groups(insts) == []


# ---------------------------------------------------------------------------
# Positive synthetic cases: the estimator axes the rule DOES span.
# ---------------------------------------------------------------------------

def test_cross_code_same_estimator_different_ref_groups_and_flags():
    # Same solver label, identical conditions, two codes: comparable, and the
    # cross-code flag fires (the direct kaldo-vs-phono3py comparison).
    insts = [
        _inst("ThermalConductivity[bte_solver=rta]", "Si", 19.46,
              {"T": 300, "mesh": "8x8x8"}, ref="kaldo"),
        _inst("ThermalConductivity[bte_solver=rta]", "Si", 16.735,
              {"T": 300, "mesh": "8x8x8"}, ref="phono3py"),
        _inst("ThermalConductivity[bte_solver=direct_inverse]", "Si", 26.908,
              {"T": 300, "mesh": "8x8x8"}, ref="kaldo"),
    ]
    groups = agreement_groups(insts)
    assert len(groups) == 1
    g = groups[0]
    assert g["has_cross_code"] is True
    assert len(g["members"]) == 3


def test_method_axis_alone_spans_two_estimators_on_a_labelless_node():
    # A neutral (labelless) node where the estimator is the method string only,
    # the PtSe2 shape: two methods, same conditions -> one group.
    insts = [
        _inst("ThermalConductivity", "X", 39.0,
              {"T": "room temperature", "direction": "in-plane", "method": "BTE"}),
        _inst("ThermalConductivity", "X", 41.4,
              {"T": "room temperature", "direction": "in-plane", "method": "FDTR"},
              kind="measurement"),
    ]
    groups = agreement_groups(insts)
    assert len(groups) == 1
    assert groups[0]["has_measurement"] is True
    assert groups[0]["n_estimators"] == 2


# ---------------------------------------------------------------------------
# The written bundle: shape and summary.
# ---------------------------------------------------------------------------

def test_build_agreement_writes_summary_and_groups(tmp_path):
    out = build_agreement(out=tmp_path / "agreement.json")
    data = json.loads(out.read_text())
    assert set(data) == {"summary", "groups"}
    s = data["summary"]
    assert s["groups"] == 5
    assert s["cross_code"] == 1
    assert s["theory_vs_experiment"] == 1
    # The version stamp is the map version the site reads.
    assert isinstance(s["version"], str) and len(s["version"]) == 64
    assert len(data["groups"]) == 5


def test_committed_agreement_bundle_matches_a_fresh_build(tmp_path):
    # The committed docs/data/agreement.json must be exactly what a fresh build
    # produces (it is derived, like instances.json): a stale bundle is a lie.
    committed = json.loads((_DOCS / "data" / "agreement.json").read_text())
    fresh = json.loads(build_agreement(out=tmp_path / "agreement.json").read_text())
    assert committed == fresh
