"""Tests for the molecular contribution (records 175-180).

The ORCA + MD/chem molecular scan (AtomisticSkills arXiv 2605.24002: the ORCA
quantum-chemistry skills chem-dft-orca-* and the MLIP/chem reaction skills
chem-neb-barrier, chem-ts-optimization, chem-bond-dissociation) lands ONE
contribution in a new molecular domain, ONE Molecular tier, THREE nodes with
three implicit edges:

  * HOMOLUMOGap (compute_homo_lumo_gap): the KS gap of two discrete frontier MOs,
    a COUSIN of the periodic BandGap, never equated;
  * ReactionBarrier[construction=neb_mep] (compute_reaction_barrier): the CI-NEB
    minimum-energy-path barrier, minted ONCE with the construction LABEL_KEY so
    the sella and ORCA routes join without a re-mint; DISTINCT from the Arrhenius
    ActivationEnergy;
  * BondDissociationEnergy (compute_bond_dissociation): a labeled sibling of the
    solid-state ReactionEnergy on the per-molecule basis.

Three nodes + three edges = records 175-180. Two rails land: orca (the map's
first molecular code) and openmm (a new classical-force-field engine), both
covering pre-existing nodes (TotalEnergy, Forces, Temperature, Pressure,
Trajectory) as well as the new molecular nodes.

Load-bearing proofs here:

  * the three new nodes REUSE the plain ENERGY exponent vector but stay DISTINCT
    uids by their quantity tags (name-based identity);
  * ReactionBarrier vs Arrhenius ActivationEnergy distinctness (the name-collision
    trap);
  * HOMOLUMOGap vs BandGap distinctness (the band / discrete-orbital category
    error);
  * the construction LABEL_KEY round-trips through the node identity;
  * the orca / openmm rails auto-parametrize at the operator/representation
    boundary (discovered specs, correct serving units).

All three new edges carry opaque solver functions, classified SKIPPED by the
dimensional gate.
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.map_data import DOMAINS, build_codes, build_graph_dict
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
# Domain shape, tier, and edge wiring.
# --------------------------------------------------------------------------

def test_molecular_domain_declares_the_single_tier_after_quasiharmonic():
    from omai.molecular.domain import MOLECULAR

    assert [t[0] for t in MOLECULAR.tiers] == ["Molecular"]
    assert MOLECULAR.tiers[0][1] == (
        "Molecular quantum chemistry and reaction energetics: orbital "
        "gaps, reaction barriers, and bond dissociation.")
    used = {n.tier for n in MOLECULAR.nodes}
    assert used == {"Molecular"}
    # Placed after quasiharmonic in DOMAINS.
    names = [d.name for d in DOMAINS]
    assert names[names.index("quasiharmonic") + 1] == "molecular"


def test_molecular_nodes_and_edges():
    from omai.molecular.operator import EDGES, NODES

    # Three from the ORCA + MD/chem scan; MolecularFrequency added by the
    # physics review (2026-07-10, the deferred normal-mode hook now landed).
    assert [s.name for s in NODES] == [
        "HOMOLUMOGap", "ReactionBarrier[construction=neb_mep]",
        "BondDissociationEnergy", "MolecularFrequency"]
    assert [op.name for op in EDGES] == [
        "compute_homo_lumo_gap", "compute_reaction_barrier",
        "compute_bond_dissociation", "compute_molecular_frequencies"]


def test_molecular_edges_wiring_and_schemes():
    from omai.molecular.operator.edges import (
        compute_bond_dissociation,
        compute_homo_lumo_gap,
        compute_reaction_barrier,
    )

    wiring = {
        compute_homo_lumo_gap: (
            ["Structure", "Potential"], ["HOMOLUMOGap"],
            {"method": "scf_orbital_gap"}),
        compute_reaction_barrier: (
            ["TotalEnergy", "Structure"],
            ["ReactionBarrier[construction=neb_mep]"],
            {"method": "ci_neb"}),
        compute_bond_dissociation: (
            ["TotalEnergy", "Structure"], ["BondDissociationEnergy"],
            {"method": "homolytic_fragment_difference"}),
    }
    for op, (ins, outs, schemes) in wiring.items():
        assert [s.name for s in op.inputs] == ins, op.name
        assert [o.name for o in op.outputs] == outs, op.name
        assert op.schemes == schemes, op.name


def test_new_nodes_carry_the_molecular_tier_and_the_tier_is_registered():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    for n in ("HOMOLUMOGap", "ReactionBarrier[construction=neb_mep]",
              "BondDissociationEnergy"):
        assert tier_of[n] == "Molecular"
    assert "Molecular" in {t["name"] for t in g["tiers"]}


# --------------------------------------------------------------------------
# The three ENERGY nodes are distinct uids (name-based identity).
# --------------------------------------------------------------------------

def test_the_three_molecular_energy_nodes_are_distinct_uids():
    """HOMOLUMOGap, ReactionBarrier, and BondDissociationEnergy all REUSE the
    plain ENERGY exponent vector shared with TotalEnergy / FormationEnergy /
    ReactionEnergy: the dimension does NO separating work. They stay distinct
    nodes purely by their quantity tags (name-based identity)."""
    from omai.operator.dimensions import ENERGY
    from omai.molecular.operator.nodes import (
        BOND_DISSOCIATION_ENERGY,
        HOMO_LUMO_GAP,
        REACTION_BARRIER,
    )
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY

    nodes = [HOMO_LUMO_GAP, REACTION_BARRIER, BOND_DISSOCIATION_ENERGY,
             TOTAL_ENERGY]
    uids = [node_id(n) for n in nodes]
    assert len(set(uids)) == 4, dict(zip([n.name for n in nodes], uids))
    tags = [node_identity(n)["quantity"] for n in nodes]
    assert tags == [
        "homolumo_gap", "reaction_barrier", "bond_dissociation_energy",
        "total_energy"]
    # All three molecular nodes carry the plain ENERGY exponent vector.
    for node, fname in (
            (HOMO_LUMO_GAP, "E_gap_mol"),
            (REACTION_BARRIER, "E_barrier"),
            (BOND_DISSOCIATION_ENERGY, "BDE")):
        assert node.field(fname).dimension == ENERGY


# --------------------------------------------------------------------------
# ReactionBarrier vs Arrhenius ActivationEnergy: the name-collision trap.
# --------------------------------------------------------------------------

def test_reaction_barrier_is_distinct_from_arrhenius_activation_energy():
    """ReactionBarrier[construction=neb_mep] (a PES minimum-energy-path barrier)
    shares the plain ENERGY dimension with ActivationEnergy (the Arrhenius
    diffusivity-slope E_a) but is a DISTINCT node by its reaction_barrier tag:
    the shared word 'barrier / activation' is a trap, two different quantities."""
    from omai.molecular.operator.nodes import REACTION_BARRIER
    from omai.materials.operator.nodes import ACTIVATION_ENERGY

    assert node_identity(REACTION_BARRIER)["quantity"] == "reaction_barrier"
    assert node_identity(ACTIVATION_ENERGY)["quantity"] == "activation_energy"
    assert node_id(REACTION_BARRIER) != node_id(ACTIVATION_ENERGY)


# --------------------------------------------------------------------------
# HOMOLUMOGap vs BandGap: the band / discrete-orbital category error.
# --------------------------------------------------------------------------

def test_homo_lumo_gap_is_distinct_from_the_periodic_band_gap():
    """HOMOLUMOGap (two discrete frontier MOs of a molecule) shares the plain
    ENERGY dimension and the KS-eigenvalue-gap family with BandGap (VBM-to-CBM
    over the Brillouin zone) but is a DISTINCT node by its homolumo_gap tag: a
    molecule has no bands, so equating them is a category error. Cousins, not
    the same node."""
    from omai.molecular.operator.nodes import HOMO_LUMO_GAP
    from omai.dft_ground_state.operator.nodes import BAND_GAP

    assert node_identity(HOMO_LUMO_GAP)["quantity"] == "homolumo_gap"
    assert node_identity(BAND_GAP)["quantity"] == "band_gap"
    assert node_id(HOMO_LUMO_GAP) != node_id(BAND_GAP)


# --------------------------------------------------------------------------
# The construction LABEL_KEY round-trips through node identity.
# --------------------------------------------------------------------------

def test_construction_label_key_round_trips_and_is_registered():
    """The ReactionBarrier node carries labels={'construction': 'neb_mep'}; the
    label enters the identity hash (stringified), and neb_mep / static_ts_mlip /
    static_ts_dft are the registered construction values so the sella and ORCA
    routes can join the same reaction_barrier family later WITHOUT a re-mint."""
    from omai.operator.registry import LABEL_KEYS
    from omai.molecular.operator.nodes import REACTION_BARRIER

    # The label survives into the identity dict as a stringified pair.
    ident = node_identity(REACTION_BARRIER)
    assert ident["labels"] == {"construction": "neb_mep"}
    assert ident["quantity"] == "reaction_barrier"
    # The construction key is registered with all three family values.
    assert LABEL_KEYS["construction"] == frozenset(
        {"neb_mep", "static_ts_mlip", "static_ts_dft"})
    # The tag strips the label block: the neb_mep node and a hypothetical
    # static_ts_mlip node would share the reaction_barrier tag but differ only in
    # the construction label (distinct uids), the carrier-label pattern.
    from omai.operator.space import Field, ObservableSpace
    from omai.operator.dimensions import ENERGY
    sella_variant = ObservableSpace(
        name="ReactionBarrier[construction=static_ts_mlip]",
        fields=(Field("E_barrier", ENERGY, indices=()),),
        labels={"construction": "static_ts_mlip"},
    )
    assert node_identity(sella_variant)["quantity"] == "reaction_barrier"
    assert node_id(sella_variant) != node_id(REACTION_BARRIER)


def test_mode_index_kind_is_registered_for_the_deferred_molecular_frequency():
    """The molecular normal-mode axis (index name 'm' -> kind 'mode') is
    registered now, though the MolecularFrequency node that will use it is
    deferred (minting it means deciding the imaginary-mode convention). A
    distinct kind so a molecular mode index never aliases a phonon (q, nu)."""
    from omai.operator.registry import INDEX_KINDS, index_kind_signature

    assert INDEX_KINDS["m"] == "mode"
    assert index_kind_signature(("m",)) == ("mode",)
    # 'mode' is not the phonon 'qpoint' / 'branch' kinds.
    assert INDEX_KINDS["q"] == "qpoint"
    assert INDEX_KINDS["nu"] == "branch"


# --------------------------------------------------------------------------
# The gates: implicit / SKIPPED, DAG clean, one connected component.
# --------------------------------------------------------------------------

def test_new_edges_are_implicit_and_skipped():
    """All three new edges carry opaque solver functions, so the dimensional
    gate classifies them SKIPPED; the two pinned schematic violations stay the
    only ones."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    for name in ("compute_homo_lumo_gap", "compute_reaction_barrier",
                 "compute_bond_dissociation"):
        assert name in report["skipped"], (name, report)
    assert all(
        "compute_gruneisen" in v or "compute_phase_space_3phonon" in v
        for v in report["violation"]
    ), report["violation"]


def test_new_edges_are_not_sympy_executable():
    from omai.molecular.operator import EDGES

    for op in EDGES:
        assert op.is_executable_in_sympy_override is False
        assert not op.is_executable_in_sympy


def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_contribution_is_one_connected_component():
    """The three new nodes + three edges are ONE weakly connected component
    through the pre-existing Structure / TotalEnergy / Potential source nodes:
    compute_homo_lumo_gap consumes Structure + Potential; the barrier and BDE
    edges consume TotalEnergy + Structure. All inputs are pre-existing store
    nodes, so the additions touch the store and are weakly connected."""
    from omai.gates import validate_contribution
    from omai.operator.identity import (
        edge_id as _eid,
        edge_identity,
        node_id as _nid,
        node_identity as _nident,
    )
    from omai.molecular.operator.edges import (
        compute_bond_dissociation,
        compute_homo_lumo_gap,
        compute_reaction_barrier,
    )
    from omai.molecular.operator.nodes import (
        BOND_DISSOCIATION_ENERGY,
        HOMO_LUMO_GAP,
        REACTION_BARRIER,
    )
    from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY, STRUCTURE
    from omai.thermal_transport.operator.nodes import POTENTIAL

    records = []
    for s in (HOMO_LUMO_GAP, REACTION_BARRIER, BOND_DISSOCIATION_ENERGY):
        records.append({
            "op": "add_node",
            "payload": {"uid": _nid(s), "identity": _nident(s),
                        "meta": {"name": s.name}},
        })
    for op in (compute_homo_lumo_gap, compute_reaction_barrier,
               compute_bond_dissociation):
        records.append({
            "op": "add_edge",
            "payload": {"uid": _eid(op, _nid),
                        "identity": edge_identity(op, _nid),
                        "meta": {"name": op.name, "schemes": op.schemes}},
        })
    current = {"nodes": {}, "edges": {}}
    for s in (TOTAL_ENERGY, STRUCTURE, POTENTIAL):
        current["nodes"][_nid(s)] = {
            "uid": _nid(s), "identity": _nident(s), "meta": {}}
    assert validate_contribution(records, current) == []


# --------------------------------------------------------------------------
# The two rails (orca, openmm) auto-parametrize at the boundary.
# --------------------------------------------------------------------------

def test_orca_rail_covers_energy_forces_and_the_molecular_nodes():
    codes = build_codes(DOMAINS)
    orca = codes["orca"]
    assert orca["TotalEnergy"]["unit"] == "ev"
    assert orca["Forces"]["unit"] == "eV_per_A"
    assert orca["HOMOLUMOGap"]["unit"] == "ev"
    assert orca["ReactionBarrier[construction=neb_mep]"]["unit"] == "ev"


def test_openmm_rail_covers_the_md_nodes_and_the_mm_total_energy():
    codes = build_codes(DOMAINS)
    openmm = codes["openmm"]
    assert openmm["Temperature"]["unit"] == "kelvin"
    assert openmm["Pressure"]["unit"] == "atm"
    assert openmm["TotalEnergy"]["unit"] == "ev"
    # Trajectory is a HiddenSpace scaffolding node: covered, no comparison unit.
    assert "Trajectory" in openmm
    assert openmm["Trajectory"]["unit"] is None


def test_atm_unit_is_registered_and_canonicalizes_to_pressure():
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["atm"].to_operator == 101325.0 * 6.241509074460763e-12
    # 1 atm = 101325 Pa exactly.
    assert abs(conversion_factor("atm", "Pa") - 101325.0) < 1e-6


# --------------------------------------------------------------------------
# The committed store and the frozen log positions (records 175-180).
# --------------------------------------------------------------------------

def test_committed_store_contains_the_contribution():
    from omai.store import Store
    from omai.molecular.operator import EDGES, NODES

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in NODES:
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in EDGES:
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_molecular_is_records_175_to_180():
    """The frozen log positions: records 175-180 are the three nodes then the
    three edges (add_node * 3 + add_edge * 3), in the sync walk order (all nodes
    across domains first, then all edges). Positions are history and never move;
    records 164-174 (quasi-harmonic) stay untouched."""
    from omai.molecular.operator.edges import (
        compute_bond_dissociation,
        compute_homo_lumo_gap,
        compute_reaction_barrier,
    )
    from omai.molecular.operator.nodes import (
        BOND_DISSOCIATION_ENERGY,
        HOMO_LUMO_GAP,
        REACTION_BARRIER,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 180, "the molecular contribution has not landed"

    node_uids = [
        node_id(HOMO_LUMO_GAP),
        node_id(REACTION_BARRIER),
        node_id(BOND_DISSOCIATION_ENERGY),
    ]
    edge_uids = [
        edge_id(compute_homo_lumo_gap, node_id),
        edge_id(compute_reaction_barrier, node_id),
        edge_id(compute_bond_dissociation, node_id),
    ]
    recs = [json.loads(line) for line in lines[174:180]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 3 + ["add_edge"] * 3
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "molecular" in r["reason"]


# --------------------------------------------------------------------------
# Instances (2026-07-10 encode tail): the real committed molecular values the
# earlier molecular slice's false absent-repo skip missed. The AtomisticSkills
# repo IS present (vendored); these ride the ReactionBarrier / BDE nodes.
# --------------------------------------------------------------------------

def test_reaction_barrier_instance_pins_the_live_node_uid():
    """Evidence: the butane gauche->anti forward NEB barrier from the committed
    chem-neb-barrier example (MACE-OFF23-small, 7 images, converged)."""
    from omai.map_data import build_instances
    from omai.molecular.operator.nodes import REACTION_BARRIER

    insts = build_instances()
    by_key = {(it["variable"], it["material"]): it for it in insts}

    it = by_key[("ReactionBarrier[construction=neb_mep]", "C4H10 (butane)")]
    assert it["value"] == 0.12280791644116062
    assert it["units"] == "eV"
    assert it["source"]["kind"] == "simulation"
    assert it["conditions"]["reaction"] == "butane_gauche_to_anti"
    assert it["conditions"]["model"] == "MACE-OFF23-small"
    assert it["node_uid"] == node_id(REACTION_BARRIER)


def test_bond_dissociation_energy_instances_pin_the_live_node_uid():
    """Evidence: the eight committed per-bond BDEs of ethanol (CCO) from the
    chem-bond-dissociation example (MACE-OFF23-small); one instance per bond."""
    from omai.map_data import build_instances
    from omai.molecular.operator.nodes import BOND_DISSOCIATION_ENERGY

    insts = build_instances()
    bdes = [it for it in insts
            if it["variable"] == "BondDissociationEnergy"]
    # Eight bonds in the committed ethanol file.
    assert len(bdes) == 8, [it["material"] for it in bdes]
    for it in bdes:
        assert it["units"] == "eV"
        assert it["source"]["kind"] == "simulation"
        assert it["conditions"]["smiles"] == "CCO"
        assert it["conditions"]["model"] == "MACE-OFF23-small"
        assert it["node_uid"] == node_id(BOND_DISSOCIATION_ENERGY)
    # The weakest bond (C-O) is the committed 3.6396048158576377 eV value.
    by_bond = {it["conditions"]["bond"]: it["value"] for it in bdes}
    assert by_bond["C(1)-O(2)"] == 3.6396048158576377
    assert by_bond["C(0)-H(5)"] == 5.100016565212172
