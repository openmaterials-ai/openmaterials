import numpy as np
import pytest

import omdc
from omdc.metrics.phonon import ModeSet, phonon_ot


def _debye(n, seed, vmax=8.0, wmax=15.0, gamma=0.1):
    """A Debye-like mode population: linear dispersion with a velocity
    plateau, bandwidth growing as omega**2 (Klemens-like)."""
    rng = np.random.default_rng(seed)
    w = wmax * rng.random(n) ** (1 / 3)
    v = vmax * np.exp(-w / wmax) * (1 + 0.05 * rng.normal(size=n))
    b = gamma * (w / wmax) ** 2 * (1 + 0.1 * rng.normal(size=n))
    cv = np.ones(n)
    return ModeSet.from_arrays(w, v, bandwidth=np.abs(b), weights=cv)


def test_same_distribution_reads_near_zero():
    same = phonon_ot(_debye(400, 1), _debye(400, 2))
    soft = phonon_ot(_debye(400, 1), _debye(400, 3, wmax=10.0))
    assert same < 0.25 * soft


def test_same_kappa_different_mechanism_is_visible():
    boundary = _debye(400, 5, gamma=0.5)  # strongly scattered everywhere
    anharmonic = _debye(400, 6, gamma=0.02)  # weakly scattered
    d = phonon_ot(boundary, anharmonic)
    same = phonon_ot(_debye(400, 7, gamma=0.5), _debye(400, 8, gamma=0.5))
    assert d > 3 * same


def test_harmonic_only_drops_bandwidth_for_both():
    full = _debye(200, 9)
    harmonic = ModeSet.from_arrays(full.points[:, 0], full.points[:, 1])
    assert not harmonic.has_bandwidth
    d = phonon_ot(full, harmonic)  # compares on the shared 2 axes
    assert np.isfinite(d)


def test_gamma_modes_and_bad_shapes():
    ms = ModeSet.from_arrays([0.0, 0.0, 0.0, 5.0], [0, 0, 0, 3.0])
    assert len(ms.points) == 1  # the three acoustic Gamma modes dropped
    with pytest.raises(ValueError, match="disagree"):
        ModeSet.from_arrays([1.0, 2.0], [1.0])
    with pytest.raises(ValueError, match="no positive-frequency"):
        ModeSet.from_arrays([0.0], [1.0])


def test_from_kaldo_layout(tmp_path):
    sub = tmp_path / "300" / "quantum"
    sub.mkdir(parents=True)
    ref = _debye(100, 11)
    np.save(sub / "frequency.npy", ref.points[:, 0])
    np.save(sub / "velocity.npy", np.stack([ref.points[:, 1], np.zeros(100), np.zeros(100)], axis=1))
    np.save(sub / "bandwidth.npy", ref.points[:, 2])
    loaded = ModeSet.from_kaldo(tmp_path)
    assert loaded.has_bandwidth and len(loaded.points) == 100
    assert phonon_ot(loaded, ref) == pytest.approx(0, abs=1e-9)
    with pytest.raises(FileNotFoundError, match="kaldo output folder"):
        ModeSet.from_kaldo(tmp_path / "empty")


def test_registry_entry():
    spec = omdc.resolve("phonon-ot")
    assert spec.input == "modeset" and spec.metric and not spec.needs_encoder
    d = omdc.distance(_debye(100, 20), _debye(100, 21), metric="phonon-ot")
    assert 0 <= d < 1.0
