r"""Formula symbol vocabulary of the molecular domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.molecular.operator` is imported. Union semantics per space.

Each molecular space carries its own new field symbol. The input side is already
covered by existing registrations: Structure's \mathcal{S}, Potential's V
(thermal-transport), and TotalEnergy's E_{tot} (dft ground state). The opaque
solver functions (\Delta_{HL}, \Delta_{NEB}, \Delta_{BDE}) are applied functions,
invisible to the free-symbol check, so they need no entries. The three output
symbols (E_{gap}^{mol}, E_{barrier}, E_{BDE}) are deliberately distinct from the
periodic BandGap's E_{gap} and from any TotalEnergy / ReactionEnergy symbol.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    "HOMOLUMOGap": {r"E_{gap}^{mol}"},
    "ReactionBarrier[construction=neb_mep]": {r"E_{barrier}"},
    "BondDissociationEnergy": {r"E_{BDE}"},
})
