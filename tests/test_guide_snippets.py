"""The guide's Python snippets are executed here, so a snippet that stops
working against the live map fails CI (the docs cannot silently drift)."""
import re
from pathlib import Path

_GUIDE = Path(__file__).resolve().parent.parent / "docs" / "guide" / "index.html"


def _python_snippets():
    html = _GUIDE.read_text()
    # each <div class="snippet" data-snippet="python"> ... <pre>CODE</pre>
    blocks = re.findall(
        r'data-snippet="python".*?<pre>(.*?)</pre>', html, re.S)
    # un-escape the minimal HTML entities the page uses
    return [b.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            for b in blocks]


def test_guide_has_python_snippets():
    assert len(_python_snippets()) >= 4


def test_every_python_snippet_runs():
    for i, code in enumerate(_python_snippets()):
        ns = {}
        try:
            exec(code, ns)
        except Exception as e:  # pragma: no cover - failure path
            raise AssertionError(
                f"guide python snippet #{i} failed: {type(e).__name__}: {e}\n"
                f"--- snippet ---\n{code}") from e
