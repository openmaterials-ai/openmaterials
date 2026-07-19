"""latent@1: cosine distance over pooled environment vectors, the ANN index key."""
from __future__ import annotations

import numpy as np

from omdc.envset import EnvironmentSet
from omdc.metrics.ot import _check


def pooled_cosine(a: EnvironmentSet, b: EnvironmentSet) -> float:
    _check(a, b)
    va, vb = a.pooled.astype(np.float64), b.pooled.astype(np.float64)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0 if np.allclose(va, vb) else 1.0
    return float(1.0 - va @ vb / denom)
