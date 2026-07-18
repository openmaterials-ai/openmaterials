r"""materialscodegraph as a representation over the ReactionEnergy node.

The materialscodegraph reaction-thermo tool computes the gas-phase reaction
enthalpy dH(298 K) of a balanced reaction from GFN2-xTB (xtb) over
conformer-searched global minima, per reaction event. Its dH298 output maps
onto the stability ReactionEnergy node:

  mcg reaction_thermo call                          symbol      -> node             units
  -----------------------------------------------  ----------  ----------------  ------
  reaction_thermo.dh298(...)                        dE_rxn      -> ReactionEnergy   eV

The epoxy-cure eval baselines are two epoxide ring-opening steps of glycidyl
phenyl ether: with aniline (-1.101722 eV) and with methylamine (-1.203292 eV)
per reaction event (mcg/evals/paper_targets.yaml cure_dh_gpe_aniline_gfn2 and
cure_dh_gpe_methylamine_gfn2), the pins the committed evidence instances and
their conformance targets carry. The ReactionEnergy normalization here is per
reaction event; the reaction, the phase (gas), the xtb version, and that
normalization ride in the record's conditions (the normalization is a
condition, not the dimension). materialscodegraph's citation and Apache-2.0
license are recorded once on its credits entry (the effective-medium rail
introduced it); this spec adds a third node to the same rail.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.stability.operator.nodes import REACTION_ENERGY

MCG_REACTION_ENERGY = SpaceRepresentationSpec(
    space=REACTION_ENERGY,
    representation_name="materialscodegraph",
    observable_units={"dE_rxn": "eV"},
    code_api={"dE_rxn": "reaction_thermo.dh298 (GFN2-xTB, per reaction event)"},
    notes=(
        "The gas-phase reaction enthalpy dH(298 K) from GFN2-xTB (xtb) over "
        "conformer-searched global minima, per reaction event "
        "(materialscodegraph reaction_thermo, return field dh298), in eV. The "
        "epoxy-cure eval baselines are two epoxide ring-opening steps of "
        "glycidyl phenyl ether: with aniline (-1.101722 eV) and with "
        "methylamine (-1.203292 eV), pinned by the mcg eval targets "
        "(mcg/evals/paper_targets.yaml cure_dh_gpe_aniline_gfn2, "
        "cure_dh_gpe_methylamine_gfn2). The reaction, the phase (gas), the xtb "
        "version, and the per-reaction-event normalization ride in the record "
        "conditions (the normalization is a condition, not the dimension)."
    ),
)
