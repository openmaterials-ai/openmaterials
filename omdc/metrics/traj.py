"""traj-ot@1: distance between trajectories (sequences of configurations).

A trajectory is always a SAMPLE of an ensemble, so the estimator is the
square root of the energy distance over frame representations (the same
recursion rule as env-ot's sampled path, one level up). The ground metric
between frames is either euclidean between weighted-mean environment vectors
(ground="mean", fast, and a certified lower bound of frame env-ot in the
exact regime) or full env-ot between frame environment sets
(ground="env-ot", quadratic in frames, sharper).

keyframes() greedily thins a trajectory: a frame is kept when its mean
vector moved more than `threshold` from the last kept frame. Because the
mean distance lower-bounds env-ot for exact sets, dropped frames are within
threshold of their keeper in the certified-bound sense."""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import cdist

from omdc.adapters import to_structure
from omdc.encoders import get_encoder
from omdc.envset import embed
from omdc.metrics.ot import env_ot


def _mean_rows(frames, enc):
    sets = [embed(to_structure(f), enc) for f in frames]
    if not sets:
        raise ValueError("a trajectory needs at least one frame")
    d = sets[0].vectors.shape[1]
    return np.stack([es.pooled[:d].astype(np.float64) for es in sets]), sets


def traj_ot(frames_a, frames_b, encoder="hist", ground="mean") -> float:
    enc = get_encoder(encoder)
    ma, sa = _mean_rows(frames_a, enc)
    mb, sb = _mean_rows(frames_b, enc)
    if ground == "mean":
        cab, caa, cbb = cdist(ma, mb), cdist(ma, ma), cdist(mb, mb)
    elif ground == "env-ot":
        cab = np.array([[env_ot(a, b) for b in sb] for a in sa])
        caa = np.array([[env_ot(a, b) for b in sa] for a in sa])
        cbb = np.array([[env_ot(a, b) for b in sb] for a in sb])
    else:
        raise ValueError(f"unknown ground {ground!r}; known: 'mean', 'env-ot'")
    energy = 2.0 * cab.mean() - caa.mean() - cbb.mean()
    return float(np.sqrt(max(energy, 0.0)))


def keyframes(frames, threshold: float, encoder="hist") -> list[int]:
    enc = get_encoder(encoder)
    rows, _ = _mean_rows(frames, enc)
    kept = [0]
    for i in range(1, len(rows)):
        if np.linalg.norm(rows[i] - rows[kept[-1]]) > threshold:
            kept.append(i)
    return kept
