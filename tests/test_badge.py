"""The version badge: one SVG, two implementations, zero drift.

omai/badge.py writes docs/badge.svg for the current map version at
map_data time; the site Worker's badge.js renders /badge/<hash>.svg for
any pinned version. The two must emit byte-identical SVG for the same
hash, the committed docs/badge.svg must match the committed version
stamp, and the Worker route must accept exactly the hash shapes the
badge contract names.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from omai.badge import LABEL, badge_svg

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"
_BADGE_JS = _ROOT / "infra" / "site" / "src" / "badge.js"

# hashes chosen to cross the formatting edge cases: the real current
# version, an all-c hash whose text width lands on an integer (72.0),
# repeated narrow digits, and a mixed a-f/digit hash
PARITY_HASHES = [
    "f69b18c18fb7",
    "cccccccccccc",
    "111111111111",
    "abcdef012345",
    "a00000000000",  # right width 94.5: a .5 tie, where banker's rounding
                     # and JS Math.round disagree unless rounding is shared
]


def test_badge_svg_shape():
    svg = badge_svg("f69b18c18fb7")
    assert svg.startswith("<svg ") and svg.endswith("</svg>")
    assert 'height="20"' in svg
    assert LABEL + ": f69b18c18fb7" in svg
    assert "f69b18c18fb7</text>" in svg
    assert "#4f46e5" in svg, "the version segment wears the brand indigo"
    assert "textLength=" in svg, "text must be width-pinned for stability"


def test_badge_truncates_to_the_canonical_short_form():
    svg = badge_svg("f" * 64)
    assert "f" * 12 + "</text>" in svg
    assert "f" * 13 not in svg


def test_committed_badge_matches_the_committed_version():
    version = json.loads((_DOCS / "data" / "version.json").read_text())["version"]
    committed = (_DOCS / "badge.svg").read_text()
    assert committed == badge_svg(version) + "\n", (
        "docs/badge.svg is stale: regenerate with "
        "PYTHONPATH=. python -c 'from omai.badge import write_badge; write_badge()' "
        "and commit the result"
    )


def test_static_pin_exists_for_the_committed_version():
    """The pinned badge the README embeds must exist as real bytes:
    before the DNS cutover, GitHub Pages serves the site and cannot run
    the Worker's /badge/<hash>.svg route. Exactly one pin, the current
    version's, byte-equal to the generator."""
    version = json.loads((_DOCS / "data" / "version.json").read_text())["version"]
    pin = _DOCS / "badge" / (version[:12] + ".svg")
    assert pin.exists(), (
        f"missing static pin {pin.name}: regenerate with PYTHONPATH=. python "
        "-c 'from omai.badge import write_badge; write_badge()' and commit"
    )
    assert pin.read_text() == badge_svg(version) + "\n"
    pins = sorted(p.name for p in (_DOCS / "badge").glob("*.svg"))
    assert pins == [version[:12] + ".svg"], (
        f"stale pins alongside the current one: {pins}"
    )


def test_python_and_worker_emit_identical_bytes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    for h in PARITY_HASHES:
        js = subprocess.run(
            [node, "--input-type=module", "-e",
             "import {badgeSVG} from '" + _BADGE_JS.resolve().as_uri() + "';"
             "process.stdout.write(badgeSVG('" + h + "'));"],
            capture_output=True, text=True, timeout=60)
        assert js.returncode == 0, js.stderr
        assert js.stdout == badge_svg(h), f"parity broken for {h}"


def test_readme_badge_is_pinned_to_the_current_version():
    """The repository's own README carries the pinned badge, and the pin
    must equal the committed version stamp. map_data refreshes it; this
    test is the reminder that cannot be forgotten."""
    import re
    readme = (_ROOT / "README.md").read_text()
    m = re.search(r"https://openmaterials\.ai/badge/([0-9a-f]{8,64})\.svg", readme)
    assert m, "README.md carries no pinned badge"
    version = json.loads((_DOCS / "data" / "version.json").read_text())["version"]
    assert m.group(1) == version[:12], (
        f"README badge pins {m.group(1)} but the committed map version is "
        f"{version[:12]}: regenerate with PYTHONPATH=. python -c "
        "'from omai.badge import pin_readme_badge; pin_readme_badge()' "
        "and commit the result"
    )
    assert "openmaterials.ai/badge.svg" not in readme, (
        "README must carry only the pinned form; the live badge would show "
        "today's version on historical commits"
    )


def test_worker_route_accepts_only_hex_svg_paths():
    src = _BADGE_JS.read_text()
    assert "BADGE_PATH_RE" in src
    assert "/^\\/badge\\/([0-9a-f]{8,64})\\.svg$/" in src, (
        "the badge route accepts 8 to 64 lowercase hex chars, .svg, nothing else"
    )
