"""Spec gates 1, 2, 3, 7 on the hist encoder: euclidean/permutation/supercell
invariance and continuity for every registered distance claiming them."""
import pytest

import omdc
from fixtures_distance import diamond_si, permuted, rattled, rotated, translated

CHANNELS = [("env-ot", "hist"), ("latent", "hist"), ("comp", None), ("amd", None), ("exact", None)]


def _d(name, enc, a, b):
    return omdc.distance(a, b, metric=name, encoder=enc) if enc else omdc.distance(a, b, metric=name)


@pytest.mark.parametrize("name,enc", CHANNELS)
def test_gate1_euclidean_and_permutation(diamond, name, enc):
    for t in (rotated(diamond), translated(diamond), permuted(diamond)):
        assert _d(name, enc, diamond, t) == pytest.approx(0, abs=2e-3)


@pytest.mark.parametrize("name,enc", CHANNELS)
def test_gate2_supercell(diamond, name, enc):
    assert _d(name, enc, diamond, diamond * (2, 2, 2)) == pytest.approx(0, abs=5e-3)


def test_gate3_continuity(diamond):
    small = omdc.distance(diamond, rattled(diamond, 0.01, 3), metric="env-ot", encoder="hist")
    big = omdc.distance(diamond, rattled(diamond, 0.10, 3), metric="env-ot", encoder="hist")
    assert 0 < small < big < 1.5


def test_gate7_symmetry_axiom(diamond):
    other = rattled(diamond * (2, 2, 2), 0.3, 5)
    for name, enc in CHANNELS:
        if not omdc.resolve(name).metric:
            continue
        ab, ba = _d(name, enc, diamond, other), _d(name, enc, other, diamond)
        assert ab == pytest.approx(ba, rel=1e-5, abs=1e-9)
