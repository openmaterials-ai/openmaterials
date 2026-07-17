"""THE LINEAGE artifact: the one versioned schema (graph + instance format).

Pins the refactor's contract: the committed artifact equals a fresh build, the
rolling version covers exactly its two halves, the chain is append-only from
genesis, and the identity-bearing source field follows the scheme:ref rules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai import lineages as lin
from omai.map_data import _lineage_version, write_lineage, write_version

_DATA = Path(__file__).resolve().parent.parent / "docs" / "data"


def test_descriptor_states_the_reference_implementation():
    d = lin.FORMAT_DESCRIPTOR
    assert d["identity"]["float_decimals"] == lin.FLOAT_DECIMALS
    assert d["identity"]["rounded_lineage_keys"] == list(lin._ROUNDED_LINEAGE_KEYS)
    assert d["wire"]["write_key"] == "lineage"
    assert d["wire"]["read_keys"] == ["lineage", "recipe"]
    assert d["source"]["schemes"] == list(lin.SOURCE_SCHEMES)


def test_committed_artifact_matches_a_fresh_build(tmp_path):
    committed = json.loads((_DATA / "lineage.json").read_text())
    fresh_path = write_lineage(tmp_path / "lineage.json")
    fresh = json.loads(fresh_path.read_text())
    assert committed == fresh, "docs/data/lineage.json is stale: rerun the build"


def test_version_covers_exactly_graph_plus_format():
    art = json.loads((_DATA / "lineage.json").read_text())
    assert art["lineage_version"] == _lineage_version(art["graph_version"])
    assert art["format_rules_version"] == lin.format_rules_version()
    v = json.loads((_DATA / "version.json").read_text())
    assert v["version"] == art["lineage_version"]
    assert v["graph_version"] == art["graph_version"]


def test_chain_is_append_only_from_genesis():
    chain = json.loads((_DATA / "versions.json").read_text())
    v = json.loads((_DATA / "version.json").read_text())
    assert chain, "the chain must have at least its seed entry"
    assert chain[0]["parent"] == v["genesis"]
    for prev, cur in zip(chain, chain[1:]):
        assert cur["parent"] == prev["version"], "broken parent link"
    assert chain[-1]["version"] == v["version"], "chain head != stamped version"


def test_rebuild_does_not_grow_the_chain(tmp_path):
    # Deterministic: rebuilding at the same state appends nothing.
    chain_before = (_DATA / "versions.json").read_text()
    write_version()
    write_lineage()
    assert (_DATA / "versions.json").read_text() == chain_before


# ---- the identity-bearing source ------------------------------------------

def _minimal(source=None, legacy=None):
    lineage = {"template": "gpumd", "values": {"kappa": 1.0}}
    if source is not None:
        lineage["source"] = source
    rec = {"lineage": lineage}
    rec["id"] = lin.lineage_id(lineage)
    if legacy is not None:
        rec["source"] = legacy
    return rec


def test_source_inside_lineage_is_identity_bearing():
    without = _minimal()
    with_src = _minimal(source="paper:cnt-2021-barbalinardo")
    assert without["id"] != with_src["id"]
    # same source, same claim -> same id (deduplication across parsers)
    again = _minimal(source="paper:cnt-2021-barbalinardo")
    assert with_src["id"] == again["id"]


@pytest.mark.parametrize("src", [
    "paper:cnt-2021-barbalinardo",
    "doi:10.1103/PhysRevLett.127.025902",
    "zotero:ABC123",
    "arxiv:2103.10633",
])
def test_valid_source_strings_validate(src):
    lin.validate_light(_minimal(source=src))


@pytest.mark.parametrize("src", ["", "noscheme", ":ref", "UPPER:ref", 42])
def test_malformed_source_rejected(src):
    with pytest.raises(lin.LineageError, match="scheme:ref"):
        lin.validate_light(_minimal(source=src))


def test_legacy_top_level_source_still_rides_outside_identity():
    rec = _minimal(legacy={"kind": "simulation", "ref": "paper:x-2020-y"})
    plain = _minimal()
    assert rec["id"] == plain["id"], "legacy source must never enter the hash"
    lin.validate_light(rec)


def test_conflicting_source_placements_rejected():
    rec = _minimal(source="paper:a-1-b", legacy={"ref": "paper:c-2-d"})
    with pytest.raises(lin.LineageError, match="conflicts"):
        lin.validate_light(rec)


def test_agreeing_source_placements_accepted():
    rec = _minimal(source="paper:a-1-b", legacy={"ref": "paper:a-1-b"})
    lin.validate_light(rec)
