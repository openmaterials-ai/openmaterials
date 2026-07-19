"""A structure as a weighted set of local atomic environments.

Crystal: spglib symmetry-unique environments with multiplicity weights.
Disordered or large: deterministic farthest-point subsample (MAX_ENVS) with
nearest-assignment weights. Pooled vector: weighted mean concatenated with
elementwise max over L2-normalized environment vectors."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from scipy.spatial.distance import cdist

from omdc.encoders.base import Encoder, EncoderPin

MAX_ENVS = 256
SYMPREC = 1e-3  # matches omai/configurations.py


@dataclass(frozen=True)
class EnvironmentSet:
    vectors: np.ndarray
    weights: np.ndarray
    pooled: np.ndarray
    pin: EncoderPin
    atom_indices: np.ndarray
    # False when the set is the structure's exact environment distribution
    # (symmetry collapse succeeded); True when it samples a disordered cell,
    # where material-level comparison needs a debiased estimator.
    sampled: bool = True


def _normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vecs / norms).astype(np.float32)


def _symmetry_groups(structure: Structure) -> np.ndarray | None:
    try:
        ds = SpacegroupAnalyzer(structure, symprec=SYMPREC).get_symmetry_dataset()
    except Exception:
        return None
    if ds is None:
        return None
    eq = getattr(ds, "equivalent_atoms", None)
    if eq is None and isinstance(ds, dict):
        eq = ds.get("equivalent_atoms")
    return None if eq is None else np.asarray(eq)


def _fps(vectors: np.ndarray, k: int) -> np.ndarray:
    start = int(np.argmax(np.linalg.norm(vectors, axis=1)))
    chosen = [start]
    dist = np.linalg.norm(vectors - vectors[start], axis=1)
    while len(chosen) < k:
        nxt = int(np.argmax(dist))
        chosen.append(nxt)
        dist = np.minimum(dist, np.linalg.norm(vectors - vectors[nxt], axis=1))
    return np.asarray(sorted(chosen))


def embed(structure: Structure, encoder: Encoder) -> EnvironmentSet:
    vecs = encoder.atom_vectors(structure)
    n = len(vecs)
    groups = _symmetry_groups(structure)
    sampled = True
    if groups is not None and len(np.unique(groups)) <= MAX_ENVS:
        sel = np.unique(groups)
        weights = np.array([(groups == r).sum() for r in sel], dtype=np.float64)
        # A collapse to strictly fewer classes than atoms is real symmetry:
        # the set is the exact distribution. All-distinct classes mean a
        # disordered (P1) cell: a sample of the material.
        sampled = len(sel) == n
    elif n <= MAX_ENVS:
        sel = np.arange(n)
        weights = np.ones(n, dtype=np.float64)
    else:
        sel = _fps(vecs, MAX_ENVS)
        nearest = np.argmin(cdist(vecs, vecs[sel]), axis=1)
        weights = np.bincount(nearest, minlength=len(sel)).astype(np.float64)
    weights = weights / weights.sum()
    chosen = _normalize(vecs[sel])
    mean = (chosen * weights[:, None]).sum(axis=0)
    pooled = np.concatenate([mean, chosen.max(axis=0)]).astype(np.float32)
    return EnvironmentSet(
        vectors=chosen,
        weights=weights,
        pooled=pooled,
        pin=encoder.pin,
        atom_indices=sel,
        sampled=sampled,
    )
