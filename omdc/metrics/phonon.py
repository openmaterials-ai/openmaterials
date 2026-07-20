"""phonon-ot@1: distance between phonon mode populations.

A material's vibrational fingerprint is its set of modes, each a point in
(frequency, group-velocity magnitude, bandwidth) space, weighted by heat
capacity when available (the transport-relevant weighting) and uniformly
otherwise. Two mode sets are always finite samples of the Brillouin zone,
so the estimator is the sampled-regime rule of this layer: the square root
of the energy distance (the same recursion as env-ot's sampled path and
traj-ot). Zero exactly when the underlying mode distributions agree, so two
k-point convergences of the same material read as the same physics.

Axes are z-scored jointly (mean and scale from the pooled pair) so THz,
km/s, and 1/ps enter comparably; missing bandwidth (harmonic-only runs)
drops that axis for BOTH sides. This sees "same kappa, different
mechanism": boundary-scattering-limited and anharmonicity-limited silicon
agree in kappa yet differ loudly here.

ModeSet.from_kaldo reads a kaldo output folder (frequency.npy,
velocity.npy, bandwidth.npy, heat_capacity.npy; kaldo's storable layout).
Zero-frequency acoustic modes at Gamma carry no weight and are dropped."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

FREQ_FLOOR = 1e-6


@dataclass(frozen=True)
class ModeSet:
    """Columns: frequency, |velocity|, bandwidth (bandwidth may be absent)."""

    points: np.ndarray  # (n, 2) or (n, 3) float64
    weights: np.ndarray  # (n,), sums to 1
    has_bandwidth: bool

    @classmethod
    def from_arrays(cls, frequency, velocity, bandwidth=None, weights=None) -> "ModeSet":
        f = np.asarray(frequency, dtype=np.float64).ravel()
        v = np.asarray(velocity, dtype=np.float64)
        if v.ndim > 1:
            v = np.linalg.norm(v.reshape(-1, v.shape[-1]), axis=1)
        v = v.ravel()
        if f.shape != v.shape:
            raise ValueError(f"frequency and velocity disagree: {f.shape} vs {v.shape}")
        cols = [f, v]
        if bandwidth is not None:
            b = np.asarray(bandwidth, dtype=np.float64).ravel()
            if b.shape != f.shape:
                raise ValueError("bandwidth shape mismatch")
            cols.append(b)
        w = (
            np.asarray(weights, dtype=np.float64).ravel()
            if weights is not None
            else np.ones_like(f)
        )
        keep = f > FREQ_FLOOR
        pts = np.stack(cols, axis=1)[keep]
        w = np.clip(w[keep], 0.0, None)
        if not len(pts) or w.sum() <= 0:
            raise ValueError("no positive-frequency modes with positive weight")
        return cls(points=pts, weights=w / w.sum(), has_bandwidth=bandwidth is not None)

    @classmethod
    def from_kaldo(cls, folder: str | Path) -> "ModeSet":
        folder = Path(folder)

        def grab(name):
            hits = sorted(folder.rglob(f"{name}.npy"))
            return np.load(hits[0]) if hits else None

        f = grab("frequency")
        v = grab("velocity")
        if f is None or v is None:
            raise FileNotFoundError(
                f"no frequency.npy / velocity.npy under {folder}; is this a kaldo output folder?"
            )
        return cls.from_arrays(f, v, bandwidth=grab("bandwidth"), weights=grab("heat_capacity"))


def phonon_ot(a: ModeSet, b: ModeSet) -> float:
    from scipy.spatial.distance import cdist

    dims = min(a.points.shape[1], b.points.shape[1])
    pa, pb = a.points[:, :dims], b.points[:, :dims]
    pooled = np.vstack([pa, pb])
    mean = pooled.mean(axis=0)
    scale = pooled.std(axis=0)
    scale[scale == 0] = 1.0
    za, zb = (pa - mean) / scale, (pb - mean) / scale
    wa = np.ascontiguousarray(a.weights)
    wb = np.ascontiguousarray(b.weights)
    cross = float(wa @ cdist(za, zb) @ wb)
    self_a = float(wa @ cdist(za, za) @ wa)
    self_b = float(wb @ cdist(zb, zb) @ wb)
    return float(np.sqrt(max(2.0 * cross - self_a - self_b, 0.0)))
