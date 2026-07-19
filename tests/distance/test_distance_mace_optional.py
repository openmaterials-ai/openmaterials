import importlib.util

import pytest

import omdc
from fixtures_distance import diamond_si, strained

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("mace") is None, reason="mace extra not installed"
)


def test_mace_smoke(diamond):
    es = omdc.embed(diamond, encoder="mace")
    assert es.pin.encoder_id == "mace-mp-0-small"
    assert es.vectors.shape[1] > 8
    assert omdc.distance(diamond, diamond) == pytest.approx(0, abs=1e-6)


def test_default_resolves_env_ot(diamond):
    d = omdc.distance(diamond, strained(diamond))
    assert 0 < d < 1.0
