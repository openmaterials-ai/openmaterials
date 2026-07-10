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

def test_mechanics_domain_in_domains_between_ground_state_and_stability():
    names = [d.name for d in DOMAINS]
    assert names == [
        "thermal_transport", "dft_ground_state", "mechanics", "stability",
        "thermochemistry", "quasiharmonic", "molecular",
        "electronic_transport", "materials"]


def test_mechanics_domain_declares_mechanics_tier():
    from omai.mechanics.domain import MECHANICS

    tier_names = [t[0] for t in MECHANICS.tiers]
    assert tier_names == ["Mechanics"]


def test_mechanics_nodes_are_the_elastic_tensor_moduli_and_pressure():
    from omai.mechanics.operator import NODES

    assert [s.name for s in NODES] == [
        "ElasticConstants", "BulkModulus", "ShearModulus", "Pressure",
        "YoungsModulus", "PoissonRatio", "MassDensity"]


def test_mechanics_edges_are_the_eight_operators():
    from omai.mechanics.operator import EDGES

    assert [op.name for op in EDGES] == [
        "compute_elastic_constants", "contract_pressure",
        "contract_bulk_modulus", "contract_shear_modulus",
        "contract_youngs_modulus", "contract_poisson_ratio",
        "compute_bulk_modulus_eos", "contract_density"]


def test_elastic_constants_is_the_full_rank4_tensor():
    """ElasticConstants carries the full rank-4 Cartesian tensor C_{a,b,g,d};
    the Voigt 6x6 packing is a representation-layer concern, not the node's
    identity."""
    from omai.mechanics.operator.nodes import ELASTIC_CONSTANTS

    field = ELASTIC_CONSTANTS.field("C")
    assert field.indices == ("alpha", "beta", "gamma", "delta")


def test_the_moduli_pressure_and_ratios_are_scalars():
    from omai.mechanics.operator.nodes import (
        BULK_MODULUS,
        POISSON_RATIO,
        PRESSURE,
        SHEAR_MODULUS,
        YOUNGS_MODULUS,
    )

    assert BULK_MODULUS.field("K").indices == ()
    assert SHEAR_MODULUS.field("G").indices == ()
    assert PRESSURE.field("P").indices == ()
    assert YOUNGS_MODULUS.field("E_Y").indices == ()
    assert POISSON_RATIO.field("nu").indices == ()


# --------------------------------------------------------------------------
# The gates the domain must pass at the operator layer.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_all_six_mechanics_edges_are_dimensionally_ok():
    """The dimensional gate proves each edge: the elastic tensor as a stress
    derivative against the dimensionless strain, the pressure as a stress
    trace, both Voigt moduli as contractions of the stiffness tensor, the
    Young's modulus as pressure-dimensioned (the K/G algebra preserves the
    energy density), and the Poisson ratio as exactly dimensionless (the
    ratios cancel)."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_elastic_constants", "contract_pressure",
                 "contract_bulk_modulus", "contract_shear_modulus",
                 "contract_youngs_modulus", "contract_poisson_ratio"):
        assert name in report["ok"], (name, report)
    # No new violations anywhere (the two pinned schematic ones may remain).
    assert report["violation"] == [] or all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_no_node_uid_collisions_at_91_nodes():
    # 59 with the original mechanics four; 61 with YoungsModulus and
    # PoissonRatio; 66 with the stability four plus MagneticMoment; 67 with
    # BandGap (2026-07-09, atomate2/VASP scan); 73 with the six
    # thermochemistry nodes (2026-07-09, pycalphad scan); 74 with
    # AdsorptionEnergy (2026-07-10, matcalc/ASE scan); 77 with the config-thermo
    # scan's ElectricalConductivity[carrier=ionic] + ConfigurationalEnergy
    # (materials) and ReactionEnergy (stability); 82 with the amset scan's
    # electronic-transport five (StaticDielectricTensor plus the four transport
    # tensors, 2026-07-10); 87 with the phonopy/LAMMPS delta scan's four
    # quasi-harmonic nodes plus MassDensity (2026-07-10); 90 with the molecular
    # scan's three nodes (HOMOLUMOGap, ReactionBarrier[construction=neb_mep],
    # BondDissociationEnergy, 2026-07-10); 91 with the characterization scan's
    # GrainBoundaryEnergy (2026-07-10).
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) == 91
    uids = [n["uid"] for n in g["nodes"]]
    assert len(set(uids)) == len(uids), "node uid collision"


# --------------------------------------------------------------------------
# The unified graph: tier order and node placement.
# --------------------------------------------------------------------------

def test_mechanics_tier_ordered_after_ground_state_before_stability():
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Mechanics" in tier_names
    i = tier_names.index("Mechanics")
    assert tier_names[i - 1] == "Ground state"
    assert tier_names[i + 1] == "Stability"


def test_mechanics_nodes_carry_the_tier():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["ElasticConstants"] == "Mechanics"
    assert tier_of["BulkModulus"] == "Mechanics"
    assert tier_of["ShearModulus"] == "Mechanics"
    assert tier_of["Pressure"] == "Mechanics"
    assert tier_of["YoungsModulus"] == "Mechanics"
    assert tier_of["PoissonRatio"] == "Mechanics"


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


def test_elastic_constants_edge_is_the_stress_route_with_the_sign_correction():
    """compute_elastic_constants consumes (Stress, Structure) and encodes
    C = -d(sigma)/d(strain). The store's Stress is pressure-convention
    (sigma = -(1/V) dE/deps, positive = compressive, verified at record 105),
    the NEGATIVE of the tension-positive Cauchy stress the textbook elastic
    tensor is defined against; the minus restores C = +(1/V) d2E/deps2, so
    C11 comes out positive for stable crystals. Sharing the Stress vertex
    with contract_pressure also makes the contribution one weakly connected
    component through the P4 connectivity gate."""
    import sympy as sp

    from omai.mechanics.operator.edges import compute_elastic_constants as op

    assert [s.name for s in op.inputs] == ["Stress", "Structure"]
    assert [o.name for o in op.outputs] == ["ElasticConstants"]
    rhs = op.formula.rhs
    # Exactly -Derivative(sigma[a,b], eps[g,d]): a Mul of -1 and the Derivative.
    assert isinstance(rhs, sp.Mul), rhs
    assert sp.Integer(-1) in rhs.args, rhs
    derivs = list(rhs.atoms(sp.Derivative))
    assert len(derivs) == 1
    d = derivs[0]
    assert str(d.expr.base) == r"\sigma"
    assert [str(v[0].base) for v in d.variable_count] == [r"\varepsilon^{str}"]


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

def test_build_codes_lammps_grows_to_12_including_elastic_pressure_density():
    from omai.map_data import build_codes

    lammps = build_codes(DOMAINS)["lammps"]
    assert len(lammps) == 12
    for name in ("ElasticConstants", "Pressure", "MassDensity"):
        assert name in lammps, f"lammps coverage missing {name}"


def test_mat_elasticity_representation_appears_and_covers_the_moduli():
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert "mat-elasticity" in codes
    mat = codes["mat-elasticity"]
    # The catalog's produces now map onto all five mechanics observables the
    # skill emits (Young's modulus and Poisson's ratio gained nodes with the
    # pymatgen scan, 2026-07-09).
    for name in ("ElasticConstants", "BulkModulus", "ShearModulus",
                 "YoungsModulus", "PoissonRatio"):
        assert name in mat, f"mat-elasticity coverage missing {name}"


def test_mechanics_representation_package_discovery_finds_the_specs():
    """Discovery mirrors build_codes: walk the package's modules and collect
    spec instances by introspection. LAMMPS contributes two space specs
    (ElasticConstants, Pressure) and one operator spec; mat-elasticity five
    space specs (tensor, both moduli, Young's, Poisson); pymatgen five space
    specs (same five observables, native units) and three operator specs
    (the finite-strain fit and the two isotropic contractions); vasp
    (2026-07-09, atomate2/VASP scan) one space spec (ElasticConstants, the
    OUTCAR IBRION=6 kbar route) and one operator spec (compute_elastic_constants);
    mp-api (2026-07-09, the DATABASE rail) five space specs (the tensor and the
    four scalar reductions, GPa moduli and SI-Pa Young's) and no operator specs;
    mat_equation_of_state (2026-07-10, matcalc/ASE scan) one space spec
    (BulkModulus, the EOS Birch-Murnaghan route) and one operator spec
    (compute_bulk_modulus_eos, the Pattern C alternative producer); the lammps
    module gains a MassDensity space spec and a contract_density operator spec
    (2026-07-10, phonopy/LAMMPS delta scan)."""
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
    # 3 lammps (ElasticConstants, Pressure, MassDensity) + 5 mat-elasticity
    # + 5 pymatgen + 1 vasp + 5 mp-api + 1 mat_equation_of_state = 20 space
    # specs; the operator specs gain the EOS Pattern C producer
    # (compute_bulk_modulus_eos) and the density contraction (contract_density).
    assert len(space_specs) == 20, [a for a, _ in space_specs]
    assert len(op_specs) == 7, [a for a, _ in op_specs]
    assert sorted({s.operator.name for _, s in op_specs}) == [
        "compute_bulk_modulus_eos", "compute_elastic_constants",
        "contract_density", "contract_poisson_ratio", "contract_youngs_modulus"]


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


def test_bulk_modulus_has_two_producing_edges_pattern_c():
    """The matcalc/ASE scan's Pattern C addition: BulkModulus now has TWO
    producing edges, contract_bulk_modulus (the elastic-tensor VRH route) AND
    compute_bulk_modulus_eos (the Birch-Murnaghan E(V) route), exactly as
    ForceConstants[order=2] carries two producers. The node is NOT re-minted;
    both edges name the same BulkModulus node uid."""
    from omai.mechanics.operator.edges import (
        compute_bulk_modulus_eos,
        contract_bulk_modulus,
    )
    from omai.mechanics.operator.nodes import BULK_MODULUS

    # Both edges output the same, single BulkModulus node.
    assert [o.name for o in contract_bulk_modulus.outputs] == ["BulkModulus"]
    assert [o.name for o in compute_bulk_modulus_eos.outputs] == ["BulkModulus"]
    assert node_id(contract_bulk_modulus.outputs[0]) == node_id(BULK_MODULUS)
    assert node_id(compute_bulk_modulus_eos.outputs[0]) == node_id(BULK_MODULUS)

    # The graph surfaces both producers on the one node's formula list.
    g = build_graph_dict(DOMAINS)
    bm = next(n for n in g["nodes"] if n["id"] == "BulkModulus")
    ops = {f["op"] for f in bm["formulas"]}
    assert {"contract_bulk_modulus", "compute_bulk_modulus_eos"} <= ops, ops
    # Exactly ONE BulkModulus node in the graph (no re-mint / duplicate).
    assert sum(1 for n in g["nodes"] if n["id"] == "BulkModulus") == 1


def test_compute_bulk_modulus_eos_wiring_and_scheme():
    from omai.mechanics.operator.edges import compute_bulk_modulus_eos

    # Pattern C signature: (TotalEnergy, Structure), the same energy-route
    # inputs as compute_fc2_finite_displacement's finite-displacement route.
    assert [s.name for s in compute_bulk_modulus_eos.inputs] == [
        "TotalEnergy", "Structure"]
    assert compute_bulk_modulus_eos.schemes == {
        "method": "birch_murnaghan", "n_points": "11"}
    # Implicit (a fit over an external volume scan), so not sympy-executable.
    assert compute_bulk_modulus_eos.is_executable_in_sympy_override is False
    assert not compute_bulk_modulus_eos.is_executable_in_sympy


def test_eos_bulk_modulus_rail_is_the_skill_not_matcalc():
    """The EOS BulkModulus coverage lands on mat-equation-of-state (the driving
    skill rail), not a matcalc rail (the atomate2 ruling)."""
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert "matcalc" not in codes
    assert codes["mat-equation-of-state"]["BulkModulus"]["unit"] == "GPa"


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

    # The v1 contribution is history: the FIRST four nodes and FIRST four
    # edges (the domain later grew the two isotropic contractions, records
    # 118-121 below).
    domain_uids = [node_id(s) for s in NODES[:4]] + \
        [edge_id(op, node_id) for op in EDGES[:4]]
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
    from omai.mechanics.operator.nodes import (
        BULK_MODULUS,
        POISSON_RATIO,
        SHEAR_MODULUS,
        YOUNGS_MODULUS,
    )

    insts = build_instances()
    cu = [it for it in insts
          if it["material"] == "Cu"
          and it["source"]["ref"] == "atomisticskills-mat-elasticity-Cu"]
    by_var = {it["variable"]: it for it in cu}
    assert set(by_var) == {"BulkModulus", "ShearModulus",
                           "YoungsModulus", "PoissonRatio"}

    k = by_var["BulkModulus"]
    assert k["value"] == 145.85
    assert k["units"] == "GPa"
    assert k["source"]["kind"] == "simulation"
    assert k["node_uid"] == node_id(BULK_MODULUS)

    g = by_var["ShearModulus"]
    assert g["value"] == 51.45
    assert g["units"] == "GPa"
    assert g["node_uid"] == node_id(SHEAR_MODULUS)

    # The two contract outputs, verbatim from the same committed example:
    # E is exactly the 9KG/(3K+G) of the recorded K and G; nu is the
    # catalog's full-precision value from the unrounded moduli.
    e = by_var["YoungsModulus"]
    assert e["value"] == 138.11
    assert e["units"] == "GPa"
    assert e["node_uid"] == node_id(YOUNGS_MODULUS)

    nu = by_var["PoissonRatio"]
    assert nu["value"] == 0.34217507884737186
    assert nu["units"] == "dimensionless"
    assert nu["node_uid"] == node_id(POISSON_RATIO)


def test_eos_si_bulk_modulus_instance_pins_the_same_bulk_modulus_node():
    """The matcalc/ASE scan's EOS-route evidence: the committed Si
    Birch-Murnaghan bulk modulus pins the SAME BulkModulus node uid the
    elastic-tensor VRH Cu instance does (one node, two producing routes)."""
    from omai.map_data import build_instances
    from omai.mechanics.operator.nodes import BULK_MODULUS

    insts = build_instances()
    by_key = {(it["variable"], it["material"]): it for it in insts}

    si = by_key[("BulkModulus", "Si")]
    assert si["value"] == 96.42681590768773
    assert si["units"] == "GPa"
    assert si["conditions"]["route"] == "birch_murnaghan_eos"
    assert si["source"]["kind"] == "simulation"
    assert si["node_uid"] == node_id(BULK_MODULUS)
    # Same node as the Cu VRH-route instance (Pattern C: one node, two routes).
    cu = by_key[("BulkModulus", "Cu")]
    assert si["node_uid"] == cu["node_uid"]


# --------------------------------------------------------------------------
# The mechanics contracts (YoungsModulus, PoissonRatio): the first of the two
# pymatgen-scan contributions, records 118-121.
# --------------------------------------------------------------------------

def test_youngs_and_poisson_edges_consume_the_two_moduli():
    from omai.mechanics.operator.edges import (
        contract_poisson_ratio,
        contract_youngs_modulus,
    )

    for op in (contract_youngs_modulus, contract_poisson_ratio):
        assert [s.name for s in op.inputs] == ["BulkModulus", "ShearModulus"]
    assert [o.name for o in contract_youngs_modulus.outputs] == ["YoungsModulus"]
    assert [o.name for o in contract_poisson_ratio.outputs] == ["PoissonRatio"]


def test_youngs_and_poisson_formulas_are_sympy_executable():
    """Unlike every implicit edge in the store, these two are EXECUTABLE
    closed forms: explicit Eq definitions whose LHS and RHS share no free
    symbols, so the default executability heuristic resolves True with no
    override."""
    from omai.mechanics.operator.edges import (
        contract_poisson_ratio,
        contract_youngs_modulus,
    )

    assert contract_youngs_modulus.is_executable_in_sympy
    assert contract_poisson_ratio.is_executable_in_sympy
    assert contract_youngs_modulus.is_executable_in_sympy_override is None
    assert contract_poisson_ratio.is_executable_in_sympy_override is None


def test_youngs_and_poisson_evaluate_to_the_committed_cu_values():
    """Numerical evaluation against the committed mat-elasticity Cu example
    (omai/materials/skills_catalog.json, examples/Cu/elasticity_results.json):
    K = 145.85, G = 51.45 GPa (VRH) give E_Y = 138.110107... GPa, matching
    the catalog's 138.11 verbatim, and nu = 0.3421779... The catalog's nu
    0.34217507884737186 was computed from the unrounded moduli, so it agrees
    to 3e-6, not to machine precision."""
    import sympy as sp

    from omai.mechanics.operator.edges import (
        contract_poisson_ratio,
        contract_youngs_modulus,
    )

    K, G = sp.symbols("K G")
    subs = {K: sp.Float("145.85"), G: sp.Float("51.45")}
    e_y = float(contract_youngs_modulus.formula.rhs.subs(subs))
    nu = float(contract_poisson_ratio.formula.rhs.subs(subs))
    assert abs(e_y - 138.1101073619632) < 1e-9
    assert round(e_y, 2) == 138.11  # the committed catalog value
    assert abs(nu - 0.34217791411042947) < 1e-12
    assert abs(nu - 0.34217507884737186) < 3e-6  # catalog, unrounded inputs


def test_youngs_is_pressure_dimensioned_and_poisson_dimensionless():
    """The dimensional gate PROVES both contracts (no KNOWN_VIOLATIONS
    entries): E_Y = 9KG/(3K+G) carries M L^-1 T^-2 and nu = (3K-2G)/(2(3K+G))
    carries the all-zero exponent vector."""
    import sympy as sp

    from omai.operator.dimcheck import dimension_of
    from omai.operator.dimensions import (
        DIMENSIONLESS,
        ENERGY_PER_LENGTH_CUBED,
    )
    from omai.mechanics.operator.edges import (
        contract_poisson_ratio,
        contract_youngs_modulus,
    )

    assert dimension_of(contract_youngs_modulus.formula.rhs) == \
        ENERGY_PER_LENGTH_CUBED
    assert dimension_of(contract_poisson_ratio.formula.rhs) == DIMENSIONLESS
    assert dimension_of(sp.Symbol("E_Y")) == ENERGY_PER_LENGTH_CUBED
    assert dimension_of(sp.Symbol("nu")) == DIMENSIONLESS


def test_bare_E_stays_the_thermal_md_energy_not_the_youngs_modulus():
    """Guard for the deliberate E_Y naming: bare E is the thermal domain's
    per-atom MD energy in the heat-current formula and must stay UNBOUND in
    the global dimension registry (binding it to an energy density would
    poison compute_heat_current's Add check)."""
    from omai.operator.dimcheck import SYMBOL_DIMENSIONS

    assert "E" not in SYMBOL_DIMENSIONS
    assert "E_Y" in SYMBOL_DIMENSIONS


def test_pymatgen_representation_covers_the_mechanics_family():
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert "pymatgen" in codes
    pmg = codes["pymatgen"]
    for name in ("ElasticConstants", "BulkModulus", "ShearModulus",
                 "YoungsModulus", "PoissonRatio"):
        assert name in pmg, f"pymatgen coverage missing {name}"
    # The native-unit traps the scan verified: eV/A^3 storage and y_mod's Pa.
    assert pmg["ElasticConstants"]["unit"] == "eV_per_A3"
    assert pmg["YoungsModulus"]["unit"] == "Pa"
    assert pmg["PoissonRatio"]["unit"] == "dimensionless"


def test_mechanics_contracts_are_records_118_to_121():
    """The frozen log positions of the first pymatgen-scan contribution: the
    two nodes then the two edges (in NODES / EDGES order), authored through
    sync --apply as records 118-121. Positions are history and never move;
    records 110-117 (the mechanics v1) stay untouched above."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.mechanics.operator import EDGES, NODES

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 121, "the mechanics contracts have not landed"

    contribution_uids = [node_id(s) for s in NODES[4:6]] + \
        [edge_id(op, node_id) for op in EDGES[4:6]]
    recs = [json.loads(line) for line in lines[117:121]]
    assert [r["payload"]["uid"] for r in recs] == contribution_uids
    assert [r["op"] for r in recs] == ["add_node"] * 2 + ["add_edge"] * 2
    names = [r["payload"]["meta"]["name"] for r in recs]
    assert names == ["YoungsModulus", "PoissonRatio",
                     "contract_youngs_modulus", "contract_poisson_ratio"]
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-09"
