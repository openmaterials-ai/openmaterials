"""Substrate-discipline validator.

Walks a node + edge set and checks the structural invariants that the
substrate's architectural commitments imply but that the type system
alone can't enforce:

  * Every HiddenState declares a gauge_group (non-empty string).
  * Every HiddenState declares kind ∈ {"scaffolding", "approximation"}.
  * Every scaffolding HiddenState declares at least one
    gauge_invariant_contractions entry, and each named entry resolves
    to an Observable that exists in the node set.
  * Every approximation HiddenState declares zero
    gauge_invariant_contractions (otherwise it would be scaffolding).
  * Every node name is unique.
  * Every operation's inputs and outputs are nodes that appear in the
    node set.

Returns a list of human-readable violation strings; empty list means
the substrate is internally consistent.
"""

from __future__ import annotations

from omai.abstract.operation import Operation
from omai.abstract.state import HiddenState, Observable, State

_VALID_KINDS = {"scaffolding", "approximation"}


def validate_substrate(
    nodes: tuple[State, ...] | list[State],
    edges: tuple[Operation, ...] | list[Operation],
) -> list[str]:
    """Return a list of substrate-discipline violations (empty if clean)."""
    errors: list[str] = []

    # Name uniqueness
    names_seen: set[str] = set()
    observable_names: set[str] = set()
    for state in nodes:
        if state.name in names_seen:
            errors.append(f"duplicate node name: {state.name!r}")
        names_seen.add(state.name)
        if isinstance(state, Observable):
            observable_names.add(state.name)

    # Per-HiddenState discipline
    for state in nodes:
        if not isinstance(state, HiddenState):
            continue
        if not state.gauge_group:
            errors.append(
                f"{state.name}: HiddenState must declare a non-empty gauge_group"
            )
        if state.kind not in _VALID_KINDS:
            errors.append(
                f"{state.name}: kind must be one of {sorted(_VALID_KINDS)}, "
                f"got {state.kind!r}"
            )
        if state.kind == "scaffolding":
            if not state.gauge_invariant_contractions:
                errors.append(
                    f"{state.name}: scaffolding HiddenState must declare at least one "
                    "gauge_invariant_contractions entry"
                )
            for obs_name in state.gauge_invariant_contractions:
                if obs_name not in observable_names:
                    errors.append(
                        f"{state.name}: declared contraction {obs_name!r} is not an "
                        "Observable in the node set"
                    )
        elif state.kind == "approximation":
            if state.gauge_invariant_contractions:
                errors.append(
                    f"{state.name}: approximation HiddenState should not declare "
                    "gauge_invariant_contractions (terminal by definition)"
                )

    # Edges reference nodes in the set
    for op in edges:
        for inp in op.inputs:
            if inp.name not in names_seen:
                errors.append(
                    f"operation {op.name!r} input {inp.name!r} not in node set"
                )
        for out in op.outputs:
            if out.name not in names_seen:
                errors.append(
                    f"operation {op.name!r} output {out.name!r} not in node set"
                )

    return errors
