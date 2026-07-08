"""Contribution validation gates (kernel P4).

A *contribution* is an ordered list of proposed change records,
``[{"op": ..., "payload": ...}, ...]`` in application order, with ``op`` drawn
from :data:`omai.store.CHANGE_OPS` (only ``add_node`` / ``add_edge`` /
``edit_meta`` / ``deprecate`` / ``supersede`` / ``equate``). :func:`validate_contribution`
checks it against a materialized map (``Store.read()`` shape) through six gates,
in a fixed order, and returns a list of human-readable problems (one per issue,
each prefixed by the failing gate name in brackets, e.g. ``"[reachability] ..."``).
An empty list means the contribution is admissible.

The gates, in check order:

1. ``[registry]``  every add_node identity draws its quantity tag, index kinds,
   label keys / values, and (for a hidden gauge class) its gauge group from the
   controlled registries in :mod:`omai.operator.registry`; add_edge schemes are
   string-valued.
2. ``[identity]``  the payload uid recomputes from the payload identity dict
   (via the single hashing implementation in :mod:`omai.operator.identity`); a
   mismatch is an error. An add whose uid already exists in ``current`` with an
   IDENTICAL identity dict is exact convergence, marked internally as a no-op;
   the same uid with a DIFFERING identity dict is an error (collision / tamper).
3. ``[reachability]``  every add_edge input / output uid resolves to a node in
   ``current`` or one added earlier in the same contribution.
4. ``[connectivity]``  the non-no-op additions form a weakly connected subgraph
   and at least one contribution edge touches a pre-existing node of ``current``.
   A contribution of only edit_meta / deprecate / supersede / equate records
   skips this gate. A contribution adding exactly one node with no edges fails
   it (a bare disconnected node is inadmissible).
5. ``[gauge]``  every add_node gauge-class string is well-formed: ``observable``,
   ``parameter``, or ``hidden/<kind>/<registered group>`` with kind in
   ``{scaffolding, approximation}``. The full contraction-resolution check (the
   store-level analogue of ``validate_dag``) stays Python-side in
   ``validate_dag``; this gate only checks the string is well-formed.
6. ``[dimensional]``  for every add_edge whose payload meta carries a
   ``formula_srepr``, reconstruct the sympy expression (``sympy.sympify`` guarded
   by try/except; a parse failure is an error). If it is an ``Eq``, evaluate both
   sides with :func:`omai.operator.dimcheck.dimension_of` against the registered
   symbol dimensions: both known and unequal is an error; unknown on either side
   is a skip (never a guess); a raised ``DimensionalViolation`` is an error.
   Edges without a ``formula_srepr`` skip.

Determinism: nothing here reads the clock or any source of randomness (mirroring
the store). The gates are pure over (records, current).
"""
from __future__ import annotations

import sympy as sp

from omai.operator.dimcheck import DimensionalViolation, dimension_of
from omai.operator.identity import (
    edge_uid_from_identity,
    node_uid_from_identity,
)
from omai.operator.registry import GAUGE_GROUPS, INDEX_KINDS, LABEL_KEYS, QUANTITY_TAGS

__all__ = ["validate_contribution"]

# The registered index kinds are the *values* of INDEX_KINDS (node identity
# stores kinds, not names). Gauge kinds are the two HiddenSpace kinds.
_REGISTERED_INDEX_KINDS = frozenset(INDEX_KINDS.values())
_HIDDEN_KINDS = frozenset({"scaffolding", "approximation"})


# --------------------------------------------------------------------------
# Gate 1: registry.
# --------------------------------------------------------------------------

def _check_registry(records: list[dict]) -> list[str]:
    problems: list[str] = []
    for rec in records:
        op = rec["op"]
        payload = rec["payload"]
        if op == "add_node":
            ident = payload.get("identity", {})
            uid12 = str(payload.get("uid", ""))[:12]
            quantity = ident.get("quantity")
            if quantity not in QUANTITY_TAGS:
                problems.append(
                    f"[registry] node {uid12}: unregistered quantity tag "
                    f"{quantity!r}")
            for field in ident.get("fields", []):
                for kind in field.get("indices", []):
                    if kind not in _REGISTERED_INDEX_KINDS:
                        problems.append(
                            f"[registry] node {uid12}: unregistered index kind "
                            f"{kind!r}")
            for key, value in ident.get("labels", {}).items():
                allowed = LABEL_KEYS.get(key)
                if allowed is None:
                    problems.append(
                        f"[registry] node {uid12}: unregistered label key "
                        f"{key!r}")
                elif str(value) not in allowed:
                    problems.append(
                        f"[registry] node {uid12}: unregistered value "
                        f"{value!r} for label key {key!r}")
            gauge = ident.get("gauge", "")
            if isinstance(gauge, str) and gauge.startswith("hidden/"):
                parts = gauge.split("/")
                if len(parts) == 3 and parts[2] not in GAUGE_GROUPS:
                    problems.append(
                        f"[registry] node {uid12}: unregistered gauge group "
                        f"{parts[2]!r}")
        elif op == "add_edge":
            schemes = payload.get("meta", {}).get("schemes", {})
            for key, value in schemes.items():
                if not isinstance(value, str):
                    problems.append(
                        f"[registry] edge {str(payload.get('uid',''))[:12]}: "
                        f"scheme {key!r} is not string-valued ({value!r})")
    return problems


# --------------------------------------------------------------------------
# Gate 2: identity. Also computes the no-op set for later gates.
# --------------------------------------------------------------------------

def _check_identity(records: list[dict], current: dict) -> tuple[list[str], set[int]]:
    """Return (problems, no_op_indices).

    A no-op is an add whose uid already exists in ``current`` with an identical
    identity dict (exact convergence). Its index in ``records`` is collected so
    the connectivity gate ignores it and ``propose`` never re-pushes it.
    """
    problems: list[str] = []
    no_ops: set[int] = set()
    nodes = current.get("nodes", {})
    edges = current.get("edges", {})
    for i, rec in enumerate(records):
        op = rec["op"]
        payload = rec["payload"]
        if op == "add_node":
            recompute = node_uid_from_identity
            existing = nodes
        elif op == "add_edge":
            recompute = edge_uid_from_identity
            existing = edges
        else:
            continue
        ident = payload.get("identity", {})
        uid = payload.get("uid")
        expected = recompute(ident)
        uid12 = str(uid)[:12]
        if uid != expected:
            problems.append(
                f"[identity] {op} {uid12}: uid does not match its identity dict "
                f"(recomputed {expected[:12]})")
            continue
        if uid in existing:
            if existing[uid].get("identity") == ident:
                no_ops.add(i)  # exact convergence
            else:
                problems.append(
                    f"[identity] {op} {uid12}: uid already exists with a "
                    f"different identity dict (collision or tampering)")
    return problems, no_ops


# --------------------------------------------------------------------------
# Gate 3: reachability.
# --------------------------------------------------------------------------

def _check_reachability(records: list[dict], current: dict) -> list[str]:
    problems: list[str] = []
    known_nodes = set(current.get("nodes", {}))
    for rec in records:
        op = rec["op"]
        payload = rec["payload"]
        if op == "add_node":
            known_nodes.add(payload.get("uid"))
            continue
        if op == "add_edge":
            ident = payload.get("identity", {})
            uid12 = str(payload.get("uid", ""))[:12]
            endpoints = list(ident.get("inputs", [])) + list(ident.get("outputs", []))
            for ep in endpoints:
                if ep not in known_nodes:
                    problems.append(
                        f"[reachability] edge {uid12}: endpoint {str(ep)[:12]} "
                        f"is not a node in the store or earlier in the "
                        f"contribution")
    return problems


# --------------------------------------------------------------------------
# Gate 4: connectivity.
# --------------------------------------------------------------------------

def _check_connectivity(records: list[dict], current: dict, no_ops: set[int]
                        ) -> list[str]:
    existing_nodes = set(current.get("nodes", {}))
    added_nodes: list[str] = []
    contribution_edges: list[tuple[list[str], str]] = []  # (endpoints, uid12)
    has_add = False
    for i, rec in enumerate(records):
        if i in no_ops:
            continue
        op = rec["op"]
        payload = rec["payload"]
        if op == "add_node":
            has_add = True
            added_nodes.append(payload.get("uid"))
        elif op == "add_edge":
            has_add = True
            ident = payload.get("identity", {})
            endpoints = list(ident.get("inputs", [])) + list(ident.get("outputs", []))
            contribution_edges.append((endpoints, str(payload.get("uid", ""))[:12]))

    # A contribution of only edit_meta / deprecate / supersede / equate (or a
    # contribution that is entirely no-ops) skips connectivity.
    if not has_add:
        return []

    problems: list[str] = []

    # Rule 1: at least one contribution edge touches a pre-existing node.
    touches_existing = any(
        any(ep in existing_nodes for ep in endpoints)
        for endpoints, _ in contribution_edges)
    if not touches_existing:
        problems.append(
            "[connectivity] the contribution touches no pre-existing node of "
            "the store (at least one edge must connect to an existing node)")

    # Rule 2: the non-no-op additions form a weakly connected subgraph. Nodes
    # are the newly-added node uids plus every endpoint of a contribution edge;
    # edges connect their endpoints. A bare single added node with no edge is a
    # single disconnected component and fails.
    graph_nodes: set[str] = set(added_nodes)
    for endpoints, _ in contribution_edges:
        graph_nodes.update(endpoints)
    adjacency: dict[str, set[str]] = {n: set() for n in graph_nodes}
    for endpoints, _ in contribution_edges:
        for a in endpoints:
            for b in endpoints:
                if a != b:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
    if graph_nodes:
        seen: set[str] = set()
        stack = [next(iter(graph_nodes))]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adjacency[n] - seen)
        if seen != graph_nodes:
            problems.append(
                "[connectivity] the contribution's additions are not weakly "
                "connected (disconnected components)")

    return problems


# --------------------------------------------------------------------------
# Gate 5: gauge.
# --------------------------------------------------------------------------

def _check_gauge(records: list[dict]) -> list[str]:
    problems: list[str] = []
    for rec in records:
        if rec["op"] != "add_node":
            continue
        payload = rec["payload"]
        gauge = payload.get("identity", {}).get("gauge", "")
        uid12 = str(payload.get("uid", ""))[:12]
        if gauge in ("observable", "parameter"):
            continue
        parts = gauge.split("/") if isinstance(gauge, str) else []
        well_formed = (
            len(parts) == 3
            and parts[0] == "hidden"
            and parts[1] in _HIDDEN_KINDS
            and parts[2] in GAUGE_GROUPS)
        if not well_formed:
            problems.append(
                f"[gauge] node {uid12}: gauge class {gauge!r} is not "
                f"well-formed (expected observable, parameter, or "
                f"hidden/<scaffolding|approximation>/<registered group>)")
    return problems


# --------------------------------------------------------------------------
# Gate 6: dimensional.
# --------------------------------------------------------------------------

def _check_dimensional(records: list[dict]) -> list[str]:
    problems: list[str] = []
    for rec in records:
        if rec["op"] != "add_edge":
            continue
        payload = rec["payload"]
        srepr = payload.get("meta", {}).get("formula_srepr")
        uid12 = str(payload.get("uid", ""))[:12]
        if srepr is None:
            continue
        try:
            expr = sp.sympify(srepr)
        except (sp.SympifyError, SyntaxError, TypeError, ValueError, AttributeError):
            problems.append(f"[dimensional] edge {uid12}: unparseable formula")
            continue
        if not isinstance(expr, sp.Eq):
            continue
        try:
            lhs_dim = dimension_of(expr.lhs)
            rhs_dim = dimension_of(expr.rhs)
        except DimensionalViolation as exc:
            problems.append(f"[dimensional] edge {uid12}: {exc}")
            continue
        if lhs_dim is None or rhs_dim is None:
            continue  # unknown on a side -> skip, never a guess
        if lhs_dim != rhs_dim:
            problems.append(
                f"[dimensional] edge {uid12}: lhs {lhs_dim.canonical()} != rhs "
                f"{rhs_dim.canonical()}")
    return problems


# --------------------------------------------------------------------------
# The public entry.
# --------------------------------------------------------------------------

def validate_contribution(records: list[dict], current: dict) -> list[str]:
    """Validate a contribution against a materialized map; return problems.

    ``records`` is the ordered list ``[{"op": ..., "payload": ...}, ...]``;
    ``current`` is the ``Store.read()`` shape ``{"nodes": {uid: entry},
    "edges": {uid: entry}}``. Returns [] when admissible, else one problem per
    issue, each prefixed by the failing gate name in brackets. Gates run in the
    documented order; the identity gate also computes the exact-convergence
    no-op set consumed by connectivity.
    """
    problems: list[str] = []
    problems.extend(_check_registry(records))
    identity_problems, no_ops = _check_identity(records, current)
    problems.extend(identity_problems)
    problems.extend(_check_reachability(records, current))
    problems.extend(_check_connectivity(records, current, no_ops))
    problems.extend(_check_gauge(records))
    problems.extend(_check_dimensional(records))
    return problems


def no_op_indices(records: list[dict], current: dict) -> set[int]:
    """The indices of add records that are exact convergence no-ops.

    Exposed for ``Store.propose`` so it pushes only the non-no-op records.
    Recomputes the identity-gate no-op set (an add whose uid already exists in
    ``current`` with an identical identity dict).
    """
    _, no_ops = _check_identity(records, current)
    return no_ops
