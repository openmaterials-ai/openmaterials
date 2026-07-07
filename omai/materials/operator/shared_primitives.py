"""Canonical leaf quantities reused across domains.

Materials edges import their shared inputs from here so that new subgraphs
connect to the SAME nodes the thermal-transport graph already uses, instead
of duplicating them. STRUCTURE is new (most mat-* skills consume a crystal
structure); the rest are re-exports of existing thermal-transport leaves.
"""
from __future__ import annotations

from omai.operator.dimensions import OPAQUE
from omai.operator.space import Field, ObservableSpace
from omai.thermal_transport.operator.nodes import (
    MEAN_SQUARED_DISPLACEMENT,
    POTENTIAL,
    TEMPERATURE_STATE as TEMPERATURE,
    TRAJECTORY,
)

STRUCTURE = ObservableSpace(
    name="Structure",
    fields=(Field("structure", OPAQUE, indices=()),),
    description=(
        "Atomic structure (cell + species + positions); in Phase 1 an opaque "
        "label, the shared source node most materials skills consume."
    ),
    tier="Sources",
)

SHARED_PRIMITIVES = (STRUCTURE, TEMPERATURE, TRAJECTORY, MEAN_SQUARED_DISPLACEMENT, POTENTIAL)
