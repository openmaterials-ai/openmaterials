"""The materials Domain descriptor (grown from AtomisticSkills)."""
from __future__ import annotations

from omai.map_data import Domain
from omai.materials import representation as mat_rep
from omai.materials.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "Diffusivity": r"D",
    "ActivationEnergy": r"E_a",
}

MATERIALS = Domain(
    name="materials",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        ("Diffusion", "Mass transport from MD: self-diffusivity via the Einstein relation and the Arrhenius activation energy."),
    ),
    representation_package=mat_rep,
)
