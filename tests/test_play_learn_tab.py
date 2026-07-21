"""The playground opens on the paper parser, with the site's own navigation.

The Learn tab is the playground's main item and default: first in the tab
row, active on landing, carrying the full parser experience (the one
implementation; the old /learn/ URL redirects here). The top bar carries the
same navigation as every other page, so moving between Map, Guide, Play,
Learn, Document, and Source is one consistent gesture site-wide.
"""
from __future__ import annotations

import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[1] / "docs"
_PLAY = (_DOCS / "play" / "index.html").read_text()
_LEARN = (_DOCS / "learn" / "index.html").read_text()


def test_learn_is_the_first_and_default_tab():
    tabs = re.findall(r'<button class="pg-tab([^"]*)" data-tab="([a-z]+)"', _PLAY)
    assert tabs, "no playground tabs found"
    first_classes, first_tab = tabs[0]
    assert first_tab == "learn", f"the first tab is {first_tab}, not learn"
    assert "on" in first_classes, "the learn tab is not active on landing"
    on_tabs = [t for c, t in tabs if "on" in c]
    assert on_tabs == ["learn"], f"exactly one default tab expected, got {on_tabs}"
    panels = re.findall(r'<div class="pg-panel([^"]*)" data-panel="([a-z]+)"', _PLAY)
    on_panels = [t for c, t in panels if "on" in c]
    assert on_panels == ["learn"], f"exactly the learn panel open on landing, got {on_panels}"


def test_learn_tab_carries_the_full_parser_experience():
    for marker in ("dropzone", "progressList", "resultReview",
                   "openmaterials-learn", "LearnLib.validateExtraction",
                   "../learn/lib.js", "verbatim"):
        assert marker in _PLAY, f"learn tab lacks {marker}"


def test_playground_navigation_matches_the_site():
    nav = re.search(r'<nav class="pg-nav"[^>]*>(.*?)</nav>', _PLAY, re.S)
    assert nav, "no site navigation on the playground top bar"
    labels = re.findall(r">([A-Za-z]+)</a>", nav.group(1))
    assert labels == ["Map", "Guide", "Play", "Learn", "Document", "Source"], labels
    assert 'class="active" href="./"' in nav.group(1), "Play must be marked active"


def test_old_learn_url_redirects_to_the_playground():
    assert "../play/#tab=learn" in _LEARN, "learn/ must redirect to the play Learn tab"
    assert "location.replace" in _LEARN and "http-equiv=\"refresh\"" in _LEARN
    assert "dropzone" not in _LEARN, "the parser must have ONE implementation (the play tab)"


def test_thin_record_offers_the_completion_path():
    """A record arriving with no mapped quantity, no values, and no conditions
    (the thin MCG handoff) must not dead-end: the datasheet says what is
    missing and offers the parser one click away, with a direct source-PDF
    link when the lineage carries an arxiv: or doi: source."""
    assert "rec-complete" in _PLAY, "no thin-record recovery panel"
    assert "Complete it from the paper" in _PLAY, "no completion affordance"
    assert "selectPlaygroundTab('learn')" in _PLAY.replace('"', "'"), \
        "the completion button must land on the Learn tab"
    assert "arxiv.org/pdf" in _PLAY and "doi.org" in _PLAY, \
        "arxiv:/doi: sources must yield a direct PDF link"
    assert "'other of'" not in _PLAY
    assert "String(template) === 'other'" in _PLAY, \
        "the catch-all template must not masquerade as a quantity in the title"
