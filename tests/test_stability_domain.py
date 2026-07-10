"""Tests for the stability domain and the magnetic moment (records 122-131).

The second pymatgen-scan contribution: four stability ObservableSpaces
(FormationEnergy, EnergyAboveHull, SurfaceEnergy, Voltage) with four implicit
energy-difference edges, plus the per-site MagneticMoment in the dft
ground-state domain with its spin-polarized producing edge. The "Stability"
tier renders between Mechanics and Diffusion; MagneticMoment joins the Ground
state tier. Two new dimensions open the electric-current axis (VOLTAGE,
MAGNETIC_MOMENT); the per-atom energies are DISTINCT quantities from the
per-cell TotalEnergy, dimension plain ENERGY with the per-atom character on
the quantity.
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

def test_stability_domain_in_domains_between_mechanics_and_materials():
    names = [d.name for d in DOMAINS]
    assert names == [
        "thermal_transport", "dft_ground_state", "mechanics", "stability",
        "thermochemistry", "quasiharmonic", "electronic_transport",
        "materials"]


def test_stability_domain_declares_stability_tier():
    from omai.stability.domain import STABILITY

    assert STABILITY.tiers == ((
        "Stability",
        "Phase stability and electrochemistry: formation energies, "
        "distance to the convex hull, surface energetics, and "
        "intercalation voltages.",
    ),)


def test_stability_nodes_are_the_five_energy_difference_observables():
    from omai.stability.operator import NODES

    assert [s.name for s in NODES] == [
        "FormationEnergy", "EnergyAboveHull", "SurfaceEnergy", "Voltage",
        "AdsorptionEnergy", "ReactionEnergy"]


def test_stability_edges_are_the_five_operators():
    from omai.stability.operator import EDGES

    assert [op.name for op in EDGES] == [
        "compute_formation_energy", "compute_energy_above_hull",
        "compute_surface_energy", "compute_intercalation_voltage",
        "compute_adsorption_energy", "compute_reaction_energy"]


# --------------------------------------------------------------------------
# Node typing: per-atom discipline, the current axis, index kinds.
# --------------------------------------------------------------------------

def test_per_atom_energies_are_distinct_nodes_with_plain_energy_dimension():
    """The scan's highest-risk trap, resolved: FormationEnergy and
    EnergyAboveHull are intensive per-atom quantities, DISTINCT nodes from
    the per-cell TotalEnergy. The per-atom normalization is declared in the
    descriptions and units, not the dimension, which is plain ENERGY."""
    from omai.operator.dimensions import ENERGY
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
    from omai.stability.operator.nodes import (
        ENERGY_ABOVE_HULL,
        FORMATION_ENERGY,
    )

    assert FORMATION_ENERGY.field("dH_f").dimension == ENERGY
    assert ENERGY_ABOVE_HULL.field("E_hull").dimension == ENERGY
    # Distinct identities from TotalEnergy (different quantity tags).
    assert node_id(FORMATION_ENERGY) != node_id(TOTAL_ENERGY)
    assert node_id(ENERGY_ABOVE_HULL) != node_id(TOTAL_ENERGY)
    assert node_id(FORMATION_ENERGY) != node_id(ENERGY_ABOVE_HULL)
    assert "per atom" in FORMATION_ENERGY.description
    assert "eV/atom" in ENERGY_ABOVE_HULL.description


def test_voltage_opens_the_current_axis_and_surface_energy_reuses_mt2():
    """Voltage is the map's first current-axis quantity (the volt,
    M L^2 T^-3 I^-1); MagneticMoment is the second (L^2 I). SurfaceEnergy
    reuses ENERGY_PER_LENGTH_SQUARED, the same M T^-2 exponents as the force
    constants, kept distinct by quantity tag alone."""
    from omai.operator.dimensions import (
        ENERGY_PER_LENGTH_SQUARED,
        MAGNETIC_MOMENT,
        VOLTAGE,
    )
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE
    from omai.stability.operator.nodes import SURFACE_ENERGY, VOLTAGE_STATE
    from omai.thermal_transport.operator.nodes import FORCE_CONSTANTS_2

    assert VOLTAGE.exponents == (1, 2, -3, 0, 0, -1, 0)
    assert MAGNETIC_MOMENT.exponents == (0, 2, 0, 0, 0, 1, 0)
    assert VOLTAGE_STATE.field("V_avg").dimension == VOLTAGE
    assert MAGNETIC_MOMENT_STATE.field("m").dimension == MAGNETIC_MOMENT
    gamma = SURFACE_ENERGY.field("gamma")
    assert gamma.dimension == ENERGY_PER_LENGTH_SQUARED
    # Same dimension as FC2, different node identity (the tag does the work).
    assert gamma.dimension == FORCE_CONSTANTS_2.field("phi").dimension
    assert node_id(SURFACE_ENERGY) != node_id(FORCE_CONSTANTS_2)


def test_magnetic_moment_is_per_site_on_the_atom_index_kind():
    """The per-site index reuses the registered atom kind `i` (orchestrator
    ruling: no new `site` kind); the identity carries the kind, not the
    name."""
    from omai.operator.identity import node_identity
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE

    assert MAGNETIC_MOMENT_STATE.field("m").indices == ("i",)
    ident = node_identity(MAGNETIC_MOMENT_STATE)
    assert ident["fields"][0]["indices"] == ["atom"]
    assert ident["quantity"] == "magnetic_moment"


def test_surface_energy_is_scalar_with_the_facet_in_conditions():
    from omai.stability.operator.nodes import SURFACE_ENERGY

    assert SURFACE_ENERGY.field("gamma").indices == ()
    assert "Miller index" in SURFACE_ENERGY.description


# --------------------------------------------------------------------------
# The gates the contribution must pass at the operator layer.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_stability_and_magnetism_edges_are_implicit_and_skipped_not_violating():
    """All five edges carry opaque selector functions (reference sets, hulls,
    slab/bulk and full/empty selectors, the spin-polarized SCF), so the
    dimensional gate classifies them SKIPPED, exactly like
    solve_ground_state; none may be a violation, and the two pinned
    schematic violations stay the only ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_formation_energy", "compute_energy_above_hull",
                 "compute_surface_energy", "compute_intercalation_voltage",
                 "compute_magnetic_moments"):
        assert name in report["skipped"], (name, report)
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_stability_edges_are_not_sympy_executable():
    from omai.stability.operator import EDGES
    from omai.dft_ground_state.operator.edges import compute_magnetic_moments

    for op in tuple(EDGES) + (compute_magnetic_moments,):
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy


def test_edge_wiring_and_schemes():
    from omai.stability.operator.edges import (
        compute_energy_above_hull,
        compute_formation_energy,
        compute_intercalation_voltage,
        compute_surface_energy,
    )
    from omai.dft_ground_state.operator.edges import compute_magnetic_moments

    wiring = {
        compute_formation_energy: (
            ["TotalEnergy", "Structure"], ["FormationEnergy"],
            {"elemental_references": "materials_project"}),
        compute_energy_above_hull: (
            ["FormationEnergy", "Structure"], ["EnergyAboveHull"],
            {"hull_source": "materials_project"}),
        compute_surface_energy: (
            ["TotalEnergy", "Structure"], ["SurfaceEnergy"],
            {"slab_termination": "symmetric"}),
        compute_intercalation_voltage: (
            ["TotalEnergy", "Structure"], ["Voltage"],
            {"working_ion": "Li"}),
        compute_magnetic_moments: (
            ["Structure", "Potential"], ["MagneticMoment"],
            {"method": "spin_polarized_scf"}),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_new_nodes_validate_against_the_registries():
    from omai.gates import validate_contribution
    from omai.operator.identity import node_identity
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE
    from omai.stability.operator import NODES

    records = []
    for s in tuple(NODES) + (MAGNETIC_MOMENT_STATE,):
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

def test_stability_tier_ordered_after_mechanics_before_thermochemistry():
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Stability" in tier_names
    i = tier_names.index("Stability")
    assert tier_names[i - 1] == "Mechanics"
    # The Thermochemistry tier (pycalphad scan) now renders between Stability
    # and the materials domain's Diffusion tier.
    assert tier_names[i + 1] == "Thermochemistry"


def test_stability_nodes_carry_the_tier():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    for name in ("FormationEnergy", "EnergyAboveHull", "SurfaceEnergy",
                 "Voltage"):
        assert tier_of[name] == "Stability"
    assert tier_of["MagneticMoment"] == "Ground state"


# --------------------------------------------------------------------------
# The units the contribution registered.
# --------------------------------------------------------------------------

def test_new_units_carry_the_full_precision_factors():
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["volt"].to_operator == 1.0  # canonical VOLTAGE
    assert UNITS["mu_B"].to_operator == 1.0  # canonical MAGNETIC_MOMENT
    # ev_per_atom measures plain ENERGY with the eV factor; the per-atom
    # character belongs to the quantity, not the unit.
    assert UNITS["ev_per_atom"].to_operator == UNITS["ev"].to_operator
    # 1 eV/A^2 = 16.021766339999996 J/m^2, full precision (the skill's
    # 16.0218 is its own truncation).
    assert abs(conversion_factor("eV_per_A2", "J_per_m2")
               - 16.021766339999996) < 1e-12
    # y_mod's Pa trap: 1 GPa = 1e9 Pa on the shared energy-density dimension.
    assert abs(conversion_factor("GPa", "Pa") - 1e9) < 1e-3


# --------------------------------------------------------------------------
# The pymatgen representation rail.
# --------------------------------------------------------------------------

def test_pymatgen_covers_the_stability_and_magnetism_nodes():
    from omai.map_data import build_codes

    pmg = build_codes(DOMAINS)["pymatgen"]
    assert pmg["FormationEnergy"]["unit"] == "ev_per_atom"
    assert pmg["EnergyAboveHull"]["unit"] == "ev_per_atom"
    assert pmg["SurfaceEnergy"]["unit"] == "J_per_m2"
    assert pmg["Voltage"]["unit"] == "volt"
    assert pmg["MagneticMoment"]["unit"] == "mu_B"


def test_pymatgen_rail_spans_the_catalogs_already_mapped_spaces():
    """The pymatgen code rail covers the scan's already-mapped SPACES (the
    three promoted parameters CellVolume / AtomicMass / AtomCount have no
    Space to represent) plus the seven new nodes of the two contributions."""
    from omai.map_data import build_codes

    pmg = build_codes(DOMAINS)["pymatgen"]
    expected = {
        # already-mapped spaces the catalog grounds
        "Structure", "TotalEnergy", "Stress",
        "ElasticConstants", "BulkModulus", "ShearModulus",
        "Diffusivity", "ActivationEnergy", "MeanSquaredDisplacement",
        "Frequency", "PhononDOS", "ForceConstants[order=2]",
        "BornCharges", "DielectricTensor",
        # the two pymatgen-scan contributions
        "YoungsModulus", "PoissonRatio",
        "FormationEnergy", "EnergyAboveHull", "SurfaceEnergy", "Voltage",
        "MagneticMoment",
    }
    assert set(pmg) == expected, sorted(set(pmg) ^ expected)


# --------------------------------------------------------------------------
# The contribution landed in the committed store through the gates.
# --------------------------------------------------------------------------

def test_committed_store_contains_the_stability_contribution():
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.store import Store
    from omai.dft_ground_state.operator.edges import compute_magnetic_moments
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE
    from omai.stability.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in tuple(NODES) + (MAGNETIC_MOMENT_STATE,):
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in tuple(EDGES) + (compute_magnetic_moments,):
        assert edge_id(op, node_id) in m["edges"], \
            f"store missing edge {op.name}"


def test_stability_and_magnetism_are_records_122_to_131():
    """The frozen log positions of the second pymatgen-scan contribution:
    five nodes (MagneticMoment first: the dft domain precedes stability in
    DOMAINS walk order) then five edges, authored through sync --apply as
    records 122-131. Positions are history and never move; records 118-121
    (the mechanics contracts) stay untouched above."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.dft_ground_state.operator.edges import compute_magnetic_moments
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE
    from omai.stability.operator import EDGES, NODES

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 131, "the stability contribution has not landed"

    # The v1 stability contribution is history: exactly the FIRST four nodes
    # and FIRST four edges (the domain later grew: AdsorptionEnergy and
    # compute_adsorption_energy landed 2026-07-10 as records 145-147 below).
    v1_nodes = NODES[:4]
    v1_edges = EDGES[:4]
    contribution_uids = (
        [node_id(MAGNETIC_MOMENT_STATE)]
        + [node_id(s) for s in v1_nodes]
        + [edge_id(compute_magnetic_moments, node_id)]
        + [edge_id(op, node_id) for op in v1_edges]
    )
    recs = [json.loads(line) for line in lines[121:131]]
    assert [r["payload"]["uid"] for r in recs] == contribution_uids
    assert [r["op"] for r in recs] == ["add_node"] * 5 + ["add_edge"] * 5
    names = [r["payload"]["meta"]["name"] for r in recs]
    assert names == [
        "MagneticMoment", "FormationEnergy", "EnergyAboveHull",
        "SurfaceEnergy", "Voltage",
        "compute_magnetic_moments", "compute_formation_energy",
        "compute_energy_above_hull", "compute_surface_energy",
        "compute_intercalation_voltage"]
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-09"


def test_stability_and_magnetism_instances_pin_the_live_node_uids():
    """Evidence: the seven stability/magnetism values recorded verbatim from
    the committed omai/materials/skills_catalog.json example_instances (the
    upstream example paths are cited in each instance's source detail)."""
    from omai.map_data import build_instances
    from omai.dft_ground_state.operator.nodes import MAGNETIC_MOMENT_STATE
    from omai.stability.operator.nodes import (
        ENERGY_ABOVE_HULL,
        FORMATION_ENERGY,
        SURFACE_ENERGY,
        VOLTAGE_STATE,
    )

    insts = build_instances()
    by_key = {(it["variable"], it["material"]): it for it in insts}

    gammas = {"Cu (111)": 1.3, "Cu (100)": 1.45, "Cu (110)": 1.55}
    for mat, val in gammas.items():
        it = by_key[("SurfaceEnergy", mat)]
        assert it["value"] == val
        assert it["units"] == "J/m^2"
        assert it["source"]["kind"] == "simulation"
        assert it["node_uid"] == node_id(SURFACE_ENERGY)

    v = by_key[("Voltage", "LiFePO4")]
    assert v["value"] == 3.260441522078377
    assert v["units"] == "V"
    assert v["conditions"]["working_ion"] == "Li"
    assert v["node_uid"] == node_id(VOLTAGE_STATE)

    m = by_key[("MagneticMoment", "Fe (bcc)")]
    assert m["value"] == 2.15
    assert m["units"] == "mu_B"
    assert m["node_uid"] == node_id(MAGNETIC_MOMENT_STATE)

    f = by_key[("FormationEnergy", "Li2O (mp-1960)")]
    assert f["value"] == -2.061597913888889
    assert f["units"] == "eV/atom"
    assert f["node_uid"] == node_id(FORMATION_ENERGY)

    h = by_key[("EnergyAboveHull", "Li2O (mp-1960)")]
    assert h["value"] == 0.0
    assert h["units"] == "eV/atom"
    assert h["node_uid"] == node_id(ENERGY_ABOVE_HULL)


def test_store_head_at_133_records_genesis_frozen():
    import json
    from pathlib import Path

    from omai.store import Store

    root = Path(__file__).resolve().parents[1] / "map"
    lines = root.joinpath("log.jsonl").read_text().splitlines()
    # 131 after the stability/electrochemistry/magnetism landing; 133 after the
    # atomate2/VASP scan's BandGap node + compute_band_gap edge (records
    # 132-133). The log only grows past 133 as later contributions land (the
    # pycalphad scan added records 134-144); this test pins the floor and the
    # frozen genesis, not the exact head.
    assert len(lines) >= 133
    assert Store(root).verify() == []
    # Genesis stays the frozen prefix, byte-identical.
    assert root.joinpath("GENESIS").read_text().strip() == \
        "e6e8044e92039696417b53b220b0f3f10559a286b0eaabbe7ea4167ff510f6cd"


# --------------------------------------------------------------------------
# The matcalc/ASE scan: AdsorptionEnergy (2026-07-10), surface energetics
# kin to SurfaceEnergy, driven by mat-surface-adsorption via AdsorptionCalc.
# --------------------------------------------------------------------------

def test_adsorption_energy_is_a_scalar_energy_node_not_per_atom():
    """AdsorptionEnergy is a scalar ENERGY per configuration (eV, extensive),
    NOT the per-atom currency of FormationEnergy / EnergyAboveHull, and NOT
    the per-cell TotalEnergy: a distinct node kin to SurfaceEnergy."""
    from omai.operator.dimensions import ENERGY
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
    from omai.stability.operator.nodes import (
        ADSORPTION_ENERGY,
        FORMATION_ENERGY,
        SURFACE_ENERGY,
    )

    assert ADSORPTION_ENERGY.field("E_ads").dimension == ENERGY
    assert ADSORPTION_ENERGY.field("E_ads").indices == ()
    # Distinct identities.
    assert node_id(ADSORPTION_ENERGY) != node_id(TOTAL_ENERGY)
    assert node_id(ADSORPTION_ENERGY) != node_id(FORMATION_ENERGY)
    assert node_id(ADSORPTION_ENERGY) != node_id(SURFACE_ENERGY)
    # Extensive, per configuration: the description says so.
    assert "EXTENSIVE" in ADSORPTION_ENERGY.description
    assert "per adsorbate-surface configuration" in ADSORPTION_ENERGY.description


def test_compute_adsorption_energy_wiring_and_scheme():
    from omai.stability.operator.edges import compute_adsorption_energy

    assert [s.name for s in compute_adsorption_energy.inputs] == [
        "TotalEnergy", "Structure"]
    assert [o.name for o in compute_adsorption_energy.outputs] == [
        "AdsorptionEnergy"]
    assert compute_adsorption_energy.schemes == {
        "reference_convention": "adslab_minus_slab_minus_adsorbate"}
    # Implicit (opaque selectors over the energy family), so not executable.
    assert compute_adsorption_energy.is_executable_in_sympy_override is False
    assert not compute_adsorption_energy.is_executable_in_sympy


def test_adsorption_edge_is_skipped_not_a_violation():
    """The adslab / slab / adsorbate selectors are opaque applied functions,
    so the dimensional gate classifies the edge SKIPPED (like the other four
    stability edges), never a violation."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    assert "compute_adsorption_energy" in report["skipped"], report
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_mat_surface_adsorption_is_the_rail_not_matcalc():
    """Per the atomate2 ruling, matcalc mints no rail: the AdsorptionEnergy
    coverage lands on the driving skill rail (mat-surface-adsorption), with
    matcalc recorded in the notes."""
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert "matcalc" not in codes
    rail = codes["mat-surface-adsorption"]
    assert rail["AdsorptionEnergy"]["unit"] == "ev"
    from omai.stability.representation.mat_surface_adsorption import (
        MATCALC_ADSORPTION_ENERGY,
    )
    assert "AdsorptionCalc" in MATCALC_ADSORPTION_ENERGY.notes
    assert "double-provenance" in MATCALC_ADSORPTION_ENERGY.notes.lower()


def test_adsorption_energy_landed_in_the_committed_store():
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.store import Store
    from omai.stability.operator.edges import compute_adsorption_energy
    from omai.stability.operator.nodes import ADSORPTION_ENERGY

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    assert node_id(ADSORPTION_ENERGY) in m["nodes"]
    assert edge_id(compute_adsorption_energy, node_id) in m["edges"]


def test_matcalc_ase_contribution_is_records_145_to_147():
    """The frozen log positions of the matcalc/ASE scan contribution: the
    AdsorptionEnergy add_node, then the two add_edges in DOMAINS walk order
    (compute_bulk_modulus_eos in mechanics before compute_adsorption_energy in
    stability). Records 145-147, authored through sync --apply on 2026-07-10.
    Positions are history and never move."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.mechanics.operator.edges import compute_bulk_modulus_eos
    from omai.stability.operator.edges import compute_adsorption_energy
    from omai.stability.operator.nodes import ADSORPTION_ENERGY

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 147, "the matcalc/ASE contribution has not landed"

    rec_145 = json.loads(lines[144])
    assert rec_145["op"] == "add_node"
    assert rec_145["payload"]["uid"] == node_id(ADSORPTION_ENERGY)
    assert rec_145["payload"]["meta"]["name"] == "AdsorptionEnergy"

    rec_146 = json.loads(lines[145])
    assert rec_146["op"] == "add_edge"
    assert rec_146["payload"]["uid"] == edge_id(compute_bulk_modulus_eos, node_id)
    assert rec_146["payload"]["meta"]["name"] == "compute_bulk_modulus_eos"

    rec_147 = json.loads(lines[146])
    assert rec_147["op"] == "add_edge"
    assert rec_147["payload"]["uid"] == edge_id(compute_adsorption_energy, node_id)
    assert rec_147["payload"]["meta"]["name"] == "compute_adsorption_energy"

    for r in (rec_145, rec_146, rec_147):
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "matcalc/ASE scan" in r["reason"]
        assert "2605.24002" in r["reason"]


def test_adsorption_energy_instance_pins_the_live_node_uid():
    """Evidence: the committed CO-on-Cu(111) most-stable-site adsorption energy
    from the mat-surface-adsorption example."""
    from omai.map_data import build_instances
    from omai.stability.operator.nodes import ADSORPTION_ENERGY

    insts = build_instances()
    by_key = {(it["variable"], it["material"]): it for it in insts}

    it = by_key[("AdsorptionEnergy", "CO on Cu (111)")]
    assert it["value"] == -1.12
    assert it["units"] == "eV"
    assert it["source"]["kind"] == "simulation"
    assert it["node_uid"] == node_id(ADSORPTION_ENERGY)
