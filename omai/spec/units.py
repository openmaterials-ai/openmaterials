"""Units and dimensions for substrate-level adapter conformance.

Abstract states are unit-free; materializations carry unit declarations supplied
by their adapter (Principle 2 of the substrate doc). The substrate normalizes to
a canonical unit before any cross-adapter comparison.

This module defines:
  * Dimension: a physical dimension (frequency, energy_per_temperature, ...)
  * Unit: a specific unit choice with a multiplicative conversion factor to the
    canonical unit for its dimension
  * UNITS: a registry of all known units, keyed by name
  * conversion_factor(from_unit, to_unit): a multiplicative factor that, when
    applied to a value expressed in `from_unit`, yields the same physical
    quantity expressed in `to_unit`
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    name: str


@dataclass(frozen=True)
class Unit:
    name: str
    dimension: Dimension
    to_canonical: float


_E = 1.602176634e-19  # Joules per electron-volt


FREQUENCY = Dimension("frequency")
LINEAR_THZ = Unit("linear_THz", FREQUENCY, 1.0)
ANGULAR_THZ = Unit("angular_THz", FREQUENCY, 1.0 / (2 * math.pi))


ENERGY_PER_TEMPERATURE = Dimension("energy_per_temperature")
J_PER_K = Unit("J_per_K", ENERGY_PER_TEMPERATURE, 1.0)
EV_PER_K = Unit("eV_per_K", ENERGY_PER_TEMPERATURE, _E)


UNITS: dict[str, Unit] = {
    u.name: u for u in [LINEAR_THZ, ANGULAR_THZ, J_PER_K, EV_PER_K]
}


def conversion_factor(from_unit: str, to_unit: str) -> float:
    a = UNITS[from_unit]
    b = UNITS[to_unit]
    if a.dimension != b.dimension:
        raise ValueError(
            f"cannot convert {from_unit} ({a.dimension.name}) to "
            f"{to_unit} ({b.dimension.name}): different dimensions"
        )
    return a.to_canonical / b.to_canonical
