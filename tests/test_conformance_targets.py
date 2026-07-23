"""Conformance targets are pinned expectations cited by identity.

A target is {id, lineage, code, expected, tolerance, evidence?, note?}: it points
at a value on the map by carrying that value's LINEAGE verbatim, so
lineage_id(target.lineage) == target.id == the evidence instance's id (a
cryptographic not-invented proof, not an asserted link). The number a code is
expected to reproduce (expected) equals the instance's own lineage.values, and
the target's code must represent the target's node in codes.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from omai.lineages import lineage_id, validate_light
from omai.map_data import _domains, build_graph_dict

_DATA = Path(__file__).resolve().parent.parent / "docs" / "data"
_FILES = sorted((_DATA / "conformance").glob("*-target.json"))
_INSTANCES = _DATA / "instances"


def _name_to_uid():
    return {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}


def test_at_least_one_committed_target():
    assert _FILES, "no committed conformance target found"


def test_every_target_has_a_valid_identity_and_shape():
    for f in _FILES:
        tgt = json.loads(f.read_text())
        # Identity is the lineage alone, exactly as for an instance: the stated
        # id must recompute from the lineage.
        assert tgt["id"] == lineage_id(tgt["lineage"]), f.name
        # tolerance shape: a non-negative number and a known kind.
        tol = tgt["tolerance"]
        assert isinstance(tol.get("value"), (int, float)) \
            and not isinstance(tol["value"], bool), f.name
        assert tol["value"] >= 0, f.name
        assert tol["kind"] in ("absolute", "relative"), f.name
        # expected carries a value and its units.
        expected = tgt["expected"]
        assert "value" in expected and "units" in expected, f.name


def test_evidence_branch_is_cited_by_identity_or_the_literature_branch():
    """A target with an `evidence` file must share the instance's identity and
    expected number byte-for-byte; a literature target (no evidence file) must
    carry a scheme:ref source in its lineage instead."""
    evidence_seen = 0
    literature_seen = 0
    for f in _FILES:
        tgt = json.loads(f.read_text())
        evidence = tgt.get("evidence")
        if evidence is not None:
            evidence_seen += 1
            inst_path = _INSTANCES / evidence
            assert inst_path.exists(), \
                f"{f.name}: evidence {evidence} not under instances/"
            inst = json.loads(inst_path.read_text())
            # The identity coincidence: the target's id EQUALS the instance's id,
            # because the lineage was copied verbatim (never retyped).
            assert inst["id"] == tgt["id"], f.name
            # expected mirrors the instance's own recorded value and units.
            vals = inst["lineage"]["values"]
            assert tgt["expected"]["value"] == vals["value"], f.name
            assert tgt["expected"]["units"] == vals["units"], f.name
        else:
            # The literature branch: no committed instance, so the lineage names
            # a scheme:ref source (e.g. doi:...) that carries the citation.
            literature_seen += 1
            src = tgt["lineage"].get("source")
            assert isinstance(src, str) and ":" in src, \
                f"{f.name}: a literature target must carry a scheme:ref " \
                f"lineage.source"
    assert evidence_seen + literature_seen == len(_FILES)


def test_every_target_node_resolves_against_the_live_map():
    name_to_uid = _name_to_uid()
    for f in _FILES:
        tgt = json.loads(f.read_text())
        report = validate_light(tgt, name_to_uid=name_to_uid, where=f.name)
        assert report["node_resolved"], f.name


def test_every_target_code_maps_its_node_in_codes_json():
    """A target's reproducer is a codes.json rail covering its node, or the
    literal sentinel "closed-form": the value of a closed-form edge is
    reproduced by the map's own executable formula, not by an external
    code, and the kernel is not a rail on its own map."""
    codes = json.loads((_DATA / "codes.json").read_text())
    for f in _FILES:
        tgt = json.loads(f.read_text())
        code = tgt["code"]
        if code == "closed-form":
            continue
        assert code in codes, f"{f.name}: code {code!r} is not a codes.json rail"
        node = tgt["lineage"]["node"]
        assert node in codes[code], \
            f"{f.name}: rail {code!r} does not cover node {node!r}"


def test_committed_index_is_the_projection_of_the_target_files():
    """docs/data/conformance/index.json is derived data (like instances.json):
    it must byte-equal a fresh projection of the committed target files, and
    each row must mirror its file's id, node, code, expected, and tolerance."""
    import json

    from omai.map_data import write_conformance_index

    index_path = _DATA / "conformance" / "index.json"
    assert index_path.exists(), "conformance index not committed"
    committed = index_path.read_text()
    fresh_path, n = write_conformance_index()
    assert fresh_path.read_text() == committed, "index.json is stale; run python -m omai.map_data"
    rows = json.loads(committed)["targets"]
    assert len(rows) == n == len(_FILES)
    for row in rows:
        t = json.loads((_DATA / "conformance" / row["file"]).read_text())
        assert row["id"] == t["id"]
        assert row["node"] == t["lineage"]["node"]
        assert row["code"] == t["code"]
        assert row["expected"] == t["expected"]
        assert row["tolerance"] == t["tolerance"]
