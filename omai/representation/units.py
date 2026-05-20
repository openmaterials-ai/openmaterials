"""Units for the representation layer.

The operator layer carries dimensions (`omai.operator.dimensions`) but no
unit choice. Concrete units live here, each tagged with the operator
dimension it measures and a multiplicative factor to a canonical unit for
that dimension.

`conversion_factor(from_unit, to_unit)` is the multiplicative factor that,
applied to a value expressed in `from_unit`, yields the same physical
quantity expressed in `to_unit`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from omai.operator.dimensions import (
    Dimension,
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_VOLUME,
    FREQUENCY,
    LENGTH_TIMES_FREQUENCY,
    THERMAL_CONDUCTIVITY,
)


@dataclass(frozen=True)
class Unit:
    name: str
    dimension: Dimension
    to_operator: float


_E = 1.602176634e-19  # Joules per electron-volt


# Canonical frequency unit: linear_THz. Angular_THz = 2π × linear_THz.
LINEAR_THZ = Unit("linear_THz", FREQUENCY, 1.0)
ANGULAR_THZ = Unit("angular_THz", FREQUENCY, 1.0 / (2 * math.pi))


# Canonical heat-capacity unit: J/K. eV/K = e × J/K.
J_PER_K = Unit("J_per_K", ENERGY_PER_TEMPERATURE, 1.0)
EV_PER_K = Unit("eV_per_K", ENERGY_PER_TEMPERATURE, _E)


# Canonical volumetric heat capacity: J/(m³·K). ShengBTE's BTE.cv.
J_PER_M3_PER_K = Unit("J_per_m3_per_K", ENERGY_PER_TEMPERATURE_PER_VOLUME, 1.0)


# Canonical molar heat capacity: J/(K·mol). Phonopy's thermal-properties output.
J_PER_K_PER_MOL = Unit("J_per_K_per_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, 1.0)


# Canonical group-velocity unit: Å × linear_THz (= Å/ps).
ANGSTROM_LINEAR_THZ = Unit("angstrom_linear_THz", LENGTH_TIMES_FREQUENCY, 1.0)
# km/s = nm × THz = 10 × Å × linear_THz. ShengBTE emits group velocities in km/s.
KM_PER_S = Unit("km_per_s", LENGTH_TIMES_FREQUENCY, 10.0)


# Canonical thermal-conductivity unit: W/(m·K).
W_PER_M_PER_K = Unit("W_per_m_per_K", THERMAL_CONDUCTIVITY, 1.0)


# Canonical molar-energy unit: J/mol. Phonopy's free_energy / internal_energy
# come in kJ/mol; convert factor is 1000.
J_PER_MOL = Unit("J_per_mol", ENERGY_PER_MOLE, 1.0)
KJ_PER_MOL = Unit("kJ_per_mol", ENERGY_PER_MOLE, 1000.0)


# Canonical FC3 unit: eV/Å³ (the "physicist's" form of the third potential
# derivative). kaldo / phono3py store FC3 numerically in eV/Å³ — this matches
# the canonical. ShengBTE's reader implicitly uses a mixed-dimension form
# eV/(Å²·nm) (= 0.1 × eV/Å³), captured at the convention layer on the FC3
# state, not as a separate unit here. See ForceConstants[order=3] in
# omai/thermal_transport/operator/nodes.py for the `fc3_normalization`
# convention that handles the 10× cross-code factor.
EV_PER_A3 = Unit("eV_per_A3", ENERGY_PER_LENGTH_CUBED, 1.0)


# Dimensionless quantities (Born charges in units of e, dielectric tensor).
DIMENSIONLESS_UNIT = Unit("dimensionless", DIMENSIONLESS, 1.0)


UNITS: dict[str, Unit] = {
    u.name: u
    for u in [
        LINEAR_THZ,
        ANGULAR_THZ,
        J_PER_K,
        EV_PER_K,
        J_PER_M3_PER_K,
        J_PER_K_PER_MOL,
        ANGSTROM_LINEAR_THZ,
        KM_PER_S,
        W_PER_M_PER_K,
        J_PER_MOL,
        KJ_PER_MOL,
        EV_PER_A3,
        DIMENSIONLESS_UNIT,
    ]
}


def conversion_factor(from_unit: str, to_unit: str) -> float:
    a = UNITS[from_unit]
    b = UNITS[to_unit]
    if a.dimension != b.dimension:
        raise ValueError(
            f"cannot convert {from_unit} ({a.dimension.name}) to "
            f"{to_unit} ({b.dimension.name}): different dimensions"
        )
    return a.to_operator / b.to_operator
