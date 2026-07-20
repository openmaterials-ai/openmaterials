import numpy as np
import pytest

import omdc
from fixtures_distance import diamond_si, fcc_si, rattled
from omdc.metrics.traj import keyframes, traj_ot


def _walk(base, sigma, seeds):
    return [rattled(base, sigma, s) for s in seeds]


def test_same_protocol_trajectories_are_near():
    a1 = _walk(diamond_si(), 0.15, range(0, 8))
    a2 = _walk(diamond_si(), 0.15, range(100, 108))
    b = _walk(fcc_si(), 0.15, range(200, 208))
    near = traj_ot(a1, a2, encoder="hist")
    far = traj_ot(a1, b, encoder="hist")
    assert near < 0.3 * far


def test_env_ot_ground_agrees_on_ordering():
    a1 = _walk(diamond_si(), 0.15, range(0, 4))
    a2 = _walk(diamond_si(), 0.15, range(100, 104))
    b = _walk(fcc_si(), 0.15, range(200, 204))
    assert traj_ot(a1, a2, encoder="hist", ground="env-ot") < traj_ot(a1, b, encoder="hist", ground="env-ot")


def test_unknown_ground_raises():
    frames = _walk(diamond_si(), 0.1, range(2))
    with pytest.raises(ValueError, match="unknown ground"):
        traj_ot(frames, frames, encoder="hist", ground="nope")


def test_keyframes_monotone_in_threshold():
    drift = [diamond_si(5.43 + 0.01 * i) for i in range(12)]
    tight = keyframes(drift, threshold=1e-4, encoder="hist")
    loose = keyframes(drift, threshold=0.05, encoder="hist")
    assert tight[0] == 0 and loose[0] == 0
    assert len(loose) <= len(tight) <= 12
    assert len(loose) < 12


def test_registry_entry():
    spec = omdc.resolve("traj-ot")
    assert spec.input == "trajectory" and spec.needs_encoder
    frames = _walk(diamond_si(), 0.1, range(3))
    d = omdc.distance(frames, frames, metric="traj-ot", encoder="hist")
    assert d == pytest.approx(0, abs=1e-6)
