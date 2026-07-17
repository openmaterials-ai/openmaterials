"""Evidence records ARE lineage instances (stage 2 of the Lineage refactor).

One construct: every value on the map is a {id, kind, lineage, source} record
whose identity is the hash of its lineage alone. The flat instances.json the
site reads is a byte-stable PROJECTION of these files, so every downstream
consumer (agreement, experiment page, coverage) is untouched by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai.lineages import lineage_id, validate_light
from omai.map_data import _domains, build_graph_dict, build_instances, record_instance

_DATA = Path(__file__).resolve().parent.parent / "docs" / "data"
_FILES = sorted((_DATA / "instances").glob("*.json"))


def _name_to_uid():
    return {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}


def test_every_committed_evidence_file_is_a_lineage_instance():
    assert _FILES, "no committed evidence found"
    name_to_uid = _name_to_uid()
    for f in _FILES:
        rec = json.loads(f.read_text())
        assert rec["id"] == lineage_id(rec["lineage"]), f.name
        assert rec["kind"] in ("simulation", "measurement"), f.name
        report = validate_light(rec, name_to_uid=name_to_uid, where=f.name)
        assert report["node_resolved"], f.name


def test_projection_matches_the_committed_flat_bundle():
    committed = json.loads((_DATA / "instances.json").read_text())
    assert build_instances() == committed, \
        "docs/data/instances.json is stale: rerun the build"


def test_scheme_sources_are_in_hash_and_agree_with_the_verbatim_block():
    in_hash = 0
    for f in _FILES:
        rec = json.loads(f.read_text())
        lin_src = rec["lineage"].get("source")
        if lin_src is not None:
            in_hash += 1
            assert ":" in lin_src, f.name
            assert lin_src == rec["source"]["ref"], f.name
        else:
            # bare code refs (e.g. "kaldo") stay only in the verbatim block
            assert ":" not in rec["source"]["ref"], f.name
    assert in_hash > 0, "expected at least one scheme:ref source in-hash"


def test_writer_emits_the_lineage_instance_shape(tmp_path):
    domains = _domains()
    p = record_instance(
        domains=domains,
        variable="ThermalConductivity",
        material="test-material",
        value=1.25,
        units="W/(m K)",
        source_kind="measurement",
        source_ref="paper:test-2026-nobody",
        conditions={"T": 300},
        uncertainty=0.05,
        detail='"a quoted sentence" (p. 1)',
        instances_dir=tmp_path,
    )
    rec = json.loads(p.read_text())
    assert rec["id"] == lineage_id(rec["lineage"])
    assert rec["kind"] == "measurement"
    assert rec["lineage"]["source"] == "paper:test-2026-nobody"
    assert rec["lineage"]["values"] == {"value": 1.25, "units": "W/(m K)",
                                       "uncertainty": 0.05}
    assert rec["source"]["detail"].startswith('"a quoted sentence"')


def test_writer_same_claim_same_source_is_idempotent(tmp_path):
    domains = _domains()
    kw = dict(domains=domains, variable="ThermalConductivity", material="m",
              value=2.0, units="W/(m K)", source_kind="simulation",
              source_ref="paper:test-2026-same", instances_dir=tmp_path)
    p1 = record_instance(**kw)
    p2 = record_instance(**kw)
    assert p1 == p2, "identical claim from the same source must dedupe"
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_writer_bare_code_ref_stays_out_of_hash(tmp_path):
    domains = _domains()
    p = record_instance(domains=domains, variable="ThermalConductivity",
                        material="m", value=3.0, units="W/(m K)",
                        source_kind="simulation", source_ref="kaldo",
                        instances_dir=tmp_path)
    rec = json.loads(p.read_text())
    assert "source" not in rec["lineage"]
    assert rec["source"]["ref"] == "kaldo"


def test_projected_entries_keep_the_legacy_contract():
    for entry in build_instances():
        for key in ("variable", "material", "conditions", "value", "units",
                    "uncertainty", "source", "node_uid"):
            assert key in entry
        assert entry["source"].get("kind") in ("simulation", "measurement")
