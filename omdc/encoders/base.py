from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pymatgen.core import Structure


@dataclass(frozen=True)
class EncoderPin:
    """Full provenance of an embedding: which encoder, which weights, which knobs."""

    encoder_id: str
    version: int
    weights_sha256: str  # "none" for weight-free encoders, "unknown" if unresolvable
    hyperparams_hash: str

    @property
    def full_id(self) -> str:
        return f"{self.encoder_id}@{self.version}"


class Encoder:
    """Per-atom environment encoder. Subclasses set `pin` and implement `_atom_vectors`."""

    pin: EncoderPin

    def atom_vectors(self, structure: Structure) -> np.ndarray:
        return np.asarray(self._atom_vectors(structure), dtype=np.float32)

    def _atom_vectors(self, structure: Structure) -> np.ndarray:
        raise NotImplementedError
