"""hist@1: a deterministic, dependency-free reference encoder.

Gaussian-smeared radial histograms of the neighbor shell (one channel for all
neighbors, one weighted by neighbor atomic number) plus two scalars for the
central atom (Z and Pettifor number, scaled). Euclidean- and permutation-
invariant by construction, continuous under small rattles. A reference and CI
encoder: chemistry-aware only through atomic number and blind beyond CUTOFF.
The traversal encoder is MACE (omdc.encoders.mace)."""
from __future__ import annotations

import hashlib
import json

import numpy as np
from pymatgen.core import Structure

from omdc.encoders.base import Encoder, EncoderPin

CUTOFF = 5.0
NBINS = 32
# Smearing at the thermal-displacement scale: broad enough that two finite
# samples of the same disordered material overlap, sharp enough to separate
# polymorphs (measured on the gate fixtures, 2026-07-18).
SIGMA = 0.2
# Species scalars scaled to carry weight comparable to the geometry
# histograms; at 1x a P dopant in Si sits 1e-6 in cosine distance from bulk
# (invisible), at 20x it clears the motif threshold with an order of margin.
SPECIES_WEIGHT = 20.0


class HistogramEncoder(Encoder):
    def __init__(self) -> None:
        hp = {"cutoff": CUTOFF, "nbins": NBINS, "sigma": SIGMA, "species_weight": SPECIES_WEIGHT}
        self.pin = EncoderPin(
            encoder_id="hist",
            version=1,
            weights_sha256="none",
            hyperparams_hash=hashlib.sha256(
                json.dumps(hp, sort_keys=True).encode()
            ).hexdigest(),
        )

    def _atom_vectors(self, structure: Structure) -> np.ndarray:
        centers = np.linspace(0.0, CUTOFF, NBINS, endpoint=False) + CUTOFF / NBINS / 2
        out = np.zeros((len(structure), 2 * NBINS + 2), dtype=np.float64)
        for i, shell in enumerate(structure.get_all_neighbors(CUTOFF)):
            plain = np.zeros(NBINS)
            zweighted = np.zeros(NBINS)
            for n in shell:
                w = np.exp(-0.5 * ((centers - n.nn_distance) / SIGMA) ** 2)
                plain += w
                zweighted += w * (n.specie.Z / 100.0)
            site = structure[i].specie
            scalars = [
                SPECIES_WEIGHT * site.Z / 100.0,
                SPECIES_WEIGHT * float(site.mendeleev_no or site.Z) / 103.0,
            ]
            out[i] = np.concatenate([plain, zweighted, scalars])
        return out
