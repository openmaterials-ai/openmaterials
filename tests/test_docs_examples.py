"""The docs/examples gallery is real, valid, and self-consistent.

Every shipped example lineage must be a valid LIGHT record whose stated id
recomputes, and index.json must agree with the record files byte-for-byte:
the fragment in the index decodes to exactly the committed record, so a
shared link and the committed file can never drift apart silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai.lineages import (
    lineage_id,
    record_from_fragment,
    record_lineage,
    validate_light,
)

_GALLERY = Path(__file__).resolve().parent.parent / "docs" / "examples"
_RECORDS = sorted(p for p in _GALLERY.glob("*.json") if p.name != "index.json")


def _index_entries():
    idx = json.loads((_GALLERY / "index.json").read_text())
    return idx if isinstance(idx, list) else idx["examples"]


def test_gallery_is_nonempty():
    assert len(_RECORDS) >= 10


@pytest.mark.parametrize("path", _RECORDS, ids=lambda p: p.stem)
def test_record_is_valid_light_and_id_recomputes(path):
    rec = json.loads(path.read_text())
    validate_light(rec, where=path.name)  # raises on a malformed record
    assert rec["id"] == lineage_id(record_lineage(rec))


def test_index_matches_the_record_files_exactly():
    by_slug = {p.stem: json.loads(p.read_text()) for p in _RECORDS}
    entries = _index_entries()
    assert len(entries) == len(by_slug)
    for e in entries:
        rec = by_slug[e["slug"]]
        assert rec["id"].startswith(e["id"]), f"{e['slug']}: index id is stale"
        decoded = record_from_fragment(e["fragment"])
        assert decoded == rec, f"{e['slug']}: index fragment does not decode to the committed record"
