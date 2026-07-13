"""Tests for the protocol registries (quantity tags, index kinds, gauge
groups, labels) and the gauge-group normalization on nodes.py.

These walk the real map (DOMAINS plus the promoted parameters and the shared
`structure` node) so that every string that will enter a content hash in P2
is proven to resolve through a controlled registry, not a free-form string.
"""
from __future__ import annotations

import pytest


def _all_nodes():
    from omai.map_data import DOMAINS
    nodes, seen = [], set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in seen:
                seen.add(s.name)
                nodes.append(s)
    return nodes


# --------------------------------------------------------------------------
# Index kinds
# --------------------------------------------------------------------------

def test_every_index_name_in_use_resolves_to_a_kind():
    from omai.operator.registry import index_kind_signature
    from omai.materials.operator.shared_primitives import STRUCTURE
    nodes = _all_nodes() + [STRUCTURE]
    for s in nodes:
        for f in s.fields:
            # Must not raise; each name maps to a registered kind.
            sig = index_kind_signature(f.indices)
            assert len(sig) == len(f.indices)


def test_index_kind_signature_maps_known_names():
    from omai.operator.registry import index_kind_signature
    assert index_kind_signature(("i", "j", "R")) == ("atom", "atom", "lattice_vector")
    assert index_kind_signature(("alpha", "q", "nu")) == ("cartesian", "qpoint", "branch")
    assert index_kind_signature(("t",)) == ("timestep",)
    assert index_kind_signature(("tau",)) == ("lag",)
    assert index_kind_signature(("omega",)) == ("omega_bin",)
    assert index_kind_signature(("omega_bin",)) == ("omega_bin",)
    assert index_kind_signature(("mfp_bin",)) == ("mfp_bin",)
    assert index_kind_signature(()) == ()


def test_index_kind_signature_unknown_name_raises_naming_the_index():
    from omai.operator.registry import index_kind_signature
    with pytest.raises(KeyError) as exc:
        index_kind_signature(("not_an_index",))
    assert "not_an_index" in str(exc.value)


# --------------------------------------------------------------------------
# Quantity tags
# --------------------------------------------------------------------------

def test_every_nodes_derived_quantity_tag_is_registered():
    from omai.operator.registry import quantity_tag_for, QUANTITY_TAGS
    from omai.materials.operator.shared_primitives import STRUCTURE
    from omai.map_data import DOMAINS
    nodes = _all_nodes() + [STRUCTURE]
    for s in nodes:
        tag = quantity_tag_for(s.name)
        assert tag in QUANTITY_TAGS, f"{s.name} -> {tag} not registered"
    # promoted parameters
    for d in DOMAINS:
        for p in d.param_promotions:
            assert quantity_tag_for(p[0]) in QUANTITY_TAGS


def test_quantity_tag_derivation_rule():
    from omai.operator.registry import quantity_tag_for
    assert quantity_tag_for("ThermalConductivity[bte_solver=rta]") == "thermal_conductivity"
    assert quantity_tag_for("PhononDOS") == "phonon_dos"
    assert quantity_tag_for("MeanSquaredDisplacement") == "mean_squared_displacement"
    assert quantity_tag_for("CellVolume") == "cell_volume"
    assert quantity_tag_for("AtomicMass") == "atomic_mass"
    assert quantity_tag_for("AtomCount") == "atom_count"
    assert quantity_tag_for("Structure") == "structure"


def test_every_registered_quantity_tag_has_a_real_description():
    from omai.operator.registry import QUANTITY_TAGS
    for tag, desc in QUANTITY_TAGS.items():
        assert isinstance(desc, str) and len(desc.strip()) >= 12, tag
        assert "placeholder" not in desc.lower(), tag
        assert "TODO" not in desc, tag


def test_validate_quantity_tag_rejects_unregistered():
    from omai.operator.registry import validate_quantity_tag
    with pytest.raises((KeyError, ValueError)):
        validate_quantity_tag("not_a_real_quantity")


# --------------------------------------------------------------------------
# Gauge groups
# --------------------------------------------------------------------------

def test_every_hidden_space_gauge_group_is_registered():
    from omai.operator.registry import GAUGE_GROUPS
    from omai.operator.space import HiddenSpace
    for s in _all_nodes():
        if isinstance(s, HiddenSpace):
            assert s.gauge_group in GAUGE_GROUPS, f"{s.name}: {s.gauge_group!r}"


def test_gauge_groups_are_exactly_the_six_identifiers():
    from omai.operator.registry import GAUGE_GROUPS
    assert set(GAUGE_GROUPS) == {
        "u1_phase_and_ud_degenerate_subspace",
        "ud_degenerate_subspace_on_eigenvectors",
        "bz_summation_permutation",
        "bz_summation_permutation_via_1_over_gamma",
        "bz_summation_permutation_via_lorentzian",
        "md_ensemble_noise",
    }


# --------------------------------------------------------------------------
# Label keys / values
# --------------------------------------------------------------------------

def test_every_label_key_and_value_on_every_node_validates():
    from omai.operator.registry import LABEL_KEYS
    for s in _all_nodes():
        for k, v in s.labels.items():
            assert k in LABEL_KEYS, f"{s.name}: label key {k!r} unregistered"
            assert str(v) in LABEL_KEYS[k], f"{s.name}: {k}={v!r} not allowed"


def test_label_keys_registry_shape():
    from omai.operator.registry import LABEL_KEYS
    assert LABEL_KEYS["order"] == frozenset({"2", "3"})
    assert LABEL_KEYS["bte_solver"] == frozenset({"rta", "direct_inverse"})
    assert LABEL_KEYS["channel"] == frozenset(
        {"anharmonic_3ph", "isotope", "boundary", "total"}
    )
    assert LABEL_KEYS["wrt"] == frozenset({"omega", "mfp"})
    assert LABEL_KEYS["transport_model"] == frozenset(
        {"wigner", "wigner_populations", "wigner_coherences", "qhgk",
         "green_kubo", "nemd", "hnemd", "landauer"}
    )


# --------------------------------------------------------------------------
# AtomicMass dimension promotion
# --------------------------------------------------------------------------

def test_atomic_mass_promotion_carries_mass_dimension():
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    by_pid = {p[0]: p for p in THERMAL_TRANSPORT.param_promotions}
    am = by_pid["AtomicMass"]
    assert len(am) >= 4 and am[3] == "mass"
