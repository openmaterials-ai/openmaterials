"""The beta label: one chip, every header, honestly worded.

The product is early and says so in one consistent place: a small chip beside
the brand in the shared injected header and in every page-local header, with a
tooltip stating what beta means here (the schema grows; committed identifiers
stay resolvable). One gesture, not scattered disclaimers.
"""
from __future__ import annotations

from pathlib import Path

_DOCS = Path(__file__).resolve().parents[1] / "docs"

_HEADER_FILES = [
    _DOCS / "assets" / "site.js",
    _DOCS / "map" / "index.html",
    _DOCS / "map-3d" / "index.html",
    _DOCS / "map-trace" / "index.html",
    _DOCS / "play" / "index.html",
    _DOCS / "agreement" / "index.html",
    _DOCS / "experiment" / "index.html",
    _DOCS / "lineage" / "index.html",
]


def test_every_header_carries_the_beta_chip():
    for f in _HEADER_FILES:
        text = f.read_text()
        assert 'om-beta' in text, f"{f.relative_to(_DOCS)} lacks the beta chip"
        assert 'content-addressed' in text or f.name == "site.js" and "content-addressed" in text, \
            f"{f.relative_to(_DOCS)}: the chip must explain itself (tooltip)"


def test_the_chip_is_styled_once_per_surface():
    css = (_DOCS / "assets" / "site.css").read_text()
    assert ".om-beta{" in css, "the shared stylesheet must style the chip"
