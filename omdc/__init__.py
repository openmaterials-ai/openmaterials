"""omdc: graded distances between atomic configurations.

The OpenMaterials hash answers "same or different"; omdc answers "how far"."""
from omdc.adapters import structure_key, to_structure
from omdc.encoders import get_encoder
from omdc.envset import EnvironmentSet
from omdc.envset import embed as _embed_envset
from omdc.errors import MissingExtraError
from omdc.registry import (
    DEFAULT_ALIAS,
    DEFAULT_ENCODER,
    DISTANCES,
    DistanceSpec,
    distance,
    resolve,
)

__version__ = "0.1.0"


def embed(structure, encoder: str = DEFAULT_ENCODER) -> EnvironmentSet:
    return _embed_envset(to_structure(structure), get_encoder(encoder))


__all__ = [
    "DEFAULT_ALIAS",
    "DEFAULT_ENCODER",
    "DISTANCES",
    "DistanceSpec",
    "EnvironmentSet",
    "MissingExtraError",
    "distance",
    "embed",
    "get_encoder",
    "resolve",
    "structure_key",
    "to_structure",
    "__version__",
]
