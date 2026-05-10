"""kaldo adapter specs for the thermal-transport DAG.

Constructed against the abstract DAG in
`omai.thermal_transport.symbolic`. Cross-code comparison happens at the
substrate level (Principle 7) via the shared abstract states; differences
surface as unit factors, convention mismatches, and discretization choice
mismatches.

References to the kaldo API (https://nanotheorygroup.github.io/kaldo/):
  * Phonons.bandwidth     — the linewidth Gamma_qν, in angular THz
  * Phonons.heat_capacity — per-mode c_qν(T), in J/K
  * Phonons(third_bandwidth=σ) — broadening parameter, half-width-style
"""

from __future__ import annotations

from omai.materialization.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.symbolic.edges import (
    compute_heat_capacity,
    compute_linewidth,
)
from omai.thermal_transport.symbolic.nodes import (
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    THERMAL_CONDUCTIVITY_STATE,
)


KALDO_FREQUENCY = StateAdapterSpec(
    state=FREQUENCY_STATE,
    adapter_name="kaldo",
    observable_units={"omega": "linear_THz"},
    notes="Phonons.frequency in linear THz, shape (n_q, n_modes).",
)


KALDO_GROUP_VELOCITY = StateAdapterSpec(
    state=GROUP_VELOCITY,
    adapter_name="kaldo",
    observable_units={"v": "angstrom_linear_THz"},
    notes="Phonons.velocity in Å·THz, shape (n_q, n_modes, 3).",
)


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


KALDO_THERMAL_CONDUCTIVITY = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_STATE,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    notes=(
        "Conductivity(method='rta'|'inverse'|'sc').conductivity in "
        "W/(m·K), tensor shape (3, 3) per direction."
    ),
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
