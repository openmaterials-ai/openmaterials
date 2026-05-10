"""Tests for Materialization, materialize(), and compare()."""

from __future__ import annotations

import math

import numpy as np
import pytest

from omai.materialization import Materialization, compare, materialize
from omai.thermal_transport.materialized import (
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
)


# --- materialize ---


def test_materialize_returns_typed_object():
    m = materialize(KALDO_LINEWIDTH, "Gamma", np.array([1.0, 2.0, 3.0]))
    assert isinstance(m, Materialization)
    assert m.adapter_name == "kaldo"
    assert m.observable_name == "Gamma"
    assert m.data.shape == (3,)


def test_materialize_rejects_unknown_observable():
    with pytest.raises(KeyError):
        materialize(KALDO_LINEWIDTH, "not_an_observable", np.array([1.0]))


def test_materialize_coerces_data_to_ndarray():
    m = materialize(KALDO_LINEWIDTH, "Gamma", [1.0, 2.0, 3.0])
    assert isinstance(m.data, np.ndarray)


# --- compare: matching identity ---


def test_compare_identical_data_passes():
    arr = np.array([1.0, 2.0, 3.0])
    mk = materialize(PHONO3PY_LINEWIDTH, "Gamma", arr)
    mp = materialize(PHONO3PY_LINEWIDTH, "Gamma", arr)
    r = compare(mk, mp, rtol=1e-9)
    assert r.passed
    assert r.factor == 1.0
    assert r.max_relative_residual == 0.0


# --- compare: factor application ---


def test_compare_applies_4pi_factor_for_kaldo_to_phono3py_linewidth():
    """The 4π Linewidth conversion: kaldo × (1/4π) = phono3py."""
    phono3py_data = np.array([1.0, 2.0, 3.0])
    kaldo_data = phono3py_data * (4 * math.pi)
    mp = materialize(PHONO3PY_LINEWIDTH, "Gamma", phono3py_data)
    mk = materialize(KALDO_LINEWIDTH, "Gamma", kaldo_data)
    r = compare(mk, mp, rtol=1e-9)
    assert r.passed
    assert math.isclose(r.factor, 1.0 / (4 * math.pi), rel_tol=1e-9)
    assert r.max_relative_residual < 1e-9


def test_compare_applies_e_factor_for_heat_capacity():
    """kaldo (J/K) × 1/e = phono3py (eV/K)."""
    e = 1.602176634e-19
    phono3py_data = np.array([1.0, 2.0, 3.0])
    kaldo_data = phono3py_data * (1 / e)  # J = (1/e) × (eV/K)? Wait — kaldo is J/K, phono3py eV/K
    # If phono3py emits in eV/K and kaldo in J/K, kaldo_value [J/K] = phono3py_value [eV/K] × e
    kaldo_data = phono3py_data * e
    mk = materialize(KALDO_HEAT_CAPACITY, "c", kaldo_data)
    mp = materialize(PHONO3PY_HEAT_CAPACITY, "c", phono3py_data)
    r = compare(mk, mp, rtol=1e-9)
    assert r.passed


# --- compare: contraction ---


def test_compare_with_sum_contraction():
    """Per-element disagreement masked by a contraction that sums first."""
    a = np.array([1.0, 1.0, 1.0])
    b = np.array([0.5, 1.5, 1.0])  # disagrees per-element but sum is 3.0 in both
    ma = materialize(PHONO3PY_LINEWIDTH, "Gamma", a)
    mb = materialize(PHONO3PY_LINEWIDTH, "Gamma", b)
    per_mode = compare(ma, mb, rtol=1e-9)
    contracted = compare(ma, mb, contraction=np.sum, rtol=1e-9)
    assert not per_mode.passed
    assert contracted.passed
    assert contracted.contracted is True


# --- compare: error paths ---


def test_compare_rejects_different_states():
    arr = np.array([1.0])
    m_lw = materialize(KALDO_LINEWIDTH, "Gamma", arr)
    m_hc = materialize(KALDO_HEAT_CAPACITY, "c", arr)
    with pytest.raises(ValueError, match="different states"):
        compare(m_lw, m_hc)


def test_compare_rejects_different_observables_within_same_state():
    """If a state had multiple observables and the materializations chose different ones."""
    arr = np.array([1.0])
    m_a = materialize(KALDO_LINEWIDTH, "Gamma", arr)
    # Build a synthetic mismatch: same state spec, claim a different observable name
    # by going around materialize() (which validates). This tests compare() directly.
    m_b = Materialization(
        state_adapter_spec=PHONO3PY_LINEWIDTH,
        observable_name="some_other_observable",
        data=arr,
    )
    with pytest.raises(ValueError, match="different observables"):
        compare(m_a, m_b)


# --- compare: residual reporting around near-zero values ---


def test_compare_handles_near_zero_with_atol():
    """Acoustic-Γ-style near-zero values: relative residual should not blow up."""
    a = np.array([1e-8, 1.0, 2.0])
    b = np.array([2e-8, 1.0, 2.0])
    ma = materialize(PHONO3PY_LINEWIDTH, "Gamma", a)
    mb = materialize(PHONO3PY_LINEWIDTH, "Gamma", b)
    r = compare(ma, mb, rtol=1e-3, atol=1e-6)
    assert r.passed
    # Relative residual computed only over entries above atol; the 1e-8 ones
    # are masked out, so max_rel reflects the 1.0 / 2.0 entries (= 0.0)
    assert r.max_relative_residual == 0.0
