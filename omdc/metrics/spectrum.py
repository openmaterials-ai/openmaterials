"""spectrum@1 and curve@1: distances between one-dimensional data.

spectrum@1 treats a nonnegative curve (a DOS, a spectrum) as a mass
distribution and computes Wasserstein-1 as the L1 difference of the two
cumulative distributions on the merged grid. Mass-normalized: shapes are
compared, absolute intensity is not seen. A true metric on distributions.

curve@1 treats a curve as a FUNCTION of its x axis (kappa vs temperature):
symmetric relative L2 on the shared x range, interpolated to a common grid.
Scale-free across decades; not a true metric (relative scaling breaks the
triangle inequality), so it is registered metric=False."""
from __future__ import annotations

import numpy as np

_GRID = 256


def _sorted_xy(c) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(c[0], dtype=np.float64).ravel()
    y = np.asarray(c[1], dtype=np.float64).ravel()
    if x.shape != y.shape or x.size == 0:
        raise ValueError("a curve is (x, y) with matching nonempty shapes")
    order = np.argsort(x)
    return x[order], y[order]


def _mass_curve(c) -> tuple[np.ndarray, np.ndarray]:
    x, y = _sorted_xy(c)
    if (y < 0).any() or y.sum() <= 0:
        raise ValueError("a mass curve needs y >= 0 with positive total")
    return x, y / y.sum()


def spectrum_w1(a, b) -> float:
    xa, ya = _mass_curve(a)
    xb, yb = _mass_curve(b)
    xs = np.union1d(xa, xb)
    ca = np.interp(xs, xa, np.cumsum(ya), left=0.0, right=1.0)
    cb = np.interp(xs, xb, np.cumsum(yb), left=0.0, right=1.0)
    if xs.size < 2:
        return 0.0
    return float(np.sum(np.abs(ca - cb)[:-1] * np.diff(xs)))


def curve_rel(a, b) -> float:
    xa, ya = _sorted_xy(a)
    xb, yb = _sorted_xy(b)
    lo, hi = max(xa[0], xb[0]), min(xa[-1], xb[-1])
    if not lo < hi:
        raise ValueError("curves share no x range")
    xs = np.linspace(lo, hi, _GRID)
    fa = np.interp(xs, xa, ya)
    fb = np.interp(xs, xb, yb)
    scale = (np.abs(fa) + np.abs(fb)) / 2.0
    scale[scale == 0] = 1.0
    return float(np.sqrt(np.mean(((fa - fb) / scale) ** 2)))
