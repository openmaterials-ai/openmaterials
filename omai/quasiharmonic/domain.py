"""The quasi-harmonic Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.quasiharmonic import representation as qha_rep
from omai.quasiharmonic.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "QHAGibbsEnergy": r"G_{qha}",
    "ThermalExpansion": r"\alpha_V",
    "HeatCapacityConstantP": r"C_P",
    "ThermalGruneisen": r"\gamma_{th}",
}

QUASIHARMONIC = Domain(
    name="quasiharmonic",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Quasi-harmonic",
            "Finite-temperature thermodynamics from the quasi-harmonic "
            "approximation: Gibbs energy, thermal expansion, constant-pressure "
            "heat capacity, and the thermal Gruneisen parameter.",
        ),
    ),
    representation_package=qha_rep,
)
