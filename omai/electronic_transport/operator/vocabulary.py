r"""Formula symbol vocabulary of the electronic-transport domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.electronic_transport.operator` is imported. Union semantics per space.

Each electronic-transport space carries its own new field symbol. The input
side is already covered by the existing registrations: DielectricTensor's
\varepsilon_\infty, BornCharges' Z^*, Frequency's \omega (thermal-transport),
ElasticConstants' C (mechanics), and Structure's \mathcal{S} (ground state).
The opaque solver functions (\varepsilon_0^{stat}, \sigma^{bte}, S^{bte},
\kappa_e^{bte}, \mu^{bte}) are applied functions, invisible to the free-symbol
check, so they need no entries. \sigma_{el} is the electronic conductivity
symbol, deliberately distinct from the materials \sigma_{ion}.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    "StaticDielectricTensor": {r"\varepsilon_0"},
    "ElectricalConductivity[carrier=electronic]": {r"\sigma_{el}"},
    "SeebeckCoefficient": {"S"},
    "ElectronicThermalConductivity": {r"\kappa_e"},
    "CarrierMobility": {r"\mu_e"},
    # ElectronicDOS: the output density g_E and its own energy-binning axis E
    # (the spectral variable the delta sum runs over), exactly as PhononDOS
    # owns g and its omega binning.
    "ElectronicDOS": {"g_E", "E"},
})
