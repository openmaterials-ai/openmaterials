"""The playground's envelope decode agrees with the python reference.

The page's dual read (docs/play/index.html: b64urlToObj + normalizeEnvelope)
and omai/lineages.py envelope_from_fragment must speak the same wire: a
python-minted multi-lineage bundle fragment decodes on the page to the same
member count, ids, and doc source, and a legacy single-record fragment still
decodes (normalized to a one-element envelope), forever.

Follows the test_run_url_configuration_param.py technique: extract the page's
top-level functions by brace matching and run them under Node against real
fragments minted by the python reference. Skipped cleanly when Node (or its
DecompressionStream, needed for the gzip fragment) is unavailable; a static
wiring check guards the feature regardless.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from omai import lineages as lin

_REPO = Path(__file__).resolve().parents[1]
_PLAY = _REPO / "docs" / "play" / "index.html"


def _grab_function(html: str, name: str) -> str:
    """Extract a top-level `function name(...) { ... }` body by brace matching."""
    m = re.search(r"(?:async )?function %s\s*\([^)]*\)\s*\{" % re.escape(name), html)
    assert m, f"could not find function {name}"
    i, depth = m.end(), 1
    while i < len(html) and depth:
        c = html[i]
        depth += c == "{"
        depth -= c == "}"
        i += 1
    return html[m.start():i]


# The page's decode path, in dependency order: fragment bytes -> object ->
# normalized envelope. normalizeLineageRecord is normalizeEnvelope's helper.
_DECODE_HELPERS = ("bytesFromB64url", "b64urlToObj",
                   "normalizeLineageRecord", "normalizeEnvelope")


def _node_or_skip() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; decode agreement checked where present")
    probe = subprocess.run(
        [node, "-e", "console.log(typeof DecompressionStream)"],
        capture_output=True, text=True)
    if probe.returncode != 0 or "function" not in probe.stdout:
        pytest.skip("node lacks DecompressionStream (gzip fragments need it)")
    return node


def _decode_on_page(fragment: str) -> dict:
    """Run the page's real decode+normalize under Node on a fragment, returning
    {count, ids, doc_source}."""
    node = _node_or_skip()
    html = _PLAY.read_text()
    src = "\n".join(_grab_function(html, n) for n in _DECODE_HELPERS)
    script = src + """
(async function(){
  var payload = await b64urlToObj(%s);
  var env = normalizeEnvelope(payload);
  console.log(JSON.stringify({
    count: env.lineages.length,
    ids: env.lineages.map(function(m){ return m.id || null; }),
    doc_source: env.doc && env.doc.source || null
  }));
})().catch(function(e){ console.error(e); process.exit(1); });
""" % json.dumps(fragment)
    proc = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _member(node_id, mat, val):
    lineage = {"node": node_id, "material": {"name": mat},
               "conditions": {"T": 300.0},
               "values": {"value": val, "units": "W/(m K)"}}
    return {"id": lin.lineage_id(lineage), "lineage": lineage}


# --------------------------------------------------------------------------
# Static wiring: the page speaks the envelope even where Node is unavailable.
# --------------------------------------------------------------------------

def test_page_wires_the_envelope_dispatch():
    html = _PLAY.read_text()
    assert "function normalizeEnvelope" in html, "no envelope normalizer on the page"
    assert "renderShared(payload)" in html, "the #x= decode does not dispatch through renderShared"
    assert "function renderBundle" in html, "no bundle (paper) view on the page"
    assert "from the shared document" in html, "no read-time source inheritance label"
    assert "showLengthFallback" in html and "8000" in html, "no length-honesty rule"
    assert "Download the envelope as JSON" in html, "no JSON download fallback"


def test_bundle_stacks_every_datasheet_on_one_page():
    """A bundle shows every member's FULL datasheet on the same page (the CEO's
    same-page rule), built by the one shared datasheetHTML so the single and
    stacked views can never drift, with the derivation drawn as a map excerpt
    (the only sanctioned graphic; value charts stay on MCG)."""
    html = _PLAY.read_text()
    assert "function datasheetHTML" in html, "no shared datasheet builder"
    assert 'class="rec bundle-member"' in html, "bundle does not stack member datasheets"
    assert "datasheetHTML(mvalid.record, mvalid" in html, \
        "the stacked members do not reuse the shared builder"
    assert "function derivationSVG" in html, "no derivation map excerpt"
    assert 'class="rec-map"' in html, "the derivation svg is not class-marked"
    assert "scrollIntoView" in html, "member rows must jump on-page, not re-render"
    # the only svg the datasheet may emit is the sanctioned map excerpt
    import re
    svgs = re.findall(r"<svg[^>]*class=\\?\"([^\"\\]*)", html)
    assert all("rec-map" in c for c in svgs), f"unsanctioned svg classes: {svgs}"


# --------------------------------------------------------------------------
# Behavior, pinned to the python reference under Node.
# --------------------------------------------------------------------------

def test_python_minted_bundle_decodes_to_member_count_n():
    members = [_member("ThermalConductivity", "Si", 148.0),
               _member("ThermalConductivity", "Ge", 62.0),
               _member("BulkModulus", "Si", 97.8)]
    doc = {"source": "doi:10.1103/PhysRevLett.127.025902", "title": "Demo"}
    frag = lin.envelope_to_fragment(lin.envelope(members, doc=doc))
    got = _decode_on_page(frag)
    ref = lin.envelope_from_fragment(frag)
    assert got["count"] == len(ref["lineages"]) == 3
    assert got["ids"] == [m["id"] for m in ref["lineages"]]
    assert got["doc_source"] == ref["doc"]["source"]


def test_legacy_single_record_fragment_still_renders():
    record = _member("ThermalConductivity", "Si", 148.0)
    frag = lin.record_to_fragment(record)          # a link minted before bundles
    got = _decode_on_page(frag)
    ref = lin.envelope_from_fragment(frag)
    assert got["count"] == len(ref["lineages"]) == 1
    assert got["ids"] == [record["id"]]
    assert got["doc_source"] is None and "doc" not in ref
