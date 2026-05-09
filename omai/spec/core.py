"""Operation and AdapterSpec: the substrate's symbolic conformance layer.

An Operation is the abstract description of a transformation between abstract
states. It declares the canonical units of its output materialization quantities
and the canonical conventions of its parameterized inputs (see substrate doc
Principles 2 and 6). Operations carry no unit choices and no convention choices
of their own.

An AdapterSpec is one code's claim about an Operation: which unit each output
quantity is in (within that code's natural emission), which convention each
input parameter follows. Differences from canonical surface mechanically as
conversion factors and convention mismatches.

The point: a 4π unit offset or a stdev-vs-halfwidth convention difference
between two adapters is visible at spec-load time, before any run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .units import conversion_factor


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    canonical_units: dict[str, str] = field(default_factory=dict)
    canonical_conventions: dict[str, str] = field(default_factory=dict)
    # Entries (parameter, value, quantity, factor) declaring that when this
    # `parameter` takes this `value`, the output `quantity` is scaled by
    # `factor` relative to the canonical convention. Canonical values
    # implicitly have factor 1.0 and need not be listed.
    output_convention_scaling: tuple[tuple[str, str, str, float], ...] = ()


@dataclass(frozen=True)
class AdapterSpec:
    operation: Operation
    adapter_name: str
    unit_overrides: dict[str, str] = field(default_factory=dict)
    convention_overrides: dict[str, str] = field(default_factory=dict)
    summation_strategy: str = "unspecified"
    notes: str = ""

    def declared_unit(self, quantity: str) -> str:
        canonical = self.operation.canonical_units.get(quantity)
        if canonical is None:
            raise KeyError(
                f"operation {self.operation.name!r} declares no quantity {quantity!r}"
            )
        return self.unit_overrides.get(quantity, canonical)

    def declared_convention(self, parameter: str) -> str:
        canonical = self.operation.canonical_conventions.get(parameter)
        if canonical is None:
            raise KeyError(
                f"operation {self.operation.name!r} declares no parameter {parameter!r}"
            )
        return self.convention_overrides.get(parameter, canonical)


def _require_same_operation(a: AdapterSpec, b: AdapterSpec) -> None:
    if a.operation != b.operation:
        raise ValueError(
            f"adapters wrap different operations: "
            f"{a.operation.name!r} vs {b.operation.name!r}"
        )


def cross_adapter_unit_factor(a: AdapterSpec, b: AdapterSpec, quantity: str) -> float:
    """Factor f such that A's emitted value × f = the same value in B's unit
    (ignoring any output-convention scaling)."""
    _require_same_operation(a, b)
    return conversion_factor(a.declared_unit(quantity), b.declared_unit(quantity))


def output_convention_factor(spec: AdapterSpec, quantity: str) -> float:
    """How much spec's emitted value of `quantity` is scaled relative to
    canonical, due to its declared (non-canonical) convention values."""
    factor = 1.0
    for parameter, value, q, f in spec.operation.output_convention_scaling:
        if q != quantity:
            continue
        if spec.declared_convention(parameter) == value:
            factor *= f
    return factor


def cross_adapter_total_factor(a: AdapterSpec, b: AdapterSpec, quantity: str) -> float:
    """Combined unit + convention factor: A's emitted value × this = B's emitted value
    for the same physical state.

    Decomposition:
      A_value × U_a→b × (c_b / c_a) = B_value
    where U_a→b is the unit factor and c_a, c_b are the output-convention factors
    relative to canonical.
    """
    unit = cross_adapter_unit_factor(a, b, quantity)
    c_a = output_convention_factor(a, quantity)
    c_b = output_convention_factor(b, quantity)
    return unit * (c_b / c_a)


def cross_adapter_convention_match(
    a: AdapterSpec, b: AdapterSpec, parameter: str
) -> tuple[bool, str]:
    """Whether two adapters agree on a parameter convention."""
    _require_same_operation(a, b)
    ca = a.declared_convention(parameter)
    cb = b.declared_convention(parameter)
    if ca == cb:
        return True, ""
    return False, (
        f"{a.adapter_name} uses {parameter}={ca}; "
        f"{b.adapter_name} uses {parameter}={cb}"
    )
