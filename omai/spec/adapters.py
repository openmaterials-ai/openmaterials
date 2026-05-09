"""Adapter specs for the operations defined in omai.spec.operations.

Each adapter spec declares, for one code, what its concrete output unit is and
what convention it uses for each parameterized input. The substrate uses these
to predict cross-adapter conversion factors and surface mismatches at
spec-load time, before any code is run.
"""

from .core import AdapterSpec
from .operations import COMPUTE_HEAT_CAPACITY, COMPUTE_SCATTERING_RATES


KALDO_COMPUTE_SCATTERING_RATES = AdapterSpec(
    operation=COMPUTE_SCATTERING_RATES,
    adapter_name="kaldo",
    unit_overrides={
        "linewidth": "angular_THz",
    },
    convention_overrides={
        "broadening_param": "halfwidth",
        "bz_summation": "full_grid",
        "gamma_definition": "linewidth_2x_imag_self_energy",
    },
    summation_strategy="full_grid_ordered_triplets_with_decay_half_factor",
    notes=(
        "Phonons.bandwidth array is in angular THz, defined as the linewidth "
        "Gamma = 2 Im Sigma. Phonons(third_bandwidth=sigma) interprets sigma "
        "as half-width (stdev = sigma / sqrt(2)). 2-sigma cutoff in the "
        "dirac-delta replacement. No degeneracy averaging applied post-hoc."
    ),
)

KALDO_COMPUTE_HEAT_CAPACITY = AdapterSpec(
    operation=COMPUTE_HEAT_CAPACITY,
    adapter_name="kaldo",
    unit_overrides={
        "heat_capacity": "J_per_K",
    },
    notes="Phonons.heat_capacity in J/K per mode.",
)


PHONO3PY_COMPUTE_SCATTERING_RATES = AdapterSpec(
    operation=COMPUTE_SCATTERING_RATES,
    adapter_name="phono3py",
    convention_overrides={
        "bz_summation": "symmetry_reduced",
    },
    summation_strategy="symmetry_reduced_triplets_with_weights",
    notes=(
        "thermal_conductivity.gamma in linear THz, defined as the imaginary "
        "self-energy Gamma = Im Sigma (no factor of 2). "
        "ph3.sigmas[0] interpreted as Gaussian standard deviation. "
        "Default no cutoff. average_by_degeneracy applied post-hoc."
    ),
)

PHONO3PY_COMPUTE_HEAT_CAPACITY = AdapterSpec(
    operation=COMPUTE_HEAT_CAPACITY,
    adapter_name="phono3py",
    unit_overrides={
        "heat_capacity": "eV_per_K",
    },
    notes="thermal_conductivity.mode_heat_capacities in eV/K per mode.",
)
