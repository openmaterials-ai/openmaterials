"""Per-instance share stubs make a hash permalink unfurl.

The playground datasheet at /play/#id=<hash> is client-side (GitHub Pages), so a
crawler that pastes the link into Slack or a social card never runs the JS and
the permalink unfurls to nothing. The build emits one tiny static page per
committed value at docs/i/<id>/index.html: the OG metadata a crawler reads, then
an instant redirect into the SAME #id= resolver the playground already speaks.

These pin the stub the way test_play_envelope_decode.py pins the resolver: the
build's real output (build_share_stubs / write_share_stubs) against the committed
instances, plus the page's real permalinkFor driven under Node so the Copy
control and the emitted stub agree on the /i/<id>/ shape. Node-driven checks skip
cleanly where node is absent; the tree checks guard the feature regardless.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from omai.map_data import build_instances, build_share_stubs, write_share_stubs

_REPO = Path(__file__).resolve().parents[1]
_PLAY = _REPO / "docs" / "play" / "index.html"
_SHARE_DIR = _REPO / "docs" / "i"
_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)">')
_REDIRECT_RE = re.compile(r'location\.replace\("(/play/#id=[0-9a-f]{64})"\)')


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


def _node_or_skip() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; permalink shape checked where present")
    return node


def _permalink_on_page(rid: str) -> str:
    """Run the page's real permalinkFor under Node for a canonical id, with a
    stub location so origin/pathname resolve, returning the emitted url."""
    node = _node_or_skip()
    src = _grab_function(_PLAY.read_text(), "permalinkFor")
    script = ("var location = { origin: 'https://openmaterials.ai',"
              " pathname: '/play/' };\n" + src +
              "\nconsole.log(permalinkFor(%s));" % json.dumps(rid))
    proc = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    return proc.stdout.strip().splitlines()[-1]


# --------------------------------------------------------------------------
# The build emits one stub per committed value, and only those.
# --------------------------------------------------------------------------

def test_every_instance_has_a_stub_titled_with_its_material():
    """Every committed value gets a stub whose og:title names its property and
    material (the customer-facing pair), so a shared /i/<id>/ link unfurls with
    what it opens. The redirect target is that value's own #id= permalink."""
    insts = build_instances()
    assert insts, "no instances projected"
    stubs = build_share_stubs(insts)
    assert set(stubs) == {e["id"] for e in insts}, \
        "the stub set must be exactly the instance set"
    for e in insts:
        page = stubs[e["id"]]
        mat = e.get("material")
        mat_name = mat.get("name") if isinstance(mat, dict) else mat
        title = _TITLE_RE.search(page)
        assert title, f"{e['id'][:12]}: no og:title in the stub"
        if mat_name:
            assert str(mat_name) in title.group(1), \
                f"{e['id'][:12]}: og:title omits the material {mat_name!r}"
        # the redirect target is THIS value's id, into the #id= resolver
        redirect = _REDIRECT_RE.search(page)
        assert redirect and redirect.group(1) == f"/play/#id={e['id']}", \
            f"{e['id'][:12]}: redirect target does not match its id"


def test_stub_carries_the_unfurl_metadata_and_lands_humans_live():
    """Each stub is the crawler surface AND the human on-ramp: og:site_name, a
    summary card, a canonical link, an instant redirect, and a <noscript> link so
    a reader with no JS still reaches the datasheet."""
    stubs = build_share_stubs()
    page = next(iter(stubs.values()))
    for needle in (
        '<meta property="og:site_name" content="openmaterials.ai">',
        '<meta name="twitter:card" content="summary">',
        '<link rel="canonical"',
        '<meta http-equiv="refresh"',
        "location.replace(",
        "<noscript>",
    ):
        assert needle in page, f"a stub is missing {needle!r}"


def test_value_and_provenance_ride_in_the_description():
    """The og:description carries the value with units and the provenance: a
    measurement names its source, a simulation is computed by its code."""
    insts = build_instances()
    stubs = build_share_stubs(insts)
    for e in insts:
        page = stubs[e["id"]]
        m = re.search(r'<meta property="og:description" content="([^"]*)">', page)
        assert m, f"{e['id'][:12]}: no og:description"
        desc = m.group(1)
        if e.get("value") is not None and e.get("units"):
            assert str(e["units"]) in desc, \
                f"{e['id'][:12]}: description omits the units"
        verb = "measured" if e["source"]["kind"] == "measurement" else "computed by"
        assert verb in desc, f"{e['id'][:12]}: description omits the provenance verb"


def test_every_interpolated_field_is_html_escaped():
    """A material or ref carrying &, <, >, or a quote is escaped, never injected
    raw into the stub (the same real-values bar the projection holds)."""
    inst = [{
        "id": "a" * 64, "variable": "BandGap",
        "material": 'A & B "x" <y>', "conditions": {},
        "value": 1.1, "units": "eV", "uncertainty": None,
        "source": {"kind": "simulation", "ref": "code&<>"},
        "node_uid": "z" * 64,
    }]
    page = build_share_stubs(inst)["a" * 64]
    assert "A & B" not in page and 'B "x"' not in page, "a special char leaked raw"
    for entity in ("&amp;", "&quot;", "&lt;", "&gt;"):
        assert entity in page, f"expected {entity} in the escaped stub"


# --------------------------------------------------------------------------
# Determinism, and the tree matches the projection exactly (no orphans).
# --------------------------------------------------------------------------

def test_regeneration_is_deterministic():
    assert build_share_stubs() == build_share_stubs(), \
        "two builds of the stubs must be byte-identical"


def test_write_share_stubs_matches_the_instance_set_and_prunes_orphans(tmp_path):
    """Written to disk, the stub tree is EXACTLY the instance set: every value has
    docs/i/<id>/index.html, and a stale stub from a prior build is pruned so no
    orphan permalink is served."""
    out = tmp_path / "i"
    orphan = out / ("d" * 64)
    orphan.mkdir(parents=True)
    (orphan / "index.html").write_text("stale")
    write_share_stubs(out)
    ids = {e["id"] for e in build_instances()}
    on_disk = {p.name for p in out.iterdir() if p.is_dir()}
    assert on_disk == ids, "the served stub set must equal the instance set"
    assert not orphan.exists(), "a stale stub must be pruned"
    for rid in ids:
        assert (out / rid / "index.html").is_file(), f"{rid[:12]}: no index.html"


def test_the_committed_stub_tree_is_up_to_date():
    """The docs/i tree checked into the build is not stale: it is exactly what the
    current projection produces, so a reviewer never merges a stale permalink."""
    if not _SHARE_DIR.exists():
        pytest.skip("docs/i not generated in this checkout; build emits it")
    expected = build_share_stubs()
    on_disk = {p.name for p in _SHARE_DIR.iterdir()
               if p.is_dir() and re.fullmatch(r"[0-9a-f]{64}", p.name)}
    assert on_disk == set(expected), "docs/i is stale; rerun python -m omai.map_data"
    for rid, doc in expected.items():
        assert (_SHARE_DIR / rid / "index.html").read_text() == doc, \
            f"{rid[:12]}: committed stub differs from the build output"


# --------------------------------------------------------------------------
# The Copy-permalink control emits the /i/<id>/ unfurling url (not #id=), while
# #id= stays the resolver the stub redirects into.
# --------------------------------------------------------------------------

def test_copy_permalink_emits_the_unfurling_stub_url():
    """The page's real permalinkFor returns the /i/<id>/ form: the shareable url
    is the crawlable stub, not the client-side #id= fragment."""
    rid = "b" * 64
    url = _permalink_on_page(rid)
    assert url == f"https://openmaterials.ai/i/{rid}/", url
    assert "#id=" not in url, "the copied permalink must not be the raw #id= fragment"


def test_id_fragment_remains_the_resolver():
    """Switching the shared url does not touch the resolver: the page still routes
    #id=<hash> and copyPermalink still sets that hash locally, so a stub's
    redirect into /play/#id=<id> opens the datasheet exactly as before."""
    html = _PLAY.read_text()
    assert "function permalinkFor" in html
    assert "'/i/' + String(id) + '/'" in html, "permalinkFor is not the /i/ form"
    # the resolver and its local hash-set are untouched
    assert "function resolveInstanceById" in html
    assert "id=([0-9a-fA-F]+)" in html, "the #id= router is gone"
    assert "var hash = '#id=' + String(id);" in html, \
        "copyPermalink no longer opens the value in place via #id="
