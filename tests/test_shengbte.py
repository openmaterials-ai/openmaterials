"""Smoke tests for the ShengBTE adapter specs.

Validates the spec-derived unit and convention factors against kaldo and
phono3py on synthetic identical-physics arrays.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from omai.representation import compare, represent
from omai.thermal_transport.representation import (
    KALDO_FREQUENCY,
    KALDO_GROUP_VELOCITY,
    KALDO_LINEWIDTH,
    KALDO_THERMAL_CONDUCTIVITY_DIRECT,
    KALDO_THERMAL_CONDUCTIVITY_RTA,
    PHONO3PY_FREQUENCY,
    PHONO3PY_LINEWIDTH,
    SHENGBTE_FREQUENCY,
    SHENGBTE_GROUP_VELOCITY,
    SHENGBTE_LINEWIDTH,
    SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT,
    SHENGBTE_THERMAL_CONDUCTIVITY_RTA,
    SHENGBTE_VOLUMETRIC_HEAT_CAPACITY,
)


def test_shengbte_frequency_to_kaldo_factor_is_two_pi():
    """ShengBTE emits ω in angular_THz (rad/ps); kaldo in linear_THz.
    Cross-code factor: angular × 1/(2π) = linear."""
    linear = np.array([1.0, 2.0, 3.0])
    angular = linear * (2 * math.pi)
    mk = represent(KALDO_FREQUENCY, "omega", linear)
    ms = represent(SHENGBTE_FREQUENCY, "omega", angular)
    r = compare(ms, mk, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 1.0 / (2 * math.pi), rel_tol=1e-9)


def test_shengbte_frequency_agrees_with_phono3py():
    """Same as above against phono3py (also linear_THz)."""
    linear = np.array([1.0, 2.0, 3.0])
    angular = linear * (2 * math.pi)
    mp = represent(PHONO3PY_FREQUENCY, "omega", linear)
    ms = represent(SHENGBTE_FREQUENCY, "omega", angular)
    r = compare(ms, mp, rtol=1e-9)
    assert r.agreed


def test_shengbte_group_velocity_to_kaldo_factor_is_ten():
    """ShengBTE: km/s. kaldo: Å × linear_THz. 1 km/s = 10 Å·THz."""
    angstrom_thz = np.array([1.0, 5.0, 10.0])
    km_per_s = angstrom_thz / 10.0  # so shengbte_value × 10 = kaldo_value
    mk = represent(KALDO_GROUP_VELOCITY, "v", angstrom_thz)
    ms = represent(SHENGBTE_GROUP_VELOCITY, "v", km_per_s)
    r = compare(ms, mk, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 10.0, rel_tol=1e-9)


def test_shengbte_linewidth_to_kaldo_is_unity():
    """ShengBTE w_anharmonic and kaldo bandwidth both carry the
    linewidth_2x_imag_self_energy convention, both in angular_THz. So the
    cross-code factor on identical physics is 1."""
    arr = np.array([0.1, 0.2, 0.5])  # Γ in angular_THz
    mk = represent(KALDO_LINEWIDTH, "Gamma", arr)
    ms = represent(SHENGBTE_LINEWIDTH, "Gamma", arr)
    # Linewidth is a HiddenState — per-element is NOT_COMPARABLE; contract.
    r = compare(ms, mk, contraction=np.sum, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 1.0, rel_tol=1e-9)


def test_shengbte_linewidth_to_phono3py_is_one_over_four_pi():
    """ShengBTE (angular_THz, 2× Im Σ) vs phono3py (linear_THz, 1× Im Σ).
    Two factors compound:
      * unit  : angular → linear is 1/(2π)
      * convention : 2× → 1× is 1/2
    Net cross-code factor: shengbte_value × 1/(4π) = phono3py_value."""
    phono3py_arr = np.array([0.1, 0.2, 0.5])
    shengbte_arr = phono3py_arr * (4 * math.pi)
    mp = represent(PHONO3PY_LINEWIDTH, "Gamma", phono3py_arr)
    ms = represent(SHENGBTE_LINEWIDTH, "Gamma", shengbte_arr)
    r = compare(ms, mp, contraction=np.sum, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 1.0 / (4 * math.pi), rel_tol=1e-9)


def test_shengbte_kappa_rta_agrees_with_kaldo():
    """κ_RTA is in W/(m·K) for both codes; no convention overrides; factor 1."""
    arr = np.eye(3) * 142.0  # silicon-ish W/(m·K)
    mk = represent(KALDO_THERMAL_CONDUCTIVITY_RTA, "kappa", arr)
    ms = represent(SHENGBTE_THERMAL_CONDUCTIVITY_RTA, "kappa", arr)
    r = compare(ms, mk, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 1.0, rel_tol=1e-9)


def test_shengbte_kappa_direct_agrees_with_kaldo():
    """κ_LBTE/CONV: same unit, same convention, same canonical bte_solver."""
    arr = np.eye(3) * 160.0
    mk = represent(KALDO_THERMAL_CONDUCTIVITY_DIRECT, "kappa", arr)
    ms = represent(SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT, "kappa", arr)
    r = compare(ms, mk, rtol=1e-9)
    assert r.agreed


def test_shengbte_volumetric_heat_capacity_roundtrip():
    """ShengBTE emits the volumetric C_V/V directly. Two representations of
    the same array (T-indexed) must agree trivially."""
    arr = np.array([1.85e6, 1.92e6, 1.96e6])  # J/(m³·K) at three temperatures
    a = represent(SHENGBTE_VOLUMETRIC_HEAT_CAPACITY, "C_V_vol", arr)
    b = represent(SHENGBTE_VOLUMETRIC_HEAT_CAPACITY, "C_V_vol", arr)
    r = compare(a, b, rtol=1e-9)
    assert r.agreed
    assert r.factor == 1.0
    assert r.status == "EXPECTED_AGREE"


def test_shengbte_and_kaldo_share_adaptive_broadening_scheme():
    """kaldo (third_bandwidth=None) and ShengBTE (scalebroad=1.0) implement
    the same velocity-projection σ formula. The cross-operation algorithmic
    match should report them in agreement on broadening_param."""
    from omai.representation.adapter import representation_algorithmic_match
    from omai.thermal_transport.representation import (
        KALDO_COMPUTE_LINEWIDTH,
        SHENGBTE_COMPUTE_LINEWIDTH,
    )

    matched, msg = representation_algorithmic_match(
        KALDO_COMPUTE_LINEWIDTH, SHENGBTE_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is True, msg


def test_shengbte_linewidth_per_element_is_not_comparable():
    """As with the other HiddenState comparisons, per-element shengbte vs kaldo
    on Linewidth must return NOT_COMPARABLE."""
    arr = np.array([0.1, 0.2, 0.5])
    mk = represent(KALDO_LINEWIDTH, "Gamma", arr)
    ms = represent(SHENGBTE_LINEWIDTH, "Gamma", arr)
    r = compare(ms, mk, rtol=1e-3)
    assert r.not_comparable
    assert r.status == "NOT_COMPARABLE"
