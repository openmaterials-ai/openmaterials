"""The playground plain data view renders facts for a pinned structure.

When a lineage's ``material.configuration`` pins a real cell, the view resolves
that uid against the configurations bundle and adds plain key-value rows for
formula, space group, atom count, and lattice lengths. These tests pin the data
contract, the page wiring, and the shipped JavaScript helper behavior.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from omai.map_data import build_configurations

_REPO = Path(__file__).resolve().parents[1]
_PLAY = _REPO / "docs" / "play" / "index.html"
_BUNDLE = _REPO / "docs" / "data" / "configurations.json"


def _si_record(records):
    for record in records:
        if record.get("formula") == "Si":
            return record
    raise AssertionError("no Si configuration record in the bundle")


def test_configuration_bundle_carries_the_fields_the_card_renders():
    records = build_configurations()
    assert records, "the configuration bundle is empty; the card has nothing to resolve"
    si = _si_record(records)
    # keyed by a content-addressed canonical uid (what material.configuration pins)
    uid = si["canonical"]["uid"]
    assert isinstance(uid, str) and len(uid) == 64
    # the summary fields, all present on the real Si record
    assert si["formula"] == "Si"
    assert si["canonical"]["spacegroup"] == 227
    assert si["natoms"] == 2
    lattice = si["structure"]["lattice"]
    assert lattice["a"] and lattice["b"] and lattice["c"]


def test_committed_bundle_matches_the_builder():
    """The page fetches the committed docs/data/configurations.json at load, so it
    must equal what build_configurations produces (else the card resolves against
    a stale cell)."""
    assert _BUNDLE.exists(), "docs/data/configurations.json is missing"
    committed = json.loads(_BUNDLE.read_text())
    assert committed == build_configurations()


def _grab_function(html: str, name: str) -> str:
    """Extract a top-level ``function name(...) { ... }`` by brace matching."""
    match = re.search(r"function %s\s*\([^)]*\)\s*\{" % re.escape(name), html)
    assert match, f"could not find function {name} in the play page"
    index, depth = match.end(), 1
    while index < len(html) and depth:
        char = html[index]
        depth += char == "{"
        depth -= char == "}"
        index += 1
    return html[match.start():index]


def test_play_page_loads_and_renders_the_pinned_configuration():
    html = _PLAY.read_text()
    assert "fetch('../data/configurations.json" in html
    assert "configByUid" in html
    assert "function resolveConfiguration" in html
    assert "function configSummaryHTML" in html

    # the lineage-rows logic lives in datasheetHTML, the builder shared by the
    # single view and the stacked bundle view
    render = _grab_function(html, "datasheetHTML")
    lineage_rows = render[render.index("// ---- THE LINEAGE"):]
    assert "configSummaryHTML(cfg)" in lineage_rows

    for label in ("formula", "space group", "atoms", "lattice a b c (Å)"):
        assert "row('%s'" % label in html, (
            f"structure summary is missing the {label!r} row"
        )


_HELPERS = ("esc", "materialConfigUid", "resolveConfiguration", "configSummaryHTML")


def test_resolver_js_resolves_a_pin_and_degrades_gracefully():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; JS resolver behavior is checked where present")

    html = _PLAY.read_text()
    helpers = "\n".join(_grab_function(html, name) for name in _HELPERS)
    bundle = json.loads(_BUNDLE.read_text())
    si_uid = _si_record(bundle)["canonical"]["uid"]

    script = (
        "const bundle=%s;const wantUid=%s;\n"
        "const configByUid={};bundle.forEach(c=>{const u=c&&c.canonical&&c.canonical.uid;"
        "if(u)configByUid[String(u)]=c;});\n"
        "%s\n"
        "const out={};\n"
        "const pin=materialConfigUid({name:'Si',configuration:wantUid});\n"
        "out.bareString=pin===wantUid;\n"
        "const rec=resolveConfiguration(pin);\n"
        "out.resolves=!!rec&&rec.formula==='Si';\n"
        "const prefixed=materialConfigUid({configuration:'sha256:'+wantUid});\n"
        "out.sha256Prefix=resolveConfiguration(prefixed)===rec;\n"
        "out.noPinNull=resolveConfiguration(materialConfigUid({name:'Si'}))===null;\n"
        "out.unknownNull=resolveConfiguration('x')===null;\n"
        "const summary=configSummaryHTML(rec);\n"
        "out.formula=/<dt>formula<\\/dt><dd>Si<\\/dd>/.test(summary);\n"
        "out.spaceGroup=/<dt>space group<\\/dt><dd>227<\\/dd>/.test(summary);\n"
        "out.atoms=/<dt>atoms<\\/dt><dd>2<\\/dd>/.test(summary);\n"
        "out.lattice=/<dt>lattice a b c [(]Å[)]<\\/dt>/.test(summary)&&"
        "(summary.match(/3\\.849/g)||[]).length===3;\n"
        "const primitive={canonical:{natoms_primitive:4}};\n"
        "out.primitiveFallback=/<dd>4 [(]primitive[)]<\\/dd>/.test(configSummaryHTML(primitive));\n"
        "out.absentEmpty=configSummaryHTML(null)===''&&configSummaryHTML({})==='';\n"
        "out.plainRows=!/class=|<span|<canvas|<img/.test(summary);\n"
        "console.log(JSON.stringify(out));\n"
    ) % (json.dumps(bundle), json.dumps(si_uid), helpers)

    proc = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    for key, value in result.items():
        assert value is True, f"resolver check {key!r} failed"
