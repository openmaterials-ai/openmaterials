"""Tests for the nuclear-quantum-effects layer (Cookbook Slice 1, records 212-215).

The Atomistic Cookbook audit (scans/cookbook-audit.json, the i-PI slice) opens
the map's nuclear-quantum-effects (NQE) layer. This contribution lands, in the
thermal_transport domain's Molecular dynamics tier (no new tier):

  * QuantumKineticEnergy (tag quantum_kinetic_energy, ENERGY, scalar): the
    centroid-virial PIMD estimator of the nuclear quantum kinetic energy. A
    genuinely NEW node with no dimensional twin it could false-merge with.
  * HeatCapacity[method=pimd] (tag heat_capacity, ENERGY_PER_TEMPERATURE, scalar,
    label method=pimd): the PIMD scaled-coordinates (double-virial) estimator of
    C_V. A METHOD-TAGGED PRODUCER VARIANT of the existing harmonic HeatCapacity,
    kept a distinct node ONLY by the method label (the carrier-label precedent).

Two implicit sampling edges, both from the pre-existing (Trajectory, Temperature)
MD tier:
  * sample_quantum_kinetic_energy -> QuantumKineticEnergy, scheme
    {method: pimd, estimator: centroid_virial};
  * sample_quantum_heat_capacity -> HeatCapacity[method=pimd], scheme
    {method: pimd, estimator: double_virial}.

The i-pi rail (representation_name 'i-pi') is the sixth Trajectory producer.

Load-bearing proofs here:
  * the heat-capacity FAMILY: two HeatCapacity nodes, SAME heat_capacity tag, the
    method=pimd label distinguishing them, DISTINCT uids;
  * QuantumKineticEnergy shares ENERGY with the per-mode InternalEnergy but is a
    DISTINCT scalar node with a DISTINCT tag (no false-merge);
  * both sampling edges are implicit (not sympy-executable) and SKIPPED by the
    dimensional gate;
  * the i-pi rail is credits-clear (dual GPL/MIT) and serves both new nodes;
  * the frozen log positions: records 212-215.
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.map_data import DOMAINS, build_codes, build_graph_dict
from omai.operator.dimcheck import dimensional_report
from omai.operator.identity import edge_id, node_id, node_identity
from omai.operator.registry import LABEL_KEYS, QUANTITY_TAGS
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
# The registry: the method label key and the quantum_kinetic_energy tag.
# --------------------------------------------------------------------------

def test_method_label_key_registered_with_pimd():
    assert "method" in LABEL_KEYS
    assert "pimd" in LABEL_KEYS["method"]


def test_quantum_kinetic_energy_tag_registered():
    assert "quantum_kinetic_energy" in QUANTITY_TAGS


# --------------------------------------------------------------------------
# The two nodes: dimensions, indices, tiers, tags.
# --------------------------------------------------------------------------

def test_quantum_kinetic_energy_is_scalar_energy_md():
    from omai.operator.dimensions import ENERGY
    from omai.thermal_transport.operator.nodes import QUANTUM_KINETIC_ENERGY

    qke = QUANTUM_KINETIC_ENERGY
    assert qke.field("E_K").dimension == ENERGY
    assert qke.field("E_K").indices == ()
    assert qke.tier == "Molecular dynamics"
    assert node_identity(qke)["quantity"] == "quantum_kinetic_energy"
    assert node_identity(qke)["labels"] == {}


def test_heat_capacity_pimd_is_scalar_ept_md_with_method_label():
    from omai.operator.dimensions import ENERGY_PER_TEMPERATURE
    from omai.thermal_transport.operator.nodes import HEAT_CAPACITY_PIMD

    hcp = HEAT_CAPACITY_PIMD
    assert hcp.field("C_V").dimension == ENERGY_PER_TEMPERATURE
    assert hcp.field("C_V").indices == ()
    assert hcp.tier == "Molecular dynamics"
    assert node_identity(hcp)["quantity"] == "heat_capacity"
    assert node_identity(hcp)["labels"] == {"method": "pimd"}


# --------------------------------------------------------------------------
# The heat-capacity FAMILY (headline): two nodes, same tag, label distinguishes.
# --------------------------------------------------------------------------

def test_heat_capacity_family_same_tag_method_label_distinct_uids():
    """The map now carries TWO HeatCapacity nodes: the existing harmonic
    HeatCapacity (per-mode, no label) and the new HeatCapacity[method=pimd]
    (scalar, method=pimd). They share the SAME heat_capacity tag; the method
    label is the ONLY distinguisher; their uids are DISTINCT (the carrier-label /
    transport_model precedent, a producer variant with no re-mint)."""
    from omai.thermal_transport.operator.nodes import (
        HEAT_CAPACITY,
        HEAT_CAPACITY_PIMD,
    )

    hc = HEAT_CAPACITY
    hcp = HEAT_CAPACITY_PIMD

    # (1) Same tag.
    assert node_identity(hc)["quantity"] == "heat_capacity"
    assert node_identity(hcp)["quantity"] == "heat_capacity"

    # (2) Same dimension (ENERGY_PER_TEMPERATURE).
    assert hc.field("c").dimension == hcp.field("C_V").dimension

    # (3) The method label is the only distinguisher.
    assert node_identity(hc)["labels"] == {}
    assert node_identity(hcp)["labels"] == {"method": "pimd"}

    # (4) Distinct uids: the label makes them separate nodes.
    assert node_id(hc) != node_id(hcp)


def test_quantum_kinetic_energy_does_not_false_merge_with_internal_energy():
    """QuantumKineticEnergy shares the ENERGY dimension with the per-mode
    InternalEnergy (the harmonic Bose-Einstein occupation energy), but they are
    DIFFERENT quantities: distinct tags, distinct uids, and different argument
    structure (scalar PIMD estimator vs (q, nu)-indexed harmonic per-mode)."""
    from omai.thermal_transport.operator.nodes import (
        INTERNAL_ENERGY,
        QUANTUM_KINETIC_ENERGY,
    )

    qke = QUANTUM_KINETIC_ENERGY
    ie = INTERNAL_ENERGY

    # Same dimension.
    assert qke.field("E_K").dimension == ie.field("e").dimension
    # Distinct tags.
    assert node_identity(qke)["quantity"] == "quantum_kinetic_energy"
    assert node_identity(ie)["quantity"] == "internal_energy"
    # Distinct uids.
    assert node_id(qke) != node_id(ie)
    # Different argument structure: scalar vs per-mode.
    assert qke.field("E_K").indices == ()
    assert ie.field("e").indices == ("q", "nu")


# --------------------------------------------------------------------------
# The edges: wiring, schemes, implicit / skipped.
# --------------------------------------------------------------------------

def test_sampling_edges_wiring_and_schemes():
    from omai.thermal_transport.operator.edges import (
        sample_quantum_heat_capacity,
        sample_quantum_kinetic_energy,
    )

    assert [s.name for s in sample_quantum_kinetic_energy.inputs] == [
        "Trajectory", "Temperature"]
    assert [o.name for o in sample_quantum_kinetic_energy.outputs] == [
        "QuantumKineticEnergy"]
    assert sample_quantum_kinetic_energy.schemes == {
        "method": "pimd", "estimator": "centroid_virial"}

    assert [s.name for s in sample_quantum_heat_capacity.inputs] == [
        "Trajectory", "Temperature"]
    assert [o.name for o in sample_quantum_heat_capacity.outputs] == [
        "HeatCapacity[method=pimd]"]
    assert sample_quantum_heat_capacity.schemes == {
        "method": "pimd", "estimator": "double_virial"}


def test_sampling_edges_are_implicit_and_skipped():
    """Both estimators are ensemble averages over the ring-polymer beads (opaque
    applied functions of the sampled Trajectory and the Temperature), so neither
    is sympy-executable and the dimensional gate SKIPS both."""
    from omai.thermal_transport.operator.edges import (
        sample_quantum_heat_capacity,
        sample_quantum_kinetic_energy,
    )

    for op in (sample_quantum_kinetic_energy, sample_quantum_heat_capacity):
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy

    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    assert "sample_quantum_kinetic_energy" in report["skipped"]
    assert "sample_quantum_heat_capacity" in report["skipped"]
    assert all("quantum_kinetic_energy" not in v for v in report["violation"])


# --------------------------------------------------------------------------
# The DAG gate, graph placement.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_new_nodes_carry_their_tier_in_the_graph():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["QuantumKineticEnergy"] == "Molecular dynamics"
    assert tier_of["HeatCapacity[method=pimd]"] == "Molecular dynamics"


# --------------------------------------------------------------------------
# The i-pi rail: coverage, units, credits.
# --------------------------------------------------------------------------

def test_ipi_rail_covers_the_nqe_layer():
    codes = build_codes(DOMAINS)
    assert "i-pi" in codes
    ipi = codes["i-pi"]
    assert set(ipi) == {
        "Temperature", "Trajectory",
        "QuantumKineticEnergy", "HeatCapacity[method=pimd]"}
    assert ipi["QuantumKineticEnergy"]["unit"] == "ev"
    assert ipi["HeatCapacity[method=pimd]"]["unit"] == "eV_per_K"
    assert ipi["Temperature"]["unit"] == "kelvin"


def test_ipi_rail_is_credits_clear():
    """The credits enforcement (Giuseppe's rule): the i-pi rail carries a
    citation, a DOI, and its dual GPL/MIT license, flowing into codes.json."""
    from omai.representation.credits import CODE_CREDITS

    cr = CODE_CREDITS["i-pi"]
    assert cr["doi"] == "10.1063/5.0215869"
    assert "Litman" in cr["citation"]
    assert "062504" in cr["citation"]
    assert "GPL" in cr["license"] and "MIT" in cr["license"]
    assert cr["url"] == "https://ipi-code.org"
    assert (cr.get("license_source") or "").strip()

    codes = build_codes(DOMAINS)
    for space, entry in codes["i-pi"].items():
        assert entry["license"] == cr["license"], space
        assert entry["citation"] == cr["citation"], space
        assert entry["license"] != "UNKNOWN", space


# --------------------------------------------------------------------------
# The committed store and the frozen log positions (records 212-215).
# --------------------------------------------------------------------------

def test_committed_store_contains_the_contribution():
    from omai.store import Store
    from omai.thermal_transport.operator.edges import (
        sample_quantum_heat_capacity,
        sample_quantum_kinetic_energy,
    )
    from omai.thermal_transport.operator.nodes import (
        HEAT_CAPACITY_PIMD,
        QUANTUM_KINETIC_ENERGY,
    )

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in (QUANTUM_KINETIC_ENERGY, HEAT_CAPACITY_PIMD):
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in (sample_quantum_kinetic_energy, sample_quantum_heat_capacity):
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_nqe_layer_is_records_212_to_215():
    """The frozen log positions: records 212-215 are the two nodes then the two
    edges (add_node * 2 + add_edge * 2), in the sync walk order (NODES order then
    EDGES order within the thermal_transport domain: QuantumKineticEnergy,
    HeatCapacity[method=pimd]; then sample_quantum_kinetic_energy,
    sample_quantum_heat_capacity). Positions are history and never move; records
    1-211 stay untouched."""
    from omai.thermal_transport.operator.edges import (
        sample_quantum_heat_capacity,
        sample_quantum_kinetic_energy,
    )
    from omai.thermal_transport.operator.nodes import (
        HEAT_CAPACITY_PIMD,
        QUANTUM_KINETIC_ENERGY,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 215, "the NQE-layer contribution has not landed"

    node_uids = [node_id(QUANTUM_KINETIC_ENERGY), node_id(HEAT_CAPACITY_PIMD)]
    edge_uids = [
        edge_id(sample_quantum_kinetic_energy, node_id),
        edge_id(sample_quantum_heat_capacity, node_id),
    ]
    recs = [json.loads(line) for line in lines[211:215]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 2 + ["add_edge"] * 2
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-11"
        assert "nuclear-quantum-effects" in r["reason"]
