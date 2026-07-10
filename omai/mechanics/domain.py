"""The mechanics Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.mechanics import representation as mech_rep
from omai.mechanics.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "ElasticConstants": r"C",
    "BulkModulus": r"K",
    "ShearModulus": r"G",
    "Pressure": r"P",
    "YoungsModulus": r"E_Y",
    "PoissonRatio": r"\nu",
}

MECHANICS = Domain(
    name="mechanics",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Mechanics",
            "Continuum mechanical response: the elastic tensor, its isotropic "
            "moduli, and the pressure.",
        ),
    ),
    representation_package=mech_rep,
)
