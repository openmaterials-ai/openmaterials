"""Tests for the electronic-transport contribution (records 154-163).

The amset scan (AtomisticSkills arXiv 2605.24002: amset 0.5.1 through atomate2's
VaspAmsetMaker) lands ONE contribution in a new electronic_transport domain:
five nodes (StaticDielectricTensor plus the four transport tensors) with five
implicit edges (the static-dielectric assembly and the four iterative-BTE
transport tensors).

Two load-bearing identity decisions are proved here:

  * The carrier family: ElectricalConductivity[carrier=electronic] shares the
    electrical_conductivity tag and the ELECTRICAL_CONDUCTIVITY dimension with
    the config-thermo [carrier=ionic] sibling, a distinct uid only by the
    carrier label.
  * The kappa firewall: ElectronicThermalConductivity reuses the
    THERMAL_CONDUCTIVITY dimension but carries its own
    electronic_thermal_conductivity tag, a distinct uid from every lattice
    ThermalConductivity node.

All five edges carry opaque solver functions, classified SKIPPED by the
dimensional gate.
"""
from __future__ import annotations

from omai.map_data import DOMAINS, build_codes, build_graph_dict
from omai.operator.dimcheck import dimensional_report
from omai.operator.identity import edge_id, node_id
from omai.operator.validate import validate_dag


def _all_nodes_edges():
    nodes: list = []
    edges: list = []
    seen_n: set = set()
    seen_e: set = set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in seen_n:
                seen_n.add(s.name)
                nodes.append(s)
        for op in d.edges:
            if op.name not in seen_e:
                seen_e.add(op.name)
                edges.append(op)
    return nodes, edges


# --------------------------------------------------------------------------
# The SEEBECK and MOBILITY dimensions: the exponent proofs.
# --------------------------------------------------------------------------

def test_seebeck_exponents_are_v_per_k():
    """S = V/K = M L^2 T^-3 Th^-1 I^-1, built from the volt (VOLTAGE) divided by
    a temperature: the first map dimension carrying BOTH the current axis (I=-1)
    and the temperature axis (Th=-1)."""
    from omai.operator.dimensions import SEEBECK, TEMPERATURE, VOLTAGE

    assert SEEBECK.exponents == (1, 2, -3, -1, 0, -1, 0)
    assert SEEBECK.canonical() == "M^1 L^2 T^-3 Th^-1 I^-1"
    # V/K: the volt divided by a temperature reproduces SEEBECK exactly.
    assert (VOLTAGE / TEMPERATURE).exponents == SEEBECK.exponents
    # BOTH the current axis (I) and the temperature axis (Th) are non-zero.
    assert SEEBECK.exponents[3] == -1  # Th
    assert SEEBECK.exponents[5] == -1  # I


def test_mobility_exponents_are_m2_per_v_s():
    """mu = m^2/(V.s) = L^2/(V.s) = M^-1 T^2 I. The alternative guess
    (0,0,1,0,0,1,-1) is wrong (that is L T^-1 I J^-1, not a mobility)."""
    from omai.operator.dimensions import MOBILITY, TIME, VOLTAGE
    from omai.operator.dimensions import LENGTH

    assert MOBILITY.exponents == (-1, 0, 2, 0, 0, 1, 0)
    assert MOBILITY.canonical() == "M^-1 T^2 I^1"
    # L^2 / (V . s) reproduces MOBILITY exactly.
    assert ((LENGTH ** 2) / (VOLTAGE * TIME)).exponents == MOBILITY.exponents
    # NOT the wrong guess.
    assert MOBILITY.exponents != (0, 0, 1, 0, 0, 1, -1)


def test_v_per_k_and_muv_per_k_factor():
    """v_per_k is canonical (to_operator 1.0); muv_per_k carries 1e-6 (amset
    multiplies the raw V/K by 1e6)."""
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["v_per_k"].to_operator == 1.0
    assert UNITS["muv_per_k"].to_operator == 1e-6
    assert abs(conversion_factor("muv_per_k", "v_per_k") - 1e-6) < 1e-18
    assert abs(conversion_factor("v_per_k", "muv_per_k") - 1e6) < 1e-6


def test_m2_per_v_s_and_cm2_per_v_s_factor():
    """m2_per_v_s is canonical (to_operator 1.0); cm2_per_v_s carries 1e-4."""
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["m2_per_v_s"].to_operator == 1.0
    assert UNITS["cm2_per_v_s"].to_operator == 1e-4
    assert abs(conversion_factor("cm2_per_v_s", "m2_per_v_s") - 1e-4) < 1e-16


# --------------------------------------------------------------------------
# The carrier family: two ElectricalConductivity nodes, same tag, different
# carrier labels, different uids.
# --------------------------------------------------------------------------

def test_electronic_and_ionic_conductivity_are_one_family_distinct_nodes():
    """ElectricalConductivity[carrier=electronic] and [carrier=ionic] share the
    electrical_conductivity tag AND the ELECTRICAL_CONDUCTIVITY dimension, and
    differ only by the carrier label, so they are one family (one quantity, one
    dimension) but distinct nodes (distinct uids)."""
    from omai.operator.dimensions import ELECTRICAL_CONDUCTIVITY
    from omai.operator.identity import node_id as _nid, node_identity
    from omai.electronic_transport.operator.nodes import (
        ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    )
    from omai.materials.operator.nodes import ELECTRICAL_CONDUCTIVITY_IONIC

    e = ELECTRICAL_CONDUCTIVITY_ELECTRONIC
    i = ELECTRICAL_CONDUCTIVITY_IONIC
    # Same dimension.
    assert e.field("sigma").dimension == ELECTRICAL_CONDUCTIVITY
    assert i.field("sigma").dimension == ELECTRICAL_CONDUCTIVITY
    # Same quantity tag.
    assert node_identity(e)["quantity"] == "electrical_conductivity"
    assert node_identity(i)["quantity"] == "electrical_conductivity"
    # Different carrier labels.
    assert node_identity(e)["labels"] == {"carrier": "electronic"}
    assert node_identity(i)["labels"] == {"carrier": "ionic"}
    # Different uids: the carrier label alone distinguishes them.
    assert _nid(e) != _nid(i)


def test_electronic_conductivity_reuses_the_registered_carrier_label():
    """carrier=electronic is a registered LABEL_KEY value; the node re-mints
    nothing (the config-thermo landing registered the key and the dimension)."""
    from omai.operator.registry import LABEL_KEYS, QUANTITY_TAGS

    assert "electronic" in LABEL_KEYS["carrier"]
    assert "electrical_conductivity" in QUANTITY_TAGS


# --------------------------------------------------------------------------
# The kappa firewall: electronic reuses the dimension, own tag, distinct uid.
# --------------------------------------------------------------------------

def test_electronic_kappa_shares_dimension_but_is_a_distinct_node():
    """ElectronicThermalConductivity reuses the THERMAL_CONDUCTIVITY dimension
    of the lattice family but carries its own electronic_thermal_conductivity
    tag, so it is a distinct node from every lattice kappa: the mandatory
    firewall (kappa_total = lattice + electronic)."""
    from omai.operator.dimensions import THERMAL_CONDUCTIVITY
    from omai.operator.identity import node_id as _nid, node_identity
    from omai.electronic_transport.operator.nodes import (
        ELECTRONIC_THERMAL_CONDUCTIVITY,
    )
    from omai.thermal_transport.operator.nodes import THERMAL_CONDUCTIVITY_RTA

    ke = ELECTRONIC_THERMAL_CONDUCTIVITY
    assert ke.field("kappa_e").dimension == THERMAL_CONDUCTIVITY
    assert node_identity(ke)["quantity"] == "electronic_thermal_conductivity"
    # Distinct quantity tag from the lattice family (which is thermal_conductivity).
    assert (node_identity(THERMAL_CONDUCTIVITY_RTA)["quantity"]
            == "thermal_conductivity")
    assert _nid(ke) != _nid(THERMAL_CONDUCTIVITY_RTA)


# --------------------------------------------------------------------------
# StaticDielectricTensor: a third distinct dielectric quantity.
# --------------------------------------------------------------------------

def test_static_dielectric_is_distinct_from_the_electronic_dielectric():
    """StaticDielectricTensor (eps_0) shares the DIMENSIONLESS rank-2 (alpha,
    beta) shape with DielectricTensor (eps_inf) but is a distinct node by its
    static_dielectric_tensor quantity tag, and sits in the Sources tier."""
    from omai.operator.identity import node_id as _nid, node_identity
    from omai.electronic_transport.operator.nodes import STATIC_DIELECTRIC_TENSOR
    from omai.thermal_transport.operator.nodes import DIELECTRIC_TENSOR

    assert node_identity(STATIC_DIELECTRIC_TENSOR)["quantity"] \
        == "static_dielectric_tensor"
    assert _nid(STATIC_DIELECTRIC_TENSOR) != _nid(DIELECTRIC_TENSOR)
    assert STATIC_DIELECTRIC_TENSOR.tier == "Sources"
    # Same index signature (Cartesian alpha, beta).
    assert STATIC_DIELECTRIC_TENSOR.field("epsilon_0").indices == ("alpha", "beta")


# --------------------------------------------------------------------------
# Edge wiring, schemes, and the boundary auto-parametrization (implicit /
# SKIPPED at the dimensional gate).
# --------------------------------------------------------------------------

def test_electronic_transport_edges_wiring_and_schemes():
    from omai.electronic_transport.operator.edges import (
        compute_carrier_mobility,
        compute_electronic_conductivity,
        compute_electronic_thermal_conductivity,
        compute_seebeck,
        compute_static_dielectric,
    )

    transport_inputs = [
        "Structure", "StaticDielectricTensor", "ElasticConstants", "Frequency"]
    transport_schemes = {
        "method": "bte_ibte", "scattering": "adp_imp_pop",
        "interpolation": "boltztrap2"}
    wiring = {
        compute_static_dielectric: (
            ["DielectricTensor", "BornCharges", "Frequency"],
            ["StaticDielectricTensor"],
            {"method": "ionic_contribution"}),
        compute_electronic_conductivity: (
            transport_inputs, ["ElectricalConductivity[carrier=electronic]"],
            transport_schemes),
        compute_seebeck: (
            transport_inputs, ["SeebeckCoefficient"], transport_schemes),
        compute_electronic_thermal_conductivity: (
            transport_inputs, ["ElectronicThermalConductivity"],
            transport_schemes),
        compute_carrier_mobility: (
            transport_inputs, ["CarrierMobility"], transport_schemes),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_electronic_transport_edges_are_implicit_and_skipped():
    """All five new edges carry opaque solver functions, so the dimensional
    gate classifies them SKIPPED; none is a violation and the two pinned
    schematic violations stay the only ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_static_dielectric", "compute_electronic_conductivity",
                 "compute_seebeck", "compute_electronic_thermal_conductivity",
                 "compute_carrier_mobility"):
        assert name in report["skipped"], (name, report)
    assert all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_electronic_transport_edges_are_not_sympy_executable():
    from omai.electronic_transport.operator.edges import EDGES

    for op in EDGES:
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy


def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


# --------------------------------------------------------------------------
# The contribution passes the P4 gates (connectivity through pre-existing nodes
# plus the intra-contribution compute_static_dielectric chain).
# --------------------------------------------------------------------------

def test_contribution_is_connected_through_pre_existing_and_chained_nodes():
    """The five nodes + five edges are one weakly connected component: the four
    transport edges share StaticDielectricTensor (produced here) and touch the
    pre-existing Structure / ElasticConstants / Frequency, while
    compute_static_dielectric chains in through DielectricTensor / BornCharges /
    Frequency."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id as _eid,
        edge_identity,
        node_id as _nid,
        node_identity,
    )
    from omai.electronic_transport.operator.edges import (
        compute_carrier_mobility,
        compute_electronic_conductivity,
        compute_electronic_thermal_conductivity,
        compute_seebeck,
        compute_static_dielectric,
    )
    from omai.electronic_transport.operator.nodes import (
        CARRIER_MOBILITY,
        ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
        ELECTRONIC_THERMAL_CONDUCTIVITY,
        SEEBECK_COEFFICIENT,
        STATIC_DIELECTRIC_TENSOR,
    )
    from omai.mechanics.operator.nodes import ELASTIC_CONSTANTS
    from omai.materials.operator.shared_primitives import STRUCTURE
    from omai.thermal_transport.operator.nodes import (
        BORN_CHARGES,
        DIELECTRIC_TENSOR,
        FREQUENCY_STATE,
    )

    records = []
    for s in (STATIC_DIELECTRIC_TENSOR, ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
              SEEBECK_COEFFICIENT, ELECTRONIC_THERMAL_CONDUCTIVITY,
              CARRIER_MOBILITY):
        records.append({
            "op": "add_node",
            "payload": {"uid": _nid(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    for op in (compute_static_dielectric, compute_electronic_conductivity,
               compute_seebeck, compute_electronic_thermal_conductivity,
               compute_carrier_mobility):
        records.append({
            "op": "add_edge",
            "payload": {"uid": _eid(op, _nid),
                        "identity": edge_identity(op, _nid),
                        "meta": {"name": op.name, "schemes": op.schemes}},
        })
    current = {"nodes": {}, "edges": {}}
    for s in (DIELECTRIC_TENSOR, BORN_CHARGES, FREQUENCY_STATE, STRUCTURE,
              ELASTIC_CONSTANTS):
        current["nodes"][_nid(s)] = {
            "uid": _nid(s), "identity": node_identity(s), "meta": {}}
    assert validate_contribution(records, current) == []


# --------------------------------------------------------------------------
# The amset rail.
# --------------------------------------------------------------------------

def test_amset_rail_covers_the_five_nodes_with_units():
    codes = build_codes(DOMAINS)
    amset = codes["amset"]
    assert set(amset) == {
        "StaticDielectricTensor",
        "ElectricalConductivity[carrier=electronic]",
        "SeebeckCoefficient",
        "ElectronicThermalConductivity",
        "CarrierMobility",
    }
    assert amset["ElectricalConductivity[carrier=electronic]"]["unit"] == "s_per_m"
    assert amset["SeebeckCoefficient"]["unit"] == "muv_per_k"
    assert amset["ElectronicThermalConductivity"]["unit"] == "W_per_m_per_K"
    assert amset["CarrierMobility"]["unit"] == "cm2_per_v_s"
    assert amset["StaticDielectricTensor"]["unit"] == "dimensionless"


# --------------------------------------------------------------------------
# The graph placement and the committed store.
# --------------------------------------------------------------------------

def test_new_nodes_carry_their_tiers_and_the_new_tier_is_registered():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["StaticDielectricTensor"] == "Sources"
    for n in ("ElectricalConductivity[carrier=electronic]", "SeebeckCoefficient",
              "ElectronicThermalConductivity", "CarrierMobility"):
        assert tier_of[n] == "Electronic transport"
    assert "Electronic transport" in {t["name"] for t in g["tiers"]}


def test_committed_store_contains_the_contribution():
    from pathlib import Path

    from omai.store import Store
    from omai.electronic_transport.operator.edges import (
        compute_carrier_mobility,
        compute_electronic_conductivity,
        compute_electronic_thermal_conductivity,
        compute_seebeck,
        compute_static_dielectric,
    )
    from omai.electronic_transport.operator.nodes import (
        CARRIER_MOBILITY,
        ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
        ELECTRONIC_THERMAL_CONDUCTIVITY,
        SEEBECK_COEFFICIENT,
        STATIC_DIELECTRIC_TENSOR,
    )

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in (STATIC_DIELECTRIC_TENSOR, ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
              SEEBECK_COEFFICIENT, ELECTRONIC_THERMAL_CONDUCTIVITY,
              CARRIER_MOBILITY):
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in (compute_static_dielectric, compute_electronic_conductivity,
               compute_seebeck, compute_electronic_thermal_conductivity,
               compute_carrier_mobility):
        assert edge_id(op, node_id) in m["edges"], \
            f"store missing edge {op.name}"


def test_electronic_transport_is_records_154_to_163():
    """The frozen log positions: records 154-163 are the five nodes then the
    five edges (add_node * 5 + add_edge * 5). Positions are history and never
    move; records 148-153 (the config-thermo contribution) stay untouched
    above."""
    import json
    from pathlib import Path

    from omai.electronic_transport.operator.edges import (
        compute_carrier_mobility,
        compute_electronic_conductivity,
        compute_electronic_thermal_conductivity,
        compute_seebeck,
        compute_static_dielectric,
    )
    from omai.electronic_transport.operator.nodes import (
        CARRIER_MOBILITY,
        ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
        ELECTRONIC_THERMAL_CONDUCTIVITY,
        SEEBECK_COEFFICIENT,
        STATIC_DIELECTRIC_TENSOR,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 163, "the electronic-transport contribution has not landed"

    node_uids = [
        node_id(STATIC_DIELECTRIC_TENSOR),
        node_id(ELECTRICAL_CONDUCTIVITY_ELECTRONIC),
        node_id(SEEBECK_COEFFICIENT),
        node_id(ELECTRONIC_THERMAL_CONDUCTIVITY),
        node_id(CARRIER_MOBILITY),
    ]
    edge_uids = [
        edge_id(compute_static_dielectric, node_id),
        edge_id(compute_electronic_conductivity, node_id),
        edge_id(compute_seebeck, node_id),
        edge_id(compute_electronic_thermal_conductivity, node_id),
        edge_id(compute_carrier_mobility, node_id),
    ]
    recs = [json.loads(line) for line in lines[153:163]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 5 + ["add_edge"] * 5
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "electronic transport from the amset scan" in r["reason"]
