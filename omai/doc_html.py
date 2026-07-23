"""Build docs/document/index.html from docs/openmaterials.tex.

The document page is generated, never hand edited: this module preprocesses
the LaTeX source (lifting the abstract into the body and replacing the two
TikZ diagrams with clearly marked fallback blocks that keep their captions),
shells out to pandoc for the LaTeX-to-HTML conversion, then post-processes
the fragment (heading levels, section numbering matching the PDF, cross
reference texts, table scroll wrappers) and wraps it in the site chrome with
a sidebar table of contents. Math is emitted as raw TeX in pandoc's
``span.math`` elements and rendered client side by the vendored KaTeX.

Run as::

    PYTHONPATH=. python -m omai.doc_html

The build is deterministic: the output depends only on the LaTeX source and
this module, so running it twice changes zero bytes.
"""

from __future__ import annotations

import html as _html
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX_PATH = ROOT / "docs" / "openmaterials.tex"
OUT_PATH = ROOT / "docs" / "document" / "index.html"

PANDOC_CANDIDATES = ("/usr/local/bin/pandoc", "/opt/homebrew/bin/pandoc")

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def find_pandoc() -> str | None:
    """Locate the pandoc binary, preferring the known system install."""
    for cand in PANDOC_CANDIDATES:
        if Path(cand).is_file():
            return cand
    return shutil.which("pandoc")


# ---------------------------------------------------------------------------
# LaTeX helpers
# ---------------------------------------------------------------------------

def balanced_arg(text: str, start: int) -> tuple[str, int]:
    """Return the balanced-brace argument starting at ``text[start] == '{'``.

    Returns (content, index_after_closing_brace).
    """
    assert text[start] == "{"
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("unbalanced braces in LaTeX source")


def command_titles(tex: str, command: str) -> list[str]:
    """All balanced-brace titles of ``\\command{...}`` (unstarred form)."""
    out = []
    for m in re.finditer(r"\\%s\{" % command, tex):
        title, _ = balanced_arg(tex, m.end() - 1)
        out.append(title)
    return out


def title_to_text(title: str) -> str:
    """Normalize a LaTeX heading title to the plain text pandoc emits."""
    t = re.sub(r"\\texttt\{([^{}]*)\}", r"\1", title)
    t = re.sub(r"\\emph\{([^{}]*)\}", r"\1", t)
    t = t.replace(r"\_", "_").replace(r"\&", "&").replace("~", " ")
    t = t.replace("''", "”").replace("``", "“")
    t = t.replace("'", "’").replace("`", "‘")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Stage 1: preprocess the LaTeX source
# ---------------------------------------------------------------------------

def preprocess_tex(tex: str) -> tuple[str, list[str]]:
    """Prepare the LaTeX source for pandoc.

    Returns the rewritten source and a list of degradation notes (constructs
    that could not be converted and were replaced by marked fallbacks).
    """
    notes: list[str] = []

    # The abstract is metadata to pandoc's fragment writer and would be
    # dropped; lift it into the body between markers the post-processor
    # turns into a styled block.
    def lift_abstract(m: re.Match) -> str:
        body = m.group(1).strip()
        body = re.sub(r"^\\noindent\s*", "", body)
        return "OMAIDOCABSSTART\n\n%s\n\nOMAIDOCABSEND" % body

    tex, n_abs = re.subn(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        lift_abstract, tex, flags=re.S)
    if n_abs == 0:
        notes.append("no abstract environment found in the LaTeX source")

    # TikZ diagrams cannot be converted by pandoc. Replace each figure that
    # contains one with a marked fallback paragraph that keeps the caption;
    # the post-processor styles it and points at the PDF.
    fig_count = [0]

    def replace_figure(m: re.Match) -> str:
        body = m.group(1)
        if "tikzpicture" not in body:
            return m.group(0)
        fig_count[0] += 1
        n = fig_count[0]
        cap = ""
        cm = re.search(r"\\caption\{", body)
        if cm:
            cap, _ = balanced_arg(body, cm.end() - 1)
        notes.append(
            "figure %d: TikZ diagram replaced by a marked fallback block "
            "(caption kept, diagram only in the PDF)" % n)
        return ("OMAIDOCFIGSTART%d\n\n%s\n\nOMAIDOCFIGEND%d"
                % (n, cap.strip(), n))

    tex = re.sub(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}",
                 replace_figure, tex, flags=re.S)

    # Any tikzpicture outside a figure would still break pandoc; drop it the
    # same way (none exist today, this is a guard).
    def replace_bare_tikz(m: re.Match) -> str:
        fig_count[0] += 1
        notes.append("bare TikZ picture %d replaced by a marked fallback "
                     "block" % fig_count[0])
        return ("OMAIDOCFIGSTART%d\n\nDiagram.\n\nOMAIDOCFIGEND%d"
                % (fig_count[0], fig_count[0]))

    tex = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
                 replace_bare_tikz, tex, flags=re.S)

    # \today would make the build nondeterministic (the date is not in the
    # fragment output today, but keep the guard explicit).
    tex = tex.replace(r"\date{\today}", r"\date{}")
    return tex, notes


# ---------------------------------------------------------------------------
# Stage 2: pandoc
# ---------------------------------------------------------------------------

def run_pandoc(tex: str, pandoc: str) -> str:
    """Convert LaTeX to an HTML body fragment with math left as TeX."""
    proc = subprocess.run(
        [pandoc, "-f", "latex", "-t", "html", "--katex"],
        input=tex.encode("utf-8"), capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError("pandoc failed: %s"
                           % proc.stderr.decode("utf-8", "replace")[:2000])
    return proc.stdout.decode("utf-8")


# ---------------------------------------------------------------------------
# Stage 3: post-process the fragment
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"<h([1-6])([^>]*)>(.*?)</h\1>", re.S)


def remap_heading_levels(body: str) -> str:
    """Shift pandoc's part/section levels to a natural h1..h5 ladder.

    pandoc 2.9 emits \\part as h1, \\section as h3, \\subsection as h4,
    \\subsubsection as h5 and \\paragraph as h6; close the gap.
    """
    for old, new in (("h3", "h2"), ("h4", "h3"), ("h5", "h4"), ("h6", "h5")):
        body = re.sub(r"<%s(\s[^>]*)?>" % old,
                      lambda m, new=new: "<%s%s>" % (new, m.group(1) or ""),
                      body)
        body = body.replace("</%s>" % old, "</%s>" % new)
    return body


def dedupe_class_attr(body: str) -> str:
    """pandoc 2.9 duplicates class="unnumbered" on starred headings."""
    return re.sub(
        r'(<h[1-6][^>]*class="unnumbered"[^>]*) class="unnumbered"',
        r"\1", body)


class Heading:
    def __init__(self, level: int, attrs: str, inner: str, span: tuple):
        self.level = level
        self.attrs = attrs
        self.inner = inner
        self.span = span
        m = re.search(r'id="([^"]*)"', attrs)
        self.id = m.group(1) if m else ""
        self.unnumbered = "unnumbered" in attrs
        self.number = ""
        self.refnum = ""


def collect_headings(body: str) -> list[Heading]:
    return [Heading(int(m.group(1)), m.group(2), m.group(3), m.span())
            for m in HEADING_RE.finditer(body)]


def assign_numbers(headings: list[Heading]) -> None:
    """Number parts/sections/subsections the way the compiled PDF does:
    roman parts, sections numbered continuously across parts, lettered
    appendix sections, dotted subsections."""
    part_i = 0
    sec_i = 0
    app_i = -1  # -1: not yet in the appendices
    sub_i = 0
    cur_sec = ""
    for h in headings:
        if h.level == 1:
            if h.id == "appendices" or h.inner.strip() == "Appendices":
                app_i = 0
            elif not h.unnumbered:
                part_i += 1
                h.number = ROMAN[part_i - 1] if part_i <= len(ROMAN) else ""
        elif h.level == 2 and not h.unnumbered:
            if app_i >= 0:
                h.number = LETTERS[app_i]
                app_i += 1
            else:
                sec_i += 1
                h.number = str(sec_i)
            cur_sec = h.number
            sub_i = 0
        elif h.level == 3 and not h.unnumbered and cur_sec:
            sub_i += 1
            h.number = "%s.%s" % (cur_sec, sub_i)


def inject_numbers(body: str, headings: list[Heading]) -> str:
    """Prepend the computed number to each numbered heading, in place."""
    out = []
    last = 0
    for h in headings:
        start, end = h.span
        out.append(body[last:start])
        if h.level == 1 and h.number:
            label = '<span class="partno">Part %s</span>' % h.number
        elif h.number:
            label = '<span class="secno">%s</span> ' % h.number
        else:
            label = ""
        out.append("<h%d%s>%s%s</h%d>"
                   % (h.level, h.attrs, label, h.inner, h.level))
        last = end
    out.append(body[last:])
    return "".join(out)


def rewrite_refs(body: str, headings: list[Heading]) -> str:
    """Give \\ref links the same numbers the headings display.

    pandoc numbers sections with its own counters (and leaves part refs
    empty); replace each resolvable reference text with the computed
    number so 'Part IV' and 'Appendix A' read correctly. A label on an
    unnumbered heading (the source labels one \\paragraph) resolves to
    the nearest preceding numbered heading, which is what LaTeX's \\ref
    prints for it.
    """
    last = ""
    for h in headings:
        if h.number:
            last = h.number
        h.refnum = h.number or last
    numbers = {h.id: h.refnum for h in headings if h.id and h.refnum}
    return re.sub(
        r'(<a href="#([^"]+)"[^>]*data-reference-type="ref"[^>]*>)([^<]*)</a>',
        lambda m: (m.group(1) + numbers[m.group(2)] + "</a>")
        if m.group(2) in numbers else m.group(0),
        body)


def wrap_markers(body: str) -> str:
    """Turn the preprocess markers into styled blocks."""
    body = body.replace(
        "<p>OMAIDOCABSSTART</p>",
        '<div class="abstract"><span class="abstract-label">Abstract</span>')
    body = body.replace("<p>OMAIDOCABSEND</p>", "</div>")
    body = re.sub(
        r"<p>OMAIDOCFIGSTART(\d+)</p>",
        r'<div class="fig-fallback">'
        r'<span class="fig-fallback-label">Figure \1: diagram not converted '
        r'to HTML.</span> <span class="fig-fallback-note">This diagram is '
        r'drawn with TikZ and renders only in '
        r'<a href="../openmaterials.pdf">the PDF</a>. Its caption:</span>',
        body)
    body = re.sub(r"<p>OMAIDOCFIGEND(\d+)</p>", "</div>", body)
    return body


def wrap_tables(body: str) -> str:
    """Wrap every table in a horizontal-scroll container."""
    body = body.replace("<table>", '<div class="tblwrap"><table>')
    body = body.replace("</table>", "</table></div>")
    return body


def build_toc(headings: list[Heading]) -> str:
    """Nested TOC list: parts as groups, sections, subsections."""

    def text_of(h: Heading) -> str:
        return re.sub(r"<[^>]+>", "", h.inner).strip()

    items = []
    stack_open = {2: False, 3: False}

    def close_sub():
        if stack_open[3]:
            items.append("</ol>")
            stack_open[3] = False

    def close_sec():
        close_sub()
        if stack_open[2]:
            items.append("</ol>")
            stack_open[2] = False

    for h in headings:
        if h.level > 3 or not h.id:
            continue
        anchor = _html.escape(h.id, quote=True)
        text = text_of(h)
        if h.level == 1:
            close_sec()
            label = ("Part %s" % h.number) if h.number else ""
            items.append(
                '<li class="toc-part"><a href="#%s">'
                '%s<span class="toc-part-title">%s</span></a>'
                % (anchor,
                   ('<span class="toc-partno">%s</span>' % label)
                   if label else "", _html.escape(text)))
            items.append('<ol class="toc-secs">')
            stack_open[2] = True
        elif h.level == 2:
            close_sub()
            if not stack_open[2]:
                items.append('<ol class="toc-secs">')
                stack_open[2] = True
            num = ('<span class="toc-no">%s</span>' % h.number) \
                if h.number else ""
            items.append('<li><a href="#%s">%s%s</a>'
                         % (anchor, num, _html.escape(text)))
            items.append('<ol class="toc-subs">')
            stack_open[3] = True
        elif h.level == 3:
            if not stack_open[3]:
                continue
            num = ('<span class="toc-no">%s</span>' % h.number) \
                if h.number else ""
            items.append('<li><a href="#%s">%s%s</a></li>'
                         % (anchor, num, _html.escape(text)))
    close_sec()
    return '<ol class="toc-parts">%s</ol>' % "".join(items)


# ---------------------------------------------------------------------------
# Stage 4: the page template
# ---------------------------------------------------------------------------

PAGE_CSS = """
  .doc-hero{max-width:1240px;margin:0 auto;padding:44px clamp(16px,3vw,26px) 8px;}
  .doc-hero .om-overline{margin-bottom:12px;}
  .doc-hero h1{font-size:clamp(1.9rem,4vw,2.6rem);margin:0 0 6px;}
  .doc-mark{width:46px;height:46px;border-radius:10px;display:block;margin:2px 0 14px;}
  .doc-tagline{font-family:var(--font-serif);font-size:1.15rem;color:var(--ink-2);margin:0 0 10px;}
  .doc-byline{color:var(--muted);font-size:.92rem;margin:0 0 20px;}
  .doc-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:0 0 10px;}
  .doc-actions .hint{color:var(--faint);font-size:.8rem;}

  .doc-layout{max-width:1240px;margin:0 auto;display:grid;
    grid-template-columns:280px minmax(0,1fr);gap:44px;align-items:start;
    padding:12px clamp(16px,3vw,26px) 90px;}
  .doc-toc{position:sticky;top:72px;max-height:calc(100vh - 96px);
    overflow-y:auto;border:1px solid var(--line);border-radius:12px;
    background:var(--surface);padding:14px 16px 18px;font-size:.84rem;}
  .doc-toc summary{cursor:pointer;font-family:var(--font-serif);font-weight:700;
    font-size:.95rem;color:var(--ink);list-style:none;}
  .doc-toc summary::-webkit-details-marker{display:none;}
  .doc-toc summary::after{content:"contents";margin-left:8px;font-family:var(--font-sans);
    font-weight:500;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);}
  .doc-toc ol{list-style:none;margin:0;padding:0;}
  .toc-parts{margin-top:10px;}
  .toc-parts > li.toc-part{margin:12px 0 4px;}
  .toc-part > a{display:block;color:var(--ink);text-decoration:none;font-weight:600;padding:3px 0;}
  .toc-partno{display:block;font-size:.66rem;font-weight:600;letter-spacing:.12em;
    text-transform:uppercase;color:var(--accent);}
  .toc-part-title{font-family:var(--font-serif);font-size:.95rem;}
  .toc-secs{margin:2px 0 0;}
  .toc-secs > li > a{display:block;color:var(--ink-2);text-decoration:none;
    padding:2.5px 6px;border-left:2px solid transparent;border-radius:0 6px 6px 0;line-height:1.45;}
  .toc-subs > li > a{display:block;color:var(--muted);text-decoration:none;
    font-size:.78rem;padding:2px 6px 2px 18px;border-left:2px solid transparent;line-height:1.4;}
  .doc-toc a:hover{color:var(--accent-2);background:var(--accent-soft);}
  .doc-toc a.active{color:var(--accent-2);border-left-color:var(--accent);background:var(--accent-soft);}
  .toc-no{display:inline-block;min-width:1.7em;margin-right:.35em;color:var(--faint);
    font-variant-numeric:tabular-nums;font-size:.9em;}

  .doc-body{max-width:72ch;min-width:0;font-size:1rem;color:var(--ink);}
  .doc-body [id]{scroll-margin-top:76px;}
  .doc-body p{line-height:1.72;margin:0 0 1.05em;}
  .doc-body h1{font-size:1.9rem;margin:2.6em 0 .6em;padding-top:1.2em;border-top:1px solid var(--line);}
  .doc-body h1:first-child{margin-top:.4em;padding-top:0;border-top:none;}
  .partno{display:block;font-size:.72rem;font-weight:600;letter-spacing:.16em;
    text-transform:uppercase;color:var(--accent);font-family:var(--font-sans);margin:0 0 8px;}
  .doc-body h2{font-size:1.38rem;margin:2.1em 0 .55em;}
  .doc-body h3{font-size:1.12rem;margin:1.8em 0 .5em;}
  .doc-body h4{font-family:var(--font-sans);font-size:.98rem;font-weight:650;margin:1.6em 0 .45em;}
  .doc-body h5{font-family:var(--font-sans);font-size:.92rem;font-weight:650;margin:1.4em 0 .4em;color:var(--ink-2);}
  .secno{color:var(--faint);font-weight:600;margin-right:.35em;font-variant-numeric:tabular-nums;}
  .doc-body a{color:var(--accent-2);text-decoration:none;}
  .doc-body a:hover{text-decoration:underline;}
  .doc-body ul,.doc-body ol{line-height:1.7;margin:0 0 1.05em;padding-left:1.5em;}
  .doc-body li{margin:0 0 .35em;}
  .doc-body li p{margin:0 0 .5em;}
  .doc-body code{font-family:var(--font-mono);font-size:.86em;background:var(--wash,#f4f2ee);
    border:1px solid var(--line);border-radius:5px;padding:.08em .32em;word-break:break-word;}
  .doc-body pre{background:#fbfaf7;border:1px solid var(--line);border-radius:10px;
    padding:14px 16px;overflow-x:auto;margin:0 0 1.2em;line-height:1.55;}
  .doc-body pre code{background:none;border:none;padding:0;font-size:.82rem;}
  .doc-body blockquote{margin:0 0 1.05em;padding:.2em 0 .2em 1em;
    border-left:3px solid var(--line);color:var(--ink-2);}
  .doc-body .math.display{display:block;overflow-x:auto;overflow-y:hidden;
    padding:.35em 0;margin:0 0 1.05em;text-align:center;}
  .doc-body .math.inline{white-space:nowrap;}

  .tblwrap{overflow-x:auto;margin:0 0 1.2em;border:1px solid var(--line);border-radius:10px;}
  .tblwrap table{border-collapse:collapse;width:100%;font-size:.9rem;}
  .tblwrap th,.tblwrap td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;}
  .tblwrap thead th{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
    color:var(--muted);font-weight:700;background:var(--surface);}
  .tblwrap tbody tr:last-child td{border-bottom:none;}

  .abstract{border:1px solid var(--line);border-radius:12px;background:var(--surface);
    padding:20px 22px 8px;margin:0 0 2.2em;}
  .abstract .abstract-label{display:block;font-size:.68rem;font-weight:600;letter-spacing:.14em;
    text-transform:uppercase;color:var(--muted);margin:0 0 10px;}
  .abstract p{font-size:.95rem;color:var(--ink-2);}

  .fig-fallback{border:1px dashed var(--faint);border-radius:12px;background:var(--surface);
    padding:16px 18px 6px;margin:0 0 1.4em;}
  .fig-fallback-label{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.1em;
    text-transform:uppercase;color:var(--muted);margin:0 0 6px;}
  .fig-fallback-note{display:block;font-size:.85rem;color:var(--muted);margin:0 0 10px;}
  .fig-fallback p{font-size:.9rem;color:var(--ink-2);}

  @media (max-width:920px){
    .doc-layout{grid-template-columns:minmax(0,1fr);gap:18px;}
    .doc-toc{position:static;max-height:none;}
    .doc-toc:not([open]){padding:12px 16px;}
  }
"""

PAGE_SCRIPT = """
(function () {
  'use strict';
  // Render pandoc's math spans with the vendored KaTeX. A few commands the
  // source uses are not KaTeX built-ins; probe and polyfill via macros so
  // nothing silently renders as an error.
  var macros = {};
  if (typeof katex !== 'undefined') {
    [['\\\\textsc', '\\\\text{#1}'], ['\\\\textup', '\\\\text{#1}']]
      .forEach(function (pair) {
        try { katex.renderToString(pair[0] + '{a}', { throwOnError: true }); }
        catch (e) { macros[pair[0]] = pair[1]; }
      });
    try { katex.renderToString('\\\\AA', { throwOnError: true }); }
    catch (e) { macros['\\\\AA'] = '\\\\text{\\u00c5}'; }
    var maths = document.querySelectorAll('.doc-body .math');
    for (var i = 0; i < maths.length; i++) {
      var el = maths[i];
      var displayMode = el.classList.contains('display');
      var src = el.textContent;
      try {
        katex.render(src, el, {
          displayMode: displayMode, throwOnError: false, macros: macros
        });
      } catch (e) { /* keep the TeX source visible */ }
    }
  }

  // The TOC is a <details>: collapsed by default on narrow screens, forced
  // open (with the summary acting as a plain title) on wide ones.
  var toc = document.getElementById('toc');
  if (toc && window.matchMedia('(min-width: 921px)').matches) {
    toc.open = true;
  }

  // Scroll spy: highlight the TOC entry of the section in view.
  var links = toc ? toc.querySelectorAll('a[href^="#"]') : [];
  var byId = {};
  for (var j = 0; j < links.length; j++) {
    byId[decodeURIComponent(links[j].hash.slice(1))] = links[j];
  }
  var current = null;
  function activate(id) {
    var link = byId[id];
    if (!link || link === current) return;
    if (current) current.classList.remove('active');
    link.classList.add('active');
    current = link;
  }
  if ('IntersectionObserver' in window && links.length) {
    var seen = [];
    var obs = new IntersectionObserver(function (entries) {
      for (var k = 0; k < entries.length; k++) {
        var e = entries[k];
        var idx = seen.indexOf(e.target);
        if (e.isIntersecting && idx === -1) seen.push(e.target);
        if (!e.isIntersecting && idx !== -1) seen.splice(idx, 1);
      }
      if (seen.length) {
        seen.sort(function (a, b) {
          return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
        });
        activate(seen[0].id);
      }
    }, { rootMargin: '-70px 0px -60% 0px' });
    var heads = document.querySelectorAll(
      '.doc-body h1[id], .doc-body h2[id], .doc-body h3[id]');
    for (var h = 0; h < heads.length; h++) obs.observe(heads[h]);
  }
})();
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>openmaterials.ai: the document</title>
<meta name="description" content="The project's single source of truth as readable documentation: vision, product, architecture, kernel, and status, converted from the LaTeX source, with the PDF one click away.">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="openmaterials.ai">
<meta property="og:title" content="openmaterials.ai: the document">
<meta property="og:description" content="Git for science: a versioned map of physics. The full document as readable HTML.">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="../assets/vendor/inter/inter.css">
<link rel="stylesheet" href="../assets/vendor/source-serif-4/source-serif-4.css">
<link rel="stylesheet" href="../assets/vendor/jetbrains-mono/jetbrains-mono.css">
<link rel="stylesheet" href="../assets/vendor/katex/dist/katex.min.css">
<link rel="stylesheet" href="../assets/site.css">
<style>__CSS__</style>
</head>
<body>
<div data-site-header></div>

<header class="doc-hero">
  <div class="om-overline"><span>The document</span><span aria-hidden="true">/</span><span>Single source of truth</span></div>
  <img class="doc-mark" src="../assets/logo.svg" alt="" width="46" height="46">
  <h1>openmaterials.ai</h1>
  <p class="doc-tagline">Git for science: a versioned map of physics</p>
  <p class="doc-byline">The OpenMaterials project &middot; open source: map data
    <a href="https://github.com/openmaterials-ai/openmaterials-ai/blob/main/LICENSE-DATA">CC BY 4.0</a>, code
    <a href="https://github.com/openmaterials-ai/openmaterials-ai/blob/main/LICENSE">Apache 2.0</a></p>
  <div class="doc-actions">
    <a class="om-btn" href="../openmaterials.pdf" id="download-pdf">Download the PDF</a>
    <span class="hint">This page is generated from the LaTeX source; the PDF is the typeset original.</span>
  </div>
</header>

<div class="doc-layout">
  <details class="doc-toc" id="toc">
    <summary>On this page</summary>
    <nav aria-label="Table of contents">
__TOC__
    </nav>
  </details>
  <article class="doc-body">
__BODY__
  </article>
</div>

<div data-site-footer></div>
<script src="../assets/site.js"></script>
<script src="../assets/vendor/katex/dist/katex.min.js"></script>
<script>__SCRIPT__</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_page(tex: str, pandoc: str) -> tuple[str, list[str]]:
    """Full pipeline: LaTeX source text to the final page HTML."""
    pre, notes = preprocess_tex(tex)
    body = run_pandoc(pre, pandoc)
    body = dedupe_class_attr(body)
    body = remap_heading_levels(body)
    headings = collect_headings(body)
    assign_numbers(headings)
    body = inject_numbers(body, headings)
    headings = collect_headings(body)
    # recover numbers (and clean titles) from the injected spans so the
    # TOC and cross references see them
    assign_numbers_from_spans(headings)
    body = rewrite_refs(body, headings)
    body = wrap_markers(body)
    body = wrap_tables(body)
    toc = build_toc(headings)
    page = (PAGE_TEMPLATE
            .replace("__CSS__", PAGE_CSS)
            .replace("__TOC__", toc)
            .replace("__BODY__", body.strip())
            .replace("__SCRIPT__", PAGE_SCRIPT))
    return page, notes


def assign_numbers_from_spans(headings: list[Heading]) -> None:
    """Recover each heading's number from the injected span and strip the
    span from the inner text used by the TOC."""
    for h in headings:
        m = re.match(
            r'\s*<span class="(?:partno|secno)">(?:Part )?([^<]*)</span>\s*',
            h.inner)
        if m:
            h.number = m.group(1)
            h.inner = h.inner[m.end():]


def main() -> int:
    pandoc = find_pandoc()
    if pandoc is None:
        raise SystemExit("pandoc not found; install it or adjust "
                         "PANDOC_CANDIDATES in omai/doc_html.py")
    tex = TEX_PATH.read_text(encoding="utf-8")
    page, notes = build_page(tex, pandoc)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    changed = (not OUT_PATH.exists()
               or OUT_PATH.read_text(encoding="utf-8") != page)
    OUT_PATH.write_text(page, encoding="utf-8")
    n_sec = len(command_titles(tex, "section"))
    n_sub = len(command_titles(tex, "subsection"))
    print("wrote %s (%s)" % (OUT_PATH.relative_to(ROOT),
                             "changed" if changed else "unchanged"))
    print("sections: %d, subsections: %d" % (n_sec, n_sub))
    for note in notes:
        print("degraded: %s" % note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
