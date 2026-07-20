"""omds: distances between simulations, the lineage record as the encoder.

omdc answers how far apart two configurations are; omds answers how far
apart two computations are, and divergence() answers where they part ways."""
from omds.mapgraph import MapGraph, default_graph
from omds.records import normalize_record
from omds.registry import (
    DEFAULT_ALIAS,
    DISTANCES,
    WEIGHTS,
    breakdown,
    distance,
    divergence,
    resolve,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_ALIAS",
    "DISTANCES",
    "MapGraph",
    "WEIGHTS",
    "breakdown",
    "default_graph",
    "distance",
    "divergence",
    "normalize_record",
    "resolve",
    "__version__",
]
