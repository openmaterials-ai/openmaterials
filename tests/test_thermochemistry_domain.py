"""Tests for the thermochemistry domain (records 134-144).

The pycalphad-scan contribution: six thermochemistry ObservableSpaces
(AssessedDatabase, MolarGibbsEnergy, MolarEnthalpy, ChemicalPotential,
PhaseFraction, TransitionTemperature) with five implicit edges driven by a
Gibbs minimization over a frozen assessed TDB. The "Thermochemistry" tier
renders between Stability and Diffusion. MolarGibbsEnergy is the map's first
mole-axis observable, reusing the existing ENERGY_PER_MOLE dimension; the
Molar* false-merge guardrail keeps it a DISTINCT node from the phonon-side
MolarHelmholtzFreeEnergy (Gibbs vs Helmholtz, atoms vs cells). Two new index
kinds open the CALPHAD axes: `component` (c) and `phase` (p).
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

def test_thermochemistry_domain_between_stability_and_materials():
    names = [d.name for d in DOMAINS]
    assert names == [
        "thermal_transport", "dft_ground_state", "mechanics", "stability",
        "thermochemistry", "electronic_transport", "materials"]


def test_thermochemistry_declares_the_single_tier():
    from omai.thermochemistry.domain import THERMOCHEMISTRY

    assert THERMOCHEMISTRY.tiers == ((
        "Thermochemistry",
        "Assessed phase thermodynamics: Gibbs energies, chemical "
        "potentials, phase fractions, and transition temperatures from "
        "CALPHAD databases.",
    ),)
    assert THERMOCHEMISTRY.param_promotions == ()


def test_thermochemistry_nodes_are_the_six_observables():
    from omai.thermochemistry.operator import NODES

    assert [s.name for s in NODES] == [
        "AssessedDatabase", "MolarGibbsEnergy", "MolarEnthalpy",
        "ChemicalPotential", "PhaseFraction", "TransitionTemperature"]


def test_thermochemistry_edges_are_the_five_operators():
    from omai.thermochemistry.operator import EDGES

    assert [op.name for op in EDGES] == [
        "solve_equilibrium", "compute_molar_enthalpy",
        "compute_chemical_potentials", "compute_phase_fractions",
        "compute_transition_temperature"]


# --------------------------------------------------------------------------
# Dimension proof: the mole axis and the ENERGY_PER_MOLE exponent vector.
# --------------------------------------------------------------------------

def test_energy_per_mole_exponents_are_the_mole_axis_vector():
    """The map's first mole-axis observable: ENERGY_PER_MOLE has exponent
    vector (1,2,-2,0,-1,0,0), the fifth (N) slot the amount-of-substance
    axis. GM, HM, MU all carry it."""
    from omai.operator.dimensions import ENERGY_PER_MOLE
    from omai.thermochemistry.operator.nodes import (
        CHEMICAL_POTENTIAL,
        MOLAR_ENTHALPY,
        MOLAR_GIBBS_ENERGY,
    )

    assert ENERGY_PER_MOLE.exponents == (1, 2, -2, 0, -1, 0, 0)
    assert MOLAR_GIBBS_ENERGY.field("G_m").dimension == ENERGY_PER_MOLE
    assert MOLAR_ENTHALPY.field("H_m").dimension == ENERGY_PER_MOLE
    assert CHEMICAL_POTENTIAL.field("mu").dimension == ENERGY_PER_MOLE


def test_molar_gibbs_is_not_the_phonon_helmholtz_node():
    """The Molar* false-merge guardrail: MolarGibbsEnergy shares the
    ENERGY_PER_MOLE exponent vector with the phonon MolarHelmholtzFreeEnergy
    but is a DISTINCT node (Gibbs vs Helmholtz, atoms vs cells), kept apart by
    the molar_gibbs_energy quantity tag, so the uids differ."""
    from omai.operator.identity import node_identity
    from omai.thermal_transport.operator.nodes import (
        MOLAR_HELMHOLTZ_FREE_ENERGY,
    )
    from omai.thermochemistry.operator.nodes import (
        MOLAR_ENTHALPY,
        MOLAR_GIBBS_ENERGY,
    )

    # Same exponent vector on the field...
    assert (MOLAR_GIBBS_ENERGY.field("G_m").dimension
            == MOLAR_HELMHOLTZ_FREE_ENERGY.fields[0].dimension)
    # ...but distinct node identities (the tag does the work).
    assert node_id(MOLAR_GIBBS_ENERGY) != node_id(MOLAR_HELMHOLTZ_FREE_ENERGY)
    assert node_id(MOLAR_ENTHALPY) != node_id(MOLAR_HELMHOLTZ_FREE_ENERGY)
    assert node_id(MOLAR_GIBBS_ENERGY) != node_id(MOLAR_ENTHALPY)
    assert node_identity(MOLAR_GIBBS_ENERGY)["quantity"] == "molar_gibbs_energy"
    assert (node_identity(MOLAR_HELMHOLTZ_FREE_ENERGY)["quantity"]
            == "molar_helmholtz_free_energy")


def test_transition_temperature_is_distinct_from_input_temperature():
    """A computed transition temperature is a DISTINCT node from the input
    Temperature Source: same TEMPERATURE dimension, distinct quantity tag."""
    from omai.operator.dimensions import TEMPERATURE
    from omai.thermal_transport.operator.nodes import TEMPERATURE_STATE
    from omai.thermochemistry.operator.nodes import TRANSITION_TEMPERATURE

    assert TRANSITION_TEMPERATURE.field("T_trans").dimension == TEMPERATURE
    assert (TRANSITION_TEMPERATURE.field("T_trans").dimension
            == TEMPERATURE_STATE.field("temperature").dimension)
    assert node_id(TRANSITION_TEMPERATURE) != node_id(TEMPERATURE_STATE)


def test_component_and_phase_index_kinds_are_registered():
    """The chemical potential is indexed by component (c), the phase fraction
    by phase (p); both are new registered index kinds, carried in identity as
    kinds not names."""
    from omai.operator.identity import node_identity
    from omai.operator.registry import INDEX_KINDS
    from omai.thermochemistry.operator.nodes import (
        CHEMICAL_POTENTIAL,
        PHASE_FRACTION,
    )

    assert INDEX_KINDS["c"] == "component"
    assert INDEX_KINDS["p"] == "phase"
    assert CHEMICAL_POTENTIAL.field("mu").indices == ("c",)
    assert PHASE_FRACTION.field("NP").indices == ("p",)
    assert node_identity(CHEMICAL_POTENTIAL)["fields"][0]["indices"] == ["component"]
    assert node_identity(PHASE_FRACTION)["fields"][0]["indices"] == ["phase"]


def test_assessed_database_is_opaque_source_artifact():
    from omai.operator.dimensions import OPAQUE
    from omai.thermochemistry.operator.nodes import ASSESSED_DATABASE

    assert ASSESSED_DATABASE.field("D_tdb").dimension == OPAQUE
    assert ASSESSED_DATABASE.field("D_tdb").indices == ()
    assert ASSESSED_DATABASE.tier == "Thermochemistry"
    assert "analog" in ASSESSED_DATABASE.description


# --------------------------------------------------------------------------
# The gates the contribution must pass at the operator layer.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_thermochemistry_edges_are_implicit_and_skipped_not_violating():
    """All five edges carry opaque solver functions (the Gibbs minimization,
    the Legendre derivative, the composition derivative, the lever rule, the
    boundary locus), so the dimensional gate classifies them SKIPPED, exactly
    like solve_ground_state and the stability edges; none may be a violation,
    and the two pinned schematic violations stay the only ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("solve_equilibrium", "compute_molar_enthalpy",
                 "compute_chemical_potentials", "compute_phase_fractions",
                 "compute_transition_temperature"):
        assert name in report["skipped"], (name, report)
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_thermochemistry_edges_are_not_sympy_executable():
    from omai.thermochemistry.operator import EDGES

    for op in EDGES:
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy


def test_edge_wiring_and_schemes():
    from omai.thermochemistry.operator.edges import (
        compute_chemical_potentials,
        compute_molar_enthalpy,
        compute_phase_fractions,
        compute_transition_temperature,
        solve_equilibrium,
    )

    wiring = {
        solve_equilibrium: (
            ["AssessedDatabase", "Temperature"], ["MolarGibbsEnergy"],
            {"method": "gibbs_minimization"}),
        compute_molar_enthalpy: (
            ["AssessedDatabase", "Temperature"], ["MolarEnthalpy"],
            {"method": "legendre_derivative"}),
        compute_chemical_potentials: (
            ["MolarGibbsEnergy"], ["ChemicalPotential"],
            {"method": "partial_molar_derivative"}),
        compute_phase_fractions: (
            ["AssessedDatabase", "Temperature"], ["PhaseFraction"],
            {"method": "lever_rule"}),
        compute_transition_temperature: (
            ["PhaseFraction", "Temperature"], ["TransitionTemperature"],
            {"method": "boundary_locus"}),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_contribution_is_one_connected_component_touching_temperature():
    """The connectivity gate: the six added nodes plus five edges form one
    weakly connected subgraph, and at least one edge touches the pre-existing
    Temperature node of the store."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id,
        edge_identity,
        node_id as _nid,
        node_identity,
    )
    from omai.thermal_transport.operator.nodes import TEMPERATURE_STATE
    from omai.thermochemistry.operator import EDGES, NODES

    records = []
    for s in NODES:
        records.append({
            "op": "add_node",
            "payload": {"uid": _nid(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    for op in EDGES:
        records.append({
            "op": "add_edge",
            "payload": {"uid": edge_id(op, _nid),
                        "identity": edge_identity(op, _nid),
                        "meta": {"name": op.name, "schemes": op.schemes}},
        })
    # Temperature pre-exists in the store; AssessedDatabase arrives here.
    current = {"nodes": {_nid(TEMPERATURE_STATE): {
        "uid": _nid(TEMPERATURE_STATE),
        "identity": node_identity(TEMPERATURE_STATE), "meta": {}}}, "edges": {}}
    problems = validate_contribution(records, current)
    assert problems == [], problems


def test_new_nodes_validate_against_the_registries():
    from omai.gates import validate_contribution
    from omai.operator.identity import node_identity
    from omai.thermochemistry.operator import NODES

    records = []
    for s in NODES:
        records.append({
            "op": "add_node",
            "payload": {"uid": node_id(s), "identity": node_identity(s),
                        "meta": {"name": s.name}},
        })
    problems = validate_contribution(records, {"nodes": {}, "edges": {}})
    reg_gauge = [p for p in problems
                 if p.startswith("[registry]") or p.startswith("[gauge]")]
    assert reg_gauge == [], reg_gauge


# --------------------------------------------------------------------------
# The unified graph: tier order and node placement.
# --------------------------------------------------------------------------

def test_thermochemistry_tier_after_stability_before_electronic_transport():
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Thermochemistry" in tier_names
    i = tier_names.index("Thermochemistry")
    assert tier_names[i - 1] == "Stability"
    # The amset scan inserted the Electronic transport tier after
    # Thermochemistry, before the materials Diffusion tier.
    assert tier_names[i + 1] == "Electronic transport"


def test_thermochemistry_nodes_carry_the_tier():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    for name in ("AssessedDatabase", "MolarGibbsEnergy", "MolarEnthalpy",
                 "ChemicalPotential", "PhaseFraction",
                 "TransitionTemperature"):
        assert tier_of[name] == "Thermochemistry"


def test_map_has_eighty_two_nodes_and_twelve_tiers():
    # 73 through the pycalphad scan; 74 with AdsorptionEnergy (2026-07-10,
    # matcalc/ASE scan); 77 with the config-thermo scan's
    # ElectricalConductivity[carrier=ionic] + ConfigurationalEnergy (joining the
    # existing Diffusion tier) and ReactionEnergy (joining Stability); 82 with
    # the amset scan's electronic-transport five (StaticDielectricTensor joins
    # Sources, the four transport tensors add the new Electronic transport tier,
    # 2026-07-10).
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) == 82
    assert len(g["tiers"]) == 12


# --------------------------------------------------------------------------
# The units: j_per_mol canonical, kj_per_mol registered, the eV/atom factor.
# --------------------------------------------------------------------------

def test_molar_energy_units_and_the_ev_atom_basis_factor():
    from omai.representation.units import UNITS, conversion_factor

    # j_per_mol is canonical for ENERGY_PER_MOLE (to_operator 1.0, the
    # CALPHAD-native basis); kj_per_mol is the phonopy 1000x form.
    assert UNITS["J_per_mol"].to_operator == 1.0
    assert UNITS["kJ_per_mol"].to_operator == 1000.0
    assert abs(conversion_factor("kJ_per_mol", "J_per_mol") - 1000.0) < 1e-9
    # The eV/atom cross-basis factor is 96485.33212331 J/mol per eV/atom
    # (= e * N_A, SI-exact). It is a basis conversion (eV/atom has N=0), NOT a
    # unit of ENERGY_PER_MOLE, so it is documented, not registered as a unit.
    assert 1.602176634e-19 * 6.02214076e23 == 96485.33212331001


# --------------------------------------------------------------------------
# The pycalphad representation rail.
# --------------------------------------------------------------------------

def test_pycalphad_rail_covers_the_six_nodes():
    from omai.map_data import build_codes

    pc = build_codes(DOMAINS)["pycalphad"]
    assert set(pc) == {
        "AssessedDatabase", "MolarGibbsEnergy", "MolarEnthalpy",
        "ChemicalPotential", "PhaseFraction", "TransitionTemperature"}
    assert pc["MolarGibbsEnergy"]["unit"] == "J_per_mol"
    assert pc["MolarEnthalpy"]["unit"] == "J_per_mol"
    assert pc["ChemicalPotential"]["unit"] == "J_per_mol"
    assert pc["PhaseFraction"]["unit"] == "dimensionless"
    assert pc["TransitionTemperature"]["unit"] == "kelvin"
    # AssessedDatabase is the opaque model artifact: no unit declared.
    assert pc["AssessedDatabase"]["unit"] is None


def test_pycalphad_is_a_rail_and_the_config_thermo_scan_added_three_rails():
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    # pycalphad was the 17th rail when it landed; the matcalc/ASE scan
    # (2026-07-10) added mat-equation-of-state and mat-surface-adsorption
    # (matcalc itself is NOT a rail, the atomate2 ruling), reaching 19; the
    # config-thermo scan (2026-07-10) added three more: smol, rxn-network, and
    # pymatgen-analysis-diffusion, reaching 22; the amset scan (2026-07-10)
    # added the amset rail, reaching 23.
    assert len(codes) == 23
    assert "pycalphad" in codes
    assert "mat-equation-of-state" in codes
    assert "mat-surface-adsorption" in codes
    assert "matcalc" not in codes
    assert "smol" in codes
    assert "rxn-network" in codes
    assert "pymatgen-analysis-diffusion" in codes
    assert "amset" in codes


# --------------------------------------------------------------------------
# The contribution landed in the committed store through the gates.
# --------------------------------------------------------------------------

def test_committed_store_contains_the_thermochemistry_contribution():
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.store import Store
    from omai.thermochemistry.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in NODES:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in EDGES:
        assert edge_id(op, node_id) in m["edges"], \
            f"store missing edge {op.name}"


def test_thermochemistry_is_records_134_to_144():
    """The frozen log positions of the pycalphad-scan contribution: six nodes
    then five edges, authored through sync --apply as records 134-144.
    Positions are history and never move; records 132-133 (the atomate2/VASP
    BandGap node + edge) stay untouched above."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.thermochemistry.operator import EDGES, NODES

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 144, "the thermochemistry contribution has not landed"

    contribution_uids = (
        [node_id(s) for s in NODES]
        + [edge_id(op, node_id) for op in EDGES]
    )
    recs = [json.loads(line) for line in lines[133:144]]
    assert [r["payload"]["uid"] for r in recs] == contribution_uids
    assert [r["op"] for r in recs] == ["add_node"] * 6 + ["add_edge"] * 5
    names = [r["payload"]["meta"]["name"] for r in recs]
    assert names == [
        "AssessedDatabase", "MolarGibbsEnergy", "MolarEnthalpy",
        "ChemicalPotential", "PhaseFraction", "TransitionTemperature",
        "solve_equilibrium", "compute_molar_enthalpy",
        "compute_chemical_potentials", "compute_phase_fractions",
        "compute_transition_temperature"]
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-09"


def test_store_head_at_144_records_genesis_frozen():
    import json
    from pathlib import Path

    from omai.store import Store

    root = Path(__file__).resolve().parents[1] / "map"
    lines = root.joinpath("log.jsonl").read_text().splitlines()
    # 133 before this contribution; 144 after the six thermochemistry nodes
    # and five edges (records 134-144). The log only grows past 144 as later
    # contributions land (the matcalc/ASE scan added records 145-147); this
    # test pins the floor and the frozen genesis, not the exact head.
    assert len(lines) >= 144
    assert Store(root).verify() == []
    # Genesis stays the frozen prefix, byte-identical.
    assert root.joinpath("GENESIS").read_text().strip() == \
        "e6e8044e92039696417b53b220b0f3f10559a286b0eaabbe7ea4167ff510f6cd"
