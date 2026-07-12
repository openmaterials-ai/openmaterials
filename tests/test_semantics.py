"""The semantic layer: fuzzy language in, checkable identity out."""
import json
from pathlib import Path

import pytest

from omai.map_data import DOMAINS, build_graph_dict
from omai.semantics import ALIASES, build_semantics, normalize, resolve

_GRAPH = build_graph_dict(DOMAINS)
_SEM = build_semantics(_GRAPH)


def test_every_element_carries_labels():
    nodes = sum(1 for e in _SEM if e["kind"] == "node")
    edges = sum(1 for e in _SEM if e["kind"] == "edge")
    assert nodes == len(_GRAPH["nodes"])
    assert edges == len({l["op"] for l in _GRAPH["links"] if l.get("op")})
    assert all(e["labels"] for e in _SEM)


def test_curated_aliases_point_only_at_real_elements():
    ids = {e["id"] for e in _SEM}
    for label, targets in ALIASES.items():
        for t in targets:
            assert t in ids, f"{label} -> {t}"
    # and the gate refuses a phantom target
    bad = dict(_GRAPH)
    with pytest.raises(ValueError):
        from omai import semantics as S
        old = S.ALIASES
        S.ALIASES = {"ghost-method": ("NotANode",)}
        try:
            build_semantics(_GRAPH)
        finally:
            S.ALIASES = old


def test_resolution_acceptance_ra2_seed():
    hits = resolve("phonon-thermal-conductivity", _SEM)
    assert {h["id"] for h in hits} >= {
        "ThermalConductivity[bte_solver=rta]",
        "ThermalConductivity[transport_model=qhgk]"}
    assert all(h["score"] == 1.0 for h in hits[:2])

    qha = resolve("quasi-harmonic-approximation", _SEM)
    kinds = {h["kind"] for h in qha}
    assert kinds == {"node", "edge"}  # families span both

    # normalization: kebab, snake, spaced, camel all meet
    for form in ("electronic-density-of-states", "electronic_density_of_states",
                 "Electronic Density of States"):
        assert resolve(form, _SEM)[0]["id"] == "ElectronicDOS"


def test_no_home_is_an_honest_empty():
    assert resolve("neb-transition-state-calculation", _SEM) == []


def test_normalize_forms():
    assert normalize("Quasi-Harmonic_Approximation") == "quasi harmonic approximation"
    assert normalize("PhononDOS") == "phonon dos"


def test_semantics_artifact_pins_uids():
    art = Path("docs/data/semantics.json")
    assert art.exists()
    data = json.loads(art.read_text())
    by_id = {e["id"]: e for e in data}
    guid = {n["id"]: n["uid"] for n in _GRAPH["nodes"]}
    for nid, uid in list(guid.items())[:20]:
        assert by_id[nid]["uid"] == uid
