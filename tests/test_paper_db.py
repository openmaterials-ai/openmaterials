"""The local paper database (omai/paper_db): the committed code that
maintains the gitignored bibliography. Fixtures only; no real PDFs."""
import json

from omai.paper_db import build_db, render_table, strict_candidates, write_db


def _claim(**over):
    c = {
        "node_id": "ThermalConductivity[bte_solver=rta]",
        "provenance": "own_result",
        "validation": {"survives": True},
        "review": {"verdict": "confirmed"},
        "kind": "value",
    }
    c.update(over)
    return c


def test_strict_candidates_bar():
    p = {"claims": [
        _claim(),                                        # passes
        _claim(provenance="cited_from_reference"),       # citation: out
        _claim(validation={"survives": False}),          # killed: out
        _claim(review={"verdict": "killed"}),            # review-killed: out
        _claim(kind="condition"),                        # run condition: out
        _claim(node_id=None),                            # unmapped: out
    ]}
    assert strict_candidates(p) == 1


def test_build_db_merges_the_three_sources(tmp_path):
    papers = tmp_path / "papers"
    proposals = tmp_path / "proposals"
    applied = tmp_path / "applied"
    for d in (papers, proposals, applied):
        d.mkdir()
    (papers / "meta.json").write_text(json.dumps({
        "x-2024": {"title": "X", "authors": "A, B", "category": "donadio"}}))
    (proposals / "x-2024.json").write_text(json.dumps({
        "map_version": "a" * 64, "cost_estimate_usd": 1.0,
        "claims": [_claim(), _claim(kind="condition")]}))
    (applied / "x-2024.json").write_text(json.dumps({
        "map_version": "a" * 64, "values": [{"value": 1}],
        "parsed": {"date": "2026-07-12"}}))
    (proposals / "y-2025.json").write_text(json.dumps({"claims": []}))

    entries = build_db(papers, proposals, applied)
    by = {e["slug"]: e for e in entries}
    x, y = by["x-2024"], by["y-2025"]
    assert x["status"] == "applied" and x["category"] == "donadio"
    assert x["parsed"]["detected"] == 2
    assert x["parsed"]["conditions"] == 1
    assert x["parsed"]["candidates"] == 1
    assert x["applied"]["values"] == 1
    assert y["status"] == "parsed"

    out = write_db(entries, papers)
    assert out.name == "db.json" and json.loads(out.read_text())
    table = render_table(entries)
    assert "x-2024" in table and "applied" in table
