"""phono3py adapter specs for the thermal-transport DAG.

Constructed against the abstract DAG in
`omai.thermal_transport.symbolic`. Cross-code comparison happens at the
substrate level (Principle 7) via the shared abstract states; differences
surface as unit factors, convention mismatches, and discretization choice
mismatches.

References to the phono3py API (https://phonopy.github.io/phono3py/):
  * thermal_conductivity.gamma                 — Gamma_qν in linear THz
  * thermal_conductivity.mode_heat_capacities  — c_qν(T) in eV/K
  * Phono3py.sigmas[0]                          — Gaussian stdev, linear THz
"""

from __future__ import annotations

from omai.materialization.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.symbolic import (
    HEAT_CAPACITY,
    LINEWIDTH,
    compute_heat_capacity,
    compute_linewidth,
)


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
