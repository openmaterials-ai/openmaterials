"""Abstract nodes (states) of the DAG.

Two concrete kinds, both inheriting from `State`:

  Observable    — a gauge-invariant first-class node. Cross-code agreement
                  is REQUIRED at this node (after spec-derived unit and
                  convention conversion). The substrate's compare() returns
                  pass/fail verdicts here.

  HiddenState   — an adapter-internal, gauge-dependent abstract node. Not
                  cross-code comparable per-element. Useful as a name for
                  computational scaffolding (per-mode arrays in a basis-
                  dependent representation, intermediate sums) that an
                  adapter produces on its way to an Observable, but whose
                  per-element content is determined by gauge / basis /
                  summation choices that the substrate does not pin down.
                  compare() on a HiddenState without a contraction returns
                  status=NOT_COMPARABLE.

Each state carries a tuple of Fields — typed slots declaring the named
quantities (with dimension and index signature) the materialization holds.
Fields used to be called "Observable" (confusingly, same name as the
outer node-level concept); they have been renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from omai.abstract.dimensions import Dimension
from omai.abstract.physics_types import PhysicsType


@dataclass(frozen=True)
class Field:
    name: str
    dimension: Dimension
    indices: tuple[str, ...] = ()
    """Symbolic index signature: which indices the field carries.

    Examples:
      omega:  ("q", "nu")            — phonon frequency
      v:      ("alpha", "q", "nu")   — group velocity component
      Phi^2:  ("i", "j", "R")        — atomic-pair force constant
      kappa:  ("alpha", "beta")      — Cartesian rank-2 tensor

    Empty for scalar / opaque fields (Temperature, Potential).
    The indices listed here must match those used in the sympy formula
    on any operation that produces this state.
    """


@dataclass(frozen=True, eq=False)
class State:
    """Base class for abstract DAG nodes. Use Observable or HiddenState directly."""

    physics_type: PhysicsType
    name: str
    fields: tuple[Field, ...] = ()
    canonical_conventions: dict[str, str] = dc_field(default_factory=dict)
    convention_factors: tuple[tuple[str, str, str, float], ...] = ()
    type_parameters: dict[str, int | str] = dc_field(default_factory=dict)
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return NotImplemented
        return self.name == other.name

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"state {self.name!r} has no field {name!r}")

    @property
    def is_observable(self) -> bool:
        """True if cross-code agreement is required at this node."""
        return isinstance(self, Observable)


@dataclass(frozen=True, eq=False)
class Observable(State):
    """A gauge-invariant first-class node in the DAG.

    Cross-code agreement is REQUIRED. Adapters that materialize an
    Observable must produce data that agrees (after unit/convention
    conversion) with other adapters' materializations of the same
    Observable, to within their declared tolerance.
    """


@dataclass(frozen=True, eq=False)
class HiddenState(State):
    """An adapter-internal, gauge-dependent abstract node.

    Not cross-code comparable per-element. Adapters can name and
    materialize HiddenStates for inspection within a single run, but
    the substrate refuses to make a pass/fail verdict on a per-element
    comparison across adapters; the per-element values reflect gauge /
    basis / summation choices that the substrate does not pin down.

    To compare two adapters' HiddenState materializations meaningfully,
    contract them into an Observable (or pass a contraction callable
    to compare()).

    Discipline fields (substrate-enforced via validate_substrate):

      gauge_group: a named identifier for the gauge equivalence that
        acts on this state. Free-form for Level 1; in Level 2 this is
        an actual GaugeAction with a sympy transformation that the
        substrate uses to prove invariance of downstream Observables.

      kind: 'scaffolding' if this HiddenState is consumed by a downstream
        operation that produces an Observable (so the gauge orbit is
        eventually summed away); 'approximation' if this HiddenState is
        terminal — an approximation of an Observable that happens to
        break gauge invariance, with no downstream Observable to
        recover from it (e.g., κ[bte_solver=rta]).

      gauge_invariant_contractions: names of Observable nodes in the
        DAG that capture the gauge-invariant content of this state.
        Empty for 'approximation' kind. The validator checks each
        name resolves to an Observable in NODES.
    """

    gauge_group: str = ""
    kind: str = "scaffolding"  # "scaffolding" or "approximation"
    gauge_invariant_contractions: tuple[str, ...] = ()
