"""The site Worker serves the static site untouched and adds only the named
dynamic routes.

infra/site is the edge deployment of the SAME docs/ every browser reads:
wrangler serves docs/ as assets and the Worker script runs only for
/l/<id> (the canonical permalink resolver) and /healthz. These tests pin the
contract statically and, where node is available, run the Worker's pure
resolver logic against the real committed projection.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SITE = _REPO / "infra" / "site"


def _wrangler_config() -> dict:
    raw = (_SITE / "wrangler.jsonc").read_text()
    return json.loads(re.sub(r"^\s*//.*$", "", raw, flags=re.M))


def test_worker_is_additive_over_the_static_site():
    cfg = _wrangler_config()
    assert cfg["assets"]["directory"] == "../../docs", \
        "the Worker must serve the SAME docs/ the static site publishes"
    assert set(cfg["assets"]["run_worker_first"]) == {"/l/*", "/healthz"}, \
        "only the named dynamic routes may bypass the assets"
    assert cfg["name"] == "openmaterials-site"


def test_worker_script_falls_through_to_assets():
    src = (_SITE / "src" / "index.js").read_text()
    assert "env.ASSETS.fetch(request)" in src, "no static fallthrough"
    assert "instances.json" in src and "version.json" in src
    for marker in ("API_KEY", "Bearer ", "Authorization"):
        assert marker not in src, f"the site Worker must hold no credentials ({marker})"


def test_resolver_logic_under_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; resolver checked where present")
    proc = subprocess.run(
        [node, "--test", str(_SITE / "src" / "resolve.test.mjs")],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
