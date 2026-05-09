"""Units for the materialization layer.

The abstract layer carries dimensions (`omai.abstract.dimensions`) but no
unit choice. Concrete units live here, each tagged with the abstract
dimension it measures and a multiplicative factor to a canonical unit for
that dimension.

`conversion_factor(from_unit, to_unit)` is the multiplicative factor that,
applied to a value expressed in `from_unit`, yields the same physical
quantity expressed in `to_unit`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from omai.abstract.dimensions import (
    Dimension,
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
)


@dataclass(frozen=True)
class Unit:
    name: str
    dimension: Dimension
    to_canonical: float


_E = 1.602176634e-19  # Joules per electron-volt


# Canonical frequency unit: linear_THz. Angular_THz = 2π × linear_THz.
LINEAR_THZ = Unit("linear_THz", FREQUENCY, 1.0)
ANGULAR_THZ = Unit("angular_THz", FREQUENCY, 1.0 / (2 * math.pi))


# Canonical heat-capacity unit: J/K. eV/K = e × J/K.
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
