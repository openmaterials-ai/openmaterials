"""Tests for omai.spec — symbolic adapter conformance."""

from __future__ import annotations

import math

import pytest

from omai.spec import (
    conversion_factor,
    cross_adapter_convention_match,
    cross_adapter_total_factor,
    cross_adapter_unit_factor,
    output_convention_factor,
)
from omai.spec.adapters import (
    KALDO_COMPUTE_HEAT_CAPACITY,
    KALDO_COMPUTE_SCATTERING_RATES,
    PHONO3PY_COMPUTE_HEAT_CAPACITY,
    PHONO3PY_COMPUTE_SCATTERING_RATES,
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


# --- adapter specs: linewidth (Gamma) ---


def test_kaldo_linewidth_is_angular_thz():
    assert KALDO_COMPUTE_SCATTERING_RATES.declared_unit("linewidth") == "angular_THz"


def test_phono3py_linewidth_is_linear_thz():
    assert PHONO3PY_COMPUTE_SCATTERING_RATES.declared_unit("linewidth") == "linear_THz"


def test_kaldo_to_phono3py_linewidth_unit_factor_is_one_over_two_pi():
    """The unit-only layer: angular vs linear THz."""
    f = cross_adapter_unit_factor(
        KALDO_COMPUTE_SCATTERING_RATES,
        PHONO3PY_COMPUTE_SCATTERING_RATES,
        "linewidth",
    )
    assert math.isclose(f, 1.0 / (2 * math.pi))


def test_kaldo_output_is_2x_canonical_for_linewidth():
    """kaldo emits Gamma = 2 Im Sigma (linewidth), not Im Sigma directly."""
    factor = output_convention_factor(KALDO_COMPUTE_SCATTERING_RATES, "linewidth")
    assert math.isclose(factor, 2.0)


def test_phono3py_output_is_canonical_for_linewidth():
    """phono3py emits Gamma = Im Sigma directly, matching canonical."""
    factor = output_convention_factor(PHONO3PY_COMPUTE_SCATTERING_RATES, "linewidth")
    assert math.isclose(factor, 1.0)


def test_kaldo_to_phono3py_total_factor_is_one_over_four_pi():
    """The total factor (unit + convention) reproduces the empirical 4π gap."""
    f = cross_adapter_total_factor(
        KALDO_COMPUTE_SCATTERING_RATES,
        PHONO3PY_COMPUTE_SCATTERING_RATES,
        "linewidth",
    )
    assert math.isclose(f, 1.0 / (4 * math.pi))


# --- adapter specs: broadening convention ---


def test_kaldo_uses_halfwidth_phono3py_uses_stdev():
    assert KALDO_COMPUTE_SCATTERING_RATES.declared_convention("broadening_param") == "halfwidth"
    assert PHONO3PY_COMPUTE_SCATTERING_RATES.declared_convention("broadening_param") == "stdev"


def test_broadening_convention_mismatch_is_surfaced():
    matched, msg = cross_adapter_convention_match(
        KALDO_COMPUTE_SCATTERING_RATES,
        PHONO3PY_COMPUTE_SCATTERING_RATES,
        "broadening_param",
    )
    assert matched is False
    assert "halfwidth" in msg
    assert "stdev" in msg


def test_bz_summation_mismatch_is_surfaced():
    matched, msg = cross_adapter_convention_match(
        KALDO_COMPUTE_SCATTERING_RATES,
        PHONO3PY_COMPUTE_SCATTERING_RATES,
        "bz_summation",
    )
    assert matched is False
    assert "full_grid" in msg
    assert "symmetry_reduced" in msg


# --- adapter specs: heat capacity ---


def test_heat_capacity_unit_factor_is_e():
    f = cross_adapter_unit_factor(
        KALDO_COMPUTE_HEAT_CAPACITY,
        PHONO3PY_COMPUTE_HEAT_CAPACITY,
        "heat_capacity",
    )
    assert math.isclose(f, 1.0 / 1.602176634e-19)


def test_heat_capacity_total_equals_unit_when_no_conventions():
    """When the operation declares no output_convention_scaling, total = unit."""
    unit = cross_adapter_unit_factor(
        KALDO_COMPUTE_HEAT_CAPACITY,
        PHONO3PY_COMPUTE_HEAT_CAPACITY,
        "heat_capacity",
    )
    total = cross_adapter_total_factor(
        KALDO_COMPUTE_HEAT_CAPACITY,
        PHONO3PY_COMPUTE_HEAT_CAPACITY,
        "heat_capacity",
    )
    assert math.isclose(unit, total)


# --- error paths ---


def test_cross_adapter_for_different_operations_raises():
    with pytest.raises(ValueError, match="different operations"):
        cross_adapter_unit_factor(
            KALDO_COMPUTE_SCATTERING_RATES,
            PHONO3PY_COMPUTE_HEAT_CAPACITY,
            "linewidth",
        )


def test_unknown_quantity_raises():
    with pytest.raises(KeyError):
        KALDO_COMPUTE_SCATTERING_RATES.declared_unit("not_a_quantity")
