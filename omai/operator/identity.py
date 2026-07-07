"""Content-addressed identity for nodes and edges (kernel P2).

Identity is a sha256 over canonical JSON of a node's / edge's *content* under
the amended rule (Resolved decisions #1 and #2):

  node id = H({"node": {quantity, field_signatures, gauge, labels}})
  edge id = H({"edge": {output, outputs, inputs, formula, schemes}})

Names, symbols, descriptions, tier, and the operator name are metadata, never
identity. Full digests are stored; a 12-hex prefix is displayed. Hashes are
deterministic across processes and runs because the JSON is canonical
(sort_keys, compact separators) and the formula fingerprint normalizes
commutative reordering via sympy.srepr.
"""
from __future__ import annotations

import hashlib
import json

import sympy as sp

from omai.operator.dimensions import DIMENSIONS
from omai.operator.registry import index_kind_signature, quantity_tag_for
from omai.operator.space import HiddenSpace, ObservableSpace


def canonical_json(obj) -> str:
    """Canonical JSON: sorted keys, compact separators. Tuples serialize as
    lists (json does this), so signatures built from tuples are stable."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def field_signature(field) -> dict:
    """The identity-bearing content of a Field: its dimension (canonical
    base-ordered string) and its index-kind signature (names -> kinds)."""
    return {
        "dimension": field.dimension.canonical(),
        "indices": list(index_kind_signature(field.indices)),
    }


def gauge_class(space) -> str:
    """The gauge class of a space: 'observable' for an ObservableSpace, or
    'hidden/<kind>/<gauge_group>' for a HiddenSpace."""
    if isinstance(space, ObservableSpace):
        return "observable"
    if isinstance(space, HiddenSpace):
        return f"hidden/{space.kind}/{space.gauge_group}"
    # Base Space (should not occur on the map; both concrete kinds are used).
    raise TypeError(f"space {space.name!r} is neither Observable nor Hidden")


def node_identity(space) -> dict:
    """The full identity dict of a node: quantity tag, the sorted multiset of
    field signatures (over ALL fields), gauge class, and stringified labels."""
    fields = sorted(
        (field_signature(f) for f in space.fields),
        key=canonical_json,
    )
    return {
        "quantity": quantity_tag_for(space.name),
        "fields": fields,
        "gauge": gauge_class(space),
        "labels": {str(k): str(v) for k, v in space.labels.items()},
    }


def node_id(space) -> str:
    return _sha256(canonical_json({"node": node_identity(space)}))


def parameter_node_id(pid: str, dimension_name: str | None) -> str:
    """Identity of a promoted parameter node (CellVolume, AtomicMass, ...).

    Parameters get a quantity tag and a single field signature like any node;
    a None dimension renders as the opaque canonical string 'opaque:opaque'.
    """
    if dimension_name is None:
        dim_canonical = "opaque:opaque"
    else:
        dim_canonical = DIMENSIONS[dimension_name].canonical()
    ident = {
        "quantity": quantity_tag_for(pid),
        "fields": [{"dimension": dim_canonical, "indices": []}],
        "gauge": "parameter",
        "labels": {},
    }
    return _sha256(canonical_json({"node": ident}))


def formula_fingerprint(formula) -> str:
    """A stable fingerprint of an operator formula.

    - sympy Basic: sympy.srepr (canonical Add/Mul ordering already makes
      commutative reordering one tree; algebraic equivalence is NOT
      canonicalized, by design).
    - str (LaTeX): whitespace-collapsed.
    - None: the literal 'none'.
    """
    if formula is None:
        return "none"
    if isinstance(formula, sp.Basic):
        return sp.srepr(formula)
    if isinstance(formula, str):
        return " ".join(formula.split())
    raise TypeError(f"unsupported formula type {type(formula)!r}")


def edge_identity(op, node_id_of) -> dict:
    """The full identity dict of an edge: the (single) primary output for the
    spec's wording, the full sorted outputs list (multi-output ops exist),
    sorted input node ids, the formula fingerprint, and sorted schemes."""
    return {
        "output": node_id_of(op.outputs[0]),
        "outputs": sorted(node_id_of(o) for o in op.outputs),
        "inputs": sorted(node_id_of(i) for i in op.inputs),
        "formula": formula_fingerprint(op.formula),
        "schemes": {k: v for k, v in sorted(op.schemes.items())},
    }


def edge_id(op, node_id_of) -> str:
    return _sha256(canonical_json({"edge": edge_identity(op, node_id_of)}))


def version_hash(prev_hex: str, record: dict) -> str:
    """The tamper-evident chain link: H(prev_hex || canonical(record)).
    The prev of genesis is 64 zeros."""
    return _sha256(prev_hex + canonical_json(record))
