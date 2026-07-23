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
    assert set(cfg["assets"]["run_worker_first"]) == {"/l/*", "/s", "/s/*", "/badge/*", "/healthz"}, \
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


def test_short_link_store_contract():
    """The /s short-link store (the one write surface): worker-first routes,
    the KV binding, origin-gated minting, open-CORS immutable raw reads, and
    the playground's #s= route all pinned; the pure logic runs under node
    against the real validation and shell builders."""
    cfg = _wrangler_config()
    assert "/s" in cfg["assets"]["run_worker_first"]
    assert "/s/*" in cfg["assets"]["run_worker_first"]
    assert any(k["binding"] == "SHORTLINKS" for k in cfg.get("kv_namespaces", [])), \
        "no KV namespace bound for the short-link store"

    src = (_SITE / "src" / "index.js").read_text()
    assert "isMintOrigin" in src, "minting must be origin-gated"
    assert "MINTS_PER_DAY" in src, "minting must be rate-limited"
    assert "access-control-allow-origin\": \"*\"" in src or "'access-control-allow-origin': '*'" in src.replace('"', "'"), \
        "raw reads must carry open CORS (a minted payload is public)"
    assert "immutable" in src, "stored payloads never change; raw reads must say so"

    play = (_REPO / "docs" / "play" / "index.html").read_text()
    assert "fetchShortlink" in play and "#s=" in play.replace("\\", ""), \
        "the playground must resolve #s= through the short-link store"
    assert "mintShortlink" in play and "bundleShort" in play, \
        "the bundle view must offer Copy short link"
    assert "public to anyone with the code" in play, \
        "the mint control must state the public-by-construction rule"

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; short-link logic checked where present")
    proc = subprocess.run(
        [node, "--test", str(_SITE / "src" / "shortlinks.test.mjs")],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_source_first_identifier_routes():
    """The paper goes first in the URL: /l/<scheme:ref> lists the source's
    committed family, /l/<scheme:ref>/<hash> names one value gated by the
    in-hash source (a speaking identifier that cannot lie), and the play badge
    shows the source chip. Pinned here; the logic runs under node."""
    src = (_SITE / "src" / "index.js").read_text()
    assert "parseLPath" in src and "sourceMismatchHTML" in src, "no source routes"
    assert "409" in src, "a mismatched namespace must refuse, never redirect silently"
    play = (_REPO / "docs" / "play" / "index.html").read_text()
    assert "rec-doi-src" in play, "the badge does not show the source namespace chip"
    resolve = (_SITE / "src" / "resolve.js").read_text()
    assert "SOURCE_REF_RE" in resolve and "canonical" in resolve
