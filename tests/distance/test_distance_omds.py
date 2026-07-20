import pytest

import omds


def _rec(node="ThermalConductivity[bte_solver=rta]", material="Si", T=300, code="kaldo", **params):
    return {
        "lineage": {
            "node": node,
            "material": material,
            "conditions": {"T": T},
            "params": dict(params),
            "hyperparameters": {},
            "values": {},
        },
        "execution": {"code": code},
    }


def test_identity_and_symmetry():
    a, b = _rec(), _rec(material="Ge", T=600, code="phono3py")
    assert omds.distance(a, a) == 0.0
    assert omds.distance(a, b) == pytest.approx(omds.distance(b, a))
    assert 0 < omds.distance(a, b) <= 1.0


def test_node_distance_uses_the_map():
    g = omds.default_graph()
    near = g.distance("Potential", "ForceConstants[order=2]")  # one operator apart
    far = g.distance("Potential", "ThermalConductivity[bte_solver=rta]")
    assert 0 < near < far <= 1.0
    same_base = g.distance("ThermalConductivity", "ThermalConductivity[bte_solver=rta]")
    assert same_base <= 0.15  # qualifier penalty caps siblings
    assert g.distance("NotANode", "AlsoNotANode") == 1.0
    assert g.distance("NotANode", "NotANode") == 0.0


def test_divergence_localizes_the_differing_field():
    a = _rec(T=300)
    b = _rec(T=600)
    top = omds.divergence(a, b)[0]
    assert top[0] == "conditions" and top[1] > 0
    bd = omds.breakdown(a, b)
    assert bd["node"] == 0 and bd["material"] == 0 and bd["execution"] == 0


def test_material_channel_orders_chemistry():
    si_ge = omds.distance(_rec(), _rec(material="Ge"), metric="lineage-material")
    si_o = omds.distance(_rec(), _rec(material="O"), metric="lineage-material")
    assert 0 < si_ge < si_o
    assert omds.distance(_rec(material="a-Si"), _rec(material="Si"), metric="lineage-material") < si_ge
    swcnt = omds.distance(_rec(material="SWCNT"), _rec(material="Si"), metric="lineage-material")
    assert swcnt == 1.0  # unparseable name compares as a plain string


def test_instance_row_normalizes():
    row = {"variable": "ThermalConductivity[bte_solver=rta]", "material": "Si", "conditions": {"T": 300}, "value": 140.0}
    assert omds.distance(row, _rec()) < 0.15  # only execution can differ (code None vs kaldo)


def test_alias_doctrine_and_registry():
    assert omds.resolve("default").full_id == omds.DEFAULT_ALIAS == "lineage@1"
    assert "default" not in omds.DISTANCES
    assert all(s.input == "lineage" for s in omds.DISTANCES.values())
    assert sum(omds.WEIGHTS.values()) == pytest.approx(1.0)
    with pytest.raises(KeyError, match="unknown distance"):
        omds.resolve("nope")
