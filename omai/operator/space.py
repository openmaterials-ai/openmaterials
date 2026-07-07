"""Operator nodes (spaces) of the DAG.

Two concrete kinds, both inheriting from `Space`:

  ObservableSpace  — a gauge-invariant first-class node. Cross-code agreement
                     is REQUIRED at this node (after spec-derived unit and
                     normalization conversion). The operator layer's compare()
                     returns pass/fail verdicts here.

  HiddenSpace      — an adapter-internal, gauge-dependent operator node. Not
                     cross-code comparable per-element. Useful as a name for
                     computational scaffolding (per-mode arrays in a basis-
                     dependent representation, intermediate sums) that an
                     adapter produces on its way to an ObservableSpace, but
                     whose per-element content is determined by gauge / basis /
                     summation choices that the operator layer does not pin
                     down. compare() on a HiddenSpace without a contraction
                     returns status=NOT_COMPARABLE.

Each `Space` carries a tuple of `Field`s — typed slots declaring the named
quantities (with dimension and index signature) the representation holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from omai.operator.dimensions import Dimension


@dataclass(frozen=True)
class Field:
    name: str
    dimension: Dimension
    indices: tuple[str, ...] = ()
    """Operator index signature: which indices the field carries.

    Examples:
      omega:  ("q", "nu")            — phonon frequency
      v:      ("alpha", "q", "nu")   — group velocity component
      Phi^2:  ("i", "j", "R")        — atomic-pair force constant
      kappa:  ("alpha", "beta")      — Cartesian rank-2 tensor

    Empty for scalar / opaque fields (Temperature, Potential).
    The indices listed here must match those used in the sympy formula
    on any operator that produces this space.
    """


@dataclass(frozen=True, eq=False)
class Space:
    """Base class for operator DAG nodes. Use ObservableSpace or HiddenSpace directly."""

    name: str
    fields: tuple[Field, ...] = ()
    labels: dict[str, int | str] = dc_field(default_factory=dict)
    description: str = ""
    tier: str = ""
    """Authored physics-stage grouping for the map's layered layout
    (e.g. 'Sources', 'Harmonic', 'Transport'). Empty means untiered; the
    map places untiered nodes in a trailing 'Other' band. Not part of
    identity: __hash__/__eq__ remain name-based."""

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Space):
            return NotImplemented
        return self.name == other.name

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"space {self.name!r} has no field {name!r}")

    @property
    def is_observable(self) -> bool:
        """True if cross-code agreement is required at this node."""
        return isinstance(self, ObservableSpace)


@dataclass(frozen=True, eq=False)
class ObservableSpace(Space):
    """A gauge-invariant first-class node in the DAG.

    Cross-code agreement is REQUIRED. Adapters that represent an
    ObservableSpace must produce data that agrees (after unit/normalization
    conversion) with other adapters' representations of the same
    ObservableSpace, to within their declared tolerance.
    """


@dataclass(frozen=True, eq=False)
class HiddenSpace(Space):
    """An adapter-internal, gauge-dependent operator node.

    Not cross-code comparable per-element. Adapters can name and
    represent HiddenSpaces for inspection within a single run, but
    the operator layer refuses to make a pass/fail verdict on a per-element
    comparison across adapters; the per-element values reflect gauge /
    basis / summation choices that the operator layer does not pin down.

    To compare two adapters' HiddenSpace representations meaningfully,
    contract them into an ObservableSpace (or pass a contraction callable
    to compare()).

    Discipline fields (validated via validate_dag):

      gauge_group: a named identifier for the gauge equivalence that
        acts on this space. Free-form for Level 1; in Level 2 this is
        an actual GaugeAction with a sympy transformation that the
        operator layer uses to prove invariance of downstream observables.

      kind: 'scaffolding' if this HiddenSpace is consumed by a downstream
        operator that produces an ObservableSpace (so the gauge orbit is
        eventually summed away); 'approximation' if this HiddenSpace is
        terminal — an approximation of an ObservableSpace that happens to
        break gauge invariance, with no downstream ObservableSpace to
        recover from it (e.g., κ[bte_solver=rta]).

      gauge_invariant_contractions: names of ObservableSpace nodes in the
        DAG that capture the gauge-invariant content of this space.
        Empty for 'approximation' kind. The validator checks each
        name resolves to an ObservableSpace in NODES.
    """

    gauge_group: str = ""
    kind: str = "scaffolding"  # "scaffolding" or "approximation"
    gauge_invariant_contractions: tuple[str, ...] = ()
