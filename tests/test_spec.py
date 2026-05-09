"""Tests for the thermal-transport adapter conformance specs."""

from __future__ import annotations

import math

import pytest

from omai.spec import (
    conversion_factor,
    cross_operation_algorithmic_match,
    cross_operation_discretization_match,
    cross_state_convention_match,
    cross_state_total_factor,
    cross_state_unit_factor,
)
from omai.spec.thermal_transport import (
    KALDO_COMPUTE_HEAT_CAPACITY,
    KALDO_COMPUTE_LINEWIDTH,
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    PHONO3PY_COMPUTE_HEAT_CAPACITY,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
)


# --- units ---


def test_linear_thz_to_angular_thz_round_trip():
    f = conversion_factor("linear_THz", "angular_THz")
    assert math.isclose(f, 2 * math.pi)
    assert math.isclose(conversion_factor("angular_THz", "linear_THz"), 1.0 / (2 * math.pi))


def test_eV_per_K_to_J_per_K_is_boltzmann_factor():
    f = conversion_factor("eV_per_K", "J_per_K")
    assert math.isclose(f, 1.602176634e-19)


def test_dimension_mismatch_raises():
    with pytest.raises(ValueError, match="different dimensions"):
        conversion_factor("linear_THz", "J_per_K")


# --- state adapters: linewidth ---


def test_kaldo_linewidth_unit_is_angular_thz():
    assert KALDO_LINEWIDTH.declared_unit("Gamma") == "angular_THz"


def test_phono3py_linewidth_unit_is_linear_thz():
    assert PHONO3PY_LINEWIDTH.declared_unit("Gamma") == "linear_THz"


def test_kaldo_to_phono3py_unit_factor_is_one_over_two_pi():
    f = cross_state_unit_factor(KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma")
    assert math.isclose(f, 1.0 / (2 * math.pi))


def test_kaldo_linewidth_convention_factor_is_2():
    """kaldo declares Gamma = 2 Im Sigma; canonical is Im Sigma."""
    assert math.isclose(KALDO_LINEWIDTH.observable_convention_factor("Gamma"), 2.0)


def test_phono3py_linewidth_convention_factor_is_canonical():
    assert math.isclose(PHONO3PY_LINEWIDTH.observable_convention_factor("Gamma"), 1.0)


def test_kaldo_to_phono3py_total_factor_closes_4pi_gap():
    """Combined unit + convention factor matches the empirical 4π."""
    f = cross_state_total_factor(KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma")
    assert math.isclose(f, 1.0 / (4 * math.pi))


def test_gamma_definition_convention_mismatch_is_surfaced():
    matched, msg = cross_state_convention_match(
        KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "gamma_definition"
    )
    assert matched is False
    assert "linewidth_2x_imag_self_energy" in msg
    assert "imag_self_energy" in msg


# --- state adapters: heat capacity ---


def test_heat_capacity_unit_factor_is_e():
    f = cross_state_unit_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    assert math.isclose(f, 1.0 / 1.602176634e-19)


def test_heat_capacity_total_equals_unit_when_no_conventions():
    """No state-level conventions on HeatCapacity, so total = unit."""
    unit = cross_state_unit_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    total = cross_state_total_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    assert math.isclose(unit, total)


# --- operation adapters: algorithmic conventions ---


def test_broadening_param_convention_mismatch_surfaced():
    matched, msg = cross_operation_algorithmic_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is False
    assert "halfwidth" in msg
    assert "stdev" in msg


# --- operation adapters: discretization choices ---


def test_bz_summation_discretization_mismatch_surfaced():
    matched, msg = cross_operation_discretization_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "bz_summation"
    )
    assert matched is False
    assert "full_grid" in msg
    assert "symmetry_reduced" in msg


def test_delta_cutoff_discretization_mismatch_surfaced():
    matched, msg = cross_operation_discretization_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "delta_cutoff_sigmas"
    )
    assert matched is False


# --- error paths ---


def test_cross_state_for_different_states_raises():
    with pytest.raises(ValueError, match="different states"):
        cross_state_unit_factor(KALDO_LINEWIDTH, PHONO3PY_HEAT_CAPACITY, "Gamma")


def test_cross_operation_for_different_operations_raises():
    with pytest.raises(ValueError, match="different operations"):
        cross_operation_algorithmic_match(
            KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_HEAT_CAPACITY, "broadening_param"
        )


def test_unknown_observable_raises():
    with pytest.raises(KeyError):
        KALDO_LINEWIDTH.declared_unit("not_a_quantity")


def test_unknown_convention_raises():
    with pytest.raises(KeyError):
        KALDO_LINEWIDTH.declared_convention("not_a_convention")
