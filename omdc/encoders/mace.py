"""mace-mp-0-small@1: per-atom invariant features from the MACE-MP-0 foundation
model. The traversal encoder: one fixed-dimensional space across the periodic
table. Weights are pinned by sha256 of the model file when resolvable."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

from omdc.encoders.base import Encoder, EncoderPin
from omdc.errors import MissingExtraError

MODEL_SIZE = "small"


@lru_cache(maxsize=2)
def _load_calc(model_size: str):
    try:
        from mace.calculators import mace_mp
    except ImportError as exc:
        raise MissingExtraError(
            "the MACE encoder (default for env-ot and latent)", "mace"
        ) from exc
    return mace_mp(model=model_size, device="cpu", default_dtype="float64")


class MaceEncoder(Encoder):
    """num_layers selects the receptive-field rung: layer l sees roughly l
    times the model cutoff, and -1 concatenates all layers (the default
    traversal space). The heavy calculator is loaded once and shared; each
    num_layers value still mints its own hyperparams hash."""

    def __init__(self, num_layers: int = -1) -> None:
        self._calc = _load_calc(MODEL_SIZE)
        self.num_layers = int(num_layers)
        weights = "unknown"
        paths = getattr(self._calc, "model_paths", None) or []
        if paths and Path(paths[0]).exists():
            weights = hashlib.sha256(Path(paths[0]).read_bytes()).hexdigest()
        hp = {"model": MODEL_SIZE, "invariants_only": True, "num_layers": self.num_layers}
        self.pin = EncoderPin(
            encoder_id=f"mace-mp-0-{MODEL_SIZE}",
            version=1,
            weights_sha256=weights,
            hyperparams_hash=hashlib.sha256(json.dumps(hp, sort_keys=True).encode()).hexdigest(),
        )

    def _atom_vectors(self, structure: Structure) -> np.ndarray:
        atoms = AseAtomsAdaptor.get_atoms(structure)
        try:
            return self._calc.get_descriptors(
                atoms, invariants_only=True, num_layers=self.num_layers
            )
        except TypeError:
            if self.num_layers != -1:
                raise RuntimeError(
                    "this mace version does not support num_layers selection; "
                    "upgrade mace-torch for layer profiles"
                ) from None
            return self._calc.get_descriptors(atoms)
