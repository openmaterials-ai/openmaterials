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


# --------------------------------------------------------------------------
# Task 3: the QE representation (pw.x energy, forces, stress, structure).
# --------------------------------------------------------------------------

def test_build_codes_qe_covers_13_including_the_ground_state():
    from omai.map_data import build_codes

    qe = build_codes(DOMAINS)["qe"]
    assert len(qe) == 13
    for name in ("Structure", "TotalEnergy", "Forces", "Stress"):
        assert name in qe, f"qe coverage missing {name}"


def test_dft_representation_package_discovery_finds_the_specs():
    """Discovery mirrors build_codes / the boundary suite: walk the package's
    modules and collect spec instances by introspection. Four space specs plus
    one operator spec, all representation_name 'qe'."""
    import importlib
    import pkgutil

    import omai.dft_ground_state.representation as pkg
    from omai.representation.adapter import (
        OperatorRepresentationSpec,
        SpaceRepresentationSpec,
    )

    space_specs, op_specs = [], []
    for info in sorted(pkgutil.iter_modules(pkg.__path__)):
        mod = importlib.import_module(
            f"omai.dft_ground_state.representation.{info.name}")
        for attr in sorted(dir(mod)):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if isinstance(obj, SpaceRepresentationSpec):
                space_specs.append((attr, obj))
            elif isinstance(obj, OperatorRepresentationSpec):
                op_specs.append((attr, obj))
    assert len(space_specs) == 4, [a for a, _ in space_specs]
    assert len(op_specs) == 1, [a for a, _ in op_specs]
    assert {s.space.name for _, s in space_specs} == {
        "Structure", "TotalEnergy", "Forces", "Stress"}
    assert op_specs[0][1].operator.name == "solve_ground_state"
    for _, s in space_specs:
        assert s.representation_name == "qe"
    assert op_specs[0][1].representation_name == "qe"


def test_qe_ground_state_units_are_the_declared_ones():
    from omai.dft_ground_state.representation.qe import (
        QE_FORCES,
        QE_STRESS,
        QE_STRUCTURE,
        QE_TOTAL_ENERGY,
    )

    assert QE_TOTAL_ENERGY.observable_units == {"E_tot": "ry"}
    assert QE_FORCES.observable_units == {"F": "Ry_per_bohr"}
    assert QE_STRESS.observable_units == {"sigma": "kbar"}
    # Structure is opaque: an artifact (input cards), never a numeric unit.
    assert QE_STRUCTURE.observable_units == {}


def test_qe_stress_notes_record_the_verified_sign_convention_with_anchors():
    """The stress sign convention comes from READING the vendored q-e source,
    never assumed: the notes must state the convention (positive diagonal =
    compressive, the pressure convention) and carry file:line anchors into
    PW/src/stress.f90 and the cell-force code that fixes the sign."""
    from omai.dft_ground_state.representation.qe import QE_STRESS

    notes = QE_STRESS.notes
    assert "compressive" in notes
    assert "stress.f90" in notes
    assert "cell_base.f90" in notes


def test_qe_solve_ground_state_declares_the_scf_discretizations():
    from omai.dft_ground_state.representation.qe import QE_SOLVE_GROUND_STATE

    for key in ("ecutwfc", "k_mesh", "smearing", "conv_thr",
                "pseudopotentials"):
        assert key in QE_SOLVE_GROUND_STATE.discretization_choices, key


# --------------------------------------------------------------------------
# Task 4: the contribution landed in the committed store through the gates.
# --------------------------------------------------------------------------

def test_committed_store_contains_the_dft_contribution():
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.store import Store
    from omai.dft_ground_state.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in NODES:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in EDGES:
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_dft_contribution_is_records_102_to_108_after_the_symbol_edit():
    """The frozen log positions of the first two post-genesis contributions:
    record 101 stays the BareDynamicalMatrix symbol edit_meta, and this
    domain's seven adds are records 102-108 (4 nodes then 3 edges, in NODES /
    EDGES order), authored through sync --apply. Positions are history and
    never move; the log may grow past 108 with later contributions."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.thermal_transport.operator.nodes import BARE_DYNAMICAL_MATRIX
    from omai.dft_ground_state.operator import EDGES, NODES

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 108, "the dft contribution has not landed"

    rec_101 = json.loads(lines[100])
    assert rec_101["op"] == "edit_meta"
    assert rec_101["payload"]["uid"] == node_id(BARE_DYNAMICAL_MATRIX)

    domain_uids = [node_id(s) for s in NODES] + \
        [edge_id(op, node_id) for op in EDGES]
    recs = [json.loads(line) for line in lines[101:108]]
    assert [r["payload"]["uid"] for r in recs] == domain_uids
    assert [r["op"] for r in recs] == ["add_node"] * 4 + ["add_edge"] * 3
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-08"
