"""The thermodynamic-identities Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.thermodynamic_identities import representation as ti_rep
from omai.thermodynamic_identities.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "ThermalConductivity[contribution=total]": r"\kappa_{tot}",
    "MolarVolume": "V_m",
    "PowerFactor": "PF",
    "ZT": "ZT",
}

THERMODYNAMIC_IDENTITIES = Domain(
    name="thermodynamic_identities",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Thermoelectric",
            "Thermodynamic identities combining the map's own formulas: the "
            "thermal Gruneisen relation and C_P - C_V (second producers), the "
            "molar volume, the total thermal conductivity (lattice + electronic), "
            "the thermoelectric power factor, and the dimensionless figure of "
            "merit ZT.",
        ),
    ),
    representation_package=ti_rep,
)
