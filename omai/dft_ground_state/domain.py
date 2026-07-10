"""The DFT ground-state Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.dft_ground_state import representation as dft_rep
from omai.dft_ground_state.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "Structure": r"\mathcal{S}",
    "TotalEnergy": r"E_{tot}",
    "Forces": r"F^{at}",
    "Stress": r"\sigma",
    "MagneticMoment": r"m^{spin}",
    "BandGap": r"E_{gap}",
}

DFT_GROUND_STATE = Domain(
    name="dft_ground_state",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Ground state",
            "First-principles ground state: the total energy, forces, and "
            "stress a DFT engine computes for a structure under a chosen "
            "potential.",
        ),
    ),
    representation_package=dft_rep,
)
