"""Dimension exponent algebra (kernel P1)."""
from __future__ import annotations

import pytest

from omai.operator.dimensions import (
    DIFFUSIVITY, DIMENSIONLESS, DIMENSIONS, ENERGY, ENERGY_PER_TEMPERATURE,
    FREQUENCY, LENGTH, LENGTH_PER_TIME, LENGTH_TIMES_FREQUENCY, MASS, OPAQUE,
    TEMPERATURE, THERMAL_CONDUCTIVITY, TIME, VOLUME, Dimension,
)


def test_equality_by_exponents_velocity_merge():
    assert LENGTH_PER_TIME == LENGTH_TIMES_FREQUENCY
    assert hash(LENGTH_PER_TIME) == hash(LENGTH_TIMES_FREQUENCY)


def test_no_other_accidental_merges():
    named = [d for d in DIMENSIONS.values() if not d.is_opaque]
    groups = {}
    for d in named:
        groups.setdefault(d.exponents, []).append(d.name)
    merged = {k: v for k, v in groups.items() if len(v) > 1}
    assert list(merged.values()) == [["length_times_frequency", "length_per_time"]] or \
           list(merged.values()) == [["length_per_time", "length_times_frequency"]]


def test_algebra_products_and_powers():
    assert ENERGY / TEMPERATURE == ENERGY_PER_TEMPERATURE
    assert LENGTH ** 2 / TIME == DIFFUSIVITY
    assert LENGTH ** 3 == VOLUME
    assert (ENERGY_PER_TEMPERATURE * (LENGTH / TIME) * LENGTH / VOLUME) == THERMAL_CONDUCTIVITY
    assert ENERGY / ENERGY == DIMENSIONLESS
    assert FREQUENCY ** -1 == TIME


def test_opaque_guards():
    assert OPAQUE.is_opaque
    assert OPAQUE == Dimension("opaque")
    assert OPAQUE != DIMENSIONLESS
    with pytest.raises(ValueError):
        _ = OPAQUE * LENGTH
    with pytest.raises(ValueError):
        _ = ENERGY / OPAQUE


def test_canonical_string_is_deterministic():
    assert THERMAL_CONDUCTIVITY.canonical() == "M^1 L^1 T^-3 Th^-1"
    assert DIMENSIONLESS.canonical() == "1"
    assert OPAQUE.canonical() == "opaque:opaque"


def test_names_unchanged_for_catalog_stability():
    assert ENERGY.name == "energy"
    assert THERMAL_CONDUCTIVITY.name == "thermal_conductivity"
    assert MASS.name == "mass" and TIME.name == "time"
