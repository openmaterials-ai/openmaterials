"""Per-code adapter specs for the molecular domain.

Two rails: orca (molecular quantum chemistry, the map's first molecular code) and
openmm (classical force-field MD, a new engine class). Both attach specs to
pre-existing nodes (TotalEnergy, Forces, Temperature, Pressure, Trajectory) as
well as the new molecular nodes (HOMOLUMOGap, ReactionBarrier). build_codes
discovers every SpaceRepresentationSpec module-level object in this package.
"""

from omai.molecular.representation.orca import (
    ORCA_TOTAL_ENERGY,
    ORCA_FORCES,
    ORCA_HOMO_LUMO_GAP,
    ORCA_REACTION_BARRIER,
    ORCA_COMPUTE_HOMO_LUMO_GAP,
    ORCA_COMPUTE_REACTION_BARRIER,
    ORCA_COMPUTE_BOND_DISSOCIATION,
)
from omai.molecular.representation.openmm import (
    OPENMM_TRAJECTORY,
    OPENMM_TEMPERATURE,
    OPENMM_PRESSURE,
    OPENMM_TOTAL_ENERGY,
)

__all__ = [
    "ORCA_TOTAL_ENERGY",
    "ORCA_FORCES",
    "ORCA_HOMO_LUMO_GAP",
    "ORCA_REACTION_BARRIER",
    "ORCA_COMPUTE_HOMO_LUMO_GAP",
    "ORCA_COMPUTE_REACTION_BARRIER",
    "ORCA_COMPUTE_BOND_DISSOCIATION",
    "OPENMM_TRAJECTORY",
    "OPENMM_TEMPERATURE",
    "OPENMM_PRESSURE",
    "OPENMM_TOTAL_ENERGY",
]
