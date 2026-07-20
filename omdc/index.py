"""Archive indexes. PooledIndex: brute-force cosine over pooled vectors in v1
(the API is the contract; an HNSW backend drops in behind it later).
MotifIndex: per-atom outlier environments for defect and impurity search,
concentration-independent by construction."""
from __future__ import annotations

import numpy as np

from omdc.envset import EnvironmentSet

# A defect is dilute AND different: an environment class qualifies as an
# outlier only when its weight is below MOTIF_HOST_WEIGHT (a 50% sublattice is
# never a defect) and its cosine distance to the nearest host mode exceeds
# MOTIF_TAU. Values calibrated on the vacancy and doped gate fixtures
# (2026-07-18): defect shells land at 4e-4 to 2e-3, symmetry-equivalent bulk
# classes at 1e-6 or below. Versioned constants of the motif index, not magic.
MOTIF_TAU = 1e-4
MOTIF_HOST_WEIGHT = 0.05


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n = np.where(n == 0, 1.0, n)
    return v / n


def funnel_search(query, entries, k: int = 10, margin: float = 1.0, stats: dict | None = None):
    """Exact env-ot kNN with latent-lb pruning, assembled from the certified
    bound. Candidates are visited in ascending bound order; once k exact
    distances are held, a candidate whose bound exceeds the kth best is
    pruned, and so is everything after it. No false dismissals when every
    set is symmetry-exact and margin == 1; pass margin > 1 as slack when
    sampled sets make the bound heuristic. Returns [(key, env_ot distance)]
    ascending; stats (optional dict) receives {"exact_evals": n}."""
    from omdc.metrics.ot import env_ot
    from omdc.metrics.pooled import latent_lb

    bounds = sorted((latent_lb(query, es), key) for key, es in entries.items())
    best: list[tuple[float, str]] = []
    evals = 0
    for bound, key in bounds:
        if len(best) == k and bound > best[-1][0] * margin:
            break
        d = env_ot(query, entries[key])
        evals += 1
        best.append((d, key))
        best.sort()
        del best[k:]
    if stats is not None:
        stats["exact_evals"] = evals
    return [(key, d) for d, key in best]


def host_modes(es: EnvironmentSet) -> np.ndarray:
    return es.vectors[es.weights >= MOTIF_HOST_WEIGHT]


def outliers(es: EnvironmentSet) -> np.ndarray:
    modes = host_modes(es)
    if len(modes) == 0:
        # No heavy classes (a glass): no host, so no defects to report.
        return np.empty(0, dtype=np.int64)
    dist = 1.0 - (es.vectors @ modes.T).max(axis=1)
    return np.where((dist > MOTIF_TAU) & (es.weights < MOTIF_HOST_WEIGHT))[0]


class PooledIndex:
    def __init__(self) -> None:
        self._keys: list[str] = []
        self._rows: list[np.ndarray] = []

    def add(self, key: str, es: EnvironmentSet) -> None:
        self._keys.append(key)
        self._rows.append(_unit(es.pooled.astype(np.float64)))

    def search(self, es: EnvironmentSet, k: int = 10) -> list[tuple[str, float]]:
        matrix = np.vstack(self._rows)
        dist = 1.0 - matrix @ _unit(es.pooled.astype(np.float64))
        order = np.argsort(dist)[:k]
        return [(self._keys[i], float(dist[i])) for i in order]


class MotifIndex:
    def __init__(self) -> None:
        self._entries: list[tuple[str, int]] = []
        self._rows: list[np.ndarray] = []

    def add(self, key: str, es: EnvironmentSet) -> None:
        for row in outliers(es):
            self._entries.append((key, int(es.atom_indices[row])))
            self._rows.append(es.vectors[row].astype(np.float64))

    def search(self, vector: np.ndarray, k: int = 10) -> list[tuple[str, int, float]]:
        if not self._rows:
            return []
        matrix = np.vstack(self._rows)
        dist = 1.0 - _unit(matrix) @ _unit(np.asarray(vector, dtype=np.float64))
        order = np.argsort(dist)[:k]
        return [(*self._entries[i], float(dist[i])) for i in order]
