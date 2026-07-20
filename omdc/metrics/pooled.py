"""latent@1 and latent-lb@1: distances over pooled environment vectors.

latent@1 is cosine over the full pooled vector (mean plus max), the ANN key.
latent-lb@1 is euclidean between the weighted-MEAN halves alone: by
Kantorovich duality with a linear test function, the distance between means
never exceeds Wasserstein-1, so on symmetry-exact sets latent-lb is a
certified lower bound of env-ot@1 and prunes without false dismissals. On
sampled sets (energy-distance regime) the bound is heuristic; the funnel
takes a margin there."""
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


def latent_lb(a: EnvironmentSet, b: EnvironmentSet) -> float:
    _check(a, b)
    d = a.vectors.shape[1]
    ma = a.pooled[:d].astype(np.float64)
    mb = b.pooled[:d].astype(np.float64)
    return float(np.linalg.norm(ma - mb))
