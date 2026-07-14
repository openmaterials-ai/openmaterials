"""The composites (effective-medium) Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.composites import representation as comp_rep
from omai.composites.operator import EDGES, NODES

# Canonical LaTeX symbol per variable (consistent symbolic names, not words).
SYMBOLS: dict[str, str] = {
    "ThermalConductivity[role=matrix]": r"\kappa_m",
    "ThermalConductivity[role=filler]": r"\kappa_f",
    "InterfaceConductance": r"G",
    "FillerVolumeFraction": r"f",
    "DepolarizationFactor": r"L",
    "ThermalConductivity[effective_medium=nan,orientation=random]": r"\kappa_c",
    "ThermalConductivity[effective_medium=nan,orientation=aligned]": r"\kappa_c^{\parallel}",
}

COMPOSITES = Domain(
    name="composites",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Composite",
            "Composite effective thermal conductivity of a filled matrix with "
            "interfacial (Kapitza) resistance: the matrix and filler "
            "conductivities, the interface conductance, the filler volume "
            "fraction and depolarization factors, and the Nan-type "
            "effective-medium conductivity (random and aligned) cross-checked "
            "against the Hasselman-Johnson spherical limit.",
        ),
    ),
    representation_package=comp_rep,
)
