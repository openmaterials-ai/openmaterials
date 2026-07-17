"""The physlib crosswalk: static, reviewed alignment of map nodes to Lean 4
declarations. Schema validity, catalog closure, source honesty."""
import json
import os
import re
from pathlib import Path

import pytest

from omai.semantics import build_semantics, physlib_for, resolve
from omai.map_data import DOMAINS, build_graph_dict

_ART = Path("docs/data/physlib_crosswalk.json")
# Every source link pins the frozen physlib rev the crosswalk was reviewed
# against: master drifts, so line numbers are only true at the pinned commit.
_PINNED_REV = json.loads(_ART.read_text())["version"]["physlib_rev"]
_URL_PREFIX = f"https://github.com/leanprover-community/physlib/blob/{_PINNED_REV}/"
_KINDS = {"def", "theorem", "lemma", "structure"}
_CONFIDENCES = {"exact", "related"}


@pytest.fixture(scope="module")
def crosswalk():
    assert _ART.exists(), "docs/data/physlib_crosswalk.json is missing"
    return json.loads(_ART.read_text())


@pytest.fixture(scope="module")
def catalog_ids():
    return {n["id"] for n in json.loads(Path("docs/data/catalog.json").read_text())}


def test_schema(crosswalk):
    v = crosswalk["version"]
    assert re.fullmatch(r"[0-9a-f]{40}", v["physlib_rev"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", v["generated"])
    assert v["method"]
    assert isinstance(crosswalk["nodes"], dict)
    for node_id, entries in crosswalk["nodes"].items():
        assert isinstance(entries, list), node_id
        for e in entries:
            assert set(e) == {"name", "module", "kind", "informal",
                              "source_url", "confidence"}, (node_id, e)
            assert e["name"] and e["informal"], (node_id, e)
            assert e["module"].startswith("Physlib."), (node_id, e)
            assert e["kind"] in _KINDS, (node_id, e)
            assert e["confidence"] in _CONFIDENCES, (node_id, e)
            assert e["source_url"].startswith(_URL_PREFIX), (node_id, e)
            assert re.search(r"#L\d+$", e["source_url"]), (node_id, e)


def test_covers_every_catalog_node_and_nothing_else(crosswalk, catalog_ids):
    ids = set(crosswalk["nodes"])
    assert ids == catalog_ids, (
        f"missing: {sorted(catalog_ids - ids)}; phantom: {sorted(ids - catalog_ids)}")


def test_no_duplicate_declarations_per_node(crosswalk):
    for node_id, entries in crosswalk["nodes"].items():
        names = [e["name"] for e in entries]
        assert len(names) == len(set(names)), node_id


def test_source_paths_exist_in_clone(crosswalk):
    root = os.environ.get("PHYSLIB_PATH")
    if not root or not Path(root).is_dir():
        pytest.skip("PHYSLIB_PATH not set to a physlib clone")
    root = Path(root)
    for node_id, entries in crosswalk["nodes"].items():
        for e in entries:
            rel, _, line = e["source_url"][len(_URL_PREFIX):].partition("#L")
            f = root / rel
            assert f.is_file(), (node_id, rel)
            lines = f.read_text().splitlines()
            assert int(line) <= len(lines), (node_id, e["source_url"])
            leaf = e["name"].rsplit(".", 1)[-1]
            assert leaf in lines[int(line) - 1], (node_id, e["source_url"])
            assert (root / (e["module"].replace(".", "/") + ".lean")).is_file(), (
                node_id, e["module"])


def test_resolve_surfaces_physlib(crosswalk):
    sem = build_semantics(build_graph_dict(DOMAINS))
    hits = resolve("temperature", sem)
    hit = next(h for h in hits if h["id"] == "Temperature")
    assert hit["physlib"] == crosswalk["nodes"]["Temperature"]
    assert hit["physlib"][0]["confidence"] == "exact"
    # honest gap: a node without formal coverage carries no physlib key
    gap = resolve("thermal-conductivity", sem)
    assert all("physlib" not in h for h in gap)
    assert physlib_for("ThermalConductivity") == []
