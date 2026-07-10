"""Tests for the quasi-harmonic + density contribution (records 164-174).

The phonopy/LAMMPS delta scan (AtomisticSkills arXiv 2605.24002: matcalc QHACalc
over phonopy.PhonopyQHA, driven by mat-qha-thermal-expansion; LAMMPS metal-unit
MD thermo from mat-lammps-md) lands ONE contribution across two domains:

  * a new quasiharmonic domain, ONE Quasi-harmonic tier, FOUR nodes
    (QHAGibbsEnergy, ThermalExpansion, HeatCapacityConstantP, ThermalGruneisen)
    with five implicit edges (the QHA Gibbs producer, the third Pattern-C
    BulkModulus producer, the two G-derived responses, the mode-Gruneisen
    contraction);
  * the mechanics domain gains MassDensity plus contract_density.

Five nodes + six edges = records 164-174. Load-bearing proofs here:

  * the THERMAL_EXPANSIVITY (1/K) and MASS_DENSITY (M L^-3) exponent vectors;
  * BulkModulus now has THREE producing edges (contract, EOS, QHA);
  * the four ENERGY-per-mole-or-plain Gibbs / free-energy quantities
    (QHAGibbsEnergy, MolarGibbsEnergy, MolarHelmholtzFreeEnergy, FormationEnergy)
    are all DISTINCT uids, kept apart by name-based identity;
  * ThermalGruneisen does not alias the mode Gruneisen.

All six new edges carry opaque solver functions, classified SKIPPED by the
dimensional gate.
"""
from __future__ import annotations

import json
from pathlib import Path

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
# The two new dimensions: the exponent proofs.
# --------------------------------------------------------------------------

def test_thermal_expansivity_exponents_are_per_kelvin():
    """alpha = (1/V)(dV/dT)_P = 1/K = Th^-1, the map's first pure
    inverse-temperature dimension. NOT the reciprocal of a heat capacity or any
    energy form: a bare Theta^-1."""
    from omai.operator.dimensions import TEMPERATURE, THERMAL_EXPANSIVITY

    assert THERMAL_EXPANSIVITY.exponents == (0, 0, 0, -1, 0, 0, 0)
    assert THERMAL_EXPANSIVITY.canonical() == "Th^-1"
    # 1 / temperature reproduces THERMAL_EXPANSIVITY exactly.
    dimensionless_over_temp = tuple(-e for e in TEMPERATURE.exponents)
    assert THERMAL_EXPANSIVITY.exponents == dimensionless_over_temp
    # Only the temperature axis is non-zero.
    assert THERMAL_EXPANSIVITY.exponents[3] == -1
    assert sum(abs(e) for e in THERMAL_EXPANSIVITY.exponents) == 1


def test_mass_density_exponents_are_m_per_l3():
    """rho = mass / volume = M L^-3. NOT an energy density (M L^-1 T^-2, the
    stress / bulk-modulus exponents): different L exponent and no time axis."""
    from omai.operator.dimensions import (
        ENERGY_PER_LENGTH_CUBED,
        LENGTH,
        MASS,
        MASS_DENSITY,
    )

    assert MASS_DENSITY.exponents == (1, -3, 0, 0, 0, 0, 0)
    assert MASS_DENSITY.canonical() == "M^1 L^-3"
    # mass / length^3 reproduces MASS_DENSITY exactly.
    assert (MASS / (LENGTH ** 3)).exponents == MASS_DENSITY.exponents
    # Emphatically NOT an energy density (the pressure / modulus dimension).
    assert MASS_DENSITY != ENERGY_PER_LENGTH_CUBED
    assert MASS_DENSITY.exponents != ENERGY_PER_LENGTH_CUBED.exponents


def test_per_kelvin_and_density_units_are_canonical_with_factors():
    """per_kelvin is canonical for 1/K; gram_per_cm3 is canonical for mass
    density and kg/m^3 carries 1e-3."""
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["per_kelvin"].to_operator == 1.0
    assert UNITS["gram_per_cm3"].to_operator == 1.0
    assert UNITS["kg_per_m3"].to_operator == 1e-3
    # 1 kg/m^3 = 1e-3 g/cm^3.
    assert abs(conversion_factor("kg_per_m3", "gram_per_cm3") - 1e-3) < 1e-18
    # 1 g/cm^3 = 1000 kg/m^3.
    assert abs(conversion_factor("gram_per_cm3", "kg_per_m3") - 1000.0) < 1e-9


# --------------------------------------------------------------------------
# BulkModulus: THREE producing edges (Pattern C, three routes).
# --------------------------------------------------------------------------

def test_bulk_modulus_has_three_producing_edges():
    """The QHA route adds a THIRD producer of the existing BulkModulus node,
    alongside contract_bulk_modulus (elastic-tensor VRH) and
    compute_bulk_modulus_eos (T=0 Birch-Murnaghan E(V)). The node is NOT
    re-minted; all three edges name the same BulkModulus node uid."""
    from omai.mechanics.operator.edges import (
        compute_bulk_modulus_eos,
        contract_bulk_modulus,
    )
    from omai.mechanics.operator.nodes import BULK_MODULUS
    from omai.quasiharmonic.operator.edges import compute_bulk_modulus_qha

    bulk_uid = node_id(BULK_MODULUS)
    producers = [
        contract_bulk_modulus, compute_bulk_modulus_eos, compute_bulk_modulus_qha]
    for op in producers:
        assert [o.name for o in op.outputs] == ["BulkModulus"], op.name
        assert node_id(op.outputs[0]) == bulk_uid, op.name
    # Three DISTINCT producer edges, one shared output node.
    edge_uids = {edge_id(op, node_id) for op in producers}
    assert len(edge_uids) == 3
    # The graph exposes all three producing formulas on the node.
    g = build_graph_dict(DOMAINS)
    bulk = next(n for n in g["nodes"] if n["id"] == "BulkModulus")
    ops = {f["op"] for f in bulk["formulas"]}
    assert {"contract_bulk_modulus", "compute_bulk_modulus_eos",
            "compute_bulk_modulus_qha"} <= ops


def test_bulk_modulus_qha_wiring_and_scheme():
    from omai.quasiharmonic.operator.edges import compute_bulk_modulus_qha

    assert [s.name for s in compute_bulk_modulus_qha.inputs] == [
        "TotalEnergy", "Structure", "Frequency"]
    assert [o.name for o in compute_bulk_modulus_qha.outputs] == ["BulkModulus"]
    assert compute_bulk_modulus_qha.schemes == {
        "method": "qha_eos_scan", "eos": "vinet_or_birch_murnaghan"}


# --------------------------------------------------------------------------
# The four Gibbs / free-energy quantities are all distinct uids.
# --------------------------------------------------------------------------

def test_the_four_gibbs_quantities_are_distinct_uids():
    """QHAGibbsEnergy (constant-P, per phonopy cell, EOS producer),
    MolarGibbsEnergy (CALPHAD, constant-P, per mole of atoms, assessed),
    MolarHelmholtzFreeEnergy (constant-V, per phonopy cell) and FormationEnergy
    (per-atom formation energy) are FOUR distinct nodes. Three share the
    ENERGY_PER_MOLE exponent vector (kept apart by name-based identity / quantity
    tag); FormationEnergy carries plain ENERGY. No two collapse."""
    from omai.operator.dimensions import ENERGY_PER_MOLE
    from omai.operator.identity import node_identity
    from omai.quasiharmonic.operator.nodes import QHA_GIBBS_ENERGY
    from omai.thermochemistry.operator.nodes import MOLAR_GIBBS_ENERGY
    from omai.thermal_transport.operator.nodes import MOLAR_HELMHOLTZ_FREE_ENERGY
    from omai.stability.operator.nodes import FORMATION_ENERGY

    quantities = [
        QHA_GIBBS_ENERGY, MOLAR_GIBBS_ENERGY, MOLAR_HELMHOLTZ_FREE_ENERGY,
        FORMATION_ENERGY]
    uids = [node_id(q) for q in quantities]
    # All four uids distinct.
    assert len(set(uids)) == 4, dict(zip([q.name for q in quantities], uids))
    # Distinct quantity tags.
    tags = [node_identity(q)["quantity"] for q in quantities]
    assert tags == [
        "qha_gibbs_energy", "molar_gibbs_energy",
        "molar_helmholtz_free_energy", "formation_energy"]
    # The three molar-energy nodes share the ENERGY_PER_MOLE exponent vector: the
    # dimension does NO separating work; the names / tags do.
    for node, fname in (
            (QHA_GIBBS_ENERGY, "G_qha"),
            (MOLAR_GIBBS_ENERGY, "G_m"),
            (MOLAR_HELMHOLTZ_FREE_ENERGY, "F_mol")):
        assert node.field(fname).dimension == ENERGY_PER_MOLE


def test_heat_capacity_constant_p_does_not_alias_molar_cv():
    """HeatCapacityConstantP (C_P) reuses the ENERGY_PER_TEMPERATURE_PER_MOLE
    exponent vector of the harmonic MolarHeatCapacity (C_V) but is a distinct
    node by its heat_capacity_constant_p tag (C_P - C_V = alpha^2 B V T)."""
    from omai.operator.dimensions import ENERGY_PER_TEMPERATURE_PER_MOLE
    from omai.operator.identity import node_identity
    from omai.quasiharmonic.operator.nodes import HEAT_CAPACITY_CONSTANT_P
    from omai.thermal_transport.operator.nodes import MOLAR_HEAT_CAPACITY

    cp = HEAT_CAPACITY_CONSTANT_P
    cv = MOLAR_HEAT_CAPACITY
    assert cp.field("C_P_mol").dimension == ENERGY_PER_TEMPERATURE_PER_MOLE
    assert cv.field("C_V_mol").dimension == ENERGY_PER_TEMPERATURE_PER_MOLE
    assert node_identity(cp)["quantity"] == "heat_capacity_constant_p"
    assert node_identity(cv)["quantity"] == "molar_heat_capacity"
    assert node_id(cp) != node_id(cv)


def test_thermal_gruneisen_does_not_alias_the_mode_gruneisen():
    """ThermalGruneisen (a T-only scalar) shares the DIMENSIONLESS dimension with
    the mode Gruneisen (gamma_G, (q,nu)-indexed) but is a distinct node by its
    thermal_gruneisen tag AND its different index signature: a contraction of the
    mode node, not an alias."""
    from omai.operator.identity import node_identity
    from omai.quasiharmonic.operator.nodes import THERMAL_GRUNEISEN
    from omai.thermal_transport.operator.nodes import GRUNEISEN

    tg = THERMAL_GRUNEISEN
    mode = GRUNEISEN
    assert node_identity(tg)["quantity"] == "thermal_gruneisen"
    assert node_identity(mode)["quantity"] == "gruneisen"
    assert node_id(tg) != node_id(mode)
    # The scalar has no index; the mode node is (q, nu)-indexed.
    assert tg.field("gamma_thermal").indices == ()
    assert mode.field("gamma_G").indices == ("q", "nu")


# --------------------------------------------------------------------------
# Domain shape, tier, and edge wiring.
# --------------------------------------------------------------------------

def test_quasiharmonic_domain_declares_the_single_tier():
    from omai.quasiharmonic.domain import QUASIHARMONIC

    assert [t[0] for t in QUASIHARMONIC.tiers] == ["Quasi-harmonic"]
    used = {n.tier for n in QUASIHARMONIC.nodes}
    assert used == {"Quasi-harmonic"}


def test_quasiharmonic_nodes_and_edges():
    from omai.quasiharmonic.operator import EDGES, NODES

    assert [s.name for s in NODES] == [
        "QHAGibbsEnergy", "ThermalExpansion", "HeatCapacityConstantP",
        "ThermalGruneisen"]
    assert [op.name for op in EDGES] == [
        "compute_qha_gibbs", "compute_bulk_modulus_qha",
        "compute_thermal_expansion", "compute_heat_capacity_p",
        "contract_thermal_gruneisen"]


def test_quasiharmonic_edges_wiring_and_schemes():
    from omai.quasiharmonic.operator.edges import (
        compute_heat_capacity_p,
        compute_qha_gibbs,
        compute_thermal_expansion,
        contract_thermal_gruneisen,
    )

    wiring = {
        compute_qha_gibbs: (
            ["TotalEnergy", "Structure", "Frequency"], ["QHAGibbsEnergy"],
            {"method": "qha_fvt_minimization"}),
        compute_thermal_expansion: (
            ["QHAGibbsEnergy"], ["ThermalExpansion"],
            {"method": "dv_dt_at_gibbs_minimum"}),
        compute_heat_capacity_p: (
            ["QHAGibbsEnergy"], ["HeatCapacityConstantP"],
            {"method": "polyfit_enthalpy_derivative"}),
        contract_thermal_gruneisen: (
            ["Gruneisen", "Frequency"], ["ThermalGruneisen"],
            {"method": "heat_capacity_weighted_average"}),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_mass_density_node_and_edge():
    from omai.mechanics.operator.edges import contract_density
    from omai.mechanics.operator.nodes import MASS_DENSITY_STATE

    assert MASS_DENSITY_STATE.tier == "Mechanics"
    assert MASS_DENSITY_STATE.field("rho").indices == ()
    assert [s.name for s in contract_density.inputs] == ["Structure"]
    assert [o.name for o in contract_density.outputs] == ["MassDensity"]


# --------------------------------------------------------------------------
# The gates: implicit / SKIPPED, DAG clean, connectivity.
# --------------------------------------------------------------------------

def test_new_edges_are_implicit_and_skipped():
    """All six new edges carry opaque solver functions, so the dimensional gate
    classifies them SKIPPED; the two pinned schematic violations stay the only
    ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_qha_gibbs", "compute_bulk_modulus_qha",
                 "compute_thermal_expansion", "compute_heat_capacity_p",
                 "contract_thermal_gruneisen", "contract_density"):
        assert name in report["skipped"], (name, report)
    assert all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_new_edges_are_not_sympy_executable():
    from omai.mechanics.operator.edges import contract_density
    from omai.quasiharmonic.operator import EDGES

    for op in list(EDGES) + [contract_density]:
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy


def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_contribution_is_one_connected_component():
    """The five new nodes + six new edges are ONE weakly connected component:
    compute_qha_gibbs and compute_bulk_modulus_qha share TotalEnergy / Structure
    / Frequency; the two G-derived edges chain off QHAGibbsEnergy;
    contract_thermal_gruneisen bridges in through Frequency (the heat-capacity
    weighting) and consumes the pre-existing mode Gruneisen; contract_density
    chains off the pre-existing Structure."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id as _eid,
        edge_identity,
        node_id as _nid,
        node_identity,
    )
    from omai.quasiharmonic.operator.edges import (
        compute_bulk_modulus_qha,
        compute_heat_capacity_p,
        compute_qha_gibbs,
        compute_thermal_expansion,
        contract_thermal_gruneisen,
    )
    from omai.quasiharmonic.operator.nodes import (
        HEAT_CAPACITY_CONSTANT_P,
        QHA_GIBBS_ENERGY,
        THERMAL_EXPANSION,
        THERMAL_GRUNEISEN,
    )
    from omai.mechanics.operator.edges import contract_density
    from omai.mechanics.operator.nodes import BULK_MODULUS, MASS_DENSITY_STATE
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY, STRUCTURE
    from omai.thermal_transport.operator.nodes import FREQUENCY_STATE, GRUNEISEN

    records = []
    for s in (QHA_GIBBS_ENERGY, THERMAL_EXPANSION, HEAT_CAPACITY_CONSTANT_P,
              THERMAL_GRUNEISEN, MASS_DENSITY_STATE):
        records.append({
            "op": "add_node",
            "payload": {"uid": _nid(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    for op in (compute_qha_gibbs, compute_bulk_modulus_qha,
               compute_thermal_expansion, compute_heat_capacity_p,
               contract_thermal_gruneisen, contract_density):
        records.append({
            "op": "add_edge",
            "payload": {"uid": _eid(op, _nid),
                        "identity": edge_identity(op, _nid),
                        "meta": {"name": op.name, "schemes": op.schemes}},
        })
    current = {"nodes": {}, "edges": {}}
    for s in (TOTAL_ENERGY, STRUCTURE, FREQUENCY_STATE, GRUNEISEN, BULK_MODULUS):
        current["nodes"][_nid(s)] = {
            "uid": _nid(s), "identity": node_identity(s), "meta": {}}
    assert validate_contribution(records, current) == []


# --------------------------------------------------------------------------
# The phonopy rail (QHA) and the graph placement.
# --------------------------------------------------------------------------

def test_phonopy_rail_covers_the_qha_nodes_with_units():
    codes = build_codes(DOMAINS)
    phonopy = codes["phonopy"]
    assert phonopy["QHAGibbsEnergy"]["unit"] == "kJ_per_mol"
    assert phonopy["ThermalExpansion"]["unit"] == "per_kelvin"
    assert phonopy["HeatCapacityConstantP"]["unit"] == "J_per_K_per_mol"
    assert phonopy["ThermalGruneisen"]["unit"] == "dimensionless"
    # The QHA route to BulkModulus rides the phonopy rail in GPa.
    assert phonopy["BulkModulus"]["unit"] == "GPa"


def test_lammps_rail_covers_mass_density_in_g_per_cm3():
    codes = build_codes(DOMAINS)
    assert codes["lammps"]["MassDensity"]["unit"] == "gram_per_cm3"


def test_new_nodes_carry_their_tiers_and_the_new_tier_is_registered():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    for n in ("QHAGibbsEnergy", "ThermalExpansion", "HeatCapacityConstantP",
              "ThermalGruneisen"):
        assert tier_of[n] == "Quasi-harmonic"
    assert tier_of["MassDensity"] == "Mechanics"
    assert "Quasi-harmonic" in {t["name"] for t in g["tiers"]}


# --------------------------------------------------------------------------
# The committed store and the frozen log positions (records 164-174).
# --------------------------------------------------------------------------

def test_committed_store_contains_the_contribution():
    from omai.store import Store
    from omai.mechanics.operator.edges import contract_density
    from omai.mechanics.operator.nodes import MASS_DENSITY_STATE
    from omai.quasiharmonic.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in list(NODES) + [MASS_DENSITY_STATE]:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in list(EDGES) + [contract_density]:
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_quasiharmonic_is_records_164_to_174():
    """The frozen log positions: records 164-174 are the five nodes then the six
    edges (add_node * 5 + add_edge * 6), in the sync walk order (MassDensity
    first from the mechanics domain, then the four quasi-harmonic nodes; then
    contract_density, then the five quasi-harmonic edges). Positions are history
    and never move; records 154-163 (electronic transport) stay untouched."""
    from omai.mechanics.operator.edges import contract_density
    from omai.mechanics.operator.nodes import MASS_DENSITY_STATE
    from omai.quasiharmonic.operator.edges import (
        compute_bulk_modulus_qha,
        compute_heat_capacity_p,
        compute_qha_gibbs,
        compute_thermal_expansion,
        contract_thermal_gruneisen,
    )
    from omai.quasiharmonic.operator.nodes import (
        HEAT_CAPACITY_CONSTANT_P,
        QHA_GIBBS_ENERGY,
        THERMAL_EXPANSION,
        THERMAL_GRUNEISEN,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 174, "the quasi-harmonic contribution has not landed"

    node_uids = [
        node_id(MASS_DENSITY_STATE),
        node_id(QHA_GIBBS_ENERGY),
        node_id(THERMAL_EXPANSION),
        node_id(HEAT_CAPACITY_CONSTANT_P),
        node_id(THERMAL_GRUNEISEN),
    ]
    edge_uids = [
        edge_id(contract_density, node_id),
        edge_id(compute_qha_gibbs, node_id),
        edge_id(compute_bulk_modulus_qha, node_id),
        edge_id(compute_thermal_expansion, node_id),
        edge_id(compute_heat_capacity_p, node_id),
        edge_id(contract_thermal_gruneisen, node_id),
    ]
    recs = [json.loads(line) for line in lines[163:174]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 5 + ["add_edge"] * 6
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "quasi-harmonic" in r["reason"]
