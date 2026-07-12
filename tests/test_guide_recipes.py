"""The guide's Python recipes are executed here, so a recipe that stops
working against the live map fails CI (the docs cannot silently drift)."""
import re
from pathlib import Path

_GUIDE = Path(__file__).resolve().parent.parent / "docs" / "guide" / "index.html"


def _python_recipes():
    html = _GUIDE.read_text()
    # each <div class="recipe" data-recipe="python"> ... <pre>CODE</pre>
    blocks = re.findall(
        r'data-recipe="python".*?<pre>(.*?)</pre>', html, re.S)
    # un-escape the minimal HTML entities the page uses
    return [b.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            for b in blocks]


def test_guide_has_python_recipes():
    assert len(_python_recipes()) >= 4


def test_every_python_recipe_runs():
    for i, code in enumerate(_python_recipes()):
        ns = {}
        try:
            exec(code, ns)
        except Exception as e:  # pragma: no cover - failure path
            raise AssertionError(
                f"guide python recipe #{i} failed: {type(e).__name__}: {e}\n"
                f"--- recipe ---\n{code}") from e
