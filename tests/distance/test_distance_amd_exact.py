import importlib.util

import pytest

from fixtures_distance import diamond_si, fcc_si, strained
from omdc.metrics.exact import exact_rmsd

HAS_AMD = importlib.util.find_spec("amd") is not None


@pytest.mark.skipif(not HAS_AMD, reason="amd extra not installed")
def test_amd_zero_self_and_supercell(diamond):
    from omdc.metrics.amdmetric import amd_distance

    assert amd_distance(diamond, diamond) == pytest.approx(0, abs=1e-8)
    assert amd_distance(diamond, diamond * (2, 2, 2)) == pytest.approx(0, abs=1e-3)


@pytest.mark.skipif(not HAS_AMD, reason="amd extra not installed")
def test_amd_ordering(diamond):
    from omdc.metrics.amdmetric import amd_distance

    d_strain = amd_distance(diamond, strained(diamond))
    d_poly = amd_distance(diamond, fcc_si())
    assert 0 < d_strain < d_poly


def test_exact_rmsd_matches_and_misses(diamond):
    assert exact_rmsd(diamond, diamond) == pytest.approx(0, abs=1e-8)
    assert exact_rmsd(diamond, strained(diamond)) < 0.1
    assert exact_rmsd(diamond, fcc_si()) > 0.0
