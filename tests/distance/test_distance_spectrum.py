import numpy as np
import pytest

import omdc
from omdc.metrics.spectrum import curve_rel, spectrum_w1


def test_delta_masses_distance_is_shift():
    assert spectrum_w1(([0.0], [1.0]), ([3.5], [1.0])) == pytest.approx(3.5)


def test_shifted_gaussian_dos_distance_is_the_shift():
    x = np.linspace(-10, 10, 2001)
    g = np.exp(-0.5 * x**2)
    d = spectrum_w1((x, g), (x + 1.25, g))
    assert d == pytest.approx(1.25, rel=1e-3)


def test_grid_mismatch_and_normalization():
    xa = np.linspace(0, 10, 101)
    xb = np.linspace(0, 10, 37)  # different grid
    ya = np.exp(-0.5 * (xa - 4) ** 2)
    yb = 7.0 * np.exp(-0.5 * (xb - 4) ** 2)  # different intensity: shapes compared
    d = spectrum_w1((xa, ya), (xb, yb))
    # Two discretizations of the same density differ by O(grid spacing) as
    # point masses (measured 0.089 vs coarse spacing 0.278); a real 1.0
    # shift reads 1.0. Assert the discretization floor stays well below both.
    assert d < (10 / 36) / 2
    assert d < 0.15 * spectrum_w1((xa, ya), (xa + 1.0, ya))


def test_mass_curve_rejects_negative():
    with pytest.raises(ValueError, match="y >= 0"):
        spectrum_w1(([0, 1], [1.0, -0.5]), ([0], [1.0]))


def test_curve_rel_kappa_like():
    t = np.linspace(100, 800, 50)
    ka = 1e4 / t
    assert curve_rel((t, ka), (t, ka)) == 0.0
    d_close = curve_rel((t, ka), (t, ka * 1.1))
    d_far = curve_rel((t, ka), (t, ka * 2.0))
    assert 0 < d_close < d_far


def test_curve_rel_needs_overlap():
    with pytest.raises(ValueError, match="share no x range"):
        curve_rel(([0, 1], [1, 1]), ([2, 3], [1, 1]))


def test_registry_dispatch():
    x = np.linspace(0, 5, 11)
    assert omdc.distance((x, np.exp(-x)), (x, np.exp(-x)), metric="spectrum") == 0.0
    assert omdc.resolve("spectrum").input == "spectrum"
    assert omdc.resolve("curve").input == "curve"
    assert omdc.resolve("env-ot").input == "structure"
