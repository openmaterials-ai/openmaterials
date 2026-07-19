import numpy as np
import pytest

from fixtures_distance import diamond_si, doped, permuted, pristine_216, rotated, translated
from omdc.encoders import get_encoder


def test_registry_knows_hist_and_rejects_unknown():
    enc = get_encoder("hist")
    assert enc.pin.full_id == "hist@1"
    assert enc.pin.weights_sha256 == "none"
    assert get_encoder(enc) is enc
    with pytest.raises(KeyError, match="unknown encoder"):
        get_encoder("nope")


def test_shapes_and_dtype(diamond):
    v = get_encoder("hist").atom_vectors(diamond)
    assert v.shape == (len(diamond), 66) and v.dtype == np.float32


def test_euclidean_invariance(diamond):
    enc = get_encoder("hist")
    ref = enc.atom_vectors(diamond)
    for t in (rotated(diamond), translated(diamond)):
        np.testing.assert_allclose(enc.atom_vectors(t), ref, atol=1e-4)
    perm = enc.atom_vectors(permuted(diamond))
    np.testing.assert_allclose(np.sort(perm, axis=0), np.sort(ref, axis=0), atol=1e-4)


def test_species_channel_differs():
    enc = get_encoder("hist")
    a, b = enc.atom_vectors(pristine_216()), enc.atom_vectors(doped())
    assert not np.allclose(a[0], b[0])
