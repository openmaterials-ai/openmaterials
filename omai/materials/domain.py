"""The materials Domain descriptor (grown from AtomisticSkills)."""
from __future__ import annotations

from omai.map_data import Domain
from omai.materials import representation as mat_rep
from omai.materials.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {}

MATERIALS = Domain(
    name="materials",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    representation_package=mat_rep,
)
