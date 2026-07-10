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
    # Reaction energy: its field symbol \Delta E_{rxn}, plus the closed-form
    # stoichiometric-sum symbols the v2 supersede surfaces (2026-07-10, review B1):
    # \Delta H_f is the per-species formation energy IndexedBase (already the
    # FormationEnergy input symbol, so derivable from the input; declared here for
    # locality), c_{rxn} the signed stoichiometric coefficient, N_{rxn} the species
    # count.
    "ReactionEnergy": {r"\Delta E_{rxn}", r"\Delta H_f", r"c_{rxn}", r"N_{rxn}"},
    # Grain-boundary energy with the CSL slab-difference bookkeeping: the
    # atom count and the boundary area (the E^{GB} / E^{bulk}_{GB} selectors
    # are applied functions, invisible to the free-symbol check), mirroring
    # the surface-energy vocabulary.
    "GrainBoundaryEnergy": {r"\gamma_{GB}", r"N_{GB}", r"A_{GB}"},
})
