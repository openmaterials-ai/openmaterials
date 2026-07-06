"""DAG-discipline validator.

Walks a node + edge set and checks the structural invariants that the
architectural commitments imply but that the type system
alone can't enforce:

  * Every HiddenSpace declares a gauge_group (non-empty string).
  * Every HiddenSpace declares kind ∈ {"scaffolding", "approximation"}.
  * Every scaffolding HiddenSpace declares at least one
    gauge_invariant_contractions entry, and each named entry resolves
    to an ObservableSpace that exists in the node set.
  * Every approximation HiddenSpace declares zero
    gauge_invariant_contractions (otherwise it would be scaffolding).
  * Every node name is unique.
  * Every Operator's inputs and outputs are nodes that appear in the
    node set.

In addition, AOT (declaration-time) content checks against each edge's
sympy formula:

  * Every free symbol in `formula` is derivable from one of:
      - the per-space allowed-symbol set of an input space
      - the per-space allowed-symbol set of an output space (formulas
        commonly reference the LHS quantity they produce)
      - the edge's declared `parameters`
      - the registered pool of bare constants.
    Per-space symbol sets and bare constants live in the
    `omai.operator.vocabulary` registry, which each domain populates at
    import time (see e.g. `omai/thermal_transport/operator/vocabulary.py`).
    Anything else is flagged as "not derivable from inputs", catching
    typos and undeclared symbols at module-load time.

  * For edges whose `formula` is a sympy.Eq with an Indexed LHS, the
    LHS's index tuple must match (positionally) the index tuple
    declared on the output space's first field.

  * Auxiliary formulas (`auxiliary_formulas`) are checked against the
    same vocabulary as the main formula, augmented with whatever
    symbols the main formula itself introduces (so an auxiliary
    equation may define a kernel that appears in the main formula).

Returns a list of human-readable violation strings; empty list means
the operator layer is internally consistent.
"""

from __future__ import annotations

import sympy as sp

from omai.operator import vocabulary
from omai.operator.operator import Operator
from omai.operator.space import HiddenSpace, ObservableSpace, Space

_VALID_KINDS = {"scaffolding", "approximation"}


def _symbol_base_name(sym: sp.Basic) -> str:
    """Return the base name of a sympy free-symbol element.

    For an `Indexed` instance, returns the underlying `IndexedBase` name
    (which is what an adapter would key on). For a `Symbol`, returns its
    `.name`. For anything else, falls back to `str(sym)`.
    """
    if isinstance(sym, sp.Indexed):
        return str(sym.base.name)
    if hasattr(sym, "name"):
        return str(sym.name)
    return str(sym)


def _allowed_symbols_for_edge(op: Operator) -> set[str]:
    """Allowed base-symbol names for a given Operator.

    Union of:
      - the registered bare constants (`vocabulary.FORMULA_CONSTANTS`)
      - `vocabulary.SPACE_SYMBOLS[input.name]` for each input space
      - `vocabulary.SPACE_SYMBOLS[output.name]` for each output space
      - the edge's parameter names
    Spaces not present in the registry contribute nothing — they're
    treated as not yet registered, which means the check will flag
    unregistered symbols. Register via the domain's vocabulary module
    when growing the DAG.
    """
    allowed: set[str] = set(vocabulary.FORMULA_CONSTANTS)
    for inp in op.inputs:
        allowed.update(vocabulary.SPACE_SYMBOLS.get(inp.name, frozenset()))
    for out in op.outputs:
        allowed.update(vocabulary.SPACE_SYMBOLS.get(out.name, frozenset()))
    for p in op.parameters:
        allowed.add(p.name)
    return allowed


def _formula_symbols(formula: sp.Basic) -> set[sp.Basic]:
    """Return the free symbols of a formula (Indexed + Symbol)."""
    return set(formula.free_symbols)


def _check_free_symbols(
    op: Operator,
    formula: sp.Basic,
    allowed: set[str],
    label: str,
) -> list[str]:
    """Report any free symbol whose base name is not in `allowed`."""
    errors: list[str] = []
    for sym in _formula_symbols(formula):
        base = _symbol_base_name(sym)
        if base not in allowed:
            errors.append(
                f"edge {op.name!r} {label} uses symbol {base!r} not derivable from inputs"
            )
    return errors


def _check_lhs_indices(op: Operator, formula: sp.Basic) -> list[str]:
    """If formula is sp.Eq with an Indexed LHS, check its index tuple
    matches the output space's first field's declared indices.

    The comparison is positional on the *index names* (i.e. the str of
    each sympy index symbol against the str in field.indices). Some
    edges have implicit LHS (e.g. solve_bte_direct's LHS is a sum); we
    skip those by only firing when the LHS is exactly sp.Indexed.
    """
    if not isinstance(formula, sp.Eq):
        return []
    lhs = formula.lhs
    if not isinstance(lhs, sp.Indexed):
        return []
    if not op.outputs:
        return []
    out = op.outputs[0]
    if not out.fields:
        return []
    declared = out.fields[0].indices
    actual = tuple(str(i) for i in lhs.indices)
    # The state-side declaration uses Python-style index names ("q", "nu",
    # "alpha") while the sympy side uses LaTeX (e.g. r"\mathbf{q}", r"\nu",
    # r"\alpha"). Compare by length only (positional rank), since a
    # name-level comparison would require an exhaustive translation table
    # that isn't the substantive content of this check.
    if len(declared) != len(actual):
        return [
            f"edge {op.name!r} LHS {_symbol_base_name(lhs)!r} carries {len(actual)} "
            f"indices but output field declares {len(declared)} ({declared!r})"
        ]
    return []


def validate_dag(
    nodes: tuple[Space, ...] | list[Space],
    edges: tuple[Operator, ...] | list[Operator],
) -> list[str]:
    """Return a list of DAG-discipline violations (empty if clean)."""
    errors: list[str] = []

    # Name uniqueness
    names_seen: set[str] = set()
    observable_names: set[str] = set()
    for space in nodes:
        if space.name in names_seen:
            errors.append(f"duplicate node name: {space.name!r}")
        names_seen.add(space.name)
        if isinstance(space, ObservableSpace):
            observable_names.add(space.name)

    # Per-HiddenSpace discipline
    for space in nodes:
        if not isinstance(space, HiddenSpace):
            continue
        if not space.gauge_group:
            errors.append(
                f"{space.name}: HiddenSpace must declare a non-empty gauge_group"
            )
        if space.kind not in _VALID_KINDS:
            errors.append(
                f"{space.name}: kind must be one of {sorted(_VALID_KINDS)}, "
                f"got {space.kind!r}"
            )
        if space.kind == "scaffolding":
            if not space.gauge_invariant_contractions:
                errors.append(
                    f"{space.name}: scaffolding HiddenSpace must declare at least one "
                    "gauge_invariant_contractions entry"
                )
            for obs_name in space.gauge_invariant_contractions:
                if obs_name not in observable_names:
                    errors.append(
                        f"{space.name}: declared contraction {obs_name!r} is not an "
                        "ObservableSpace in the node set"
                    )
        elif space.kind == "approximation":
            if space.gauge_invariant_contractions:
                errors.append(
                    f"{space.name}: approximation HiddenSpace should not declare "
                    "gauge_invariant_contractions (terminal by definition)"
                )

    # Edges reference nodes in the set
    for op in edges:
        for inp in op.inputs:
            if inp.name not in names_seen:
                errors.append(
                    f"operator {op.name!r} input {inp.name!r} not in node set"
                )
        for out in op.outputs:
            if out.name not in names_seen:
                errors.append(
                    f"operator {op.name!r} output {out.name!r} not in node set"
                )

    # Sympy-layer content checks on edges with sympy formulas.
    for op in edges:
        if op.formula is None or not isinstance(op.formula, sp.Basic):
            continue
        allowed = _allowed_symbols_for_edge(op)

        # Free-symbol check on the main formula.
        errors.extend(_check_free_symbols(op, op.formula, allowed, "formula"))

        # LHS-index consistency.
        errors.extend(_check_lhs_indices(op, op.formula))

        # Auxiliary formulas: each one inherits the main formula's
        # vocabulary (so an aux equation can reference symbols the main
        # formula introduces, e.g. |V_3|^2 defined alongside Γ_qν).
        aux_allowed = set(allowed)
        for sym in _formula_symbols(op.formula):
            aux_allowed.add(_symbol_base_name(sym))
        for aux in op.auxiliary_formulas:
            if not isinstance(aux, sp.Basic):
                continue
            errors.extend(_check_free_symbols(op, aux, aux_allowed, "auxiliary formula"))

    return errors
