"""Tiers: authored physics-stage grouping on Spaces, exported to graph.json."""
from __future__ import annotations

from omai.operator.space import ObservableSpace, Field
from omai.operator.dimensions import DIMENSIONLESS


def test_space_carries_tier_default_empty():
    s = ObservableSpace(name="X", fields=(Field("x", DIMENSIONLESS),))
    assert s.tier == ""


def test_space_tier_settable():
    s = ObservableSpace(name="X", fields=(Field("x", DIMENSIONLESS),), tier="Sources")
    assert s.tier == "Sources"


def test_domain_carries_tiers_default_empty():
    from omai.map_data import Domain
    from omai.thermal_transport import representation as tt_rep
    d = Domain(name="d", nodes=(), edges=(), symbols={}, param_promotions=(),
               representation_package=tt_rep)
    assert d.tiers == ()
