"""Representation-layer adapter specs.

A StateAdapterSpec declares one code's claim about a node (operator State):
  * the unit each observable is in (within that code's natural emission)
  * the convention each observable carries (overrides of canonical)

An OperationAdapterSpec declares one code's claim about an edge (operator
Operation):
  * the unit each parameter is in (within that code's API surface)
  * the algorithmic-convention overrides
  * the discretization choices the code makes (e.g., BZ summation strategy);
    these don't change *what* is computed, only *how*, so they live here
    rather than on the operator Operation.

Cross-adapter agreement is checked at the State level (the observable layer,
per Principle 7). Operation-level adapter specs are diagnostic:
they describe how each code performs the operation; mismatches don't yield
a numerical conversion factor but flag where the codes do something
algorithmically different.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omai.operator.operation import Operation
from omai.operator.state import State
from omai.representation.units import conversion_factor


@dataclass(frozen=True)
class StateAdapterSpec:
    state: State
    adapter_name: str
    observable_units: dict[str, str] = field(default_factory=dict)
    observable_convention_overrides: dict[str, str] = field(default_factory=dict)
    # Per-field native API name in the code. Used by tooling (visualization,
    # docs) to surface what a user actually calls to get this state's data
    # in the code. Example: kaldo's Linewidth → {"Gamma": "Phonons.bandwidth"};
    # shengbte's Linewidth → {"Gamma": "BTE.w_anharmonic"}. May be empty for
    # adapters where the API name lives in prose `notes` instead.
    code_api: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def declared_unit(self, observable_name: str) -> str:
        unit = self.observable_units.get(observable_name)
        if unit is not None:
            return unit
        # Canonical unit isn't declared at the operator level (the operator
        # layer is unit-free); the representation layer either declares a
        # unit or refuses to compare. Most scaffolding specs (Temperature,
        # FC2/FC3, DM, MFD, ...) intentionally omit units — they exist to
        # mark coverage on the DAG, not to support numerical comparison.
        raise KeyError(
            f"adapter {self.adapter_name!r} has no unit declared for "
            f"observable {observable_name!r} of state {self.state.name!r} "
            f"— cannot canonicalise. Add an observable_units entry "
            f"({{'{observable_name}': '<unit_name>'}}) to its StateAdapterSpec, "
            f"or operate on the canonical (operator-form) Representation."
        )

    def declared_convention(self, convention_name: str) -> str:
        if convention_name in self.observable_convention_overrides:
            return self.observable_convention_overrides[convention_name]
        if convention_name in self.state.canonical_conventions:
            return self.state.canonical_conventions[convention_name]
        raise KeyError(
            f"state {self.state.name!r} declares no convention {convention_name!r}"
        )

    def observable_convention_factor(self, observable_name: str) -> float:
        """Multiplicative factor scaling this adapter's output of `observable`
        relative to canonical, due to the adapter's declared convention values."""
        factor = 1.0
        for conv_name, conv_value, field_name, f in self.state.convention_factors:
            if field_name != observable_name:
                continue
            if self.declared_convention(conv_name) == conv_value:
                factor *= f
        return factor


@dataclass(frozen=True)
class OperationAdapterSpec:
    operation: Operation
    adapter_name: str
    parameter_units: dict[str, str] = field(default_factory=dict)
    algorithmic_convention_overrides: dict[str, str] = field(default_factory=dict)
    discretization_choices: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def declared_parameter_unit(self, parameter_name: str) -> str:
        unit = self.parameter_units.get(parameter_name)
        if unit is None:
            raise KeyError(
                f"adapter {self.adapter_name!r} did not declare a unit for "
                f"parameter {parameter_name!r} of operation {self.operation.name!r}"
            )
        return unit

    def declared_algorithmic_convention(self, convention_name: str) -> str:
        if convention_name in self.algorithmic_convention_overrides:
            return self.algorithmic_convention_overrides[convention_name]
        if convention_name in self.operation.algorithmic_conventions:
            return self.operation.algorithmic_conventions[convention_name]
        raise KeyError(
            f"operation {self.operation.name!r} declares no algorithmic "
            f"convention {convention_name!r}"
        )


# ---------------------------------------------------------------------------
# Cross-adapter helpers (state level)
# ---------------------------------------------------------------------------


def _require_same_state(a: StateAdapterSpec, b: StateAdapterSpec) -> None:
    if a.state != b.state:
        raise ValueError(
            f"adapters wrap different states: "
            f"{a.state.name!r} vs {b.state.name!r}"
        )


def inter_representation_unit_factor(
    a: StateAdapterSpec, b: StateAdapterSpec, observable_name: str
) -> float:
    """Factor f such that A's emitted value × f = the same value in B's unit
    (ignoring any convention-driven scaling)."""
    _require_same_state(a, b)
    return conversion_factor(
        a.declared_unit(observable_name), b.declared_unit(observable_name)
    )


def inter_representation_factor(
    a: StateAdapterSpec, b: StateAdapterSpec, observable_name: str
) -> float:
    """Combined unit + convention factor: A's emitted value × this = B's
    emitted value for the same physical state.

    A_value × U_a→b × (c_b / c_a) = B_value
    where U_a→b is the unit factor and c_a, c_b are the observable-convention
    factors relative to canonical.
    """
    unit = inter_representation_unit_factor(a, b, observable_name)
    c_a = a.observable_convention_factor(observable_name)
    c_b = b.observable_convention_factor(observable_name)
    return unit * (c_b / c_a)


def representation_convention_match(
    a: StateAdapterSpec, b: StateAdapterSpec, convention_name: str
) -> tuple[bool, str]:
    """Whether two state adapters agree on a state-level convention."""
    _require_same_state(a, b)
    ca = a.declared_convention(convention_name)
    cb = b.declared_convention(convention_name)
    if ca == cb:
        return True, ""
    return False, (
        f"{a.adapter_name} uses {convention_name}={ca}; "
        f"{b.adapter_name} uses {convention_name}={cb}"
    )


# ---------------------------------------------------------------------------
# Cross-adapter helpers (operation level — diagnostic only)
# ---------------------------------------------------------------------------


def _require_same_operation(a: OperationAdapterSpec, b: OperationAdapterSpec) -> None:
    if a.operation != b.operation:
        raise ValueError(
            f"adapters wrap different operations: "
            f"{a.operation.name!r} vs {b.operation.name!r}"
        )


def representation_algorithmic_match(
    a: OperationAdapterSpec, b: OperationAdapterSpec, convention_name: str
) -> tuple[bool, str]:
    """Whether two operation adapters agree on an algorithmic convention."""
    _require_same_operation(a, b)
    ca = a.declared_algorithmic_convention(convention_name)
    cb = b.declared_algorithmic_convention(convention_name)
    if ca == cb:
        return True, ""
    return False, (
        f"{a.adapter_name} uses {convention_name}={ca}; "
        f"{b.adapter_name} uses {convention_name}={cb}"
    )


def representation_discretization_match(
    a: OperationAdapterSpec, b: OperationAdapterSpec, choice_name: str
) -> tuple[bool, str]:
    """Whether two operation adapters agree on a discretization choice
    (e.g., BZ summation strategy)."""
    _require_same_operation(a, b)
    ca = a.discretization_choices.get(choice_name, "<unspecified>")
    cb = b.discretization_choices.get(choice_name, "<unspecified>")
    if ca == cb:
        return True, ""
    return False, (
        f"{a.adapter_name} uses {choice_name}={ca}; "
        f"{b.adapter_name} uses {choice_name}={cb}"
    )
