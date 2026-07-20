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
    """The module constants are the defaults; a custom cutoff gives the
    scale-profile ladder (omdc.profile). Bin width is held fixed, so nbins
    scales with the cutoff (capped at 128), and every parameter set mints its
    own hyperparams hash: embeddings at different scales never mix."""

    def __init__(
        self,
        cutoff: float = CUTOFF,
        nbins: int | None = None,
        sigma: float = SIGMA,
        species_weight: float = SPECIES_WEIGHT,
    ) -> None:
        self.cutoff = float(cutoff)
        self.nbins = int(nbins) if nbins else max(16, min(128, round(NBINS * self.cutoff / CUTOFF)))
        self.sigma = float(sigma)
        self.species_weight = float(species_weight)
        hp = {
            "cutoff": self.cutoff,
            "nbins": self.nbins,
            "sigma": self.sigma,
            "species_weight": self.species_weight,
        }
        self.pin = EncoderPin(
            encoder_id="hist",
            version=1,
            weights_sha256="none",
            hyperparams_hash=hashlib.sha256(
                json.dumps(hp, sort_keys=True).encode()
            ).hexdigest(),
        )

    def _atom_vectors(self, structure: Structure) -> np.ndarray:
        centers = np.linspace(0.0, self.cutoff, self.nbins, endpoint=False) + self.cutoff / self.nbins / 2
        out = np.zeros((len(structure), 2 * self.nbins + 2), dtype=np.float64)
        for i, shell in enumerate(structure.get_all_neighbors(self.cutoff)):
            plain = np.zeros(self.nbins)
            zweighted = np.zeros(self.nbins)
            for n in shell:
                w = np.exp(-0.5 * ((centers - n.nn_distance) / self.sigma) ** 2)
                plain += w
                zweighted += w * (n.specie.Z / 100.0)
            site = structure[i].specie
            scalars = [
                self.species_weight * site.Z / 100.0,
                self.species_weight * float(site.mendeleev_no or site.Z) / 103.0,
            ]
            out[i] = np.concatenate([plain, zweighted, scalars])
        return out
