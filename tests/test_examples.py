"""Smoke test: the bundled examples run end to end.

Guards the claim that the examples in `examples/` actually work. The
quickstart is self-contained (no external codes), so it runs in CI; its
internal asserts check the numbers.
"""

from __future__ import annotations

import runpy
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_quickstart_runs():
    runpy.run_path(str(_EXAMPLES / "quickstart.py"), run_name="__main__")
