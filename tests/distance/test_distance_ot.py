import numpy as np
import pytest

from fixtures_distance import diamond_si, glass, rotated
from omdc.encoders import get_encoder
from omdc.envset import embed
from omdc.metrics.ot import env_ot
from omdc.metrics.pooled import pooled_cosine


def _es(s):
    return embed(s, get_encoder("hist"))


def test_self_distance_zero(diamond):
    assert env_ot(_es(diamond), _es(diamond)) == pytest.approx(0, abs=1e-8)
    assert pooled_cosine(_es(diamond), _es(diamond)) == pytest.approx(0, abs=1e-8)


def test_rotation_invariance(diamond):
    assert env_ot(_es(diamond), _es(rotated(diamond))) == pytest.approx(0, abs=1e-4)


def test_symmetry_of_the_distance(diamond):
    a, b = _es(diamond), _es(glass(1, rep=3))
    assert env_ot(a, b) == pytest.approx(env_ot(b, a), rel=1e-6)
    assert env_ot(a, b) > 0.01


def test_pin_mismatch_raises(diamond):
    from dataclasses import replace

    a = _es(diamond)
    b = a.__class__(a.vectors, a.weights, a.pooled, replace(a.pin, version=2), a.atom_indices)
    with pytest.raises(ValueError, match="different encoders"):
        env_ot(a, b)
    with pytest.raises(ValueError, match="different encoders"):
        pooled_cosine(a, b)


def _mk(v, sampled):
    from omdc.encoders.base import EncoderPin
    from omdc.envset import EnvironmentSet, _normalize

    n = len(v)
    pin = EncoderPin("hist", 1, "none", "x")
    return EnvironmentSet(
        _normalize(v), np.full(n, 1 / n), np.zeros(16, np.float32), pin, np.arange(n), sampled
    )


def test_energy_path_orders_by_separation():
    from omdc.metrics import ot as motu

    rng = np.random.default_rng(0)
    va = rng.normal(size=(300, 8))
    vb = rng.normal(size=(300, 8))
    near = motu.env_ot(_mk(va, True), _mk(vb + 0.5, True))
    far = motu.env_ot(_mk(va, True), _mk(vb + 2.0, True))
    assert 0 < near < far


def test_energy_path_kills_finite_sample_floor():
    from omdc.metrics import ot as motu

    rng = np.random.default_rng(1)
    va = rng.normal(size=(300, 8))
    vb = rng.normal(size=(300, 8))  # independent draws, same distribution
    same = motu.env_ot(_mk(va, True), _mk(vb, True))
    apart = motu.env_ot(_mk(va, True), _mk(vb + 2.0, True))
    # Measured floor: 0.092 at n=300 shrinking to 0.044 at n=1000 (the
    # n**(-1/2) energy-distance bias in sqrt scale) vs apart=0.913.
    assert same < 0.15 * apart
