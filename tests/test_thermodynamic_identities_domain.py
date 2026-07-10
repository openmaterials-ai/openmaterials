"""Tests for the thermodynamic-identities contribution (records 183-192).

The whole-map physics review (scans/map-physics-review-2026-07-10.md) read the
entire published map as a theoretical physicist and closed the gap between the
map's prose and its wiring with SIX executable sympy identities the dimensional
gate PROVES, plus FOUR new nodes and TWO new dimensions. This domain is special:
EVERY edge is closed-form (no opaque solver functions), so every one is
dimension_of-provable, in contrast to every other domain's SKIPPED opaque edges.

Load-bearing proofs here:

  * the two new dimensions VOLUME_PER_MOLE (m^3/mol) and POWER_FACTOR (W/(m K^2));
  * ALL SIX edges are classified OK (PROVEN) by the dimensional gate, not skipped
    and not violating: the headline of this contribution;
  * ThermalGruneisen now has TWO producing edges (Pattern C): the QHA
    mode-average and this thermodynamic identity gamma = alpha B / C_V^vol;
  * HeatCapacityConstantP now has TWO producing edges (Pattern C): the QHA
    polyfit and this identity C_P = C_V + T V_m alpha^2 B;
  * the supersede-free additive kappa_total, and the ZT chain that stitches the
    lattice and electronic thermal-transport halves together.
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.map_data import DOMAINS, build_graph_dict
from omai.operator.dimcheck import dimensional_report
from omai.operator.identity import edge_id, node_id, node_identity
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
# The two new dimensions: the exponent proofs.
# --------------------------------------------------------------------------

def test_volume_per_mole_exponents_are_l3_per_mole():
    """V_m = N_A V_cell = m^3/mol = L^3 N^-1. Exactly CellVolume's VOLUME times
    Avogadro's N^-1; NOT a plain volume (it carries the mole axis)."""
    from omai.operator.dimensions import VOLUME, VOLUME_PER_MOLE

    assert VOLUME_PER_MOLE.exponents == (0, 3, 0, 0, -1, 0, 0)
    assert VOLUME_PER_MOLE.canonical() == "L^3 N^-1"
    # VOLUME divided by a mole axis (N^+1) reproduces it exactly.
    n_axis = (0, 0, 0, 0, 1, 0, 0)
    assert VOLUME_PER_MOLE.exponents == tuple(
        v - n for v, n in zip(VOLUME.exponents, n_axis))
    assert VOLUME_PER_MOLE != VOLUME


def test_power_factor_exponents_are_w_per_m_k2():
    """PF = sigma_e S^2 = W/(m K^2) = M L T^-3 Th^-2. Built from
    ELECTRICAL_CONDUCTIVITY + 2 SEEBECK; a genuinely new derived dimension."""
    from omai.operator.dimensions import (
        ELECTRICAL_CONDUCTIVITY,
        POWER_FACTOR,
        SEEBECK,
        THERMAL_CONDUCTIVITY,
    )

    assert POWER_FACTOR.exponents == (1, 1, -3, -2, 0, 0, 0)
    assert POWER_FACTOR.canonical() == "M^1 L^1 T^-3 Th^-2"
    # sigma_e * S^2 reproduces POWER_FACTOR exactly.
    assert (ELECTRICAL_CONDUCTIVITY * (SEEBECK ** 2)).exponents == \
        POWER_FACTOR.exponents
    # NOT a thermal conductivity (W/(m K), Th^-1): differs by a Th axis.
    assert POWER_FACTOR != THERMAL_CONDUCTIVITY


def test_new_dimensions_are_registered_in_the_core_table():
    from omai.operator.dimensions import DIMENSIONS

    assert "volume_per_mole" in DIMENSIONS
    assert "power_factor" in DIMENSIONS


def test_molar_volume_units_canonical_with_cm3_factor():
    """m3_per_mol is canonical for molar volume; cm3_per_mol carries 1e-6."""
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["m3_per_mol"].to_operator == 1.0
    assert UNITS["cm3_per_mol"].to_operator == 1e-6
    assert abs(conversion_factor("cm3_per_mol", "m3_per_mol") - 1e-6) < 1e-24


def test_power_factor_unit_canonical():
    from omai.representation.units import UNITS

    assert UNITS["w_per_m_k2"].to_operator == 1.0


# --------------------------------------------------------------------------
# THE HEADLINE: all six edges are PROVEN by the dimensional gate.
# --------------------------------------------------------------------------

def test_all_six_identities_are_dimensionally_proven():
    """EVERY edge of this domain is classified OK (both sides known and equal) by
    the dimensional gate: the defining property of this contribution. None is
    skipped, none violates."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    six = [
        "contract_thermal_gruneisen_identity",
        "sum_thermal_conductivity",
        "contract_molar_volume",
        "contract_heat_capacity_p_identity",
        "contract_power_factor",
        "contract_zt",
    ]
    for name in six:
        assert name in report["ok"], (name, report)
        assert name not in report["skipped"], name
        assert not any(name in v for v in report["violation"]), name


def test_the_six_edges_are_sympy_executable_closed_forms():
    """Each formula is an explicit Eq with disjoint LHS/RHS free symbols, so the
    default executability heuristic makes it closed-form; none carries the
    override=False that the opaque edges use."""
    from omai.thermodynamic_identities.operator import EDGES

    assert len(EDGES) == 6
    for op in EDGES:
        assert op.is_executable_in_sympy_override is None, op.name
        assert op.is_executable_in_sympy, op.name


def test_each_identity_side_evaluates_to_its_declared_dimension():
    """Spot-check the actual dimension_of results on both sides of each identity,
    the machine-checked A-list proofs from the review."""
    import sympy as sp
    from omai.operator.dimcheck import dimension_of
    from omai.operator.dimensions import (
        DIMENSIONLESS,
        ENERGY_PER_TEMPERATURE_PER_MOLE,
        POWER_FACTOR,
        THERMAL_CONDUCTIVITY,
        VOLUME_PER_MOLE,
    )
    from omai.thermodynamic_identities.operator.edges import (
        contract_heat_capacity_p_identity,
        contract_molar_volume,
        contract_power_factor,
        contract_thermal_gruneisen_identity,
        contract_zt,
        sum_thermal_conductivity,
    )

    expected = {
        contract_thermal_gruneisen_identity: DIMENSIONLESS,
        sum_thermal_conductivity: THERMAL_CONDUCTIVITY,
        contract_molar_volume: VOLUME_PER_MOLE,
        contract_heat_capacity_p_identity: ENERGY_PER_TEMPERATURE_PER_MOLE,
        contract_power_factor: POWER_FACTOR,
        contract_zt: DIMENSIONLESS,
    }
    for op, dim in expected.items():
        f = op.formula
        assert isinstance(f, sp.Eq)
        lhs = dimension_of(f.lhs)
        rhs = dimension_of(f.rhs)
        assert lhs == dim, (op.name, lhs, dim)
        assert rhs == dim, (op.name, rhs, dim)
        assert lhs == rhs, op.name


# --------------------------------------------------------------------------
# Pattern C: two second-producers.
# --------------------------------------------------------------------------

def test_thermal_gruneisen_has_two_producing_edges():
    """The thermodynamic identity gamma = alpha B / C_V^vol is a SECOND producer
    of the existing ThermalGruneisen node, alongside the QHA
    heat-capacity-weighted mode-average. Same output node uid, distinct edges."""
    from omai.quasiharmonic.operator.edges import contract_thermal_gruneisen
    from omai.quasiharmonic.operator.nodes import THERMAL_GRUNEISEN
    from omai.thermodynamic_identities.operator.edges import (
        contract_thermal_gruneisen_identity,
    )

    gruneisen_uid = node_id(THERMAL_GRUNEISEN)
    producers = [contract_thermal_gruneisen, contract_thermal_gruneisen_identity]
    for op in producers:
        assert [o.name for o in op.outputs] == ["ThermalGruneisen"], op.name
        assert node_id(op.outputs[0]) == gruneisen_uid, op.name
    edge_uids = {edge_id(op, node_id) for op in producers}
    assert len(edge_uids) == 2
    # The node is NOT re-minted: the identity edge produces the SAME uid.
    g = build_graph_dict(DOMAINS)
    node = next(n for n in g["nodes"] if n["id"] == "ThermalGruneisen")
    ops = {f["op"] for f in node["formulas"]}
    assert {"contract_thermal_gruneisen",
            "contract_thermal_gruneisen_identity"} <= ops


def test_heat_capacity_constant_p_has_two_producing_edges():
    """C_P = C_V + T V_m alpha^2 B is a SECOND producer of the existing
    HeatCapacityConstantP node, alongside the QHA polyfit-enthalpy-derivative."""
    from omai.quasiharmonic.operator.edges import compute_heat_capacity_p
    from omai.quasiharmonic.operator.nodes import HEAT_CAPACITY_CONSTANT_P
    from omai.thermodynamic_identities.operator.edges import (
        contract_heat_capacity_p_identity,
    )

    cp_uid = node_id(HEAT_CAPACITY_CONSTANT_P)
    producers = [compute_heat_capacity_p, contract_heat_capacity_p_identity]
    for op in producers:
        assert [o.name for o in op.outputs] == ["HeatCapacityConstantP"], op.name
        assert node_id(op.outputs[0]) == cp_uid, op.name
    edge_uids = {edge_id(op, node_id) for op in producers}
    assert len(edge_uids) == 2
    g = build_graph_dict(DOMAINS)
    node = next(n for n in g["nodes"] if n["id"] == "HeatCapacityConstantP")
    ops = {f["op"] for f in node["formulas"]}
    assert {"compute_heat_capacity_p",
            "contract_heat_capacity_p_identity"} <= ops


# --------------------------------------------------------------------------
# The four new nodes: tags, labels, dimensions, distinct uids.
# --------------------------------------------------------------------------

def test_the_four_new_nodes_tags_and_labels():
    from omai.operator.dimensions import (
        DIMENSIONLESS,
        POWER_FACTOR,
        THERMAL_CONDUCTIVITY,
        VOLUME_PER_MOLE,
    )
    from omai.thermodynamic_identities.operator.nodes import (
        MOLAR_VOLUME,
        POWER_FACTOR_NODE,
        THERMAL_CONDUCTIVITY_TOTAL,
        ZT,
    )

    # ThermalConductivity[contribution=total]: same thermal_conductivity tag as
    # the lattice family, kept distinct by the contribution=total label.
    ident = node_identity(THERMAL_CONDUCTIVITY_TOTAL)
    assert ident["quantity"] == "thermal_conductivity"
    assert ident["labels"] == {"contribution": "total"}
    assert THERMAL_CONDUCTIVITY_TOTAL.field("kappa_tot").dimension == \
        THERMAL_CONDUCTIVITY

    assert node_identity(MOLAR_VOLUME)["quantity"] == "molar_volume"
    assert MOLAR_VOLUME.field("V_m").dimension == VOLUME_PER_MOLE

    assert node_identity(POWER_FACTOR_NODE)["quantity"] == "power_factor"
    assert POWER_FACTOR_NODE.field("PF").dimension == POWER_FACTOR

    assert node_identity(ZT)["quantity"] == "zt"
    assert ZT.field("ZT").dimension == DIMENSIONLESS


def test_total_kappa_does_not_alias_the_lattice_or_electronic_kappa():
    """ThermalConductivity[contribution=total] reuses the THERMAL_CONDUCTIVITY
    dimension and (for the lattice sibling) the thermal_conductivity tag, but the
    contribution=total label makes it a distinct uid from every lattice variant
    and from the differently-tagged ElectronicThermalConductivity."""
    from omai.electronic_transport.operator.nodes import (
        ELECTRONIC_THERMAL_CONDUCTIVITY,
    )
    from omai.thermal_transport.operator.nodes import THERMAL_CONDUCTIVITY_DIRECT
    from omai.thermodynamic_identities.operator.nodes import (
        THERMAL_CONDUCTIVITY_TOTAL,
    )

    total = node_id(THERMAL_CONDUCTIVITY_TOTAL)
    lattice = node_id(THERMAL_CONDUCTIVITY_DIRECT)
    electronic = node_id(ELECTRONIC_THERMAL_CONDUCTIVITY)
    assert len({total, lattice, electronic}) == 3
    # The lattice variant shares the tag but differs by label; the electronic
    # sibling differs by tag.
    assert node_identity(THERMAL_CONDUCTIVITY_DIRECT)["quantity"] == \
        "thermal_conductivity"
    assert node_identity(ELECTRONIC_THERMAL_CONDUCTIVITY)["quantity"] == \
        "electronic_thermal_conductivity"


def test_contribution_label_key_is_registered_and_collision_free():
    """The contribution LABEL_KEY is a fresh, unique key, collision-free against
    the other seven keys (orchestrator decision #1)."""
    from omai.operator.registry import LABEL_KEYS

    assert "contribution" in LABEL_KEYS
    assert LABEL_KEYS["contribution"] == frozenset({"total"})
    # A unique key (a dict key can appear once); no OTHER key is 'contribution'.
    keys = list(LABEL_KEYS)
    assert keys.count("contribution") == 1
    # Collision-free against the seven pre-existing keys.
    for k in ("order", "bte_solver", "transport_model", "channel", "wrt",
              "carrier", "construction"):
        assert k in LABEL_KEYS
        assert k != "contribution"


# --------------------------------------------------------------------------
# Edge wiring and the ZT connective story.
# --------------------------------------------------------------------------

def test_the_six_edges_wiring():
    from omai.thermodynamic_identities.operator.edges import (
        contract_heat_capacity_p_identity,
        contract_molar_volume,
        contract_power_factor,
        contract_thermal_gruneisen_identity,
        contract_zt,
        sum_thermal_conductivity,
    )

    wiring = {
        contract_thermal_gruneisen_identity: (
            ["ThermalExpansion", "BulkModulus", "VolumetricHeatCapacity"],
            ["ThermalGruneisen"]),
        sum_thermal_conductivity: (
            ["ThermalConductivity[bte_solver=direct_inverse]",
             "ElectronicThermalConductivity"],
            ["ThermalConductivity[contribution=total]"]),
        contract_molar_volume: ([], ["MolarVolume"]),
        contract_heat_capacity_p_identity: (
            ["MolarHeatCapacity", "Temperature", "MolarVolume",
             "ThermalExpansion", "BulkModulus"],
            ["HeatCapacityConstantP"]),
        contract_power_factor: (
            ["ElectricalConductivity[carrier=electronic]", "SeebeckCoefficient"],
            ["PowerFactor"]),
        contract_zt: (
            ["PowerFactor", "Temperature",
             "ThermalConductivity[contribution=total]"],
            ["ZT"]),
    }
    for op, (ins, outs) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name


def test_zt_stitches_lattice_and_electronic_halves():
    """ZT consumes the total kappa, which is itself lattice + electronic, so ZT
    transitively depends on both transport families: the review's headline
    connective link."""
    from omai.thermodynamic_identities.operator.edges import (
        contract_zt,
        sum_thermal_conductivity,
    )

    total = "ThermalConductivity[contribution=total]"
    assert total in [s.name for s in contract_zt.inputs]
    sum_inputs = [s.name for s in sum_thermal_conductivity.inputs]
    assert "ThermalConductivity[bte_solver=direct_inverse]" in sum_inputs  # lattice
    assert "ElectronicThermalConductivity" in sum_inputs  # electronic


def test_molar_volume_producer_is_nullary_and_reads_cell_volume():
    """CellVolume is a promoted parameter, so contract_molar_volume is a nullary
    producer whose formula reads V_{cell}; graph.json draws the provide_CellVolume
    -> MolarVolume presentation link."""
    from omai.thermodynamic_identities.operator.edges import contract_molar_volume

    assert contract_molar_volume.is_nullary()
    syms = {str(s) for s in contract_molar_volume.formula.free_symbols}
    assert "V_{cell}" in syms
    assert "N_A" in syms
    g = build_graph_dict(DOMAINS)
    link = [l for l in g["links"]
            if l["source"] == "CellVolume" and l["target"] == "MolarVolume"]
    assert link, "provide_CellVolume -> MolarVolume link missing"


# --------------------------------------------------------------------------
# The gates: DAG clean, connectivity, tier.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_contribution_is_one_connected_component_and_gate_clean():
    """The four new nodes + six new edges validate as one weakly connected
    contribution touching pre-existing store nodes (the P4 gates return no
    problems), including the DIMENSIONAL gate proving all six formulas."""
    from omai.gates import validate_contribution
    from omai.operator.identity import edge_identity
    from omai.genesis import _formula_srepr
    from omai.thermodynamic_identities.operator import EDGES, NODES
    from omai.quasiharmonic.operator.nodes import (
        HEAT_CAPACITY_CONSTANT_P,
        THERMAL_EXPANSION,
        THERMAL_GRUNEISEN,
    )
    from omai.mechanics.operator.nodes import BULK_MODULUS
    from omai.thermal_transport.operator.nodes import (
        MOLAR_HEAT_CAPACITY,
        TEMPERATURE_STATE,
        THERMAL_CONDUCTIVITY_DIRECT,
        VOLUMETRIC_HEAT_CAPACITY,
    )
    from omai.electronic_transport.operator.nodes import (
        ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
        ELECTRONIC_THERMAL_CONDUCTIVITY,
        SEEBECK_COEFFICIENT,
    )

    records = []
    for s in NODES:
        records.append({
            "op": "add_node",
            "payload": {"uid": node_id(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    for op in EDGES:
        records.append({
            "op": "add_edge",
            "payload": {"uid": edge_id(op, node_id),
                        "identity": edge_identity(op, node_id),
                        "meta": {"name": op.name, "schemes": op.schemes,
                                 "formula_srepr": _formula_srepr(op.formula)}},
        })
    current = {"nodes": {}, "edges": {}}
    for s in (THERMAL_EXPANSION, BULK_MODULUS, VOLUMETRIC_HEAT_CAPACITY,
              THERMAL_GRUNEISEN, THERMAL_CONDUCTIVITY_DIRECT,
              ELECTRONIC_THERMAL_CONDUCTIVITY, MOLAR_HEAT_CAPACITY,
              TEMPERATURE_STATE, HEAT_CAPACITY_CONSTANT_P,
              ELECTRICAL_CONDUCTIVITY_ELECTRONIC, SEEBECK_COEFFICIENT):
        current["nodes"][node_id(s)] = {
            "uid": node_id(s), "identity": node_identity(s), "meta": {}}
    assert validate_contribution(records, current) == []


def test_new_nodes_carry_the_thermoelectric_tier():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    for n in ("ThermalConductivity[contribution=total]", "MolarVolume",
              "PowerFactor", "ZT"):
        assert tier_of[n] == "Thermoelectric"
    assert "Thermoelectric" in {t["name"] for t in g["tiers"]}


def test_domain_declares_the_single_thermoelectric_tier():
    from omai.thermodynamic_identities.domain import THERMODYNAMIC_IDENTITIES

    assert [t[0] for t in THERMODYNAMIC_IDENTITIES.tiers] == ["Thermoelectric"]
    used = {n.tier for n in THERMODYNAMIC_IDENTITIES.nodes}
    assert used == {"Thermoelectric"}


# --------------------------------------------------------------------------
# The committed store and the frozen log positions (records 183-192).
# --------------------------------------------------------------------------

def test_committed_store_contains_the_contribution():
    from omai.store import Store
    from omai.thermodynamic_identities.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in NODES:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in EDGES:
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_thermodynamic_identities_is_records_183_to_192():
    """Frozen log positions: records 183-192 are the four nodes then the six
    edges (add_node * 4 + add_edge * 6), in sync walk order. Positions are
    history and never move; records 1-182 stay untouched."""
    from omai.thermodynamic_identities.operator.edges import (
        contract_heat_capacity_p_identity,
        contract_molar_volume,
        contract_power_factor,
        contract_thermal_gruneisen_identity,
        contract_zt,
        sum_thermal_conductivity,
    )
    from omai.thermodynamic_identities.operator.nodes import (
        MOLAR_VOLUME,
        POWER_FACTOR_NODE,
        THERMAL_CONDUCTIVITY_TOTAL,
        ZT,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 192, "the thermodynamic-identities contribution has not landed"

    node_uids = [
        node_id(THERMAL_CONDUCTIVITY_TOTAL),
        node_id(MOLAR_VOLUME),
        node_id(POWER_FACTOR_NODE),
        node_id(ZT),
    ]
    edge_uids = [
        edge_id(contract_thermal_gruneisen_identity, node_id),
        edge_id(sum_thermal_conductivity, node_id),
        edge_id(contract_molar_volume, node_id),
        edge_id(contract_heat_capacity_p_identity, node_id),
        edge_id(contract_power_factor, node_id),
        edge_id(contract_zt, node_id),
    ]
    recs = [json.loads(line) for line in lines[182:192]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 4 + ["add_edge"] * 6
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "thermodynamic identities" in r["reason"]
