"""The compact node catalog that rides in the cached system prompt.

Built from the live registry/graph (omai.map_data.build_catalog) so it always
reflects the real 98-node map. Deterministically sorted (by id) and rendered to
a byte-stable string so prompt caching sees an identical prefix across calls and
retries within a run.
"""
from __future__ import annotations

import json


def build_node_catalog(domains=None) -> list[dict]:
    """Return the catalog rows (id, symbol, type, dimension, description).

    Deterministically sorted by node id so the serialized form is byte-stable.
    Delegates to map_data.build_catalog, which reads dimensions and one-line
    descriptions from the live spaces and promoted-parameter declarations.
    """
    from omai.map_data import _domains, build_catalog

    rows = build_catalog(domains or _domains())
    return sorted(rows, key=lambda r: r["id"])


def render_catalog(rows: list[dict]) -> str:
    """Render the catalog rows to a stable, compact text block for the system
    prompt.

    One line per node: `id | symbol | dimension | description`. The dimension is
    the node's field-dimension string (or 'unspecified'); the description is the
    curated one-liner. json.dumps is avoided for the body so the text stays
    human- and cache-friendly; the id sort in build_node_catalog fixes ordering.
    """
    lines = ["# OpenMaterials map node catalog (id | symbol | dimension | description)"]
    for r in rows:
        dim = r.get("dimension") or "unspecified"
        desc = (r.get("description") or "").replace("\n", " ").strip()
        sym = r.get("symbol") or ""
        lines.append(f"{r['id']} | {sym} | {dim} | {desc}")
    return "\n".join(lines)


def catalog_ids(rows: list[dict]) -> set[str]:
    """The set of valid node ids in the catalog (for MAP-stage validation)."""
    return {r["id"] for r in rows}


def catalog_fingerprint(rendered: str) -> str:
    """A short, key-free fingerprint of the rendered catalog for logging.

    Lets a run confirm the cached prefix is byte-identical across calls without
    dumping the full catalog. sha256 of the rendered text, first 12 hex chars.
    """
    import hashlib

    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:12]
