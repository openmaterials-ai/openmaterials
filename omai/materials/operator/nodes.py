"""Operator nodes for the materials domain (grown from AtomisticSkills)."""
from __future__ import annotations

from omai.operator.dimensions import DIFFUSIVITY, ENERGY
from omai.operator.space import Field, ObservableSpace, Space

DIFFUSIVITY_STATE = ObservableSpace(
    name="Diffusivity",
    fields=(Field("D", DIFFUSIVITY, indices=()),),
    description=(
        "Self-diffusion coefficient D from the Einstein relation "
        "MSD(t) = 2 d D t in the linear regime. Produced from "
        "MeanSquaredDisplacement; per temperature."
    ),
    tier="Diffusion",
)

ACTIVATION_ENERGY = ObservableSpace(
    name="ActivationEnergy",
    fields=(Field("E_a", ENERGY, indices=()),),
    description=(
        "Arrhenius activation energy E_a from D(T) = D0 exp(-E_a/k_B T), "
        "obtained by a weighted fit over diffusivities at several temperatures."
    ),
    tier="Diffusion",
)

NODES: tuple[Space, ...] = (DIFFUSIVITY_STATE, ACTIVATION_ENERGY)
