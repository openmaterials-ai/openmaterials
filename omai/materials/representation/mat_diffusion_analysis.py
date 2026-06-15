"""mat-diffusion-analysis skill as a representation over the materials DAG."""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.nodes import ACTIVATION_ENERGY, DIFFUSIVITY_STATE

DIFFUSION_DIFFUSIVITY = SpaceRepresentationSpec(
    space=DIFFUSIVITY_STATE,
    representation_name="mat-diffusion-analysis",
    observable_units={"D": "cm^2/s"},
    code_api={"D": "scripts/analyze_diffusion.py"},
    notes="pymatgen DiffusionAnalyzer over an MLIP MD trajectory; Einstein slope.",
)

DIFFUSION_ACTIVATION = SpaceRepresentationSpec(
    space=ACTIVATION_ENERGY,
    representation_name="mat-diffusion-analysis",
    observable_units={"E_a": "eV"},
    code_api={"E_a": "scripts/calculate_activation_energy.py"},
    notes="Weighted Arrhenius fit over multi-temperature diffusivities.",
)
