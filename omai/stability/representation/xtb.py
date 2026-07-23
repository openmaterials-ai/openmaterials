r"""xtb as a representation over the ReactionEnergy node.

xtb (grimme-lab/xtb) computes total free energies and enthalpies per
species from GFN2-xTB Hessian runs; a balanced reaction's dH(298 K) is the
difference of product and reactant enthalpies over conformer-searched
global minima, per reaction event. The committed epoxy-cure evidence
instances (glycidyl phenyl ether with aniline, -1.101722 eV, and with
methylamine, -1.203292 eV) name `xtb 6.7.1` in their in-hash conditions;
this rail records the interface that reproduces them.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.stability.operator.nodes import REACTION_ENERGY

XTB_REACTION_ENERGY = SpaceRepresentationSpec(
    space=REACTION_ENERGY,
    representation_name="xtb",
    observable_units={"dE_rxn": "eV"},
    code_api={"dE_rxn": "xtb <geom> --ohess --temp 298.15 per species; dH298 = sum(products) - sum(reactants)"},
    notes=(
        "Gas-phase reaction enthalpy dH(298 K) from GFN2-xTB total "
        "enthalpies over conformer-searched global minima, per reaction "
        "event. The reaction, the phase, the normalization, the model "
        "(GFN2-xTB), and the xtb version ride in the record's conditions "
        "(the normalization is a condition, not the dimension)."
    ),
)
