"""The codes bibliography page.

One entry per cited code, rendered client-side from the same codes.json
the map reads; Lean opens the page because it checks reasoning where the
other codes compute numbers; the license posture is stated plainly. The
page must never hardcode the roster (the data file is the single source)
and never invent references (the physlib citation carries no DOI because
none exists).
"""

import re
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
