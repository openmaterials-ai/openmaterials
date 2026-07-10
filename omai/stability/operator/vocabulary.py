r"""Formula symbol vocabulary of the stability domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.stability.operator` is imported. Union semantics per space.

Each stability space carries its own field symbol plus the bookkeeping
symbols of its producing formula (slab count and area for the surface
energy; ion count, ion chemical potential, and elementary charge for the
voltage). The opaque selector functions (E^{form}_{ref}, d^{hull}, E^{slab},
E^{bulk}, E^{full}, E^{empty}) are applied functions, invisible to the
free-symbol check, so they need no entries; their arguments E_{tot} and
\mathcal{S} are already registered by the ground-state domain on the
TotalEnergy and Structure spaces this domain consumes.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The per-atom formation energy; its symbol also appears as the input of
    # the hull-distance formula (FormationEnergy is that edge's input, so it
    # is derivable there already).
    "FormationEnergy": {r"\Delta H_f"},
    "EnergyAboveHull": {r"E_{hull}"},
    # Surface energy with the slab-difference bookkeeping: the bulk-unit
    # count and the in-plane area.
    "SurfaceEnergy": {r"\gamma_{surf}", r"N_{slab}", r"A_{surf}"},
    # Voltage with the Nernst bookkeeping: ion count, working-ion chemical
    # potential, elementary charge.
    "Voltage": {r"V_{avg}", r"n_{ion}", r"\mu_{ion}", "q_e"},
    # Adsorption energy: just its field symbol (the adslab / slab / adsorbate
    # selectors are applied functions, invisible to the free-symbol check).
    "AdsorptionEnergy": {r"E_{ads}"},
    # Reaction energy: its field symbol (the stoichiometric-combination
    # selector E^{rxn} is an applied function over the FormationEnergy family,
    # invisible to the free-symbol check).
    "ReactionEnergy": {r"\Delta E_{rxn}"},
})
