"""env-ot@1: transport-family distance between weighted environment sets.

Two estimators behind one id, chosen by what the sets ARE:

- Both sets exact (symmetry-collapsed crystal distributions): exact EMD,
  Wasserstein-1, a true metric on the cell's environment distribution.
- Either set sampled (disordered or subsampled cell): the square root of the
  energy distance (Szekely), computed on the weighted sets. Two independent
  finite realizations of the same material genuinely differ as multisets, and
  empirical Wasserstein carries a finite-sample floor decaying only as
  n**(-1/d); the energy distance is zero exactly when the underlying
  distributions agree, with n**(-1/2) sample bias, no tuning parameter, and
  full determinism. Its square root is a metric.

The two paths share the contract that matters for traversal: zero for the
same material-level environment distribution, monotone in dissimilarity,
bounded by the ground-space diameter. Scales are commensurate but not
identical across paths; ranked comparisons should stay within one regime.

Ground metric: euclidean between L2-normalized environment vectors."""
from __future__ import annotations

import numpy as np
import ot as pot
from scipy.spatial.distance import cdist

from omdc.envset import EnvironmentSet

EXACT_MAX_PAIRS = 65536


def _check(a: EnvironmentSet, b: EnvironmentSet) -> None:
    if a.pin != b.pin:
        raise ValueError(
            f"environment sets from different encoders: {a.pin.full_id} vs {b.pin.full_id}"
        )


def _energy(wa, va, wb, vb) -> float:
    cross = float(wa @ cdist(va, vb) @ wb)
    self_a = float(wa @ cdist(va, va) @ wa)
    self_b = float(wb @ cdist(vb, vb) @ wb)
    return float(np.sqrt(max(2.0 * cross - self_a - self_b, 0.0)))


def env_ot(a: EnvironmentSet, b: EnvironmentSet) -> float:
    _check(a, b)
    va = a.vectors.astype(np.float64)
    vb = b.vectors.astype(np.float64)
    wa = np.ascontiguousarray(a.weights, dtype=np.float64)
    wb = np.ascontiguousarray(b.weights, dtype=np.float64)
    exact = not (a.sampled or b.sampled)
    if exact and va.shape[0] * vb.shape[0] <= EXACT_MAX_PAIRS:
        return float(pot.emd2(wa, wb, cdist(va, vb)))
    return _energy(wa, va, wb, vb)
