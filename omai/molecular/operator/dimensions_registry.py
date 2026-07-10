r"""Symbol-dimension registry of the molecular domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.molecular.operator` is imported, next to the vocabulary module.

All three molecular formulas contain opaque solver functions (the molecular SCF
HOMO-LUMO gap, the NEB barrier, the fragment-difference BDE), so the dimensional
gate classifies them SKIPPED rather than proven, exactly like the
electronic-transport, thermochemistry, and quasi-harmonic edges: these bindings
document the intended dimensions and keep future closed-form refinements
provable, they do not force a proof today.

Collision notes: all three outputs are ENERGY (the plain energy exponent vector
1,2,-2,0,0,0,0 shared with TotalEnergy, FormationEnergy, ReactionEnergy). They
are kept apart at the NODE level by their quantity tags (homo_lumo_gap,
reaction_barrier, bond_dissociation_energy), not by the dimension. None of these
base symbol names is otherwise used by an edge formula.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import ENERGY

register_symbol_dimensions({
    r"E_{gap}^{mol}": ENERGY,
    r"E_{barrier}": ENERGY,
    r"E_{BDE}": ENERGY,
})
