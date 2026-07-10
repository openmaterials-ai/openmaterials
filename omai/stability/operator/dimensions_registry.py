r"""Symbol-dimension registry of the stability domain.

Registered into the core registry (`omai.operator.dimcheck`) when
`omai.stability.operator` is imported, next to the vocabulary module.

All four stability formulas contain opaque selector functions (applied
functions the dimension walker returns None for), so the dimensional gate
classifies them SKIPPED rather than proven, exactly like solve_ground_state:
these bindings document the intended dimensions and keep future closed-form
refinements provable, they do not force a proof today.

Collision notes: \gamma_{surf}, not bare \gamma (the generic dummy index);
E_{hull} and \Delta H_f are plain ENERGY (the per-atom character belongs to
the quantity, not the dimension); q_e composes charge as ENERGY / VOLTAGE
(T I), no new base constant needed.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY,
    ENERGY_PER_LENGTH_SQUARED,
    LENGTH_SQUARED,
    VOLTAGE,
)

register_symbol_dimensions({
    r"\Delta H_f": ENERGY,
    r"E_{hull}": ENERGY,
    r"\gamma_{surf}": ENERGY_PER_LENGTH_SQUARED,
    r"V_{avg}": VOLTAGE,
    # Surface-difference bookkeeping.
    r"N_{slab}": DIMENSIONLESS,
    r"A_{surf}": LENGTH_SQUARED,
    # Nernst bookkeeping: the elementary charge is energy per voltage (T I).
    r"n_{ion}": DIMENSIONLESS,
    r"\mu_{ion}": ENERGY,
    "q_e": ENERGY / VOLTAGE,
    # Adsorption energy: plain ENERGY (an energy difference over whole cells,
    # extensive, NOT the per-atom currency).
    r"E_{ads}": ENERGY,
})
