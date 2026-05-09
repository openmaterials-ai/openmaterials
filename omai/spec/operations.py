"""Canonical operations registry.

Each entry declares the abstract operation: name, canonical units of its output
materialization, and canonical conventions of its parameterizable inputs.
Adapters consume these and override any deviations.
"""

from .core import Operation


COMPUTE_SCATTERING_RATES = Operation(
    name="compute_scattering_rates",
    description=(
        "Compute the imaginary self-energy / phonon linewidth Gamma_qν "
        "from third-order anharmonic interactions, energy/momentum "
        "conservation under the dirac-delta replacement, and Bose-"
        "Einstein population factors at temperature T."
    ),
    canonical_units={
        "linewidth": "linear_THz",
        "broadening_sigma": "linear_THz",
    },
    canonical_conventions={
        # Gaussian broadening kernel parameterization:
        #   "stdev"     — sigma is the standard deviation
        #   "halfwidth" — sigma is stdev × sqrt(2) (kaldo's choice)
        "broadening_param": "stdev",
        # BZ summation strategy for the triplet sum:
        #   "full_grid"        — enumerate all ordered triplets
        #   "symmetry_reduced" — iterate the reduced set with weights
        # The choice does not affect Sigma Gamma but redistributes per-mode Gamma.
        "bz_summation": "full_grid",
        # Definition of the output linewidth quantity:
        #   "imag_self_energy"            — Gamma = Im Sigma (canonical)
        #   "linewidth_2x_imag_self_energy" — Gamma = 2 Im Sigma (kaldo's choice)
        "gamma_definition": "imag_self_energy",
    },
    output_convention_scaling=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "linewidth", 2.0),
    ),
)


COMPUTE_HEAT_CAPACITY = Operation(
    name="compute_heat_capacity",
    description=(
        "Compute the per-mode quantum heat capacity c_qν(T) "
        "from the Bose-Einstein occupation at temperature T."
    ),
    canonical_units={
        "heat_capacity": "J_per_K",
    },
    canonical_conventions={},
)
