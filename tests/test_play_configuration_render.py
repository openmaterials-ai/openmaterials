"""The playground recipe card renders a pinned structure (issue #32).

When a recipe's ``material.configuration`` pins a real cell, the card resolves
that uid against the configurations bundle and shows a structure summary
(formula, spacegroup, atom count, lattice) instead of a bare material name. This
pins three things so the feature cannot silently rot:

1. The DATA CONTRACT: ``build_configurations`` (and the committed
   ``docs/data/configurations.json`` the page fetches) carries the exact fields
   the card reads, keyed by ``canonical.uid``.
2. The WIRING in ``docs/play/index.html``: it fetches the bundle, indexes it by
   uid, and calls the structure-summary render from the Material group.
3. The RESOLVER LOGIC: the page's own JS helpers, run under Node against the
   real bundle, resolve a pin to its cell and render real fields, and degrade to
   nothing when the pin is absent or unresolved (the card's graceful-absence
   ethos). Skipped cleanly when Node is unavailable.
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


# --------------------------------------------------------------------------
# 1) The data contract the card renders from.
# --------------------------------------------------------------------------

def _si_record(records):
    for r in records:
        if r.get("formula") == "Si":
            return r
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
    lat = si["structure"]["lattice"]
    assert lat["a"] and lat["b"] and lat["c"]


def test_committed_bundle_matches_the_builder():
    """The page fetches the committed docs/data/configurations.json at load, so it
    must equal what build_configurations produces (else the card resolves against
    a stale cell)."""
    assert _BUNDLE.exists(), "docs/data/configurations.json is missing"
    committed = json.loads(_BUNDLE.read_text())
    assert committed == build_configurations()


# --------------------------------------------------------------------------
# 2) The wiring in the playground page.
# --------------------------------------------------------------------------

def test_play_page_loads_and_renders_the_pinned_configuration():
    html = _PLAY.read_text()
    # fetches the bundle at load
    assert "data/configurations.json" in html
    # indexes it by canonical uid for the pin lookup
    assert "configByUid" in html
    # the resolver + summary helpers exist and are called from the render
    assert "function resolveConfiguration" in html
    assert "function configSummaryHTML" in html
    assert "configSummaryHTML(cfg)" in html
    # the summary renders the real structure fields
    for label in ("Formula", "Space group", "Atoms", "Lattice"):
        assert label in html, f"structure summary is missing the {label!r} fact"


# --------------------------------------------------------------------------
# 3) The page's own resolver JS, exercised against the real bundle under Node.
# --------------------------------------------------------------------------

_HELPERS = ("materialConfigUid", "resolveConfiguration", "configSummaryHTML")


def _grab_function(html: str, name: str) -> str:
    """Extract a top-level `function name(...) { ... }` body by brace matching."""
    m = re.search(r"function %s\s*\([^)]*\)\s*\{" % re.escape(name), html)
    assert m, f"could not find function {name} in the play page"
    i, depth = m.end(), 1
    while i < len(html) and depth:
        c = html[i]
        depth += c == "{"
        depth -= c == "}"
        i += 1
    return html[m.start():i]


def test_resolver_js_resolves_a_pin_and_degrades_gracefully():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; JS resolver behavior checked in CI where present")
    html = _PLAY.read_text()
    helpers = "\n".join(_grab_function(html, n) for n in _HELPERS)
    bundle = json.loads(_BUNDLE.read_text())
    si_uid = _si_record(bundle)["canonical"]["uid"]

    script = (
        "const esc=s=>String(s==null?'':s).replace(/[&<>\"]/g,"
        "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));\n"
        "const bundle=%s;const wantUid=%s;\n"
        "const configByUid={};bundle.forEach(c=>{const u=c&&c.canonical&&c.canonical.uid;"
        "if(u)configByUid[String(u)]=c;});\n"
        "%s\n"
        "const out={};\n"
        "out.bareString=materialConfigUid({name:'Si',configuration:wantUid})===wantUid;\n"
        "out.sha256Prefix=materialConfigUid({configuration:'sha256:'+wantUid})===wantUid;\n"
        "out.bareNameNoUid=materialConfigUid('Si')===''&&materialConfigUid({name:'Si'})==='';\n"
        "const rec=resolveConfiguration({configuration:wantUid});\n"
        "out.resolves=!!rec&&rec.formula==='Si';\n"
        "out.unknownNull=resolveConfiguration({configuration:'x'})===null;\n"
        "const sum=configSummaryHTML(rec);\n"
        "out.summaryFormula=/Formula/.test(sum)&&/Si/.test(sum);\n"
        "out.summarySpacegroup=/227/.test(sum);\n"
        "out.summaryLattice=/Lattice/.test(sum)&&/3\\.849/.test(sum);\n"
        "out.absentEmpty=configSummaryHTML(null)===''&&configSummaryHTML({})==='';\n"
        "console.log(JSON.stringify(out));\n"
    ) % (json.dumps(bundle), json.dumps(si_uid), helpers)

    proc = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    res = json.loads(proc.stdout.strip().splitlines()[-1])
    for key, val in res.items():
        assert val is True, f"resolver check {key!r} failed"
