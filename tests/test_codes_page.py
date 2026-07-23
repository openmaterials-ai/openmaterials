"""The codes bibliography page.

One entry per cited code, rendered client-side from the same codes.json
the map reads; Lean opens the page because it checks reasoning where the
other codes compute numbers; the license posture is stated plainly. The
page must never hardcode the roster (the data file is the single source)
and never invent references (the physlib citation carries no DOI because
none exists).
"""

import json
import re
import subprocess
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
PAGE = (DOCS / "codes/index.html").read_text()
FLAT = re.sub(r"\s+", " ", PAGE)


def test_page_renders_from_the_published_data():
    assert "fetch('../data/codes.json')" in PAGE
    assert "esc(" in PAGE, "JSON strings must be escaped into HTML"
    assert "could not be loaded" in PAGE, "fetch failure must render honestly"
    assert "<noscript>" in PAGE


def test_lean_opens_the_bibliography():
    assert '<section class="gsec" id="lean">' in PAGE
    assert "10.1007/978-3-030-79876-5_37" in PAGE, "Lean 4 CADE-28 DOI"
    assert "10.1145/3372885.3373824" in PAGE, "mathlib CPP 2020 DOI"
    assert "leanprover-community/physlib" in PAGE
    assert "carries no DOI of its own" in FLAT, \
        "physlib is cited by name and URL only; no DOI exists to cite"
    assert '"../lean/"' in PAGE or "'../lean/'" in PAGE


def test_license_posture_is_stated():
    assert "GPL-3.0" in PAGE and "GPUMD" in PAGE
    assert "Apache 2.0" in PAGE and "CC BY 4.0" in PAGE
    assert "never vendors or copies" in FLAT
    assert "test_code_credits.py" in PAGE


def test_entries_link_the_map_code_filter():
    assert "../map/#code=" in PAGE


def test_no_hardcoded_roster():
    """The page must not bake in per-code citations; codes.json is the
    single source. Codes may appear only in prose (GPUMD in the posture
    section), never as data rows."""
    assert "bib-card" in PAGE, "card renderer present"
    body = PAGE.split("<body", 1)[1]
    static = re.sub(r"<script>.*?</script>", "", body, flags=re.S)
    for code in ("kaldo", "phono3py", "lammps", "quantum"):
        assert code not in static.lower(), code + " is baked into the markup"


def test_per_node_citations_are_never_hidden():
    """A code serving nodes through different methods shows every distinct
    citation on its card, with the quantities each one covers: the primary
    included, and an entry without a citation can never outrank one that
    has one."""
    assert "bib-cite-more" in PAGE
    assert "named.slice(1)" in PAGE
    assert "groups.filter(function (g) { return g.citation; })" in PAGE, \
        "the primary citation must be the largest NAMED group"
    assert "primary && named.length > 1" in PAGE, \
        "with several methods the primary must state its coverage too"


NODE_HARNESS = r"""
const fs = require('fs');
const page = fs.readFileSync(process.argv[1],'utf8');
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const body = script.slice(script.indexOf('function esc'), script.indexOf('fetch('));
const {card} = new Function(body + '; return {esc: esc, card: card};')();
const codes = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const assert = require('assert');
assert(!('materialscodegraph' in codes), 'the platform must not be a code rail');
const k = card('kaldo', codes['kaldo']);
assert(!k.includes('bib-cite-for'));
assert(k.includes('doi.org/10.1063/5.0020443'));
// per-node method split: synthetic, since no live code carries one today;
// the mechanism stays (PER_NODE_CREDITS) and the renderer must keep it honest
const split = {A:{citation:'Method One 2019',doi:'10.1/a',license:'MIT'},
               B:{citation:'Method One 2019',doi:'10.1/a',license:'MIT'},
               C:{citation:'Method Two 2021',doi:'10.1/b',license:'MIT'}};
const sp = card('split', split);
assert(sp.includes('for A, B') && sp.includes('for C'), 'coverage labels');
assert(sp.includes('doi.org/10.1/b'), 'secondary method DOI linked');
const synth = {A:{citation:'',license:'MIT'},B:{citation:'',license:'MIT'},
               C:{citation:'Real Paper 2020',doi:'10.1/x',license:'MIT'}};
const sh = card('synth', synth);
assert(sh.includes('Real Paper 2020') && !sh.includes('No citation recorded'));
console.log('ok');
"""


def test_card_renderer_behaves_on_real_data():
    """The card function itself, run in node against the real codes.json:
    per-node method citations render with their coverage, the primary is
    the largest NAMED group even when an unnamed group is larger, and a
    single-method card carries no coverage-label noise."""
    import shutil
    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("node not available")
    out = subprocess.run(
        [node, "-e", NODE_HARNESS, str(DOCS / "codes/index.html"),
         str(DOCS / "data/codes.json")],
        capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
