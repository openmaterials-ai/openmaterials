"""The generated document page: docs/document/index.html.

Covers the four contract points of the HTML edition of the document:
(a) the build is byte-deterministic, (b) the committed page matches a fresh
build, (c) every numbered section and subsection title of the LaTeX source
appears exactly once as a heading in the HTML, and (d) the PDF download
link and the homepage button wiring exist.
"""

import html
import re

import pytest

from omai import doc_html

PANDOC = doc_html.find_pandoc()
needs_pandoc = pytest.mark.skipif(
    PANDOC is None, reason="pandoc is not installed on this machine")


def _fresh_build() -> str:
    tex = doc_html.TEX_PATH.read_text(encoding="utf-8")
    page, _notes = doc_html.build_page(tex, PANDOC)
    return page


@needs_pandoc
def test_build_is_byte_deterministic():
    assert _fresh_build() == _fresh_build()


@needs_pandoc
def test_committed_page_matches_fresh_build():
    committed = doc_html.OUT_PATH.read_text(encoding="utf-8")
    assert committed == _fresh_build(), (
        "docs/document/index.html is stale: rerun "
        "PYTHONPATH=. python -m omai.doc_html and commit the result")


def _heading_texts(page: str) -> list:
    """Plain heading texts, with injected number spans and markup removed."""
    out = []
    for _lvl, attrs, inner in re.findall(
            r"<h([1-6])([^>]*)>(.*?)</h\1>", page, re.S):
        inner = re.sub(
            r'<span class="(?:partno|secno)">.*?</span>', "", inner)
        text = html.unescape(re.sub(r"<[^>]+>", "", inner))
        out.append(re.sub(r"\s+", " ", text).strip())
    return out


def test_every_section_title_appears_exactly_once_as_heading():
    tex = doc_html.TEX_PATH.read_text(encoding="utf-8")
    page = doc_html.OUT_PATH.read_text(encoding="utf-8")
    headings = _heading_texts(page)
    sections = doc_html.command_titles(tex, "section")
    subsections = doc_html.command_titles(tex, "subsection")
    assert len(sections) > 30 and len(subsections) > 30
    # Each distinct title must appear as an HTML heading exactly as many
    # times as the LaTeX source declares it (the source titles two distinct
    # sections "The index", so the expected count is per title, not 1).
    expected_counts = {}
    for title in sections + subsections:
        text = doc_html.title_to_text(title)
        expected_counts[text] = expected_counts.get(text, 0) + 1
    for text, expected in expected_counts.items():
        n = headings.count(text)
        assert n == expected, (
            "section title %r appears %d times as an HTML heading, "
            "expected %d" % (text, n, expected))


def test_pdf_download_link_and_homepage_button():
    page = doc_html.OUT_PATH.read_text(encoding="utf-8")
    assert 'href="../openmaterials.pdf"' in page
    assert "Download the PDF" in page

    home = (doc_html.ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<a class="om-btn" href="([^"]+)">Read the document</a>',
                  home)
    assert m, "homepage is missing the Read the document button"
    assert m.group(1) == "document/", (
        "the homepage button must link to the document page, got %r"
        % m.group(1))
