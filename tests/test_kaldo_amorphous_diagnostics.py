"""Tests for the kaldo amorphous / localization diagnostics (records 208-211).

The kaldo delta scan (scans/kaldo-delta.json, 9/9 CONFIRMED), triggered by the
QHGK paper parse (Isaeva et al. 2019), surfaced two per-mode quantities that the
map could not yet carry and that kaldo computes directly. This contribution mints
them as TWO nodes in the thermal_transport domain (no new tier):

  * ParticipationRatio (tag participation_ratio, DIMENSIONLESS, indices (q, nu),
    tier Harmonic): the Bell/Dean 1/N inverse participation ratio, the
    harmonic-side localization diagnostic of the amorphous / QHGK branch;
  * ModalDiffusivity (tag modal_diffusivity, DIFFUSIVITY = L^2 T^-1, indices
    (q, nu), tier Transport): the QHGK / Allen-Feldman per-mode heat-mode
    diffusivity, served in mm^2/s.

Two edges: compute_participation_ratio (Eigenvectors -> ParticipationRatio,
PROVABLY dimensionless) and compute_modal_diffusivity (Frequency, Eigenvectors,
Linewidth[channel=total] -> ModalDiffusivity, the implicit QHGK kernel).

Load-bearing proofs here:

  * the participation-ratio edge is PROVEN dimensionless by the dimensional gate
    (in report['ok'], not skipped, not a violation);
  * the FALSE-MERGE guardrail: ModalDiffusivity and the mass-transport
    Diffusivity SHARE the DIFFUSIVITY (L^2 T^-1) dimension but are DISTINCT uids
    with DISTINCT tags (all three facts asserted);
  * the kaldo rail grows 32 -> 34 and serves ModalDiffusivity in mm^2/s;
  * the frozen log positions: records 208-211.
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
# The two nodes: dimensions, indices, tiers, tags.
# --------------------------------------------------------------------------

def test_participation_ratio_is_dimensionless_per_mode_harmonic():
    from omai.operator.dimensions import DIMENSIONLESS
    from omai.thermal_transport.operator.nodes import PARTICIPATION_RATIO

    pr = PARTICIPATION_RATIO
    assert pr.field("p").dimension == DIMENSIONLESS
    assert pr.field("p").indices == ("q", "nu")
    assert pr.tier == "Harmonic"
    assert node_identity(pr)["quantity"] == "participation_ratio"


def test_modal_diffusivity_is_l2_t_per_mode_transport():
    from omai.operator.dimensions import DIFFUSIVITY
    from omai.thermal_transport.operator.nodes import MODAL_DIFFUSIVITY

    md = MODAL_DIFFUSIVITY
    assert md.field("D_mode").dimension == DIFFUSIVITY
    assert md.field("D_mode").dimension.exponents == (0, 2, -1, 0, 0, 0, 0)
    assert md.field("D_mode").indices == ("q", "nu")
    assert md.tier == "Transport"
    assert node_identity(md)["quantity"] == "modal_diffusivity"


# --------------------------------------------------------------------------
# The FALSE-MERGE guardrail (headline): same dimension, distinct nodes/tags.
# --------------------------------------------------------------------------

def test_modal_diffusivity_does_not_false_merge_with_mass_diffusivity():
    """ModalDiffusivity (per-mode QHGK heat diffusivity) SHARES the DIFFUSIVITY
    (L^2 T^-1) exponent vector with the existing mass-transport Diffusivity node
    (D = slope_MSD/(2d), the scalar Einstein self-diffusion coefficient), but
    they are DIFFERENT quantities kept apart by NAME and TAG, never merged on the
    shared dimension. Three facts asserted: same dimension, distinct uids,
    distinct tags."""
    from omai.materials.operator.nodes import DIFFUSIVITY_STATE
    from omai.thermal_transport.operator.nodes import MODAL_DIFFUSIVITY

    md = MODAL_DIFFUSIVITY
    mass = DIFFUSIVITY_STATE

    # (1) Same dimension: the shared L^2 T^-1 exponent vector.
    assert md.field("D_mode").dimension == mass.field("D").dimension

    # (2) Distinct uids: name-based identity keeps them apart.
    assert node_id(md) != node_id(mass)

    # (3) Distinct tags.
    assert node_identity(md)["quantity"] == "modal_diffusivity"
    assert node_identity(mass)["quantity"] == "diffusivity"

    # The mass diffusivity is a scalar; the modal one is (q, nu)-indexed.
    assert mass.field("D").indices == ()
    assert md.field("D_mode").indices == ("q", "nu")


# --------------------------------------------------------------------------
# The edges: PR proven dimensionless, MD implicit / skipped.
# --------------------------------------------------------------------------

def test_participation_ratio_edge_is_proven_dimensionless():
    """The Bell/Dean form PR = 1/(N sum_i a_i^2), written over the per-atom
    (cartesian-summed squared eigenvector) amplitude a_i registered DIMENSIONLESS,
    makes the dimensional gate PROVE the ratio dimensionless: the edge is in
    report['ok'], NOT skipped and NOT a violation."""
    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    assert "compute_participation_ratio" in report["ok"]
    assert "compute_participation_ratio" not in report["skipped"]
    assert all("participation_ratio" not in v for v in report["violation"])


def test_modal_diffusivity_edge_is_implicit_and_skipped():
    """The QHGK kernel is an opaque applied function D^{QHGK}[omega, e, Gamma],
    so compute_modal_diffusivity is not sympy-executable and the dimensional gate
    SKIPS it (no false proof, no false violation)."""
    from omai.thermal_transport.operator.edges import compute_modal_diffusivity

    assert compute_modal_diffusivity.is_executable_in_sympy_override is False
    assert not compute_modal_diffusivity.is_executable_in_sympy

    nodes, edges = _all_nodes_edges()
    report = dimensional_report(nodes, edges)
    assert "compute_modal_diffusivity" in report["skipped"]
    assert all("modal_diffusivity" not in v for v in report["violation"])


def test_new_edges_wiring_and_schemes():
    from omai.thermal_transport.operator.edges import (
        compute_modal_diffusivity,
        compute_participation_ratio,
    )

    assert [s.name for s in compute_participation_ratio.inputs] == ["Eigenvectors"]
    assert [o.name for o in compute_participation_ratio.outputs] == [
        "ParticipationRatio"]
    assert compute_participation_ratio.schemes == {
        "normalization": "bell_dean_1_over_N"}

    assert [s.name for s in compute_modal_diffusivity.inputs] == [
        "Frequency", "Eigenvectors", "Linewidth[channel=total]"]
    assert [o.name for o in compute_modal_diffusivity.outputs] == [
        "ModalDiffusivity"]
    assert compute_modal_diffusivity.schemes == {
        "method": "qhgk", "scope": "qhgk_only"}


# --------------------------------------------------------------------------
# The units: mm2_per_s canonicalizes to m2_per_s (1e-6).
# --------------------------------------------------------------------------

def test_modal_diffusivity_units_canonicalize():
    """The QHGK modal diffusivity's serving unit mm2_per_s carries to_operator
    1e-6 to the canonical m2_per_s (1 mm^2/s = 1e-6 m^2/s); both are DIFFUSIVITY
    (L^2 T^-1)."""
    from omai.operator.dimensions import DIFFUSIVITY
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["m2_per_s"].to_operator == 1.0
    assert UNITS["m2_per_s"].dimension == DIFFUSIVITY
    assert UNITS["mm2_per_s"].to_operator == 1e-6
    assert UNITS["mm2_per_s"].dimension == DIFFUSIVITY
    # 1 mm^2/s = 1e-6 m^2/s.
    assert abs(conversion_factor("mm2_per_s", "m2_per_s") - 1e-6) < 1e-24


# --------------------------------------------------------------------------
# The DAG gate, graph placement, and the kaldo rail.
# --------------------------------------------------------------------------

def test_unified_validate_dag_is_clean():
    nodes, edges = _all_nodes_edges()
    assert validate_dag(nodes, edges) == []


def test_new_nodes_carry_their_tiers_in_the_graph():
    g = build_graph_dict(DOMAINS)
    tier_of = {n["id"]: n["tier"] for n in g["nodes"]}
    assert tier_of["ParticipationRatio"] == "Harmonic"
    assert tier_of["ModalDiffusivity"] == "Transport"


def test_kaldo_rail_covers_both_new_nodes():
    codes = build_codes(DOMAINS)
    kaldo = codes["kaldo"]
    assert kaldo["ParticipationRatio"]["unit"] == "dimensionless"
    assert kaldo["ParticipationRatio"]["api"] == "Phonons.participation_ratio"
    assert kaldo["ModalDiffusivity"]["unit"] == "mm2_per_s"
    assert kaldo["ModalDiffusivity"]["api"] == (
        "Conductivity(method='qhgk').diffusivity")


# --------------------------------------------------------------------------
# The committed store and the frozen log positions (records 208-211).
# --------------------------------------------------------------------------

def test_committed_store_contains_the_contribution():
    from omai.store import Store
    from omai.thermal_transport.operator.edges import (
        compute_modal_diffusivity,
        compute_participation_ratio,
    )
    from omai.thermal_transport.operator.nodes import (
        MODAL_DIFFUSIVITY,
        PARTICIPATION_RATIO,
    )

    m = Store(Path(__file__).resolve().parents[1] / "map").read()
    for s in (PARTICIPATION_RATIO, MODAL_DIFFUSIVITY):
        assert node_id(s) in m["nodes"], f"store missing node {s.name}"
    for op in (compute_participation_ratio, compute_modal_diffusivity):
        assert edge_id(op, node_id) in m["edges"], f"store missing edge {op.name}"


def test_amorphous_diagnostics_are_records_208_to_211():
    """The frozen log positions: records 208-211 are the two nodes then the two
    edges (add_node * 2 + add_edge * 2), in the sync walk order (NODES order then
    EDGES order within the thermal_transport domain: ParticipationRatio,
    ModalDiffusivity; then compute_participation_ratio, compute_modal_diffusivity).
    Positions are history and never move; records 1-207 stay untouched."""
    from omai.thermal_transport.operator.edges import (
        compute_modal_diffusivity,
        compute_participation_ratio,
    )
    from omai.thermal_transport.operator.nodes import (
        MODAL_DIFFUSIVITY,
        PARTICIPATION_RATIO,
    )

    lines = (Path(__file__).resolve().parents[1] / "map" / "log.jsonl") \
        .read_text().splitlines()
    assert len(lines) >= 211, "the amorphous-diagnostics contribution has not landed"

    node_uids = [node_id(PARTICIPATION_RATIO), node_id(MODAL_DIFFUSIVITY)]
    edge_uids = [
        edge_id(compute_participation_ratio, node_id),
        edge_id(compute_modal_diffusivity, node_id),
    ]
    recs = [json.loads(line) for line in lines[207:211]]
    assert [r["payload"]["uid"] for r in recs] == node_uids + edge_uids
    assert [r["op"] for r in recs] == ["add_node"] * 2 + ["add_edge"] * 2
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-11"
        assert "modal diffusivity" in r["reason"]
