"""Embedding cache: parquet rows keyed by (structure_key, encoder pin).
Derived data, rebuildable, never identity-bearing."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from omdc.encoders.base import EncoderPin
from omdc.envset import EnvironmentSet

_FIELDS = [
    "structure_key", "encoder_id", "encoder_version", "weights_sha256",
    "hyperparams_hash", "dim", "pooled", "env_vectors", "env_weights",
    "atom_indices", "sampled",
]


def save(path: str | Path, entries: dict[str, EnvironmentSet]) -> None:
    rows: dict[str, list] = {f: [] for f in _FIELDS}
    for key, es in entries.items():
        rows["structure_key"].append(key)
        rows["encoder_id"].append(es.pin.encoder_id)
        rows["encoder_version"].append(es.pin.version)
        rows["weights_sha256"].append(es.pin.weights_sha256)
        rows["hyperparams_hash"].append(es.pin.hyperparams_hash)
        rows["dim"].append(es.vectors.shape[1])
        rows["pooled"].append(es.pooled.astype(np.float32).tolist())
        rows["env_vectors"].append(es.vectors.astype(np.float32).reshape(-1).tolist())
        rows["env_weights"].append(np.asarray(es.weights, dtype=np.float64).tolist())
        rows["atom_indices"].append(np.asarray(es.atom_indices, dtype=np.int64).tolist())
        rows["sampled"].append(bool(es.sampled))
    pq.write_table(pa.table(rows), path)


def load(path: str | Path) -> dict[str, EnvironmentSet]:
    t = pq.read_table(path).to_pydict()
    out: dict[str, EnvironmentSet] = {}
    for i, key in enumerate(t["structure_key"]):
        dim = t["dim"][i]
        pin = EncoderPin(
            t["encoder_id"][i], t["encoder_version"][i],
            t["weights_sha256"][i], t["hyperparams_hash"][i],
        )
        out[key] = EnvironmentSet(
            vectors=np.asarray(t["env_vectors"][i], dtype=np.float32).reshape(-1, dim),
            weights=np.asarray(t["env_weights"][i], dtype=np.float64),
            pooled=np.asarray(t["pooled"][i], dtype=np.float32),
            pin=pin,
            atom_indices=np.asarray(t["atom_indices"][i], dtype=np.int64),
            sampled=bool(t["sampled"][i]),
        )
    return out
