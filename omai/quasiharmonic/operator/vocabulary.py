r"""Formula symbol vocabulary of the quasi-harmonic domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.quasiharmonic.operator` is imported. Union semantics per space.

Each quasi-harmonic space carries its own new field symbol. The input side is
already covered by existing registrations: TotalEnergy's E_{tot}, Structure's
\mathcal{S}, Frequency's \omega (thermal-transport), the mode Gruneisen's
\gamma_G (thermal-transport), and BulkModulus's K (mechanics; the QHA route is a
Pattern C producer of the existing node, whose symbol set already carries K). The
opaque solver functions (G^{qha}, K^{qha}, \alpha^{qha}, C_P^{qha}, \gamma^{qha})
are applied functions, invisible to the free-symbol check, so they need no
entries. G_{qha} is deliberately distinct from the mechanics / dft E_{tot} and
from any Molar* free-energy symbol; \gamma_{th} is distinct from the mode \gamma_G.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    "QHAGibbsEnergy": {r"G_{qha}"},
    "ThermalExpansion": {r"\alpha_V"},
    "HeatCapacityConstantP": {"C_P"},
    "ThermalGruneisen": {r"\gamma_{th}"},
})
