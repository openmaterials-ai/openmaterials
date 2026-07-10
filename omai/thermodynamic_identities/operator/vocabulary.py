r"""Formula symbol vocabulary of the thermodynamic-identities domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.thermodynamic_identities.operator` is imported. Union semantics per space.

Every INPUT symbol these six identities reference is already registered by the
domain that owns the input node (ThermalExpansion's \alpha_V, BulkModulus's K,
VolumetricHeatCapacity's C_V^{vol}, MolarHeatCapacity's C_V^{mol}, the direct-BTE
and electronic \kappa / \kappa_e, ElectricalConductivity[carrier=electronic]'s
\sigma_{el}, SeebeckCoefficient's S, Temperature's T, and the generic constant
N_A), so only the four NEW output field symbols need registering here, each on its
producing node's output space plus, where an identity reads the promoted
CellVolume, the V_{cell} parameter symbol.

  * ThermalGruneisen already carries \gamma_{th} (QHA); this domain's second
    producer reuses it (no new registration needed, but declared for locality).
  * MolarVolume carries V_m (new) and, because contract_molar_volume reads the
    promoted CellVolume, the V_{cell} parameter symbol so the free-symbol gate
    accepts the nullary V_m = N_A V_cell formula.
  * PowerFactor carries PF (new); ZT carries ZT (new); the total kappa node carries
    \kappa_{tot} (new). ZT is deliberately the bare token ZT (not Z T, which would
    read as two symbols); it renders fine.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The total kappa sum output symbol.
    "ThermalConductivity[contribution=total]": {r"\kappa_{tot}"},
    # MolarVolume: its own field V_m plus the promoted CellVolume symbol V_{cell}
    # the nullary producer reads (V_m = N_A V_cell).
    "MolarVolume": {"V_m", "V_{cell}"},
    # PowerFactor and ZT field symbols.
    "PowerFactor": {"PF"},
    "ZT": {"ZT"},
    # ThermalGruneisen's thermal-Gruneisen symbol (already registered by QHA;
    # re-declared here for the second producer's locality, union semantics).
    "ThermalGruneisen": {r"\gamma_{th}"},
})
