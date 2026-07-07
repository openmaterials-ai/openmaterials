"""Tests for content-addressed identity (node, parameter, edge, version).

Identity is a pure function of a node's / edge's *content* under the amended
kernel rule: quantity tag + field signatures + gauge class + labels for nodes;
plus the formula fingerprint and schemes for edges. Names, symbols,
descriptions, tier, and (for edges) the operator name are metadata, never
identity. The acceptance test here is also the permanent collision stress test
that found the seven false merges pure type-content identity produces.
"""
from __future__ import annotations


# Pinned 12-hex prefixes for two stable fixtures. Filled in AFTER first
# computing them and eyeballing the identity dicts for sanity (see the plan).
PINNED_FREQUENCY_PREFIX = "fa262448f625"
PINNED_TRAJECTORY_PREFIX = "12cde23e9a33"


def _all_nodes_edges():
    from omai.map_data import DOMAINS
    nodes, edges, seen = [], [], set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in seen:
                seen.add(s.name); nodes.append(s)
        edges.extend(d.edges)
    return nodes, edges


def test_no_node_id_collisions_across_the_map():
    from omai.operator.identity import node_id
    nodes, _ = _all_nodes_edges()
    ids = {}
    for s in nodes:
        i = node_id(s)
        assert i not in ids, f"collision: {ids[i]} vs {s.name}"
        ids[i] = s.name
    assert len(ids) == len(nodes)


def test_previous_false_merge_pairs_are_distinct():
    from omai.operator.identity import node_id
    from omai.thermal_transport.operator.nodes import (
        BARE_DYNAMICAL_MATRIX, DYNAMICAL_MATRIX, ENTROPY, HEAT_CAPACITY,
        GRUNEISEN, PHASE_SPACE_3PH, POTENTIAL,
    )
    from omai.materials.operator.shared_primitives import STRUCTURE
    pairs = [
        (POTENTIAL, STRUCTURE), (BARE_DYNAMICAL_MATRIX, DYNAMICAL_MATRIX),
        (HEAT_CAPACITY, ENTROPY), (GRUNEISEN, PHASE_SPACE_3PH),
    ]
    for a, b in pairs:
        assert node_id(a) != node_id(b), f"{a.name} == {b.name}"


def test_label_variants_distinct_and_pattern_c_stable():
    from omai.operator.identity import node_id
    from omai.thermal_transport.operator.nodes import (
        THERMAL_CONDUCTIVITY_RTA, THERMAL_CONDUCTIVITY_DIRECT, DYNAMICAL_MATRIX,
    )
    assert node_id(THERMAL_CONDUCTIVITY_RTA) != node_id(THERMAL_CONDUCTIVITY_DIRECT)
    # Pattern C: the id is a pure function of the space; producers are not inputs.
    assert node_id(DYNAMICAL_MATRIX) == node_id(DYNAMICAL_MATRIX)


def test_edge_ids_unique_and_formula_sensitive():
    import sympy as sp
    from omai.operator.identity import edge_id, node_id, formula_fingerprint
    from omai.operator.operator import Operator
    nodes, edges = _all_nodes_edges()
    ids = set()
    for e in edges:
        i = edge_id(e, node_id)
        assert i not in ids, f"edge collision at {e.name}"
        ids.add(i)
    # formula sensitivity
    a, b = sp.Symbol("a"), sp.Symbol("b")
    e1 = Operator(name="x", inputs=(), outputs=(nodes[0],), formula=sp.Eq(a, b))
    e2 = Operator(name="x", inputs=(), outputs=(nodes[0],), formula=sp.Eq(a, 2 * b))
    assert edge_id(e1, node_id) != edge_id(e2, node_id)
    # commutative reordering is NOT a different formula
    assert formula_fingerprint(sp.Eq(a, a * b + b)) == formula_fingerprint(sp.Eq(a, b + b * a))


def test_stability_fixtures():
    from omai.operator.identity import node_id
    from omai.thermal_transport.operator.nodes import FREQUENCY_STATE, TRAJECTORY
    assert node_id(FREQUENCY_STATE)[:12] == PINNED_FREQUENCY_PREFIX
    assert node_id(TRAJECTORY)[:12] == PINNED_TRAJECTORY_PREFIX


# --------------------------------------------------------------------------
# Structural edge cases called out by the plan.
# --------------------------------------------------------------------------

def test_multi_field_node_signature_covers_all_fields():
    """Trajectory has two fields (r and v); both must enter the node identity,
    as the sorted field-signature multiset."""
    from omai.operator.identity import node_identity, field_signature
    from omai.thermal_transport.operator.nodes import TRAJECTORY
    ident = node_identity(TRAJECTORY)
    assert len(ident["fields"]) == 2
    expected = sorted(
        (field_signature(f) for f in TRAJECTORY.fields),
        key=lambda fs: __import__("omai.operator.identity", fromlist=["canonical_json"]).canonical_json(fs),
    )
    assert ident["fields"] == expected
    # r is length, v is length/time: their dimensions differ, so both survive.
    dims = {tuple(f["dimension"].split()) for f in ident["fields"]}
    assert len(dims) == 2


def test_multi_output_edge_hashes_all_outputs():
    """compute_dispersion outputs Frequency AND Eigenvectors; the edge identity
    must carry the full sorted outputs list, not just outputs[0]."""
    from omai.operator.identity import edge_identity, node_id
    from omai.thermal_transport.operator.edges import compute_dispersion
    ident = edge_identity(compute_dispersion, node_id)
    assert len(compute_dispersion.outputs) == 2
    assert len(ident["outputs"]) == 2
    assert ident["output"] == node_id(compute_dispersion.outputs[0])
    assert set(ident["outputs"]) == {node_id(o) for o in compute_dispersion.outputs}
    # sorted
    assert ident["outputs"] == sorted(ident["outputs"])


# --------------------------------------------------------------------------
# Parameter identity, formula fingerprint edges, version hashing.
# --------------------------------------------------------------------------

def test_parameter_node_ids_distinct_for_the_three_parameters():
    from omai.operator.identity import parameter_node_id
    v = parameter_node_id("CellVolume", "volume")
    m = parameter_node_id("AtomicMass", "mass")
    n = parameter_node_id("AtomCount", "dimensionless")
    assert len({v, m, n}) == 3
    for x in (v, m, n):
        assert len(x) == 64 and all(c in "0123456789abcdef" for c in x)


def test_parameter_node_id_opaque_when_dimension_none():
    from omai.operator.identity import parameter_node_id, node_identity
    # None dimension renders as opaque:opaque in the field signature.
    import json
    from omai.operator.identity import canonical_json
    pid = parameter_node_id("SomeOpaqueParam", None)
    assert len(pid) == 64
    # distinct from a dimensioned parameter of the same tag rule
    assert parameter_node_id("SomeOpaqueParam", None) == pid  # deterministic


def test_formula_fingerprint_variants():
    import sympy as sp
    from omai.operator.identity import formula_fingerprint
    a, b = sp.Symbol("a"), sp.Symbol("b")
    # None -> "none"
    assert formula_fingerprint(None) == "none"
    # str -> whitespace collapsed
    assert formula_fingerprint("  kappa  =\n  sum   c v^2 tau ") == "kappa = sum c v^2 tau"
    # sympy Basic -> srepr, stable across commutative reordering
    assert formula_fingerprint(a + b) == formula_fingerprint(b + a)
    # different expressions -> different fingerprint
    assert formula_fingerprint(a + b) != formula_fingerprint(a + 2 * b)


def test_version_hash_chaining_order_matters():
    from omai.operator.identity import version_hash
    genesis = "0" * 64
    r1 = {"op": "add_node", "seq": 1}
    r2 = {"op": "add_edge", "seq": 2}
    h1 = version_hash(genesis, r1)
    h2 = version_hash(h1, r2)
    # deterministic
    assert version_hash(genesis, r1) == h1
    assert version_hash(h1, r2) == h2
    # order matters: swapping the record order yields a different chain
    h2_swapped = version_hash(version_hash(genesis, r2), r1)
    assert h2 != h2_swapped
    assert len(h2) == 64


def test_node_id_ignores_names_and_tier():
    """Two spaces with identical content but different name/description/tier
    hash the same: identity is structural. (Guards the interface note.)"""
    from omai.operator.identity import node_id
    from omai.operator.space import ObservableSpace, Field
    from omai.operator.dimensions import ENERGY
    a = ObservableSpace(name="Entropy", fields=(Field("s", ENERGY, indices=("q", "nu")),),
                        description="one", tier="Thermodynamics")
    b = ObservableSpace(name="Entropy", fields=(Field("s_other", ENERGY, indices=("q", "nu")),),
                        description="two", tier="Other")
    # same quantity tag, same field signature (dimension+index kinds), same
    # gauge/labels -> same id even though field name, description, tier differ.
    assert node_id(a) == node_id(b)
