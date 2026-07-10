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
    ELECTRICAL_CONDUCTIVITY,
    FORCE,
    FREQUENCY,
    FREQUENCY_SQUARED,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    MAGNETIC_MOMENT,
    MASS_DENSITY,
    MOBILITY,
    SEEBECK,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
    THERMAL_EXPANSIVITY,
    VOLTAGE,
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
# Surface energy shares the M T^-2 exponents with the force constants (energy
# per area vs force per length: same dimension, different quantities, kept
# apart by the surface_energy quantity tag). Canonical stays eV/Å² (the map's
# eV-Å family); 1 eV/Å² = 1.602176634e-19 J / 1e-20 m² = 16.021766339999996
# J/m² (full precision; mat-surface-energy truncates to 16.0218), so
# 1 J/m² = 1/16.021766339999996 eV/Å².
J_PER_M2 = Unit("J_per_m2", ENERGY_PER_LENGTH_SQUARED, 1.0 / 16.021766339999996)


# Energy units for the DFT ground state. JOULE stays the canonical ENERGY unit
# (to_operator 1.0); eV and Ry are the forms QE and most electronic-structure
# codes emit. 1 eV = 1.602176634e-19 J (exact, CODATA e). 1 Ry =
# 13.605693122994 eV (CODATA Rydberg energy), so its to_operator to Joules is
# 13.605693122994 * 1.602176634e-19.
EV = Unit("ev", ENERGY, _E)
RY = Unit("ry", ENERGY, 13.605693122994 * _E)
# eV per atom: the phase-diagram currency (formation energies, hull
# distances). Numerically identical to eV: the per-atom character belongs to
# the QUANTITY (formation_energy, energy_above_hull are intensive per-atom
# nodes), not to the unit, which measures plain energy. Registered as its own
# name so specs and instances state the convention explicitly.
EV_PER_ATOM = Unit("ev_per_atom", ENERGY, _E)


# Force units. Canonical: eV/Å (to_operator 1.0); its absolute SI scale is
# 1 eV/Å = 1.602176634e-19 J / 1e-10 m = 1.602176634e-9 N. QE prints forces in
# Ry/bohr ("Ry/au"), whose factor to eV/Å is Ry[eV] / bohr[Å] =
# 13.605693122994 / 0.529177210903 = 25.71104309541616.
EV_PER_A = Unit("eV_per_A", FORCE, 1.0, si_scale=1.602176634e-9)
RY_PER_BOHR = Unit("Ry_per_bohr", FORCE, 13.605693122994 / 0.529177210903)


# Pressure / stress units, sharing the ENERGY_PER_LENGTH_CUBED dimension with
# the FC3 canonical eV/Å³ (EV_PER_A3, to_operator 1.0). Derivation:
# 1 eV/Å³ = 1.602176634e-19 J / 1e-30 m³ = 1.602176634e11 Pa, so
# 1 Pa = 1 / 1.602176634e11 eV/Å³. Then 1 kbar = 1e8 Pa =
# 1e8 / 1.602176634e11 = 6.241509074460763e-4 eV/Å³, and 1 GPa = 1e9 Pa =
# 6.241509074460763e-3 eV/Å³ (so kbar -> GPa is exactly 0.1).
KBAR = Unit("kbar", ENERGY_PER_LENGTH_CUBED, 6.241509074460763e-4)
GPA = Unit("GPa", ENERGY_PER_LENGTH_CUBED, 6.241509074460763e-3)
# 1 Pa = 1e-9 GPa. Registered because pymatgen's ElasticTensor.y_mod emits the
# Young's modulus in SI pascal (elastic.py:199-204, a 9.0e9 factor over its
# eV/A^3 moduli), a 1e9 trap against the GPa the mat-* skills report.
PA = Unit("Pa", ENERGY_PER_LENGTH_CUBED, 6.241509074460763e-12)


# Canonical length unit: Å (angstrom). Canonical volume unit: Å³.
ANGSTROM = Unit("angstrom", LENGTH, 1.0, si_scale=1e-10)
ANGSTROM_CUBED = Unit("angstrom_cubed", VOLUME, 1.0, si_scale=1e-30)


# Dimensionless quantities (Born charges in units of e, dielectric tensor).
DIMENSIONLESS_UNIT = Unit("dimensionless", DIMENSIONLESS, 1.0, si_scale=1.0)


# Canonical voltage unit: the SI volt (energy per charge). eV per elementary
# charge = 1 V exactly, so intercalation voltages computed as eV energy
# differences over n electrons are already in volts with no extra factor.
VOLT = Unit("volt", VOLTAGE, 1.0, si_scale=1.0)


# Canonical magnetic-moment unit: the Bohr magneton, the currency of every
# spin-polarized DFT output (VASP MAGMOM/magnetization, MP total_magnetization,
# QE site moments). Absolute SI scale: mu_B = 9.2740100783e-24 J/T = A m^2
# (CODATA 2018).
MU_B = Unit("mu_B", MAGNETIC_MOMENT, 1.0, si_scale=9.2740100783e-24)


# Canonical electrical-conductivity unit: the SI siemens per metre (S/m). The
# pymatgen-analysis-diffusion Nernst-Einstein conductivity is emitted in
# mS/cm; 1 S/m = 10 mS/cm, so mS/cm carries to_operator 0.1 to the canonical
# S/m. (1 S/cm would be 100; the skills report mS/cm.)
S_PER_M = Unit("s_per_m", ELECTRICAL_CONDUCTIVITY, 1.0, si_scale=1.0)
MS_PER_CM = Unit("ms_per_cm", ELECTRICAL_CONDUCTIVITY, 0.1)


# Canonical Seebeck unit: volt per kelvin (V/K). amset serializes the Seebeck
# coefficient in microvolts per kelvin (the raw V/K multiplied by 1e6,
# transport.py:191; header 'S [muV/K]', the micro-sign U+00B5 in the source
# rendered ASCII here), so muv_per_k carries to_operator 1e-6 to the canonical
# V/K.
V_PER_K = Unit("v_per_k", SEEBECK, 1.0, si_scale=1.0)
MUV_PER_K = Unit("muv_per_k", SEEBECK, 1e-6)


# Canonical mobility unit: metre squared per volt-second (m^2/(V.s)). amset
# serves carrier mobility in cm^2/(V.s) (transport.py:133-135); 1 cm^2 = 1e-4
# m^2, so cm2_per_v_s carries to_operator 1e-4 to the canonical m^2/(V.s).
M2_PER_V_S = Unit("m2_per_v_s", MOBILITY, 1.0, si_scale=1.0)
CM2_PER_V_S = Unit("cm2_per_v_s", MOBILITY, 1e-4)


# Canonical thermal-expansivity unit: reciprocal kelvin (1/K). The volumetric
# thermal expansion coefficient alpha = (1/V)(dV/dT)_P; phonopy / matcalc QHACalc
# serve it directly in 1/K (thermal_expansion_coefficients, _qha.py:298), so
# per_kelvin is canonical with to_operator 1.0.
PER_KELVIN = Unit("per_kelvin", THERMAL_EXPANSIVITY, 1.0, si_scale=1.0)


# Canonical mass-density unit: gram per cubic centimetre (g/cm^3), the LAMMPS
# metal-unit MD thermo 'density' column. The SI kg/m^3 is 1e-3 g/cm^3
# (1000 g / 1e6 cm^3 = 1e-3 g/cm^3), so kg_per_m3 carries to_operator 1e-3 to
# the canonical g/cm^3. Absolute SI scale of g/cm^3 is 1000 kg/m^3.
GRAM_PER_CM3 = Unit("gram_per_cm3", MASS_DENSITY, 1.0, si_scale=1000.0)
KG_PER_M3 = Unit("kg_per_m3", MASS_DENSITY, 1e-3)


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
        J_PER_M2,
        EV,
        RY,
        EV_PER_ATOM,
        EV_PER_A,
        RY_PER_BOHR,
        KBAR,
        GPA,
        PA,
        ANGSTROM,
        ANGSTROM_CUBED,
        DIMENSIONLESS_UNIT,
        VOLT,
        MU_B,
        S_PER_M,
        MS_PER_CM,
        V_PER_K,
        MUV_PER_K,
        M2_PER_V_S,
        CM2_PER_V_S,
        PER_KELVIN,
        GRAM_PER_CM3,
        KG_PER_M3,
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
