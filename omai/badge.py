"""The openmaterials version badge: a shields-style SVG naming the map version.

Left segment: the mark and the word "openmaterials" on neutral dark. Right
segment: a map version hash (12 hex characters, the canonical short form) on
the brand indigo. A repository that uses the map embeds the badge to state
which version its results were computed against, the same way a CI badge
states a build:

    [![openmaterials](https://openmaterials.ai/badge/<version12>.svg)](https://openmaterials.ai/)

Two implementations exist and MUST stay byte-identical: this module (writes
docs/badge.svg for the CURRENT version at map_data time) and the site
Worker's badge.js (renders /badge/<hash>.svg for any pinned version).
tests/test_badge.py pins the parity byte for byte, so neither can drift.

The text is width-pinned with the SVG textLength attribute, so the rendered
badge is pixel-stable regardless of the viewer's fonts; the per-character
width table below only has to MATCH badge.js, not match Verdana exactly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# Approximate Verdana-11 advance widths, px. Shared verbatim with badge.js:
# parity matters, typographic exactness does not (textLength pins rendering).
_WIDTHS = {
    "o": 6.9, "p": 6.9, "e": 6.6, "n": 6.9, "m": 10.6, "a": 6.6, "t": 4.6,
    "r": 4.8, "i": 3.2, "l": 3.2, "s": 5.9,
    "0": 6.9, "1": 6.9, "2": 6.9, "3": 6.9, "4": 6.9, "5": 6.9, "6": 6.9,
    "7": 6.9, "8": 6.9, "9": 6.9, "b": 6.9, "c": 6.0, "d": 6.9, "f": 3.7,
}
_FALLBACK = 7.0

LABEL = "openmaterials"
LEFT_BG = "#555"
RIGHT_BG = "#4f46e5"

# the mark, inlined from docs/assets/favicon.svg (16-grid), scaled to 14px
_MARK = (
    '<g transform="translate(5,3) scale(0.875)">'
    '<rect width="16" height="16" rx="4" fill="#4f46e5"/>'
    '<path d="M4 4.5 L8 7.5 L4 10.5" stroke="#ffffff" stroke-width="1.6" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="11" cy="8" r="2.6" fill="#ffffff"/>'
    '<circle cx="11" cy="8" r="1.1" fill="#4f46e5"/>'
    "</g>"
)


def _round_half_up(x: float) -> int:
    """JavaScript's Math.round for the positive values used here: ties go
    UP. Python's round() is banker's rounding (ties to even), which would
    break byte parity on any .5 width (e.g. the hash a00000000000)."""
    return math.floor(x + 0.5)


def _tenths(x: float) -> float:
    return _round_half_up(x * 10) / 10


def _num(x: float) -> str:
    """Format a tenth-precision number the way JavaScript does: integers
    bare (79 not 79.0), everything else with its single decimal."""
    r = _tenths(x)
    return str(int(r)) if float(r).is_integer() else str(r)


def _text_width(s: str) -> float:
    return _tenths(sum(_WIDTHS.get(c, _FALLBACK) for c in s))


def badge_svg(version: str) -> str:
    """The badge SVG for one map version hash (shown at the canonical 12)."""
    v = str(version)[:12]
    lw = _text_width(LABEL)
    rw = _text_width(v)
    # mark at x=5 (14 wide), 4px gap, label, 6px right pad
    left = _round_half_up(5 + 14 + 4 + lw + 6)
    right = _round_half_up(6 + rw + 6)
    total = left + right
    lx = _tenths(23 + lw / 2)
    rx = _tenths(left + right / 2)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="' + str(total) +
        '" height="20" role="img" aria-label="' + LABEL + ": " + v + '">' +
        "<title>" + LABEL + " map version " + v + "</title>" +
        '<linearGradient id="s" x2="0" y2="100%">' +
        '<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>' +
        '<stop offset="1" stop-opacity=".1"/></linearGradient>' +
        '<clipPath id="r"><rect width="' + str(total) +
        '" height="20" rx="3" fill="#fff"/></clipPath>' +
        '<g clip-path="url(#r)">' +
        '<rect width="' + str(left) + '" height="20" fill="' + LEFT_BG + '"/>' +
        '<rect x="' + str(left) + '" width="' + str(right) +
        '" height="20" fill="' + RIGHT_BG + '"/>' +
        '<rect width="' + str(total) + '" height="20" fill="url(#s)"/></g>' +
        _MARK +
        '<g fill="#fff" text-anchor="middle" ' +
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">' +
        '<text x="' + _num(lx) + '" y="15" fill="#010101" fill-opacity=".3" ' +
        'textLength="' + _num(lw) + '">' + LABEL + "</text>" +
        '<text x="' + _num(lx) + '" y="14" textLength="' + _num(lw) + '">' +
        LABEL + "</text>" +
        '<text x="' + _num(rx) + '" y="15" fill="#010101" fill-opacity=".3" ' +
        'textLength="' + _num(rw) + '">' + v + "</text>" +
        '<text x="' + _num(rx) + '" y="14" textLength="' + _num(rw) + '">' +
        v + "</text></g></svg>"
    )


def write_badge(path: Path | None = None) -> Path:
    """Write docs/badge.svg for the current map version, read from the
    version stamp write_version() has already written (single source).

    Also emits the PINNED form as a static file, docs/badge/<version12>.svg,
    and prunes pins of other versions: before the DNS cutover the site is
    served by GitHub Pages, which cannot run the Worker's /badge/<hash>.svg
    route, so the pin the README carries must exist as real bytes. The
    Worker serves the same bytes for the current version and generates any
    other hash on demand; the static set is always exactly one file."""
    docs = Path(__file__).resolve().parents[1] / "docs"
    version = json.loads((docs / "data" / "version.json").read_text())["version"]
    out = path or docs / "badge.svg"
    out.write_text(badge_svg(version) + "\n", encoding="utf-8")
    pin_dir = docs / "badge"
    pin_dir.mkdir(exist_ok=True)
    pin = pin_dir / (version[:12] + ".svg")
    pin.write_text(badge_svg(version) + "\n", encoding="utf-8")
    for stale in pin_dir.glob("*.svg"):
        if stale.name != pin.name:
            stale.unlink()
    return out


import re as _re

_README_BADGE_RE = _re.compile(
    r"https://openmaterials\.ai/badge/[0-9a-f]{8,64}\.svg"
)


def pin_readme_badge(readme: Path | None = None) -> Path:
    """Pin the README badge to the current map version.

    The repository's own README carries the PINNED badge form, not the
    live /badge.svg: an old commit's README then shows the version that
    commit actually had. map_data calls this after write_version, so the
    pin updates in the same commit that moves the version, and
    tests/test_badge.py fails whenever README and version.json disagree,
    so a stale pin cannot land."""
    root = Path(__file__).resolve().parents[1]
    version = json.loads(
        (root / "docs" / "data" / "version.json").read_text())["version"][:12]
    path = readme or root / "README.md"
    text = path.read_text()
    pinned = "https://openmaterials.ai/badge/" + version + ".svg"
    new_text, n = _README_BADGE_RE.subn(pinned, text)
    if n == 0:
        raise RuntimeError(
            "README.md carries no pinned badge URL to update "
            "(expected https://openmaterials.ai/badge/<hash>.svg)")
    if new_text != text:
        path.write_text(new_text)
    return path
