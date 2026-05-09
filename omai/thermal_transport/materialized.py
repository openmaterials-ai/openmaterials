"""Adapter specs for the thermal-transport DAG.

Per the substrate's Principle 7, cross-code agreement is checked at the
state (observable) level. State-adapter specs declare units and
state-level conventions; operation-adapter specs declare parameter units,
algorithmic-convention overrides, and discretization choices (the latter
being where BZ-summation strategy lives — it's a discretization choice,
not an abstract-operation property).
"""

from __future__ import annotations

from omai.spec.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.symbolic import (
    HEAT_CAPACITY,
    LINEWIDTH,
    compute_heat_capacity,
    compute_linewidth,
)


# ---------------------------------------------------------------------------
# kaldo
# ---------------------------------------------------------------------------

KALDO_LINEWIDTH = StateAdapterSpec(
    state=LINEWIDTH,
    adapter_name="kaldo",
    observable_units={"Gamma": "angular_THz"},
    observable_convention_overrides={
        "gamma_definition": "linewidth_2x_imag_self_energy",
    },
    notes=(
        "Phonons.bandwidth array is in angular THz, defined as the linewidth "
        "Gamma = 2 Im Sigma (factor of 2 from the linewidth-vs-self-energy "
        "convention)."
    ),
)

KALDO_HEAT_CAPACITY = StateAdapterSpec(
    state=HEAT_CAPACITY,
    adapter_name="kaldo",
    observable_units={"c": "J_per_K"},
    notes="Phonons.heat_capacity in J/K per mode.",
)


KALDO_COMPUTE_LINEWIDTH = OperationAdapterSpec(
    operation=compute_linewidth,
    adapter_name="kaldo",
    parameter_units={"broadening_sigma": "linear_THz"},
    algorithmic_convention_overrides={
        # kaldo's third_bandwidth parameter is interpreted as a half-width-
        # style param: σ_kaldo_input = stdev × √2.
        "broadening_param": "halfwidth",
    },
    discretization_choices={
        "bz_summation": "full_grid",
        "delta_cutoff_sigmas": "2",
        "degeneracy_averaging": "off",
    },
    notes=(
        "Iterates the full BZ grid (ordered triplets) with a 0.5 factor on "
        "the decay channel to compensate the double-count. Truncates the "
        "Gaussian at 2σ in the dirac-delta replacement."
    ),
)

KALDO_COMPUTE_HEAT_CAPACITY = OperationAdapterSpec(
    operation=compute_heat_capacity,
    adapter_name="kaldo",
    notes="No parameters or algorithmic conventions exposed.",
)


# ---------------------------------------------------------------------------
# phono3py
# ---------------------------------------------------------------------------

PHONO3PY_LINEWIDTH = StateAdapterSpec(
    state=LINEWIDTH,
    adapter_name="phono3py",
    observable_units={"Gamma": "linear_THz"},
    # No convention overrides: canonical "imag_self_energy".
    notes=(
        "thermal_conductivity.gamma in linear THz, defined as the imaginary "
        "self-energy Gamma = Im Sigma (no factor of 2)."
    ),
)

PHONO3PY_HEAT_CAPACITY = StateAdapterSpec(
    state=HEAT_CAPACITY,
    adapter_name="phono3py",
    observable_units={"c": "eV_per_K"},
    notes="thermal_conductivity.mode_heat_capacities in eV/K per mode.",
)


PHONO3PY_COMPUTE_LINEWIDTH = OperationAdapterSpec(
    operation=compute_linewidth,
    adapter_name="phono3py",
    parameter_units={"broadening_sigma": "linear_THz"},
    # No algorithmic convention overrides: canonical broadening_param=stdev.
    discretization_choices={
        "bz_summation": "symmetry_reduced",
        "delta_cutoff_sigmas": "infinity",
        "degeneracy_averaging": "on",
    },
    notes=(
        "Iterates symmetry-reduced triplets with explicit weights. "
        "ph3.sigmas[0] is the Gaussian stdev. Default no cutoff. "
        "average_by_degeneracy applied post-hoc to the per-mode Gamma."
    ),
)

PHONO3PY_COMPUTE_HEAT_CAPACITY = OperationAdapterSpec(
    operation=compute_heat_capacity,
    adapter_name="phono3py",
    notes="No parameters or algorithmic conventions exposed.",
)
