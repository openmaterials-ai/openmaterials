import importlib.util

import pytest

from fixtures_distance import diamond_si, glass, strained
from omdc.encoders.histogram import HistogramEncoder
from omdc.profile import scale_profile

HAS_AMD = importlib.util.find_spec("amd") is not None
HAS_MACE = importlib.util.find_spec("mace") is not None


def test_strain_accumulates_with_radius():
    p = scale_profile(diamond_si(), strained(diamond_si(), 0.01))
    assert set(p) == {2.5, 5.0, 10.0}
    assert all(v > 0 for v in p.values())
    assert p[10.0] > p[2.5]  # long-range strain accumulates; locally it is tiny


def test_glass_realizations_stay_near_at_every_scale():
    radii = (2.5, 5.0)
    same = scale_profile(glass(1, rep=3), glass(2, rep=3), radii=radii)
    ref = scale_profile(glass(1, rep=3), diamond_si(), radii=radii)
    for r in radii:
        assert same[r] < 0.5 * ref[r]


def test_custom_cutoff_changes_pin_and_bins():
    default = HistogramEncoder()
    short = HistogramEncoder(cutoff=2.5)
    assert default.pin != short.pin
    assert short.nbins < default.nbins
    assert HistogramEncoder(cutoff=20.0).nbins <= 128


@pytest.mark.skipif(not HAS_AMD, reason="amd extra not installed")
def test_amd_profile_is_monotone_nested_bounds():
    from omdc.metrics.amdmetric import amd_distance, amd_profile

    a, b = diamond_si(), strained(diamond_si(), 0.02)
    prof = amd_profile(a, b)
    ks = sorted(prof)
    assert all(prof[ks[i]] <= prof[ks[i + 1]] + 1e-12 for i in range(len(ks) - 1))
    assert prof[100] == pytest.approx(amd_distance(a, b))


@pytest.mark.skipif(not HAS_MACE, reason="mace extra not installed")
def test_layer_profile_runs_and_distinguishes():
    from omdc.profile import layer_profile

    p = layer_profile(diamond_si(), strained(diamond_si(), 0.02))
    assert set(p) == {1, 2}
    assert all(v >= 0 for v in p.values())
