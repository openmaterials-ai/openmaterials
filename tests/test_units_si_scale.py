"""SI scales on canonical units + dimension_si_scale lookup."""
from __future__ import annotations

import pytest

from omai.operator.dimensions import (
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    THERMAL_CONDUCTIVITY,
    VOLUME,
)
from omai.representation.units import UNITS, dimension_si_scale


def test_volume_dimension_registered():
    assert VOLUME.name == "volume"


def test_length_and_volume_have_canonical_units():
    assert UNITS["angstrom"].dimension is LENGTH
    assert UNITS["angstrom"].to_operator == 1.0
    assert UNITS["angstrom_cubed"].dimension is VOLUME
    assert UNITS["angstrom_cubed"].to_operator == 1.0


def test_dimension_si_scale_values():
    assert dimension_si_scale(FREQUENCY) == 1e12
    assert dimension_si_scale(LENGTH) == 1e-10
    assert dimension_si_scale(LENGTH_TIMES_FREQUENCY) == 1e2
    assert dimension_si_scale(ENERGY_PER_TEMPERATURE) == 1.0
    assert dimension_si_scale(THERMAL_CONDUCTIVITY) == 1.0
    assert dimension_si_scale(VOLUME) == 1e-30


def test_dimension_si_scale_raises_for_dimension_without_scale():
    from omai.operator.dimensions import OPAQUE
    with pytest.raises(ValueError, match="no canonical unit"):
        dimension_si_scale(OPAQUE)
