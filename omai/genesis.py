"""The one-time genesis migration (kernel P3).

Walks the Python ``DOMAINS`` in a fixed order and pushes one ``add_node``
record per node (51) and one ``add_edge`` per operator (49) into a fresh store,
with a FIXED genesis date, then freezes the resulting version hash into
``map/GENESIS``. After this, the map's source of truth is the log; the Python
operator layer is an authoring client.

Determinism is load-bearing. The migration reads no clock and no randomness:
the date is the constant ``GENESIS_DATE``, the author is ``GENESIS_AUTHOR``, and
the walk order is fully specified (domains in DOMAINS order; within a domain,
nodes in NODES order, then promoted parameters in param_promotions order, then
edges in EDGES order; shared elements deduped by uid, first occurrence wins).
Running it into two directories yields byte-identical ``log.jsonl`` and the same
genesis hash.

The records are data only: each payload carries the full identity dict (the
exact dict that was hashed) and, for edges, the formula srepr and display latex
inline. Nothing in a payload is a domain object, so the store is rebuildable
from the log without importing any omai domain module.
"""
from __future__ import annotations

from pathlib import Path

import sympy as sp

from omai.operator.dimensions import DIMENSIONS
from omai.operator.identity import (
    edge_id,
    edge_identity,
    node_id,
    node_identity,
    parameter_node_id,
)
from omai.operator.registry import quantity_tag_for
from omai.store import Store

__all__ = [
    "GENESIS_AUTHOR",
    "GENESIS_DATE",
    "genesis_records",
    "run_genesis",
]

# The frozen genesis date and author. Never a clock read: the genesis hash must
# be reproducible from the code alone.
GENESIS_DATE = "2026-07-07"
GENESIS_AUTHOR = "genesis"


def _parameter_identity(pid: str, dimension_name: str | None) -> dict:
    """The identity dict of a promoted parameter node, replicated so the
    payload carries exactly what ``parameter_node_id`` hashed."""
    if dimension_name is None:
        dim_canonical = "opaque:opaque"
    else:
        dim_canonical = DIMENSIONS[dimension_name].canonical()
    return {
        "quantity": quantity_tag_for(pid),
        "fields": [{"dimension": dim_canonical, "indices": []}],
        "gauge": "parameter",
        "labels": {},
    }


def _formula_srepr(formula) -> str | None:
    """The formula fingerprint for storage: sympy.srepr for a Basic, the
    whitespace-normalized string for a str formula, None otherwise. This is
    the display/rebuild copy; the identity hash uses the same normalization
    via ``formula_fingerprint`` (which maps None to the literal 'none')."""
    if formula is None:
        return None
    if isinstance(formula, sp.Basic):
        return sp.srepr(formula)
    if isinstance(formula, str):
        return " ".join(formula.split())
    raise TypeError(f"unsupported formula type {type(formula)!r}")


def _formula_latex(formula) -> str | None:
    """Display latex: sympy.latex for a Basic (guarded by try/except), the
    string itself for a str formula, None otherwise or on failure."""
    if formula is None:
        return None
    if isinstance(formula, sp.Basic):
        try:
            return sp.latex(formula)
        except Exception:
            return None
    if isinstance(formula, str):
        return formula
    return None


def genesis_records() -> list[tuple[str, dict, str]]:
    """The deterministic (op, payload, reason) sequence for the genesis log.

    Order: domains in DOMAINS order; within a domain, nodes in NODES order,
    then the promoted parameters in param_promotions order, then edges in
    EDGES order. Shared nodes and edges are deduped by uid, first occurrence
    winning (a domain re-using another's node adds nothing).
    """
    from omai.map_data import DOMAINS

    # Merged symbol table (same precedence build_graph_dict uses): later
    # domains override earlier keys, matching the site's symbol resolution.
    symbols: dict[str, str] = {}
    for d in DOMAINS:
        symbols.update(d.symbols)

    records: list[tuple[str, dict, str]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()

    for d in DOMAINS:
        # 1. Spaces, in NODES order.
        for s in d.nodes:
            uid = node_id(s)
            if uid in seen_nodes:
                continue
            seen_nodes.add(uid)
            payload = {
                "uid": uid,
                "identity": node_identity(s),
                "meta": {
                    "name": s.name,
                    "symbol": symbols.get(s.name, s.name),
                    "description": s.description,
                    "tier": s.tier,
                },
            }
            records.append(("add_node", payload, f"genesis: node {s.name}"))

        # 2. Promoted parameters, in param_promotions order (tier 'Sources').
        for pid, psym, _sobj, *rest in d.param_promotions:
            dim_name = rest[0] if rest else None
            uid = parameter_node_id(pid, dim_name)
            if uid in seen_nodes:
                continue
            seen_nodes.add(uid)
            payload = {
                "uid": uid,
                "identity": _parameter_identity(pid, dim_name),
                "meta": {
                    "name": pid,
                    "symbol": psym,
                    "description": "",
                    "tier": "Sources",
                },
            }
            records.append(("add_node", payload, f"genesis: parameter {pid}"))

    for d in DOMAINS:
        # 3. Edges (operators), in EDGES order.
        for op in d.edges:
            uid = edge_id(op, node_id)
            if uid in seen_edges:
                continue
            seen_edges.add(uid)
            payload = {
                "uid": uid,
                "identity": edge_identity(op, node_id),
                "meta": {
                    "name": op.name,
                    "description": op.description,
                    "formula_srepr": _formula_srepr(op.formula),
                    "formula_latex": _formula_latex(op.formula),
                    "schemes": {k: v for k, v in sorted(op.schemes.items())},
                },
            }
            records.append(("add_edge", payload, f"genesis: edge {op.name}"))

    return records


def run_genesis(root: Path) -> str:
    """Build a fresh store at ``root``, push every genesis record with the
    fixed date and author, write ``GENESIS`` with the final version hash, and
    return that hash.

    Idempotent per directory only in the sense of determinism: an existing log
    is not cleared, so callers pass a fresh directory. A repeat call into the
    same directory would append duplicate records; the migration is meant to
    run once per store.
    """
    root = Path(root)
    store = Store(root)
    for op, payload, reason in genesis_records():
        store.push(op, payload, GENESIS_AUTHOR, GENESIS_DATE, reason)
    genesis_hash = store.head
    store.genesis_path.write_text(genesis_hash + "\n")
    return genesis_hash
