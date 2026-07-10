"""The electronic-transport Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.electronic_transport import representation as et_rep
from omai.electronic_transport.operator import EDGES, NODES

SYMBOLS: dict[str, str] = {
    "StaticDielectricTensor": r"\varepsilon_0",
    "ElectricalConductivity[carrier=electronic]": r"\sigma_{el}",
    "SeebeckCoefficient": r"S",
    "ElectronicThermalConductivity": r"\kappa_e",
    "CarrierMobility": r"\mu_e",
}

ELECTRONIC_TRANSPORT = Domain(
    name="electronic_transport",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(),
    tiers=(
        (
            "Electronic transport",
            "Carrier transport from ab-initio scattering: electronic "
            "conductivity, Seebeck, electronic thermal conductivity, and "
            "mobility.",
        ),
    ),
    representation_package=et_rep,
)
