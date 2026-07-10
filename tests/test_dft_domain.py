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

def test_dft_domain_in_domains_after_thermal():
    # The mechanics domain now sits between dft and materials in DOMAINS order
    # (thermal, dft, mechanics, materials); dft still follows thermal directly.
    names = [d.name for d in DOMAINS]
    assert names[:2] == ["thermal_transport", "dft_ground_state"]
    assert "dft_ground_state" in names


def test_dft_domain_declares_ground_state_tier():
    from omai.dft_ground_state.domain import DFT_GROUND_STATE

    tier_names = [t[0] for t in DFT_GROUND_STATE.tiers]
    assert tier_names == ["Ground state"]


def test_dft_nodes_are_structure_energy_forces_stress_moments():
    from omai.dft_ground_state.operator import NODES

    assert [s.name for s in NODES] == [
        "Structure", "TotalEnergy", "Forces", "Stress", "MagneticMoment",
        "BandGap"]


def test_dft_edges_are_the_ground_state_operators():
    # Derived from the live EDGES tuple order; extend this list when the
    # domain grows (the store pins history separately below).
    from omai.dft_ground_state.operator import EDGES

    assert [op.name for op in EDGES] == [
        "solve_ground_state", "compute_forces_hf", "compute_stress_cell",
        "compute_fc2_finite_displacement", "compute_magnetic_moments",
        "compute_band_gap"]


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


def test_no_node_uid_collisions():
    # The graph grows as domains land (55 with dft, 59 with mechanics); the
    # invariant this test pins is that node uids stay collision-free, not a
    # fixed count. The DFT domain adds four nodes over the thermal baseline.
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) >= 55
    uids = [n["uid"] for n in g["nodes"]]
    assert len(set(uids)) == len(uids), "node uid collision"


# --------------------------------------------------------------------------
# The unified graph: tier order and node placement.
# --------------------------------------------------------------------------

def test_ground_state_tier_ordered_after_md_before_mechanics():
    # The Ground state tier follows Molecular dynamics; the mechanics domain
    # now renders its Mechanics tier immediately after Ground state (Diffusion
    # follows Mechanics). This pins Ground state's position relative to its
    # neighbours as the tier list grows.
    g = build_graph_dict(DOMAINS)
    tier_names = [t["name"] for t in g["tiers"]]
    assert "Ground state" in tier_names
    i = tier_names.index("Ground state")
    assert tier_names[i - 1] == "Molecular dynamics"
    assert tier_names[i + 1] == "Mechanics"


def test_ground_state_nodes_carry_the_tier_and_structure_in_sources():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["TotalEnergy"] == "Ground state"
    assert tier_of["Forces"] == "Ground state"
    assert tier_of["Stress"] == "Ground state"
    assert tier_of["MagneticMoment"] == "Ground state"
    assert tier_of["BandGap"] == "Ground state"
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

    new_names = {"TotalEnergy", "Forces", "Stress", "MagneticMoment"}
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
    modules and collect spec instances by introspection. QE contributes four
    space specs and one operator spec; pymatgen (2026-07-09) four space specs
    (Structure, TotalEnergy, Stress, MagneticMoment) and one operator spec
    (compute_magnetic_moments); the three MLIP rails (2026-07-09) ground the
    shared Potential plus the ground-state E/F/S, matgl additionally the CHGNet
    MagneticMoment head, each with one solve_ground_state operator spec."""
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
    by_rep_space, by_rep_op = {}, {}
    for _, s in space_specs:
        by_rep_space.setdefault(s.representation_name, set()).add(s.space.name)
    for _, s in op_specs:
        by_rep_op.setdefault(s.representation_name, set()).add(s.operator.name)
    assert by_rep_space["qe"] == {
        "Structure", "TotalEnergy", "Forces", "Stress"}
    assert by_rep_op["qe"] == {"solve_ground_state"}
    assert by_rep_space["pymatgen"] == {
        "Structure", "TotalEnergy", "Stress", "MagneticMoment"}
    assert by_rep_op["pymatgen"] == {"compute_magnetic_moments"}
    # The three MLIP rails: each grounds Potential + TotalEnergy/Forces/Stress;
    # matgl additionally carries the CHGNet MagneticMoment head.
    assert by_rep_space["mace"] == {
        "Potential", "TotalEnergy", "Forces", "Stress"}
    assert by_rep_space["fairchem"] == {
        "Potential", "TotalEnergy", "Forces", "Stress"}
    assert by_rep_space["matgl"] == {
        "Potential", "TotalEnergy", "Forces", "Stress", "MagneticMoment"}
    for rep in ("mace", "matgl", "fairchem"):
        assert by_rep_op[rep] == {"solve_ground_state"}, rep
    # vasp (2026-07-09, atomate2/VASP scan): six space specs (the four QE
    # grounds plus MagneticMoment and the new electronic BandGap) and four
    # operator specs (the SCF solve, the band-gap read, and the force/stress
    # responses read off the same TaskDoc).
    assert by_rep_space["vasp"] == {
        "Structure", "TotalEnergy", "Forces", "Stress", "MagneticMoment",
        "BandGap"}
    assert by_rep_op["vasp"] == {
        "solve_ground_state", "compute_band_gap", "compute_forces_hf",
        "compute_stress_cell"}
    # The mp-api DATABASE rail (2026-07-09) grounds three dft-domain nodes by
    # RETRIEVAL (Structure, MagneticMoment, BandGap) and carries no operator
    # specs (MP retrieves; it does not run the producing operators).
    assert by_rep_space["mp-api"] == {
        "Structure", "MagneticMoment", "BandGap"}
    assert "mp-api" not in by_rep_op
    # ase (2026-07-10, matcalc/ASE scan): the relaxed-Structure producer spec
    # lives here (where the Structure node lives); the ase Potential and
    # Trajectory specs live in the thermal-transport package. No operator spec.
    assert by_rep_space["ase"] == {"Structure"}
    assert "ase" not in by_rep_op
    # 8 (qe 4 + pymatgen 4) + mace 4 + matgl 5 + fairchem 4 + vasp 6 + mp-api 3
    # + ase 1 = 31 space specs; 2 (qe, pymatgen operator) + 3 MLIP + 4 vasp = 9
    # operator specs (mp-api and ase add none).
    assert len(space_specs) == 31, [a for a, _ in space_specs]
    assert len(op_specs) == 9, [a for a, _ in op_specs]


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
# The vasp rail (atomate2/VASP scan, arXiv 2605.24002): a SECOND representation
# of the QE-grounded ground state plus MagneticMoment and the new BandGap,
# spanning three domains (dft, mechanics, thermal).
# --------------------------------------------------------------------------

def test_vasp_ground_state_units_are_the_declared_ones():
    from omai.dft_ground_state.representation.vasp import (
        VASP_BAND_GAP,
        VASP_FORCES,
        VASP_MAGNETIC_MOMENT,
        VASP_STRESS,
        VASP_STRUCTURE,
        VASP_TOTAL_ENERGY,
    )

    # eV per cell, eV/A, kbar (NOT GPa), mu_B, eV for the gap.
    assert VASP_TOTAL_ENERGY.observable_units == {"E_tot": "ev"}
    assert VASP_FORCES.observable_units == {"F": "eV_per_A"}
    assert VASP_STRESS.observable_units == {"sigma": "kbar"}
    assert VASP_MAGNETIC_MOMENT.observable_units == {"m": "mu_B"}
    assert VASP_BAND_GAP.observable_units == {"E_gap": "ev"}
    # Structure is opaque: an artifact (POSCAR/CONTCAR), never a numeric unit.
    assert VASP_STRUCTURE.observable_units == {}


def test_vasp_stress_is_kbar_compression_positive_no_flip_to_store():
    """The scan's central finding: VASP stress is kbar (both routes, NOT GPa),
    compression-positive (the SAME sign as the map's Stress store), so VASP ->
    store needs NO sign flip. The 10x AtomisticSkills bug and the ASE re-sign
    are recorded but do not change the stored representation."""
    from omai.dft_ground_state.representation.vasp import VASP_STRESS

    assert VASP_STRESS.observable_units == {"sigma": "kbar"}
    notes = VASP_STRESS.notes
    assert "compression-positive" in notes
    assert "NO sign flip" in notes
    assert "10x too large" in notes  # the AtomisticSkills atomate2_utils.py:456 defect
    assert "units of kB" in notes  # the emmet OutputDoc contract
    assert "elastic.py:518-519" in notes  # the independent confirmation anchor


def test_vasp_total_energy_declares_the_e_0_energy_variant():
    """TotalEnergy is the e_0_energy (sigma->0) variant; the other two VASP
    variants are named as DIFFERENT quantities, not this node."""
    from omai.dft_ground_state.representation.vasp import VASP_TOTAL_ENERGY

    notes = VASP_TOTAL_ENERGY.notes
    assert "e_0_energy" in notes
    assert "e_fr_energy" in notes
    assert "e_wo_entrp" in notes
    assert "RELATIVE energies" in notes  # the absolute-zero caveat


def test_vasp_band_gap_notes_record_the_ks_gap_and_functional_dependence():
    """The KS-gap vs fundamental-gap caveat, the functional dependence, and the
    BandStructureMaker producer are the facts on the BandGap spec."""
    from omai.dft_ground_state.representation.vasp import (
        VASP_BAND_GAP,
        VASP_COMPUTE_BAND_GAP,
    )

    notes = VASP_BAND_GAP.notes
    assert "Kohn-Sham" in notes
    assert "NOT the fundamental" in notes
    assert "functional" in notes
    # The compute edge's scheme is quantity=ks_gap; the maker is BandStructureMaker.
    assert VASP_COMPUTE_BAND_GAP.operator.schemes == {"quantity": "ks_gap"}
    assert "BandStructureMaker" in VASP_COMPUTE_BAND_GAP.notes


def test_vasp_solve_ground_state_declares_the_incar_discretizations():
    from omai.dft_ground_state.representation.vasp import VASP_SOLVE_GROUND_STATE

    for key in ("ENCUT", "k_mesh", "smearing", "EDIFF", "potcar_xc"):
        assert key in VASP_SOLVE_GROUND_STATE.discretization_choices, key
    # atomate2 is the workflow layer, pinned to the verified 0.1.4 wheel.
    assert "0.1.4" in VASP_SOLVE_GROUND_STATE.notes
    assert "StaticMaker" in VASP_SOLVE_GROUND_STATE.notes


def test_vasp_rail_spans_three_domains_in_build_codes():
    """The vasp rail is cross-domain (like the pymatgen encode): dft
    (Structure/E/F/S/MagneticMoment/BandGap), mechanics (ElasticConstants),
    thermal (BornCharges/DielectricTensor) = nine space specs on one rail."""
    from omai.map_data import build_codes

    vasp = build_codes(DOMAINS)["vasp"]
    assert set(vasp) == {
        "Structure", "TotalEnergy", "Forces", "Stress", "MagneticMoment",
        "BandGap", "ElasticConstants", "BornCharges", "DielectricTensor"}


def test_vasp_elastic_constants_is_kbar_outcar_route_expected_agree():
    """The mechanics vasp spec: ElasticConstants in kbar (OUTCAR IBRION=6
    direct), an EXPECTED_AGREE alternate to the matcalc eV/A^3 route, with the
    from_independent_strains(vasp=True) stress-fit route noted as distinct."""
    from omai.mechanics.representation.vasp import VASP_ELASTIC_CONSTANTS

    assert VASP_ELASTIC_CONSTANTS.observable_units == {"C": "kbar"}
    notes = VASP_ELASTIC_CONSTANTS.notes
    assert "kBar" in notes  # the OUTCAR header
    assert "IBRION=6" in notes
    assert "EXPECTED_AGREE" in notes
    assert "elastic.py:518-519" in notes  # the distinct stress-fit route


def test_vasp_thermal_response_tensors_are_the_lepsilon_producers():
    """The thermal vasp specs: BornCharges and the STATIC DielectricTensor from
    LEPSILON (dimensionless), the direct DFT-domain producers, with the
    frequency-dependent LOPTICS spectrum flagged as a deferred distinct node."""
    from omai.thermal_transport.representation.vasp import (
        VASP_BORN_CHARGES,
        VASP_DIELECTRIC_TENSOR,
    )

    assert VASP_BORN_CHARGES.observable_units == {"Z_star": "dimensionless"}
    assert VASP_DIELECTRIC_TENSOR.observable_units == {
        "epsilon_infinity": "dimensionless"}
    assert "LEPSILON" in VASP_BORN_CHARGES.notes
    assert "LOPTICS" in VASP_DIELECTRIC_TENSOR.notes  # the deferred spectrum


# --------------------------------------------------------------------------
# The MLIP rails (mace / matgl / fairchem): representation-only, grounding the
# shared Potential plus the ground-state E/F/S (matgl also MagneticMoment).
# --------------------------------------------------------------------------

def test_build_codes_has_the_three_mlip_rails_with_node_coverage():
    from omai.map_data import build_codes

    codes = build_codes(DOMAINS)
    assert set(codes["mace"]) == {"Potential", "TotalEnergy", "Forces", "Stress"}
    assert set(codes["fairchem"]) == {
        "Potential", "TotalEnergy", "Forces", "Stress"}
    assert set(codes["matgl"]) == {
        "Potential", "TotalEnergy", "Forces", "Stress", "MagneticMoment"}


def test_mlip_efs_units_are_ase_ev_not_gpa():
    """All three rails emit the ASE native units: eV per cell, eV/A, eV/A^3 -
    the stress is eV/A^3, NOT GPa (the matgl native GPa default is overridden
    in the wrapper). Potential is opaque and carries no unit."""
    from omai.dft_ground_state.representation.mace import (
        MACE_FORCES, MACE_POTENTIAL, MACE_STRESS, MACE_TOTAL_ENERGY,
    )
    from omai.dft_ground_state.representation.matgl import (
        MATGL_FORCES, MATGL_MAGNETIC_MOMENT, MATGL_POTENTIAL, MATGL_STRESS,
        MATGL_TOTAL_ENERGY,
    )
    from omai.dft_ground_state.representation.fairchem import (
        FAIRCHEM_FORCES, FAIRCHEM_POTENTIAL, FAIRCHEM_STRESS,
        FAIRCHEM_TOTAL_ENERGY,
    )

    for energy in (MACE_TOTAL_ENERGY, MATGL_TOTAL_ENERGY, FAIRCHEM_TOTAL_ENERGY):
        assert energy.observable_units == {"E_tot": "ev"}
    for forces in (MACE_FORCES, MATGL_FORCES, FAIRCHEM_FORCES):
        assert forces.observable_units == {"F": "eV_per_A"}
    for stress in (MACE_STRESS, MATGL_STRESS, FAIRCHEM_STRESS):
        assert stress.observable_units == {"sigma": "eV_per_A3"}
        assert "GPa" not in stress.observable_units.values()
    # matgl's CHGNet magmom head is mu_B per site.
    assert MATGL_MAGNETIC_MOMENT.observable_units == {"m": "mu_B"}
    # Potential is opaque: an artifact (the checkpoint), never a numeric unit.
    for potential in (MACE_POTENTIAL, MATGL_POTENTIAL, FAIRCHEM_POTENTIAL):
        assert potential.observable_units == {}


def test_mlip_stress_notes_record_ase_voigt_order_and_the_store_sign_factor():
    """The stress notes must record the ASE Voigt order (xx,yy,zz,yz,xz,xy),
    that ASE is tensile-positive, and that the store convention is the OPPOSITE
    sign (factor -1) so a consumer knows how to reach sigma_store."""
    from omai.dft_ground_state.representation.mace import MACE_STRESS
    from omai.dft_ground_state.representation.matgl import MATGL_STRESS
    from omai.dft_ground_state.representation.fairchem import FAIRCHEM_STRESS

    for stress in (MACE_STRESS, MATGL_STRESS, FAIRCHEM_STRESS):
        notes = stress.notes
        assert "xx, yy, zz, yz, xz, xy" in notes
        assert "tensile-positive" in notes.lower()
        assert "-1" in notes
        assert "store" in notes.lower()


def test_matgl_stress_notes_record_the_gpa_default_override_and_use_voigt():
    """matgl's PESCalculator native stress default IS GPa (overridden in the
    wrapper to eV/A3) and use_voigt defaults False (a 3x3 the get_stress()
    reduces): both source-verified facts belong in the notes."""
    from omai.dft_ground_state.representation.matgl import MATGL_STRESS

    notes = MATGL_STRESS.notes
    assert "GPa" in notes
    assert "eV/A3" in notes or "eV/A^3" in notes
    assert "use_voigt" in notes


def test_matgl_magmom_notes_record_the_chgnet_head_and_the_charges_mislabel():
    """The CHGNet sitewise magmom head surfaced as results['magmoms'] under
    calc_magmom, and the wrapper's 'charges' capability mislabel, are the two
    source-verified facts the orchestrator required on this spec."""
    from omai.dft_ground_state.representation.matgl import MATGL_MAGNETIC_MOMENT

    notes = MATGL_MAGNETIC_MOMENT.notes
    assert "magmoms" in notes
    assert "_chgnet.py:437" in notes
    assert "matgl_wrapper.py:288" in notes
    assert "mislabel" in notes.lower()


def test_fairchem_notes_record_force_type_and_nve_conservation():
    """fairchem ships conservative and direct heads; force_type {conservative,
    direct} and the NVE non-conservation of a direct head must be in the notes
    (on the Potential spec and the Forces spec)."""
    from omai.dft_ground_state.representation.fairchem import (
        FAIRCHEM_FORCES, FAIRCHEM_POTENTIAL,
    )

    for spec in (FAIRCHEM_POTENTIAL, FAIRCHEM_FORCES):
        notes = spec.notes
        assert "conservative" in notes
        assert "direct" in notes
        assert "NVE" in notes


def test_mace_notes_record_committee_uncertainty_as_a_deferred_candidate():
    """The committee-uncertainty availability (energy_var / forces_var when
    num_models>1) is recorded as a deferred node candidate, NOT encoded."""
    from omai.dft_ground_state.representation.mace import MACE_POTENTIAL

    notes = MACE_POTENTIAL.notes
    assert "energy_var" in notes and "forces_var" in notes
    assert "mace.py:704-717" in notes
    assert "num_models>1" in notes or "num_models > 1" in notes


def test_mace_notes_record_the_cross_engine_lammps_agreement_candidate():
    """mat-lammps-md compiles the same MACE checkpoint into a LAMMPS pair style:
    the notes flag the same-PES-two-engines EXPECTED_AGREE candidate and the
    ~1e-8 CODATA-generation tolerance."""
    from omai.dft_ground_state.representation.mace import MACE_POTENTIAL

    notes = MACE_POTENTIAL.notes
    assert "mat-lammps-md" in notes
    assert "EXPECTED_AGREE" in notes
    assert "1e-8" in notes


def test_mace_notes_record_the_mat_elasticity_matcalc_provenance_chain():
    """The mat-elasticity Cu instances were computed with a MACE checkpoint via
    matcalc; that provenance chain lives in the mace notes until a future
    instance-schema slice (committed instances are NOT retro-edited)."""
    from omai.dft_ground_state.representation.mace import MACE_POTENTIAL

    notes = MACE_POTENTIAL.notes
    assert "mat-elasticity" in notes
    assert "matcalc" in notes


def test_mlip_potentials_ground_the_shared_potential_node():
    """The three rails ground the SAME shared Potential node the thermal-transport
    graph uses (imported via materials.shared_primitives), not a duplicate."""
    from omai.materials.operator.shared_primitives import POTENTIAL as SHARED
    from omai.dft_ground_state.representation.mace import MACE_POTENTIAL
    from omai.dft_ground_state.representation.matgl import MATGL_POTENTIAL
    from omai.dft_ground_state.representation.fairchem import FAIRCHEM_POTENTIAL

    for spec in (MACE_POTENTIAL, MATGL_POTENTIAL, FAIRCHEM_POTENTIAL):
        assert spec.space is SHARED


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

    # The v1 contribution is history: exactly the FIRST four nodes plus the
    # FIRST three edges (the domain later grew: record 109 below, and the
    # MagneticMoment node landed 2026-07-09 as part of records 122-131).
    v1_edges = [op for op in EDGES if op.name in (
        "solve_ground_state", "compute_forces_hf", "compute_stress_cell")]
    domain_uids = [node_id(s) for s in NODES[:4]] + \
        [edge_id(op, node_id) for op in v1_edges]
    recs = [json.loads(line) for line in lines[101:108]]
    assert [r["payload"]["uid"] for r in recs] == domain_uids
    assert [r["op"] for r in recs] == ["add_node"] * 4 + ["add_edge"] * 3
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-08"

    # Record 109: the finite-displacement FC2 route (Pattern C producer),
    # the third post-genesis contribution.
    assert len(lines) >= 109
    fd_edge = next(op for op in EDGES
                   if op.name == "compute_fc2_finite_displacement")
    rec_109 = json.loads(lines[108])
    assert rec_109["op"] == "add_edge"
    assert rec_109["payload"]["uid"] == edge_id(fd_edge, node_id)


def test_band_gap_contribution_is_records_132_133():
    """The atomate2/VASP scan's single node landed as records 132-133 (log
    positions 131-132): the BandGap add_node then the compute_band_gap
    add_edge, in NODES / EDGES order, authored through sync --apply on
    2026-07-09. Positions are history and never move."""
    import json
    from pathlib import Path

    from omai.operator.identity import edge_id
    from omai.dft_ground_state.operator.edges import compute_band_gap
    from omai.dft_ground_state.operator.nodes import BAND_GAP

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 133, "the band-gap contribution has not landed"

    rec_132 = json.loads(lines[131])
    assert rec_132["op"] == "add_node"
    assert rec_132["payload"]["uid"] == node_id(BAND_GAP)
    assert rec_132["payload"]["meta"]["name"] == "BandGap"

    rec_133 = json.loads(lines[132])
    assert rec_133["op"] == "add_edge"
    assert rec_133["payload"]["uid"] == edge_id(compute_band_gap, node_id)
    assert rec_133["payload"]["meta"]["name"] == "compute_band_gap"

    for r in (rec_132, rec_133):
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-09"
        assert "atomate2/VASP scan" in r["reason"]
        assert "2605.24002" in r["reason"]


# --------------------------------------------------------------------------
# Task 5: evidence: the first QE instances from the Si cross-check.
# --------------------------------------------------------------------------

def test_instances_bundle_32_records_all_uid_pinned():
    # 9 at genesis, 11 with the QE Si cross-check pair, 13 with the two
    # mat-elasticity Cu moduli, 22 with the nine pymatgen-scan values
    # (Cu E/nu, three Cu surface facets, LiFePO4 voltage, Fe moment, Li2O
    # formation and hull), 28 with the six mp-api-scan MP-retrieved values
    # (Li2S / LiS4 band gap, formation energy, and energy above hull from the
    # committed mat-db-mp query_mp li_s_stable.json), 30 with the two
    # matcalc/ASE-scan values (CO-on-Cu(111) adsorption energy and the Si EOS
    # Birch-Murnaghan bulk modulus), 32 with the two config-thermo-scan values
    # (the LGPS Nernst-Einstein RT ionic conductivity and the LiZnPO4 reaction
    # energy, both committed AtomisticSkills examples).
    from omai.map_data import build_instances

    insts = build_instances()
    assert len(insts) == 32
    for it in insts:
        assert it.get("node_uid"), f"instance for {it['variable']} lacks node_uid"


def test_qe_si_instances_exist_and_pin_the_live_node_uids():
    from omai.map_data import build_instances
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
    from omai.thermal_transport.operator.nodes import FREQUENCY_STATE

    insts = build_instances()
    qe_si = [it for it in insts
             if it["material"] == "Si" and it["source"]["ref"] == "qe"]
    by_var = {it["variable"]: it for it in qe_si}
    assert set(by_var) == {"TotalEnergy", "Frequency"}

    e = by_var["TotalEnergy"]
    assert e["value"] == -15.76602463
    assert e["units"] == "Ry"
    assert e["source"]["kind"] == "simulation"
    assert e["conditions"]["ecutwfc"] == "50 Ry"
    assert e["node_uid"] == node_id(TOTAL_ENERGY)

    f = by_var["Frequency"]
    assert f["value"] == 15.398
    assert f["source"]["kind"] == "simulation"
    assert f["conditions"]["q"] == "Gamma"
    assert f["node_uid"] == node_id(FREQUENCY_STATE)
