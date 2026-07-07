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
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_VOLUME,
    FREQUENCY,
    FREQUENCY_SQUARED,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
    VOLUME,
)


@dataclass(frozen=True)
class Unit:
    name: str
    dimension: Dimension
    to_operator: float
    si_scale: float | None = None


_E = 1.602176634e-19  # Joules per electron-volt


# Canonical energy unit: Joule. Per-mode energies (Helmholtz free energy,
# internal energy) are bound in Joules by the executor's ℏ_eff convention.
JOULE = Unit("joule", ENERGY, 1.0, si_scale=1.0)


# Canonical temperature unit: Kelvin.
KELVIN = Unit("kelvin", TEMPERATURE, 1.0, si_scale=1.0)


# Canonical frequency unit: linear_THz. Angular_THz = 2π × linear_THz.
LINEAR_THZ = Unit("linear_THz", FREQUENCY, 1.0, si_scale=1e12)
ANGULAR_THZ = Unit("angular_THz", FREQUENCY, 1.0 / (2 * math.pi))
# Linear wavenumber: 1 cm⁻¹ = c·(100 m⁻¹) = 0.0299792458 linear THz. QE's
# matdyn.freq / matdyn.dos axis unit (ph.x prints THz and cm⁻¹ side by side).
INVERSE_CM = Unit("inverse_cm", FREQUENCY, 0.0299792458)


# Canonical frequency-squared unit: linear_THz². The dynamical-matrix
# eigenvalues are omega², so the canonical SI scale is (1e12)² = 1e24 s⁻²,
# keeping dimension_si_scale(frequency_squared) consistent with the square of
# the frequency scale (the executor's monomial bridge relies on this).
LINEAR_THZ_SQUARED = Unit("linear_THz_squared", FREQUENCY_SQUARED, 1.0, si_scale=1e24)


# Canonical heat-capacity unit: J/K. eV/K = e × J/K.
J_PER_K = Unit("J_per_K", ENERGY_PER_TEMPERATURE, 1.0, si_scale=1.0)
EV_PER_K = Unit("eV_per_K", ENERGY_PER_TEMPERATURE, _E)


# Canonical volumetric heat capacity: J/(m³·K). ShengBTE's BTE.cv.
J_PER_M3_PER_K = Unit("J_per_m3_per_K", ENERGY_PER_TEMPERATURE_PER_VOLUME, 1.0, si_scale=1.0)


# Canonical molar heat capacity: J/(K·mol). Phonopy's thermal-properties output.
J_PER_K_PER_MOL = Unit("J_per_K_per_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, 1.0, si_scale=1.0)


# Canonical group-velocity unit: Å × linear_THz (= Å/ps).
ANGSTROM_LINEAR_THZ = Unit("angstrom_linear_THz", LENGTH_TIMES_FREQUENCY, 1.0, si_scale=1e2)
# km/s = nm × THz = 10 × Å × linear_THz. ShengBTE emits group velocities in km/s.
KM_PER_S = Unit("km_per_s", LENGTH_TIMES_FREQUENCY, 10.0)


# Canonical thermal-conductivity unit: W/(m·K).
W_PER_M_PER_K = Unit("W_per_m_per_K", THERMAL_CONDUCTIVITY, 1.0, si_scale=1.0)


# Canonical molar-energy unit: J/mol. Phonopy's free_energy / internal_energy
# come in kJ/mol; convert factor is 1000.
J_PER_MOL = Unit("J_per_mol", ENERGY_PER_MOLE, 1.0, si_scale=1.0)
KJ_PER_MOL = Unit("kJ_per_mol", ENERGY_PER_MOLE, 1000.0)


# Canonical FC3 unit: eV/Å³ (the "physicist's" form of the third potential
# derivative). kaldo / phono3py store FC3 numerically in eV/Å³ — this matches
# the canonical. ShengBTE's reader implicitly uses a mixed-dimension form
# eV/(Å²·nm) (= 0.1 × eV/Å³), captured at the convention layer on the FC3
# state, not as a separate unit here. See ForceConstants[order=3] in
# omai/thermal_transport/operator/nodes.py for the `fc3_normalization`
# convention that handles the 10× cross-code factor.
EV_PER_A3 = Unit("eV_per_A3", ENERGY_PER_LENGTH_CUBED, 1.0)


# Canonical FC2 unit: eV/Å² (kaldo / phonopy / phono3py native). QE's dyn and
# flfrc files store force constants in Rydberg atomic units, Ry/bohr², with no
# unit string printed in the file; the factor is Ry[eV] / bohr[Å]² (CODATA).
EV_PER_A2 = Unit("eV_per_A2", ENERGY_PER_LENGTH_SQUARED, 1.0)
RY_PER_BOHR2 = Unit("Ry_per_bohr2", ENERGY_PER_LENGTH_SQUARED, 13.605693122994 / 0.529177210903**2)


# Canonical length unit: Å (angstrom). Canonical volume unit: Å³.
ANGSTROM = Unit("angstrom", LENGTH, 1.0, si_scale=1e-10)
ANGSTROM_CUBED = Unit("angstrom_cubed", VOLUME, 1.0, si_scale=1e-30)


# Dimensionless quantities (Born charges in units of e, dielectric tensor).
DIMENSIONLESS_UNIT = Unit("dimensionless", DIMENSIONLESS, 1.0, si_scale=1.0)


UNITS: dict[str, Unit] = {
    u.name: u
    for u in [
        JOULE,
        KELVIN,
        LINEAR_THZ,
        ANGULAR_THZ,
        INVERSE_CM,
        LINEAR_THZ_SQUARED,
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
        EV_PER_A2,
        RY_PER_BOHR2,
        ANGSTROM,
        ANGSTROM_CUBED,
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


def dimension_si_scale(dimension: Dimension) -> float:
    """Absolute SI scale of `dimension`'s canonical unit (the registered Unit
    with to_operator == 1.0). Raises ValueError if the dimension has no
    canonical unit with an si_scale set."""
    for u in UNITS.values():
        if u.dimension == dimension and u.to_operator == 1.0 and u.si_scale is not None:
            return u.si_scale
    raise ValueError(
        f"dimension {dimension.name!r} has no canonical unit with an si_scale; "
        f"register one in omai/representation/units.py"
    )
