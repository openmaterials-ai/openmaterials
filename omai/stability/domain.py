"""The stability Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.stability import representation as stab_rep
from omai.stability.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "FormationEnergy": r"\Delta H_f",
    "EnergyAboveHull": r"E_{hull}",
    "SurfaceEnergy": r"\gamma_{surf}",
    "Voltage": r"V_{avg}",
    "AdsorptionEnergy": r"E_{ads}",
}

STABILITY = Domain(
    name="stability",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Stability",
            "Phase stability and electrochemistry: formation energies, "
            "distance to the convex hull, surface energetics, and "
            "intercalation voltages.",
        ),
    ),
    representation_package=stab_rep,
)
