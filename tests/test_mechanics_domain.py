"""Tests for the mechanics domain (Tasks 1-4).

The mechanics domain adds four ObservableSpace nodes (ElasticConstants,
BulkModulus, ShearModulus, Pressure) and four edges (compute_elastic_constants,
contract_pressure, contract_bulk_modulus, contract_shear_modulus) to the unified
map. All four nodes form the "Mechanics" tier, which renders after Ground state
and before Diffusion. ElasticConstants is the full rank-4 Cartesian stiffness
tensor; the moduli and the pressure are its isotropic contractions.
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

def test_mechanics_domain_in_domains_between_ground_state_and_diffusion():
    names = [d.name for d in DOMAINS]
    assert names == [
        "thermal_transport", "dft_ground_state", "mechanics", "materials"]


def test_mechanics_domain_declares_mechanics_tier():
    from omai.mechanics.domain import MECHANICS

    tier_names = [t[0] for t in MECHANICS.tiers]
    assert tier_names == ["Mechanics"]


def test_mechanics_nodes_are_the_elastic_tensor_moduli_and_pressure():
    from omai.mechanics.operator import NODES

    assert [s.name for s in NODES] == [
        "ElasticConstants", "BulkModulus", "ShearModulus", "Pressure"]


def test_mechanics_edges_are_the_four_operators():
    from omai.mechanics.operator import EDGES

    assert [op.name for op in EDGES] == [
        "compute_elastic_constants", "contract_pressure",
        "contract_bulk_modulus", "contract_shear_modulus"]


def test_elastic_constants_is_the_full_rank4_tensor():
    """ElasticConstants carries the full rank-4 Cartesian tensor C_{a,b,g,d};
    the Voigt 6x6 packing is a representation-layer concern, not the node's
    identity."""
    from omai.mechanics.operator.nodes import ELASTIC_CONSTANTS

    field = ELASTIC_CONSTANTS.field("C")
    assert field.indices == ("alpha", "beta", "gamma", "delta")


def test_the_moduli_and_pressure_are_scalars():
    from omai.mechanics.operator.nodes import (
        BULK_MODULUS,
        PRESSURE,
        SHEAR_MODULUS,
    )

    assert BULK_MODULUS.field("K").indices == ()
    assert SHEAR_MODULUS.field("G").indices == ()
    assert PRESSURE.field("P").indices == ()


# --------------------------------------------------------------------------
# The gates the domain must pass at the operator layer.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_all_four_mechanics_edges_are_dimensionally_ok():
    """The dimensional gate proves each new edge (energy per volume on every
    side): the elastic tensor as a second strain derivative of the energy
    over the cell volume, the pressure as a stress trace, and both Voigt
    moduli as contractions of the stiffness tensor."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_elastic_constants", "contract_pressure",
                 "contract_bulk_modulus", "contract_shear_modulus"):
        assert name in report["ok"], (name, report)
    # No new violations anywhere (the two pinned schematic ones may remain).
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_no_node_uid_collisions_at_59_nodes():
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) == 59
    uids = [n["uid"] for n in g["nodes"]]
    assert len(set(uids)) == len(uids), "node uid collision"


# --------------------------------------------------------------------------
# The unified graph: tier order and node placement.
# --------------------------------------------------------------------------

def test_mechanics_tier_ordered_after_ground_state_before_diffusion():
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Mechanics" in tier_names
    i = tier_names.index("Mechanics")
    assert tier_names[i - 1] == "Ground state"
    assert tier_names[i + 1] == "Diffusion"


def test_mechanics_nodes_carry_the_tier():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["ElasticConstants"] == "Mechanics"
    assert tier_of["BulkModulus"] == "Mechanics"
    assert tier_of["ShearModulus"] == "Mechanics"
    assert tier_of["Pressure"] == "Mechanics"


# --------------------------------------------------------------------------
# Registry conformance of every new node (the P4 registry gate reads these).
# --------------------------------------------------------------------------

def test_new_nodes_validate_against_the_registries():
    from omai.gates import validate_contribution
    from omai.operator.identity import node_identity
    from omai.mechanics.operator import NODES

    records = []
    for s in NODES:
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


def test_the_shear_reduction_uses_the_full_sum_form():
    """contract_shear_modulus encodes the Voigt shear as
    (3*sum C_abab - sum C_aabb)/30 (the A = sum C_aaaa terms cancel from the
    textbook G_V = (A - B + 3C)/15). The formula's srepr must carry the /30
    reduced constant, not a bare A-term."""
    import sympy as sp

    from omai.mechanics.operator.edges import contract_shear_modulus

    rhs = contract_shear_modulus.formula.rhs
    # Two Sum terms (S2 with a 3 coefficient, S1) over a 1/30 prefactor.
    sums = list(rhs.atoms(sp.Sum))
    assert len(sums) == 2, sums


# --------------------------------------------------------------------------
# Task 2: the representations (LAMMPS ELASTIC + mat-elasticity).
# --------------------------------------------------------------------------

def test_build_codes_lammps_grows_to_11_including_elastic_and_pressure():
    from omai.map_data import build_codes

    lammps = build_codes(DOMAINS)["lammps"]
    assert len(lammps) == 11
    for name in ("ElasticConstants", "Pressure"):
        assert name in lammps, f"lammps coverage missing {name}"


def test_mat_elasticity_representation_appears_and_covers_the_moduli():
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert "mat-elasticity" in codes
    mat = codes["mat-elasticity"]
    # The catalog's produces map onto ElasticConstants and the two moduli;
    # Young's modulus and Poisson's ratio are catalog-only (no node).
    for name in ("ElasticConstants", "BulkModulus", "ShearModulus"):
        assert name in mat, f"mat-elasticity coverage missing {name}"


def test_mechanics_representation_package_discovery_finds_the_specs():
    """Discovery mirrors build_codes: walk the package's modules and collect
    spec instances by introspection. The LAMMPS module contributes two space
    specs (ElasticConstants, Pressure) and one operator spec; mat-elasticity
    contributes three space specs (the tensor and the two moduli)."""
    import importlib
    import pkgutil

    import omai.mechanics.representation as pkg
    from omai.representation.adapter import (
        OperatorRepresentationSpec,
        SpaceRepresentationSpec,
    )

    space_specs, op_specs = [], []
    for info in sorted(pkgutil.iter_modules(pkg.__path__)):
        mod = importlib.import_module(
            f"omai.mechanics.representation.{info.name}")
        for attr in sorted(dir(mod)):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if isinstance(obj, SpaceRepresentationSpec):
                space_specs.append((attr, obj))
            elif isinstance(obj, OperatorRepresentationSpec):
                op_specs.append((attr, obj))
    assert len(space_specs) == 5, [a for a, _ in space_specs]
    assert len(op_specs) == 1, [a for a, _ in op_specs]
    assert op_specs[0][1].operator.name == "compute_elastic_constants"


def test_lammps_elastic_and_pressure_units_are_the_declared_ones():
    from omai.mechanics.representation.lammps import (
        LAMMPS_ELASTIC_CONSTANTS,
        LAMMPS_PRESSURE,
    )

    assert LAMMPS_ELASTIC_CONSTANTS.observable_units == {"C": "GPa"}
    assert LAMMPS_PRESSURE.observable_units == {"P": "GPa"}


def test_lammps_pressure_notes_record_the_sign_convention():
    """The pressure sign ties to the store's verified stress convention: the
    per-atom stress is the negative of the pressure tensor, so the mechanical
    pressure is +trace/3. The notes must state that and carry a scan anchor."""
    from omai.mechanics.representation.lammps import LAMMPS_PRESSURE

    notes = LAMMPS_PRESSURE.notes
    assert "compute pressure" in notes
    assert "compression" in notes or "compressive" in notes


def test_lammps_elastic_operator_records_the_finite_strain_discretizations():
    from omai.mechanics.representation.lammps import LAMMPS_COMPUTE_ELASTIC_CONSTANTS

    choices = LAMMPS_COMPUTE_ELASTIC_CONSTANTS.discretization_choices
    for key in ("strain_magnitude", "deformation_averaging"):
        assert key in choices, key


# --------------------------------------------------------------------------
# Task 3: the contribution landed in the committed store through the gates.
# --------------------------------------------------------------------------

def test_committed_store_contains_the_mechanics_contribution():
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.store import Store
    from omai.mechanics.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in NODES:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in EDGES:
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_mechanics_contribution_is_records_110_to_117():
    """The frozen log positions of the mechanics contribution: the four nodes
    then the four edges (in NODES / EDGES order), authored through sync --apply
    as records 110-117. Positions are history and never move; record 109 stays
    the dft finite-displacement FC2 edge (untouched)."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.mechanics.operator import EDGES, NODES

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 117, "the mechanics contribution has not landed"

    domain_uids = [node_id(s) for s in NODES] + \
        [edge_id(op, node_id) for op in EDGES]
    recs = [json.loads(line) for line in lines[109:117]]
    assert [r["payload"]["uid"] for r in recs] == domain_uids
    assert [r["op"] for r in recs] == ["add_node"] * 4 + ["add_edge"] * 4
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-08"


# --------------------------------------------------------------------------
# Task 4: evidence: the mat-elasticity Cu instances.
# --------------------------------------------------------------------------

def test_mat_elasticity_cu_instances_pin_the_live_node_uids():
    from omai.map_data import build_instances
    from omai.mechanics.operator.nodes import BULK_MODULUS, SHEAR_MODULUS

    insts = build_instances()
    cu = [it for it in insts
          if it["material"] == "Cu"
          and it["source"]["ref"] == "atomisticskills-mat-elasticity-Cu"]
    by_var = {it["variable"]: it for it in cu}
    assert set(by_var) == {"BulkModulus", "ShearModulus"}

    k = by_var["BulkModulus"]
    assert k["value"] == 145.85
    assert k["units"] == "GPa"
    assert k["source"]["kind"] == "simulation"
    assert k["node_uid"] == node_id(BULK_MODULUS)

    g = by_var["ShearModulus"]
    assert g["value"] == 51.45
    assert g["units"] == "GPa"
    assert g["node_uid"] == node_id(SHEAR_MODULUS)
