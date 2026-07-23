"""Tests for the composites (effective-medium) contribution, domain eleven.

Composite effective thermal conductivity of a filled matrix with interfacial
(Kapitza) resistance, via Nan-type effective-medium theory (Nan et al., J. Appl.
Phys. 81, 6692 (1997)), cross-checked in the spherical limit against
Hasselman-Johnson (J. Compos. Mater. 21, 508 (1987)).

Load-bearing proofs here:

  * the new dimension INTERFACE_CONDUCTANCE (W/(m^2 K)), distinct from
    THERMAL_CONDUCTANCE (W/K) and THERMAL_CONDUCTIVITY (W/(m K));
  * the reference DGEBA epoxy + 5 vol% GNP draft reproduces kappa_random =
    1.2452 W/(m K) and the Kapitza radius a_K = km/G = 8.0 nm, from BOTH a
    self-contained Python port and the domain's sympy formula (they agree);
  * the depolarization analytic limits: sphere (1/3, 1/3), long fiber (1/2, ~0),
    thin disk (~0, 1), and the sum rule 2 L11 + L33 = 1;
  * the Hasselman-Johnson second producer agrees with Nan-random at aspect ratio
    1 (a sphere) to machine precision (the redundant-route pattern);
  * zero loading returns the matrix conductivity exactly;
  * the three closed-form edges (Nan random, Nan aligned, Hasselman-Johnson) are
    classified OK (PROVEN) by the dimensional gate; the depolarization Piecewise
    and the resolve identity are SKIPPED (both acceptable);
  * the effective-kappa random node resolves onto the neutral ThermalConductivity
    observable (the connectivity bridge), and the reference instance pins 1.2452.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import sympy as sp

from omai.map_data import DOMAINS, build_graph_dict, build_instances
from omai.operator.dimcheck import dimensional_report
from omai.operator.identity import node_id
from omai.operator.validate import validate_dag


# --------------------------------------------------------------------------
# A self-contained Python port of the materialscodegraph emt tool (a verbatim
# port of mcg/tools/composite/emt.py). The domain test reproduces the pinned
# value from THIS port and cross-checks the sympy formula against it.
# --------------------------------------------------------------------------

def _depolarization(aspect):
    """(L11, L33) for a spheroid, polar axis 3; 2 L11 + L33 = 1."""
    p = aspect
    if p <= 0 or abs(p - 1.0) < 1e-9:
        return (1.0 / 3.0, 1.0 / 3.0)
    if p > 1.0:  # prolate (fiber)
        e = math.sqrt(1.0 - 1.0 / (p * p))
        l33 = ((1.0 - e * e) / e**3) * (math.atanh(e) - e)
    else:        # oblate (platelet)
        e = math.sqrt(1.0 / (p * p) - 1.0)
        l33 = ((1.0 + e * e) / e**3) * (e - math.atan(e))
    return ((1.0 - l33) / 2.0, l33)


def _effective_kappa(km, k11, k33, d1um, d3um, g_MW, f):
    """Nan-type EMT with a per-direction interfacial series film. Returns
    (kappa_random, kappa_aligned_11, kappa_aligned_33, kapitza_radius_nm)."""
    g = g_MW * 1e6
    r = 1.0 / g
    d1 = d1um * 1e-6
    d3 = d3um * 1e-6
    l11, l33 = _depolarization(d3um / d1um)
    kc11 = k11 / (1.0 + 2.0 * r * k11 / d1)
    kc33 = k33 / (1.0 + 2.0 * r * k33 / d3)
    b11 = (kc11 - km) / (km + l11 * (kc11 - km))
    b33 = (kc33 - km) / (km + l33 * (kc33 - km))
    rand = km * (3.0 + f * (2.0 * b11 * (1.0 - l11) + b33 * (1.0 - l33))) \
              / (3.0 - f * (2.0 * b11 * l11 + b33 * l33))
    al11 = km * (1.0 + f * b11 * (1.0 - l11)) / (1.0 - f * b11 * l11)
    al33 = km * (1.0 + f * b33 * (1.0 - l33)) / (1.0 - f * b33 * l33)
    return (rand, al11, al33, (km / g) * 1e9)


def _hasselman_johnson(km, kp, a_um, g_MW, f):
    """Independent reference: HJ spheres with interfacial resistance. alpha =
    Kapitza radius / particle radius (a_um is the sphere RADIUS = d/2)."""
    alpha = (km / (g_MW * 1e6)) / (a_um * 1e-6)
    num = kp * (1 + 2 * alpha) + 2 * km + 2 * f * (kp * (1 - alpha) - km)
    den = kp * (1 + 2 * alpha) + 2 * km - f * (kp * (1 - alpha) - km)
    return km * num / den


# The reference DGEBA epoxy + 5 vol% GNP formulation (the mcg eval target).
_REF = dict(km=0.2, k11=1200.0, k33=6.0, d1um=5.0, d3um=0.02, g_MW=25.0, f=0.05)


def _domain_edges():
    for d in DOMAINS:
        if d.name == "composites":
            return {op.name: op for op in d.edges}
    raise AssertionError("composites domain not registered")


def _domain_nodes():
    for d in DOMAINS:
        if d.name == "composites":
            return {s.name: s for s in d.nodes}
    raise AssertionError("composites domain not registered")


# --------------------------------------------------------------------------
# The new dimension: INTERFACE_CONDUCTANCE (W/(m^2 K)).
# --------------------------------------------------------------------------

def test_interface_conductance_exponents_are_w_per_m2_k():
    """G = W/(m^2 K) = M T^-3 Th^-1. A conductance per area, distinct from both
    the Landauer conductance (W/K) and the per-length conductivity (W/(m K))."""
    from omai.operator.dimensions import (
        INTERFACE_CONDUCTANCE,
        THERMAL_CONDUCTANCE,
        THERMAL_CONDUCTIVITY,
    )

    assert INTERFACE_CONDUCTANCE.exponents == (1, 0, -3, -1, 0, 0, 0)
    assert INTERFACE_CONDUCTANCE.canonical() == "M^1 T^-3 Th^-1"
    # THERMAL_CONDUCTANCE (W/K) divided by an area (L^2) reproduces it.
    area = (0, 2, 0, 0, 0, 0, 0)
    assert INTERFACE_CONDUCTANCE.exponents == tuple(
        c - a for c, a in zip(THERMAL_CONDUCTANCE.exponents, area))
    # NOT the per-length thermal conductivity (differs by an L axis).
    assert INTERFACE_CONDUCTANCE != THERMAL_CONDUCTIVITY
    assert INTERFACE_CONDUCTANCE != THERMAL_CONDUCTANCE


def test_interface_conductance_registered_and_the_kapitza_radius_is_a_length():
    from omai.operator.dimensions import (
        DIMENSIONS,
        INTERFACE_CONDUCTANCE,
        LENGTH,
        THERMAL_CONDUCTIVITY,
    )

    assert "interface_conductance" in DIMENSIONS
    # a_K = km / G is a length: W/(m K) over W/(m^2 K) = m.
    assert (THERMAL_CONDUCTIVITY / INTERFACE_CONDUCTANCE).exponents == LENGTH.exponents


def test_interface_conductance_units_registered():
    from omai.representation.units import UNITS, conversion_factor

    assert "W_per_m2_k" in UNITS and "MW_per_m2_k" in UNITS
    from omai.operator.dimensions import INTERFACE_CONDUCTANCE
    assert UNITS["W_per_m2_k"].dimension == INTERFACE_CONDUCTANCE
    assert UNITS["W_per_m2_k"].si_scale == 1.0
    # 1 MW/(m^2 K) = 1e6 W/(m^2 K).
    assert conversion_factor("MW_per_m2_k", "W_per_m2_k") == 1e6


# --------------------------------------------------------------------------
# The reference value: 1.2452 W/(m K) and the 8.0 nm Kapitza radius.
# --------------------------------------------------------------------------

def test_reference_epoxy_reproduces_1p2452_from_the_python_port():
    rand, _al11, _al33, a_k_nm = _effective_kappa(**_REF)
    assert round(rand, 4) == 1.2452
    assert round(a_k_nm, 1) == 8.0  # a_K = km/G = 0.2 / 2.5e7 = 8 nm


def test_reference_epoxy_reproduces_1p2452_from_the_sympy_formula():
    """The domain's nan_effective_kappa sympy Eq, evaluated at the reference
    inputs (with the depolarization factors from the closed form), reproduces
    the same 1.2452 the Python port gives."""
    op = _domain_edges()["nan_effective_kappa"]
    rhs = op.formula.rhs

    l11, l33 = _depolarization(_REF["d3um"] / _REF["d1um"])
    subs = {
        sp.Symbol("k_m", positive=True): _REF["km"],
        sp.IndexedBase("k_f")[1, 1]: _REF["k11"],
        sp.IndexedBase("k_f")[3, 3]: _REF["k33"],
        sp.Symbol("G_{int}", positive=True): _REF["g_MW"] * 1e6,
        sp.Symbol("d_1", positive=True): _REF["d1um"] * 1e-6,
        sp.Symbol("d_3", positive=True): _REF["d3um"] * 1e-6,
        sp.Symbol("f_{vol}", nonnegative=True): _REF["f"],
        sp.Symbol("L_{11}"): l11,
        sp.Symbol("L_{33}"): l33,
    }
    value = float(rhs.subs(subs))
    port, *_ = _effective_kappa(**_REF)
    assert abs(value - port) < 1e-12
    assert round(value, 4) == 1.2452


def test_zero_loading_returns_the_matrix_conductivity():
    ref0 = dict(_REF, f=0.0)
    rand, al11, al33, _ = _effective_kappa(**ref0)
    assert math.isclose(rand, _REF["km"], rel_tol=1e-12)
    assert math.isclose(al11, _REF["km"], rel_tol=1e-12)
    assert math.isclose(al33, _REF["km"], rel_tol=1e-12)


def test_small_filler_weak_interface_degrades_below_the_matrix():
    """Below the Kapitza radius a conductive filler LOWERS kappa (the interface
    resistance dominates): a nanoscale platelet with a weak interface."""
    rand, *_ = _effective_kappa(km=0.2, k11=1200, k33=6, d1um=0.05, d3um=0.005,
                                g_MW=1.0, f=0.05)
    assert rand < 0.2


# --------------------------------------------------------------------------
# Depolarization factors: analytic limits and the sum rule.
# --------------------------------------------------------------------------

def test_depolarization_sphere_is_one_third():
    l11, l33 = _depolarization(1.0)
    assert math.isclose(l11, 1 / 3) and math.isclose(l33, 1 / 3)


def test_depolarization_long_fiber_limit():
    l11, l33 = _depolarization(1e6)
    assert math.isclose(l11, 0.5, rel_tol=1e-4)
    assert l33 < 1e-6


def test_depolarization_thin_disk_limit():
    l11, l33 = _depolarization(1e-6)
    assert l11 < 1e-4
    assert math.isclose(l33, 1.0, rel_tol=1e-4)


def test_depolarization_sum_rule_holds():
    for p in (0.004, 0.01, 0.3, 2.0, 7.0, 400.0):
        l11, l33 = _depolarization(p)
        assert math.isclose(2 * l11 + l33, 1.0, rel_tol=1e-12)


# --------------------------------------------------------------------------
# Hasselman-Johnson spherical-limit agreement (the second producer).
# --------------------------------------------------------------------------

def test_hasselman_johnson_agrees_with_nan_at_aspect_one():
    """At aspect ratio 1 (a sphere: k11=k33=kp, d1=d3=2a), the Nan random result
    reduces to the Hasselman-Johnson sphere formula EXACTLY. HJ takes the sphere
    RADIUS a = d/2, so a d=10um sphere is a_um=5.0."""
    for g_MW, f in ((10.0, 0.1), (50.0, 0.2), (200.0, 0.05)):
        nan_rand, *_ = _effective_kappa(km=0.2, k11=30.0, k33=30.0,
                                        d1um=10.0, d3um=10.0, g_MW=g_MW, f=f)
        hj = _hasselman_johnson(km=0.2, kp=30.0, a_um=5.0, g_MW=g_MW, f=f)
        assert math.isclose(nan_rand, hj, rel_tol=1e-9)


def test_hasselman_johnson_sympy_edge_matches_nan_sympy_edge_at_sphere():
    """The domain's hasselman_johnson sympy Eq and nan_effective_kappa sympy Eq,
    evaluated at a sphere, agree to machine precision (the gate-level second
    producer of the same node)."""
    edges = _domain_edges()
    km, kp, a_um, g_MW, f = 0.2, 30.0, 5.0, 50.0, 0.2
    # Nan at the sphere (aspect 1 -> L11=L33=1/3, d1=d3=2a=10um).
    l = 1.0 / 3.0
    nan_subs = {
        sp.Symbol("k_m", positive=True): km,
        sp.IndexedBase("k_f")[1, 1]: kp,
        sp.IndexedBase("k_f")[3, 3]: kp,
        sp.Symbol("G_{int}", positive=True): g_MW * 1e6,
        sp.Symbol("d_1", positive=True): 2 * a_um * 1e-6,
        sp.Symbol("d_3", positive=True): 2 * a_um * 1e-6,
        sp.Symbol("f_{vol}", nonnegative=True): f,
        sp.Symbol("L_{11}"): l,
        sp.Symbol("L_{33}"): l,
    }
    nan_val = float(edges["nan_effective_kappa"].formula.rhs.subs(nan_subs))
    hj_subs = {
        sp.Symbol("k_m", positive=True): km,
        sp.IndexedBase("k_f")[3, 3]: kp,
        sp.Symbol("G_{int}", positive=True): g_MW * 1e6,
        sp.Symbol("a_{rad}", positive=True): a_um * 1e-6,
        sp.Symbol("f_{vol}", nonnegative=True): f,
    }
    hj_val = float(edges["hasselman_johnson"].formula.rhs.subs(hj_subs))
    assert abs(nan_val - hj_val) < 1e-9
    assert abs(nan_val - _hasselman_johnson(km, kp, a_um, g_MW, f)) < 1e-9


# --------------------------------------------------------------------------
# The dimensional gate: the closed-form edges are PROVEN.
# --------------------------------------------------------------------------

def test_nan_and_hj_edges_are_dimensionally_proven():
    """nan_effective_kappa, nan_effective_kappa_aligned, and hasselman_johnson
    are executable closed forms the dimensional gate PROVES (both sides land on
    THERMAL_CONDUCTIVITY). The depolarization Piecewise and the resolve identity
    are SKIPPED (acceptable: the gate only needs the dimensionless shape / the
    identity)."""
    edges = list(_domain_edges().values())
    rep = dimensional_report([], edges)
    assert set(rep["ok"]) == {
        "nan_effective_kappa",
        "nan_effective_kappa_aligned",
        "hasselman_johnson",
    }
    assert set(rep["skipped"]) == {
        "depolarization_factors",
        "resolve_effective_conductivity",
    }
    assert rep["violation"] == []


def test_effective_kappa_edges_output_thermal_conductivity():
    from omai.operator.dimcheck import dimension_of
    from omai.operator.dimensions import THERMAL_CONDUCTIVITY

    for name in ("nan_effective_kappa", "nan_effective_kappa_aligned",
                 "hasselman_johnson"):
        op = _domain_edges()[name]
        assert dimension_of(op.formula.lhs) == THERMAL_CONDUCTIVITY
        assert dimension_of(op.formula.rhs) == THERMAL_CONDUCTIVITY


# --------------------------------------------------------------------------
# Nodes, labels, and the family membership.
# --------------------------------------------------------------------------

def test_composite_kappa_nodes_join_the_thermal_conductivity_family():
    """All four ThermalConductivity[...] composite nodes carry the
    thermal_conductivity tag (the family), kept distinct only by their labels."""
    from omai.operator.registry import quantity_tag_for

    nodes = _domain_nodes()
    for name in ("ThermalConductivity[role=matrix]",
                 "ThermalConductivity[role=filler]",
                 "ThermalConductivity[effective_medium=nan,orientation=random]",
                 "ThermalConductivity[effective_medium=nan,orientation=aligned]"):
        assert name in nodes
        assert quantity_tag_for(name) == "thermal_conductivity"
    # Distinct uids despite the shared tag (labels enter identity).
    ids = {node_id(nodes[n]) for n in (
        "ThermalConductivity[role=matrix]",
        "ThermalConductivity[role=filler]",
        "ThermalConductivity[effective_medium=nan,orientation=random]",
        "ThermalConductivity[effective_medium=nan,orientation=aligned]")}
    assert len(ids) == 4


def test_new_label_keys_registered():
    from omai.operator.registry import LABEL_KEYS

    assert LABEL_KEYS["role"] == frozenset({"matrix", "filler"})
    assert LABEL_KEYS["effective_medium"] == frozenset({"nan"})
    assert LABEL_KEYS["orientation"] == frozenset({"random", "aligned"})


def test_new_quantity_tags_registered():
    from omai.operator.registry import QUANTITY_TAGS

    for tag in ("interface_conductance", "filler_volume_fraction",
                "depolarization_factor"):
        assert tag in QUANTITY_TAGS and QUANTITY_TAGS[tag]


# --------------------------------------------------------------------------
# Connectivity: the resolve edge bridges to the neutral observable.
# --------------------------------------------------------------------------

def test_resolve_edge_targets_the_neutral_thermal_conductivity():
    op = _domain_edges()["resolve_effective_conductivity"]
    assert [i.name for i in op.inputs] == [
        "ThermalConductivity[effective_medium=nan,orientation=random]"]
    assert [o.name for o in op.outputs] == ["ThermalConductivity"]


def test_dag_validates_with_the_composites_domain():
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
    # validate_dag raises on a malformed DAG; a clean return is the assertion.
    validate_dag(tuple(nodes), tuple(edges))


# --------------------------------------------------------------------------
# The reference instance and the graph totals.
# --------------------------------------------------------------------------

def test_reference_instance_pins_the_nan_random_node():
    insts = build_instances()
    mine = [i for i in insts if i["source"]["ref"] == "materialscodegraph"]
    assert len(mine) == 1
    rec = mine[0]
    assert rec["variable"] == \
        "ThermalConductivity[effective_medium=nan,orientation=random]"
    assert rec["value"] == 1.2452
    assert rec["units"] == "W/(m K)"
    assert rec["source"]["kind"] == "simulation"
    assert rec["conditions"]["f"] == 0.05
    assert rec["conditions"]["kapitza_radius_nm"] == 8.0
    # pinned to the live node uid.
    g = build_graph_dict(DOMAINS)
    uid = {n["id"]: n["uid"] for n in g["nodes"]}[rec["variable"]]
    assert rec["node_uid"] == uid


def test_no_platform_rail_on_the_map():
    """The composite formulas are the map's own closed-form edges; the
    partner platform is provenance on the evidence, never a code rail
    (removed 2026-07-22). The instances keep their source refs."""
    from omai.map_data import build_codes
    from omai.representation.credits import CODE_CREDITS

    codes = build_codes(DOMAINS)
    assert "materialscodegraph" not in codes
    assert "materialscodegraph" not in CODE_CREDITS


def test_graph_totals_after_the_composites_domain():
    g = build_graph_dict(DOMAINS)
    assert len(g["nodes"]) == 114  # 107 + 7 composite nodes
    ops = set()
    for d in DOMAINS:
        for op in d.edges:
            ops.add(op.name)
    assert len(ops) == 114  # 109 + 5 composite edges
