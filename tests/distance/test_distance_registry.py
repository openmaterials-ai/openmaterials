import importlib.util

import pytest

import omdc
from fixtures_distance import diamond_si, fcc_si

HAS_MACE = importlib.util.find_spec("mace") is not None


def test_registry_contents_and_metadata():
    assert set(omdc.DISTANCES) == {
        "env-ot@1", "latent@1", "comp@1", "amd@1", "exact@1",
        "latent-lb@1", "spectrum@1", "curve@1", "traj-ot@1",
    }
    assert "default" not in omdc.DISTANCES
    spec = omdc.resolve("default")
    assert spec.full_id == omdc.DEFAULT_ALIAS == "env-ot@1"
    assert spec.metric and not spec.ann_indexable
    assert omdc.resolve("comp").ann_indexable
    assert {"rotation", "supercell"} <= set(omdc.resolve("env-ot").invariances)


def test_bare_id_resolves_latest_and_unknown_raises():
    assert omdc.resolve("comp").full_id == "comp@1"
    with pytest.raises(KeyError, match="unknown distance"):
        omdc.resolve("nope")


def test_distance_with_named_channels(diamond):
    assert omdc.distance(diamond, fcc_si(), metric="comp") == 0.0
    d = omdc.distance(diamond, fcc_si(), metric="env-ot", encoder="hist")
    assert d > 0.01
    assert omdc.distance(diamond, diamond, metric="latent", encoder="hist") == pytest.approx(0, abs=1e-8)


@pytest.mark.skipif(HAS_MACE, reason="only meaningful without the mace extra")
def test_default_without_extra_raises_loudly(diamond):
    with pytest.raises(omdc.MissingExtraError, match=r"openmaterials-ai\[distance,mace\]"):
        omdc.distance(diamond, diamond)


def test_embed_returns_pinned_envset(diamond):
    es = omdc.embed(diamond, encoder="hist")
    assert es.pin.full_id == "hist@1"
