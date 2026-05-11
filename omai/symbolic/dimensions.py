"""Physical dimensions for the symbolic layer.

The symbolic layer is unit-free (Principle 2): observables and
parameters carry a *dimension* but no unit choice. Units appear only on
materializations, declared by adapters.

A Dimension is a tag, not a quantity. We use a closed registry to keep the
surface small and Lean-transliterable (Principle 10, closed unions).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    name: str


DIMENSIONLESS = Dimension("dimensionless")
FREQUENCY = Dimension("frequency")
ENERGY = Dimension("energy")
LENGTH = Dimension("length")
TEMPERATURE = Dimension("temperature")
ENERGY_PER_TEMPERATURE = Dimension("energy_per_temperature")
ENERGY_PER_TEMPERATURE_PER_VOLUME = Dimension("energy_per_temperature_per_volume")
ENERGY_PER_TEMPERATURE_PER_MOLE = Dimension("energy_per_temperature_per_mole")
LENGTH_TIMES_FREQUENCY = Dimension("length_times_frequency")
ENERGY_PER_LENGTH_SQUARED = Dimension("energy_per_length_squared")
ENERGY_PER_LENGTH_CUBED = Dimension("energy_per_length_cubed")
THERMAL_CONDUCTIVITY = Dimension("thermal_conductivity")
OPAQUE = Dimension("opaque")  # for parameter states like Potential whose internal structure is unmodeled


DIMENSIONS: dict[str, Dimension] = {
    d.name: d
    for d in [
        DIMENSIONLESS,
        FREQUENCY,
        ENERGY,
        LENGTH,
        TEMPERATURE,
        ENERGY_PER_TEMPERATURE,
        ENERGY_PER_TEMPERATURE_PER_VOLUME,
        ENERGY_PER_TEMPERATURE_PER_MOLE,
        LENGTH_TIMES_FREQUENCY,
        ENERGY_PER_LENGTH_SQUARED,
        ENERGY_PER_LENGTH_CUBED,
        THERMAL_CONDUCTIVITY,
        OPAQUE,
    ]
}
