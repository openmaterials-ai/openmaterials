"""Tests for the DFT ground-state domain (Tasks 2-5).

The dft_ground_state domain adds four ObservableSpace nodes (Structure entering
from shared_primitives, plus the new TotalEnergy, Forces, Stress) and three
edges (solve_ground_state, compute_forces_hf, compute_stress_cell) to the
unified map. Structure keeps the Sources tier; the three new quantities form the
"Ground state" tier, which renders after Molecular dynamics and before Diffusion.
"""
from __future__ import annotations

from omai.map_data import DOMAINS, build_graph_dict
from omai.operator.dimcheck import dimensional_report
from omai.operator.identity import node_id
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
# The domain descriptor and its wiring into DOMAINS.
# --------------------------------------------------------------------------

def test_dft_domain_in_domains_between_thermal_and_materials():
    names = [d.name for d in DOMAINS]
    assert names == ["thermal_transport", "dft_ground_state", "materials"]


def test_dft_domain_declares_ground_state_tier():
    from omai.dft_ground_state.domain import DFT_GROUND_STATE

    tier_names = [t[0] for t in DFT_GROUND_STATE.tiers]
    assert tier_names == ["Ground state"]


def test_dft_nodes_are_structure_total_energy_forces_stress():
    from omai.dft_ground_state.operator import NODES

    assert [s.name for s in NODES] == [
        "Structure", "TotalEnergy", "Forces", "Stress"]


def test_dft_edges_are_the_three_ground_state_operators():
    from omai.dft_ground_state.operator import EDGES

    assert [op.name for op in EDGES] == [
        "solve_ground_state", "compute_forces_hf", "compute_stress_cell"]


def test_structure_is_imported_from_shared_primitives():
    from omai.dft_ground_state.operator.nodes import STRUCTURE
    from omai.materials.operator.shared_primitives import STRUCTURE as SHARED

    assert STRUCTURE is SHARED
    assert STRUCTURE.tier == "Sources"


# --------------------------------------------------------------------------
# The gates the domain must pass at the operator layer.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_hellmann_feynman_and_stress_are_dimensionally_ok():
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    assert "compute_forces_hf" in report["ok"], report
    assert "compute_stress_cell" in report["ok"], report
    # No new violations anywhere.
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_no_node_uid_collisions_at_55_nodes():
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) == 55
    uids = [n["uid"] for n in g["nodes"]]
    assert len(set(uids)) == len(uids), "node uid collision"


# --------------------------------------------------------------------------
# The unified graph: tier order and node placement.
# --------------------------------------------------------------------------

def test_ground_state_tier_ordered_after_md_before_diffusion():
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Ground state" in tier_names
    i = tier_names.index("Ground state")
    assert tier_names[i - 1] == "Molecular dynamics"
    assert tier_names[i + 1] == "Diffusion"


def test_ground_state_nodes_carry_the_tier_and_structure_in_sources():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["TotalEnergy"] == "Ground state"
    assert tier_of["Forces"] == "Ground state"
    assert tier_of["Stress"] == "Ground state"
    assert tier_of["Structure"] == "Sources"


# --------------------------------------------------------------------------
# Registry conformance of every new node (the P4 registry gate reads these).
# --------------------------------------------------------------------------

def test_new_nodes_validate_against_the_registries():
    from omai.gates import validate_contribution
    from omai.genesis import genesis_records

    # The add_node records the genesis builder emits for the new nodes must
    # pass the registry / gauge gates in isolation (tag registered, index kinds
    # registered, gauge class well-formed).
    from omai.operator.identity import node_identity
    from omai.dft_ground_state.operator import NODES

    new_names = {"TotalEnergy", "Forces", "Stress"}
    records = []
    for s in NODES:
        if s.name in new_names:
            records.append({
                "op": "add_node",
                "payload": {"uid": node_id(s), "identity": node_identity(s),
                            "meta": {"name": s.name}},
            })
    # Only the registry + gauge gates are relevant in isolation; connectivity
    # would (correctly) complain about bare nodes, so filter to those prefixes.
    problems = validate_contribution(records, {"nodes": {}, "edges": {}})
    reg_gauge = [p for p in problems
                 if p.startswith("[registry]") or p.startswith("[gauge]")]
    assert reg_gauge == [], reg_gauge
