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
    assert labels == ["Map", "Guide", "Play", "Learn", "Codes", "Document", "Source"], labels
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
    # The button must actually LEAVE the datasheet: body.lin-open hides the
    # tab strip, and only the hash router removes that class, so the handler
    # must navigate by hash exactly like the back link does.
    assert "location.hash = '#/play?tab=learn'" in _PLAY, \
        "the completion button must navigate by hash so lin-open is cleared"
    assert "document.body.classList.remove('lin-open')" in _PLAY
    assert "arxiv.org/pdf" in _PLAY and "doi.org" in _PLAY, \
        "arxiv:/doi: sources must yield a direct PDF link"
    assert "'other of'" not in _PLAY


def test_thin_record_detector_is_narrow():
    """The recovery panel is for the nodeless catch-all shape only. A record
    with an explicit node that merely is not on this map version, or one that
    carries values, conditions, or params, keeps the normal datasheet."""
    detector = (
        "if (!node && (!template || String(template) === 'other') &&\n"
        "      !thinValues && !thinConds && !thinParams) {"
    )
    assert detector in _PLAY, "detector must require nodeless catch-all + empty data"
    assert "!known && !thinValues" not in _PLAY, \
        "an unresolved explicit node must not trigger the panel"


def test_catch_all_template_never_masquerades_as_a_quantity():
    """One shared rule (displayProp) drops the property for the nodeless
    catch-all template everywhere a display name is composed: the datasheet
    lede, bundle member rows, and the document title."""
    assert "function displayProp(node, template)" in _PLAY
    assert _PLAY.count("displayProp(") >= 4, \
        "lede, member rows, and title must all use displayProp"
    assert "String(template) === 'other'" in _PLAY
