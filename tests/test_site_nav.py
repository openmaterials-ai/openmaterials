"""One navigation, everywhere.

The site had three nav generations at once: the canonical bar, a stale
bar (Tracer / Experiments / Playground) on the evidence pages, and no
bar at all. This contract pins a single canonical link set across every
primary page, whether the header is injected by site.js or inlined by
an app page that needs its own toolbar.
"""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

CANONICAL = ["Map", "Guide", "Play", "Learn", "Codes", "Document", "Source"]

# Pages whose header is injected by site.js (mount point + script include).
INJECTED = [
    "index.html",
    "guide/index.html",
    "document/index.html",
    "lean/index.html",
    "lineage/index.html",
    "experiment/index.html",
    "agreement/index.html",
    "codes/index.html",
]

# App pages that inline the header because they carry their own controls.
INLINE = [
    "map/index.html",
    "map-3d/index.html",
    "map-trace/index.html",
    "play/index.html",
]

# Standalone artifacts, deliberately outside the primary navigation.
EXEMPT_DIRS = {"deck", "slides", "map-lab", "learn", "i"}


def _nav_labels(page_text):
    """Anchor labels of the page's primary nav block, in order."""
    m = re.search(r'<nav[^>]*(?:class="(?:nav|pg-nav)"|aria-label="Primary")[^>]*>(.*?)</nav>',
                  page_text, re.S)
    assert m, "no primary nav block found"
    return re.findall(r"<a[^>]*>([^<]+)</a>", m.group(1))


def test_sitejs_nav_is_canonical():
    s = (DOCS / "assets/site.js").read_text()
    labels = re.findall(r"\['(\w+)', ", s)
    assert labels == CANONICAL, labels


def test_injected_pages_mount_the_shared_header():
    for rel in INJECTED:
        s = (DOCS / rel).read_text()
        assert "data-site-header" in s, rel + " lacks the header mount"
        assert "assets/site.js" in s, rel + " lacks the site.js include"
        assert '<header class="top">' not in s, rel + " still inlines a header"


def test_inline_navs_match_the_canonical_links():
    for rel in INLINE:
        s = (DOCS / rel).read_text()
        assert _nav_labels(s) == CANONICAL, rel


def test_inline_navs_point_document_at_the_document_page():
    for rel in INLINE:
        nav = re.search(r"<nav[^>]*>(.*?)</nav>", (DOCS / rel).read_text(), re.S).group(1)
        assert "openmaterials.pdf" not in nav, rel + " nav still links the raw PDF"


def test_no_page_is_headerless():
    for page in sorted(DOCS.glob("*/index.html")):
        rel = page.relative_to(DOCS)
        if rel.parts[0] in EXEMPT_DIRS:
            continue
        s = page.read_text()
        assert "data-site-header" in s or 'aria-label="Primary"' in s, str(rel)


def test_stale_nav_generation_is_gone():
    for page in DOCS.glob("**/index.html"):
        s = page.read_text()
        assert ">Tracer</a>" not in s, str(page)
        assert ">Experiments</a>" not in s, str(page)
        assert ">Playground</a>" not in s, str(page)


def test_footer_links_codes_and_lean():
    s = (DOCS / "assets/site.js").read_text()
    assert "The codes bibliography" in s
    assert "The verified layer" in s


def test_map_supports_the_code_hash_filter():
    s = (DOCS / "map/index.html").read_text()
    assert "codeFromHash" in s
    assert re.search(r"codeRef && codesData\[codeRef\]", s)
