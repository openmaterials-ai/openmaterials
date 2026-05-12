"""Smoke tests for the phonopy adapter specs."""

from __future__ import annotations

import math

import numpy as np

from omai.representation import compare, represent
from omai.thermal_transport.representation import (
    KALDO_FREQUENCY,
    PHONO3PY_FREQUENCY,
    PHONOPY_FREQUENCY,
    PHONOPY_MOLAR_HEAT_CAPACITY,
)


def test_phonopy_frequency_agrees_with_kaldo():
    """Both emit ω in linear_THz; factor 1, agree per-element on identical data."""
    arr = np.array([1.0, 5.0, 12.5])
    mk = represent(KALDO_FREQUENCY, "omega", arr)
    mp = represent(PHONOPY_FREQUENCY, "omega", arr)
    r = compare(mp, mk, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, 1.0, rel_tol=1e-9)


def test_phonopy_frequency_agrees_with_phono3py():
    arr = np.array([1.0, 5.0, 12.5])
    mp3 = represent(PHONO3PY_FREQUENCY, "omega", arr)
    pp = represent(PHONOPY_FREQUENCY, "omega", arr)
    r = compare(pp, mp3, rtol=1e-9)
    assert r.agreed


def test_phonopy_molar_heat_capacity_roundtrip():
    """Phonopy emits C_V_mol directly in J/(K·mol). Identity check."""
    arr = np.array([22.5, 23.1, 23.5])  # J/(K·mol) on a three-T grid
    a = represent(PHONOPY_MOLAR_HEAT_CAPACITY, "C_V_mol", arr)
    b = represent(PHONOPY_MOLAR_HEAT_CAPACITY, "C_V_mol", arr)
    r = compare(a, b, rtol=1e-9)
    assert r.agreed
    assert r.factor == 1.0
    assert r.status == "EXPECTED_AGREE"
