"""Tests for the config-thermo contribution (records 148-153).

The config-thermo scan (AtomisticSkills arXiv 2605.24002: smol, rxn_network,
pymatgen-analysis-diffusion) lands as TWO contributions:

  * Contribution A (records 148-151, materials domain):
    ElectricalConductivity[carrier=ionic] + ConfigurationalEnergy nodes with the
    compute_ionic_conductivity + compute_configurational_energy edges. The
    ionic conductivity carries the fresh ELECTRICAL_CONDUCTIVITY dimension
    (M=-1,L=-3,T=3,I=2), the map's first I=+2 node, and the new carrier label.
  * Contribution B (records 152-153, stability domain): ReactionEnergy with
    compute_reaction_energy.

Both join existing tiers (Diffusion, Stability); no new tier. The two new
materials edges and the reaction-energy edge are implicit (opaque solver
functions), classified SKIPPED by the dimensional gate.
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
# The ELECTRICAL_CONDUCTIVITY dimension: the exponent proof.
# --------------------------------------------------------------------------

def test_electrical_conductivity_exponents_are_s_per_m():
    """S/m = M^-1 L^-3 T^3 I^2, verified two ways (Nernst-Einstein product and
    S/m first-principles). The map's first I=+2 dimension; NOT Thermal
    Conductivity, which shares only the English word 'conductivity'."""
    from omai.operator.dimensions import (
        ELECTRICAL_CONDUCTIVITY,
        THERMAL_CONDUCTIVITY,
    )

    assert ELECTRICAL_CONDUCTIVITY.exponents == (-1, -3, 3, 0, 0, 2, 0)
    assert ELECTRICAL_CONDUCTIVITY.canonical() == "M^-1 L^-3 T^3 I^2"
    # I=+2, the conductivity-squared-current slot.
    assert ELECTRICAL_CONDUCTIVITY.exponents[5] == 2
    # Emphatically NOT ThermalConductivity (1,1,-3,-1,0,0,0).
    assert ELECTRICAL_CONDUCTIVITY != THERMAL_CONDUCTIVITY
    assert ELECTRICAL_CONDUCTIVITY.exponents != THERMAL_CONDUCTIVITY.exponents


def test_ionic_conductivity_is_the_first_i_plus_two_node_not_thermal():
    from omai.materials.operator.nodes import ELECTRICAL_CONDUCTIVITY_IONIC
    from omai.operator.dimensions import ELECTRICAL_CONDUCTIVITY
    from omai.operator.identity import node_id as _nid
    from omai.thermal_transport.operator.nodes import THERMAL_CONDUCTIVITY_RTA

    assert (ELECTRICAL_CONDUCTIVITY_IONIC.field("sigma").dimension
            == ELECTRICAL_CONDUCTIVITY)
    # A distinct node from any thermal conductivity node (different dimension,
    # different quantity tag).
    assert _nid(ELECTRICAL_CONDUCTIVITY_IONIC) != _nid(THERMAL_CONDUCTIVITY_RTA)


def test_s_per_m_canonical_and_ms_per_cm_factor():
    """s_per_m is canonical (to_operator 1.0); ms_per_cm carries 0.1 (1 S/m =
    10 mS/cm)."""
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["s_per_m"].to_operator == 1.0
    assert UNITS["ms_per_cm"].to_operator == 0.1
    # 1 mS/cm expressed in S/m is 0.1; 1 S/m is 10 mS/cm.
    assert abs(conversion_factor("ms_per_cm", "s_per_m") - 0.1) < 1e-12
    assert abs(conversion_factor("s_per_m", "ms_per_cm") - 10.0) < 1e-12


# --------------------------------------------------------------------------
# The carrier label: round-trip in identity, collision-free registry.
# --------------------------------------------------------------------------

def test_carrier_label_round_trips_in_node_identity():
    """ElectricalConductivity[carrier=ionic] carries the carrier label into its
    identity dict (stringified), so the quantity tag (electrical_conductivity)
    plus the carrier label are what distinguish it from the electronic sibling
    that will share the tag and dimension."""
    from omai.operator.identity import node_identity
    from omai.operator.registry import quantity_tag_for
    from omai.materials.operator.nodes import ELECTRICAL_CONDUCTIVITY_IONIC

    ident = node_identity(ELECTRICAL_CONDUCTIVITY_IONIC)
    assert ident["quantity"] == "electrical_conductivity"
    assert ident["labels"] == {"carrier": "ionic"}
    # The name's [carrier=ionic] block strips to the bare tag.
    assert quantity_tag_for("ElectricalConductivity[carrier=ionic]") \
        == "electrical_conductivity"


def test_carrier_is_a_registered_label_key_collision_free():
    """carrier is a new LABEL_KEY with values {ionic, electronic}, collision-free
    against the existing keys (order, bte_solver, transport_model, channel,
    wrt): no key or value overlaps."""
    from omai.operator.registry import LABEL_KEYS

    assert "carrier" in LABEL_KEYS
    assert LABEL_KEYS["carrier"] == frozenset({"ionic", "electronic"})
    existing = {"order", "bte_solver", "transport_model", "channel", "wrt"}
    assert existing.isdisjoint({"carrier"})
    # No value of carrier collides with any value of the other keys.
    other_values: set = set()
    for k in existing:
        other_values |= set(LABEL_KEYS[k])
    assert other_values.isdisjoint(LABEL_KEYS["carrier"])


def test_electronic_sibling_would_be_a_distinct_node_same_family():
    """The electronic carrier (a future amset node) shares the tag and dimension
    but the carrier label alone gives it a distinct uid: the family stays one
    quantity, the siblings distinct nodes."""
    from omai.operator.dimensions import ELECTRICAL_CONDUCTIVITY
    from omai.operator.identity import node_id as _nid
    from omai.operator.space import Field, ObservableSpace
    from omai.materials.operator.nodes import ELECTRICAL_CONDUCTIVITY_IONIC

    electronic = ObservableSpace(
        name="ElectricalConductivity[carrier=electronic]",
        fields=(Field("sigma", ELECTRICAL_CONDUCTIVITY, indices=()),),
        labels={"carrier": "electronic"},
        tier="Diffusion",
    )
    assert _nid(electronic) != _nid(ELECTRICAL_CONDUCTIVITY_IONIC)


# --------------------------------------------------------------------------
# ConfigurationalEnergy and ReactionEnergy: distinct nodes, shared ENERGY.
# --------------------------------------------------------------------------

def test_configurational_energy_is_energy_but_distinct_from_total_and_formation():
    from omai.operator.dimensions import ENERGY
    from omai.operator.identity import node_id as _nid, node_identity
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
    from omai.materials.operator.nodes import CONFIGURATIONAL_ENERGY
    from omai.stability.operator.nodes import FORMATION_ENERGY

    assert CONFIGURATIONAL_ENERGY.field("E_cfg").dimension == ENERGY
    assert node_identity(CONFIGURATIONAL_ENERGY)["quantity"] \
        == "configurational_energy"
    assert _nid(CONFIGURATIONAL_ENERGY) != _nid(TOTAL_ENERGY)
    assert _nid(CONFIGURATIONAL_ENERGY) != _nid(FORMATION_ENERGY)


def test_reaction_energy_is_energy_but_distinct_from_formation():
    from omai.operator.dimensions import ENERGY
    from omai.operator.identity import node_id as _nid, node_identity
    from omai.stability.operator.nodes import FORMATION_ENERGY, REACTION_ENERGY

    assert REACTION_ENERGY.field("dE_rxn").dimension == ENERGY
    assert node_identity(REACTION_ENERGY)["quantity"] == "reaction_energy"
    assert _nid(REACTION_ENERGY) != _nid(FORMATION_ENERGY)


# --------------------------------------------------------------------------
# Edge wiring, schemes, and the boundary auto-parametrization (implicit /
# SKIPPED at the dimensional gate).
# --------------------------------------------------------------------------

def test_config_thermo_edges_wiring_and_schemes():
    from omai.materials.operator.edges import (
        compute_configurational_energy,
        compute_ionic_conductivity,
    )
    from omai.stability.operator.edges import compute_reaction_energy

    wiring = {
        # The Nernst-Einstein edge was superseded to the EXECUTABLE form
        # (physics review 2026-07-10, second supersede): inputs are now
        # (CarrierDensity, Diffusivity, Temperature), not the opaque-v1
        # (Diffusivity, Temperature, Structure). Schemes unchanged.
        compute_ionic_conductivity: (
            ["CarrierDensity", "Diffusivity", "Temperature"],
            ["ElectricalConductivity[carrier=ionic]"],
            {"method": "nernst_einstein", "haven_ratio": "1"}),
        compute_configurational_energy: (
            ["Potential", "Structure"], ["ConfigurationalEnergy"],
            {"method": "cluster_expansion"}),
        compute_reaction_energy: (
            ["FormationEnergy"], ["ReactionEnergy"],
            {"method": "stoichiometric_combination"}),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_config_thermo_edges_are_implicit_and_skipped():
    """The cluster-expansion edge carries an opaque solver function, so the
    dimensional gate classifies it SKIPPED. The reaction-energy edge, opaque
    when this scan landed, was reformulated to the closed-form stoichiometric
    sum (2026-07-10 physics-review supersede) and is now PROVEN (ok). The
    Nernst-Einstein edge, opaque when this scan landed, was likewise superseded
    to the EXECUTABLE form sigma = n_c z^2 e^2 D / (k_B T) (physics review, the
    SECOND supersede) and is now PROVEN (ok), not skipped. None is a violation;
    the two pinned schematic violations stay the only ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    # The cluster-expansion edge stays opaque-implicit / skipped.
    assert "compute_configurational_energy" in report["skipped"], report
    # The reaction-energy and ionic-conductivity edges are now closed-form and
    # PROVEN (both superseded from opaque v1 to executable v2).
    assert "compute_reaction_energy" in report["ok"], report
    assert "compute_reaction_energy" not in report["skipped"], report
    assert "compute_ionic_conductivity" in report["ok"], report
    assert "compute_ionic_conductivity" not in report["skipped"], report
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_config_thermo_edges_are_not_sympy_executable():
    from omai.materials.operator.edges import (
        compute_configurational_energy,
        compute_ionic_conductivity,
    )
    from omai.stability.operator.edges import compute_reaction_energy

    # The cluster-expansion edge stays opaque-implicit.
    assert compute_configurational_energy.is_executable_in_sympy_override is False
    assert not compute_configurational_energy.is_executable_in_sympy
    # The reaction-energy edge was superseded to a closed-form sum (2026-07-10),
    # so it is now sympy-executable (override None, heuristic True).
    assert compute_reaction_energy.is_executable_in_sympy_override is None
    assert compute_reaction_energy.is_executable_in_sympy
    # The ionic-conductivity edge was superseded to the executable Nernst-Einstein
    # (physics review, the second supersede), so it is now sympy-executable too.
    assert compute_ionic_conductivity.is_executable_in_sympy_override is None
    assert compute_ionic_conductivity.is_executable_in_sympy


def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


# --------------------------------------------------------------------------
# The two contributions pass the P4 gates (connectivity through pre-existing
# nodes).
# --------------------------------------------------------------------------

def test_contribution_a_is_connected_through_pre_existing_nodes():
    """The materials contribution is one weakly connected component and touches
    the pre-existing Diffusivity / Temperature / Structure / Potential Sources
    of the store. NOTE the ionic-conductivity edge is now the EXECUTABLE v2
    (physics review, second supersede): it consumes CarrierDensity (added here)
    alongside the pre-existing Diffusivity and Temperature, so the connectivity
    set adds CarrierDensity as a produced node."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id as _eid,
        edge_identity,
        node_id as _nid,
        node_identity,
    )
    from omai.materials.operator.edges import (
        compute_carrier_density,
        compute_configurational_energy,
        compute_ionic_conductivity,
    )
    from omai.materials.operator.nodes import (
        CARRIER_DENSITY,
        CONFIGURATIONAL_ENERGY,
        DIFFUSIVITY_STATE,
        ELECTRICAL_CONDUCTIVITY_IONIC,
    )
    from omai.materials.operator.shared_primitives import (
        POTENTIAL,
        STRUCTURE,
        TEMPERATURE,
    )

    records = []
    for s in (ELECTRICAL_CONDUCTIVITY_IONIC, CONFIGURATIONAL_ENERGY,
              CARRIER_DENSITY):
        records.append({
            "op": "add_node",
            "payload": {"uid": _nid(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    for op in (compute_carrier_density, compute_ionic_conductivity,
               compute_configurational_energy):
        records.append({
            "op": "add_edge",
            "payload": {"uid": _eid(op, _nid),
                        "identity": edge_identity(op, _nid),
                        "meta": {"name": op.name, "schemes": op.schemes}},
        })
    current = {"nodes": {}, "edges": {}}
    for s in (DIFFUSIVITY_STATE, TEMPERATURE, STRUCTURE, POTENTIAL):
        current["nodes"][_nid(s)] = {
            "uid": _nid(s), "identity": node_identity(s), "meta": {}}
    assert validate_contribution(records, current) == []


def test_contribution_b_is_connected_through_formation_energy():
    """Contribution B (1 node + 1 edge) touches the pre-existing FormationEnergy
    node of the store."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id as _eid,
        edge_identity,
        node_id as _nid,
        node_identity,
    )
    from omai.stability.operator.edges import compute_reaction_energy
    from omai.stability.operator.nodes import FORMATION_ENERGY, REACTION_ENERGY

    records = [
        {"op": "add_node",
         "payload": {"uid": _nid(REACTION_ENERGY),
                     "identity": node_identity(REACTION_ENERGY),
                     "meta": {"name": REACTION_ENERGY.name}}},
        {"op": "add_edge",
         "payload": {"uid": _eid(compute_reaction_energy, _nid),
                     "identity": edge_identity(compute_reaction_energy, _nid),
                     "meta": {"name": compute_reaction_energy.name,
                              "schemes": compute_reaction_energy.schemes}}},
    ]
    current = {"nodes": {_nid(FORMATION_ENERGY): {
        "uid": _nid(FORMATION_ENERGY),
        "identity": node_identity(FORMATION_ENERGY), "meta": {}}}, "edges": {}}
    assert validate_contribution(records, current) == []


# --------------------------------------------------------------------------
# The rails: three new representations.
# --------------------------------------------------------------------------

def test_pymatgen_analysis_diffusion_rail_covers_five_nodes():
    codes = build_codes(DOMAINS)
    pad = codes["pymatgen-analysis-diffusion"]
    # Four from the config-thermo scan; CarrierDensity added by the physics
    # review (2026-07-10, the executable Nernst-Einstein input).
    assert set(pad) == {
        "Diffusivity", "MeanSquaredDisplacement", "ActivationEnergy",
        "ElectricalConductivity[carrier=ionic]", "CarrierDensity"}
    assert pad["ElectricalConductivity[carrier=ionic]"]["unit"] == "ms_per_cm"
    assert pad["Diffusivity"]["unit"] == "cm^2/s"
    assert pad["CarrierDensity"]["unit"] == "per_cm3"


def test_smol_rail_covers_configurational_energy_and_the_potential_analog():
    codes = build_codes(DOMAINS)
    smol = codes["smol"]
    assert set(smol) == {"ConfigurationalEnergy", "Potential"}
    assert smol["ConfigurationalEnergy"]["unit"] == "ev"
    # The cluster-expansion checkpoint maps onto the existing opaque Potential
    # node (an MLIP-checkpoint sibling): no unit.
    assert smol["Potential"]["unit"] is None


def test_rxn_network_rail_covers_reaction_energy():
    codes = build_codes(DOMAINS)
    rxn = codes["rxn-network"]
    assert set(rxn) == {"ReactionEnergy"}
    assert rxn["ReactionEnergy"]["unit"] == "ev"


# --------------------------------------------------------------------------
# The graph placement and the committed store.
# --------------------------------------------------------------------------

def test_new_nodes_carry_their_existing_tiers():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["ElectricalConductivity[carrier=ionic]"] == "Diffusion"
    assert tier_of["ConfigurationalEnergy"] == "Diffusion"
    assert tier_of["ReactionEnergy"] == "Stability"


def test_committed_store_contains_both_contributions():
    from pathlib import Path

    from omai.store import Store
    from omai.materials.operator.edges import (
        compute_configurational_energy,
        compute_ionic_conductivity,
    )
    from omai.materials.operator.nodes import (
        CONFIGURATIONAL_ENERGY,
        ELECTRICAL_CONDUCTIVITY_IONIC,
    )
    from omai.stability.operator.edges import compute_reaction_energy
    from omai.stability.operator.nodes import REACTION_ENERGY

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in (ELECTRICAL_CONDUCTIVITY_IONIC, CONFIGURATIONAL_ENERGY,
              REACTION_ENERGY):
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in (compute_ionic_conductivity, compute_configurational_energy,
               compute_reaction_energy):
        assert edge_id(op, node_id) in m["edges"], \
            f"store missing edge {op.name}"


def test_config_thermo_is_records_148_to_153_two_contributions():
    """The frozen log positions: Contribution A is records 148-151 (2 nodes then
    2 edges), Contribution B records 152-153 (1 node then 1 edge). Positions are
    history and never move; records 145-147 (the matcalc/ASE contribution) stay
    untouched above."""
    import json
    from pathlib import Path

    from omai.materials.operator.edges import (
        compute_configurational_energy,
        compute_ionic_conductivity,
    )
    from omai.materials.operator.nodes import (
        CONFIGURATIONAL_ENERGY,
        ELECTRICAL_CONDUCTIVITY_IONIC,
    )
    from omai.stability.operator.nodes import REACTION_ENERGY

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 153, "the config-thermo contribution has not landed"

    # Record 150 is the ORIGINAL v1 ionic-conductivity edge. Its uid is frozen
    # history: the 2026-07-10 physics-review SECOND supersede reformulated the
    # edge to the executable Nernst-Einstein form (changing the LIVE edge_id),
    # but record 150 itself never moves and still carries the opaque-v1 uid.
    OLD_V1_IONIC_EDGE_UID = ("504b2deeec3553dc90f91bdc0b4136feaf52abcbc585edd6"
                             "5500d5cab9f27cb2")
    a_uids = [
        node_id(ELECTRICAL_CONDUCTIVITY_IONIC), node_id(CONFIGURATIONAL_ENERGY),
        OLD_V1_IONIC_EDGE_UID,
        edge_id(compute_configurational_energy, node_id),
    ]
    # Record 153 is the ORIGINAL v1 reaction-energy edge. Its uid is frozen
    # history: the 2026-07-10 physics-review supersede later reformulated the
    # edge (records 193-194), which changed the LIVE edge_id, but record 153
    # itself never moves and still carries the opaque-v1 uid.
    OLD_V1_REACTION_EDGE_UID = ("fd5d0e69fde548b23498f3ef5908ae15c2b32e7140cbdd"
                                "9f0773175fa0cc82e8")
    b_uids = [
        node_id(REACTION_ENERGY),
        OLD_V1_REACTION_EDGE_UID,
    ]
    recs_a = [json.loads(line) for line in lines[147:151]]
    recs_b = [json.loads(line) for line in lines[151:153]]
    assert [r["payload"]["uid"] for r in recs_a] == a_uids
    assert [r["payload"]["uid"] for r in recs_b] == b_uids
    assert [r["op"] for r in recs_a] == ["add_node"] * 2 + ["add_edge"] * 2
    assert [r["op"] for r in recs_b] == ["add_node", "add_edge"]
    # Two distinct contributions: distinct reasons, same author / date.
    for r in recs_a + recs_b:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
    assert all("ionic transport and configurational energetics" in r["reason"]
               for r in recs_a)
    assert all("reaction energetics" in r["reason"] for r in recs_b)
