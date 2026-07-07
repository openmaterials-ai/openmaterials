"""Physical dimensions for the operator layer.

The operator layer is unit-free (Principle 2): observables and
parameters carry a *dimension* but no unit choice. Units appear only on
representations, declared by adapters.

A Dimension is no longer a flat name-tag: it carries an exponent vector
over the seven SI base dimensions (M, L, T, Theta, N, I, J), with an
opaque escape hatch (exponents = None) for deliberately unmodeled
internals (Potential, Structure, Trajectory fields, the ACF kinds typed
OPAQUE). Multiplication, division, and integer powers compose the
exponents; equality and hash go by exponents (opaque dimensions compare
by name). Every existing named constant keeps its exact name and its call
sites, so serialized data that writes `dimension.name` is unaffected.

The `canonical()` string is the deterministic base-ordered rendering of
the exponents; it becomes part of node identity in kernel P2, so its form
must stay stable (fixed base order, fixed-length integer exponents).
"""

from __future__ import annotations

from dataclasses import dataclass


_BASE = ("M", "L", "T", "Th", "N", "I", "J")


def _synth_name(exps: tuple[int, ...]) -> str:
    """Name for a dimension synthesized by algebra.

    Synthesized (transient) dimensions are anonymous results of mul / div /
    pow; naming them by their canonical string keeps them printable without
    minting a registry entry. The named constants below pass explicit names
    instead, so their `.name` is stable for serialization.
    """
    parts = [f"{b}^{e}" for b, e in zip(_BASE, exps) if e != 0]
    return " ".join(parts) if parts else "1"


@dataclass(frozen=True, eq=False)
class Dimension:
    name: str
    exponents: tuple[int, int, int, int, int, int, int] | None = None

    @property
    def is_opaque(self) -> bool:
        return self.exponents is None

    def __eq__(self, other):
        if not isinstance(other, Dimension):
            return NotImplemented
        if self.is_opaque or other.is_opaque:
            return self.is_opaque and other.is_opaque and self.name == other.name
        return self.exponents == other.exponents

    def __hash__(self):
        return hash(self.exponents) if not self.is_opaque else hash(("opaque", self.name))

    def _require_algebra(self, other):
        if self.is_opaque or (isinstance(other, Dimension) and other.is_opaque):
            raise ValueError("no dimension algebra on opaque dimensions")

    def __mul__(self, other):
        self._require_algebra(other)
        exps = tuple(a + b for a, b in zip(self.exponents, other.exponents))
        return Dimension(_synth_name(exps), exps)

    def __truediv__(self, other):
        self._require_algebra(other)
        exps = tuple(a - b for a, b in zip(self.exponents, other.exponents))
        return Dimension(_synth_name(exps), exps)

    def __pow__(self, k: int):
        self._require_algebra(self)
        exps = tuple(a * k for a in self.exponents)
        return Dimension(_synth_name(exps), exps)

    def canonical(self) -> str:
        if self.is_opaque:
            return f"opaque:{self.name}"
        parts = [f"{b}^{e}" for b, e in zip(_BASE, self.exponents) if e != 0]
        return " ".join(parts) if parts else "1"


# Base dimensions.
MASS = Dimension("mass", (1, 0, 0, 0, 0, 0, 0))
TIME = Dimension("time", (0, 0, 1, 0, 0, 0, 0))

DIMENSIONLESS = Dimension("dimensionless", (0, 0, 0, 0, 0, 0, 0))
FREQUENCY = Dimension("frequency", (0, 0, -1, 0, 0, 0, 0))
ENERGY = Dimension("energy", (1, 2, -2, 0, 0, 0, 0))
LENGTH = Dimension("length", (0, 1, 0, 0, 0, 0, 0))
TEMPERATURE = Dimension("temperature", (0, 0, 0, 1, 0, 0, 0))
ENERGY_PER_TEMPERATURE = Dimension("energy_per_temperature", (1, 2, -2, -1, 0, 0, 0))
ENERGY_PER_TEMPERATURE_PER_VOLUME = Dimension(
    "energy_per_temperature_per_volume", (1, -1, -2, -1, 0, 0, 0)
)
ENERGY_PER_TEMPERATURE_PER_MOLE = Dimension(
    "energy_per_temperature_per_mole", (1, 2, -2, -1, -1, 0, 0)
)
ENERGY_PER_MOLE = Dimension("energy_per_mole", (1, 2, -2, 0, -1, 0, 0))
LENGTH_TIMES_FREQUENCY = Dimension("length_times_frequency", (0, 1, -1, 0, 0, 0, 0))
ENERGY_PER_LENGTH_SQUARED = Dimension("energy_per_length_squared", (1, 0, -2, 0, 0, 0, 0))
ENERGY_PER_LENGTH_CUBED = Dimension("energy_per_length_cubed", (1, -1, -2, 0, 0, 0, 0))
THERMAL_CONDUCTIVITY = Dimension("thermal_conductivity", (1, 1, -3, -1, 0, 0, 0))
# MD-primitive dimensions (phase 2 P2). length_per_time and
# length_times_frequency are both velocity, so they share exponents and
# compare equal by design.
LENGTH_PER_TIME = Dimension("length_per_time", (0, 1, -1, 0, 0, 0, 0))
LENGTH_SQUARED = Dimension("length_squared", (0, 2, 0, 0, 0, 0, 0))  # MeanSquaredDisplacement
# Heat current density carries energy × velocity, i.e. (energy / area) × (length /
# time). For per-volume J the canonical SI unit is W/m² (= J / (s · m²)); we
# spell the dimension out as energy × length / time to keep the chain unambiguous.
ENERGY_TIMES_LENGTH_PER_TIME = Dimension(
    "energy_times_length_per_time", (1, 3, -3, 0, 0, 0, 0)
)
OPAQUE = Dimension("opaque")  # for parameter states like Potential whose internal structure is unmodeled
VOLUME = Dimension("volume", (0, 3, 0, 0, 0, 0, 0))
DIFFUSIVITY = Dimension("diffusivity", (0, 2, -1, 0, 0, 0, 0))  # length^2 / time


DIMENSIONS: dict[str, Dimension] = {
    d.name: d
    for d in [
        MASS,
        TIME,
        DIMENSIONLESS,
        FREQUENCY,
        ENERGY,
        LENGTH,
        TEMPERATURE,
        ENERGY_PER_TEMPERATURE,
        ENERGY_PER_TEMPERATURE_PER_VOLUME,
        ENERGY_PER_TEMPERATURE_PER_MOLE,
        ENERGY_PER_MOLE,
        LENGTH_TIMES_FREQUENCY,
        ENERGY_PER_LENGTH_SQUARED,
        ENERGY_PER_LENGTH_CUBED,
        THERMAL_CONDUCTIVITY,
        LENGTH_PER_TIME,
        LENGTH_SQUARED,
        ENERGY_TIMES_LENGTH_PER_TIME,
        OPAQUE,
        VOLUME,
        DIFFUSIVITY,
    ]
}
