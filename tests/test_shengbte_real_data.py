"""Validate the ShengBTE adapter against the bundled reference output.

ShengBTE ships a pre-computed reference run for InAs (12×12×12 q-grid,
T=300K) under `Test-VASP/Reference/`. This module reads those real
output files, materializes them through the adapter spec, and confirms:

  * the files parse to the expected shapes,
  * physical magnitudes are sensible (κ ≈ 26.7 W/(m·K), c_V ≈ 1.4×10⁶ J/(m³·K)),
  * materialize() + compare() round-trip cleanly on real numbers.

These tests are skipped if the ShengBTE reference is not present (e.g.
for users who only cloned omai-ai without ShengBTE).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from omai.materialization import compare, materialize
from omai.thermal_transport.materialized import (
    SHENGBTE_FREQUENCY,
    SHENGBTE_GROUP_VELOCITY,
    SHENGBTE_LINEWIDTH,
    SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT,
    SHENGBTE_THERMAL_CONDUCTIVITY_RTA,
    SHENGBTE_VOLUMETRIC_HEAT_CAPACITY,
)


_REPO = Path(__file__).resolve().parents[1]
_REF = _REPO / "shengbte" / "Test-VASP" / "Reference"
_T300 = _REF / "T300K"

pytestmark = pytest.mark.skipif(
    not _REF.exists(),
    reason="ShengBTE reference output not available (shengbte/ not cloned)",
)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_omega(path: Path) -> np.ndarray:
    """BTE.omega: one row per irreducible q-point; columns are mode freqs."""
    return np.loadtxt(path)


def _parse_v(path: Path) -> np.ndarray:
    """BTE.v: 3 cartesian components per (q,band) row; q changes first,
    then band. Returns shape (n_modes, n_q_irr, 3)."""
    raw = np.loadtxt(path)
    n_total, three = raw.shape
    assert three == 3
    # File ordering: q changes fastest, then band → n_q_irr × n_modes.
    n_q_irr = _parse_omega(_REF / "BTE.omega").shape[0]
    n_modes = n_total // n_q_irr
    return raw.reshape(n_modes, n_q_irr, 3)


def _parse_w_anharmonic(path: Path) -> np.ndarray:
    """BTE.w_anharmonic: two columns, (ω, Γ). q changes first, then band."""
    raw = np.loadtxt(path)
    return raw[:, 1]  # the rate column


def _parse_cv(path: Path) -> float:
    return float(np.loadtxt(path))


def _parse_kappa_tensor_vs_t(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """First column T, next 9 are tensor in row-major. Returns (T, kappa[T,3,3])."""
    raw = np.loadtxt(path, ndmin=2)
    T = raw[:, 0]
    kappa = raw[:, 1:10].reshape(-1, 3, 3)
    return T, kappa


def _kappa_300K(path: Path) -> np.ndarray:
    T, k = _parse_kappa_tensor_vs_t(path)
    idx = int(np.argmin(np.abs(T - 300.0)))
    return k[idx]


# ---------------------------------------------------------------------------
# Shape & magnitude
# ---------------------------------------------------------------------------


def test_real_omega_shape_and_range():
    omega = _parse_omega(_REF / "BTE.omega")
    n_q_irr, n_modes = omega.shape
    # InAs: 2 atoms/cell → 6 modes. Test-VASP CONTROL declares ngrid 12³ on
    # a primitive zincblende cell; the IBZ wedge has 72 q-points.
    assert n_modes == 6
    assert n_q_irr == 72
    # Acoustic Γ has ω = 0 (first three modes of first q-point); optical
    # frequencies are ~41 rad/ps for InAs LO at Γ.
    assert np.all(omega >= 0.0)
    assert omega.max() < 100.0  # rad/ps — sanity bound
    assert omega[0, 0] == 0.0  # acoustic Γ


def test_real_volumetric_heat_capacity_is_dulong_petit_scale():
    cv = _parse_cv(_T300 / "BTE.cv")
    # Dulong-Petit estimate for InAs (a₀ ≈ 6.06 Å zincblende):
    #   V_cell ≈ (a₀/√2)³ × √2 = 56 Å³ (primitive volume of zincblende)
    #   C_V_classical ≈ 6 × k_B / V_cell ≈ 1.5 × 10⁶ J/(m³K)
    # ShengBTE's quantum value at 300K should land within ±20%.
    assert 1.0e6 < cv < 2.0e6


def test_real_kappa_300K_is_sensible_for_InAs():
    k = _kappa_300K(_REF / "BTE.KappaTensorVsT_CONV")
    # InAs at 300K experimentally: κ ≈ 27 W/(m·K). ShengBTE-VASP reference: ~26.67.
    diag = np.diag(k)
    assert diag.min() > 20.0
    assert diag.max() < 35.0
    # Cubic isotropy: diagonal entries equal, off-diagonals ≈ 0
    assert np.allclose(diag, diag.mean(), rtol=1e-3)
    off_diag = k - np.diag(diag)
    assert np.abs(off_diag).max() < 1e-12 * np.abs(k).max() + 1e-10


def test_real_kappa_rta_lower_than_converged():
    """Iterative solver always finds κ ≥ κ_RTA (corrections are non-negative)."""
    k_rta = _kappa_300K(_REF / "BTE.KappaTensorVsT_RTA")
    k_conv = _kappa_300K(_REF / "BTE.KappaTensorVsT_CONV")
    assert np.diag(k_rta).mean() <= np.diag(k_conv).mean()


# ---------------------------------------------------------------------------
# Adapter round-trip: materialize() the real arrays
# ---------------------------------------------------------------------------


def test_real_omega_materializes_and_round_trips():
    omega = _parse_omega(_REF / "BTE.omega")
    a = materialize(SHENGBTE_FREQUENCY, "omega", omega)
    b = materialize(SHENGBTE_FREQUENCY, "omega", omega)
    r = compare(a, b, rtol=1e-12)
    assert r.agreed
    assert r.status == "EXPECTED_AGREE"


def test_real_velocity_materializes():
    v = _parse_v(_REF / "BTE.v")
    a = materialize(SHENGBTE_GROUP_VELOCITY, "v", v)
    assert a.data.shape == v.shape


def test_real_linewidth_materializes_and_contracts():
    Gamma = _parse_w_anharmonic(_T300 / "BTE.w_anharmonic")
    a = materialize(SHENGBTE_LINEWIDTH, "Gamma", Gamma)
    b = materialize(SHENGBTE_LINEWIDTH, "Gamma", Gamma)
    # Per-element on HiddenState: NOT_COMPARABLE
    r_per = compare(a, b, rtol=1e-12)
    assert r_per.not_comparable
    # Contracted sum: EXPECTED_AGREE
    r_sum = compare(a, b, contraction=np.sum, rtol=1e-12)
    assert r_sum.agreed


def test_real_volumetric_heat_capacity_materializes():
    cv = np.array([_parse_cv(_T300 / "BTE.cv")])
    a = materialize(SHENGBTE_VOLUMETRIC_HEAT_CAPACITY, "C_V_vol", cv)
    b = materialize(SHENGBTE_VOLUMETRIC_HEAT_CAPACITY, "C_V_vol", cv)
    r = compare(a, b, rtol=1e-12)
    assert r.agreed


def test_real_kappa_tensors_materialize():
    k_rta = _kappa_300K(_REF / "BTE.KappaTensorVsT_RTA")
    k_dir = _kappa_300K(_REF / "BTE.KappaTensorVsT_CONV")
    materialize(SHENGBTE_THERMAL_CONDUCTIVITY_RTA, "kappa", k_rta)
    materialize(SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT, "kappa", k_dir)
