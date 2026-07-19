"""The published distance data: registry-true, deterministic, honestly labeled.

docs/data/distances.json is derived data for the site's Distance tab: the
metric registry read from omdc itself, the illustrative silicon zoo computed
fresh on the hist encoder, and pairwise committed-configuration distances
(which grow as configurations land). Regeneration must be byte-stable and the
committed artifact must equal a fresh build. Skips cleanly without the
distance extras, like the rest of the extras-gated surface.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_DATA = Path(__file__).resolve().parents[1] / "docs" / "data" / "distances.json"

omdc_deps = pytest.importorskip("ot", reason="distance extras not installed")


def test_committed_distances_match_fresh_build(tmp_path):
    from omai.distance_data import write_distances

    assert _DATA.exists(), "distances.json not committed"
    fresh = tmp_path / "distances.json"
    write_distances(fresh)
    assert fresh.read_text() == _DATA.read_text(), \
        "distances.json is stale; run python -m omai.map_data"


def test_registry_mirrors_omdc():
    import omdc

    d = json.loads(_DATA.read_text())
    keys = [m["key"] for m in d["registry"]["distances"]]
    assert sorted(keys) == sorted(omdc.DISTANCES.keys())
    assert d["registry"]["default"] == omdc.DEFAULT_ALIAS
    for m in d["registry"]["distances"]:
        spec = omdc.DISTANCES[m["key"]]
        assert m["description"] == spec.description
        assert m["metric"] == bool(spec.metric)


def test_zoo_is_labeled_illustrative_and_complete():
    d = json.loads(_DATA.read_text())
    zoo = d["zoo"]
    assert zoo["illustrative"] is True, "constructed cells must be labeled"
    ids = {m["id"] for m in d["registry"]["distances"]}
    for row in zoo["rows"]:
        assert set(row["distances"].keys()) == ids, row["name"]


def test_committed_section_counts_honestly():
    d = json.loads(_DATA.read_text())
    c = d["committed"]
    n = c["configurations"]
    assert len(c["pairs"]) == n * (n - 1) // 2
