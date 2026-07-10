"""Per-code adapter specs for the quasi-harmonic domain.

The phonopy rail: the QHA thermodynamics phonopy.PhonopyQHA emits, driven by
matcalc QHACalc and the mat-qha-thermal-expansion skill. matcalc QHACalc schemes
ride the phonopy operator specs (the driver layer carries no rail of its own).
"""

from omai.quasiharmonic.representation.phonopy import (
    PHONOPY_QHA_GIBBS_ENERGY,
    PHONOPY_THERMAL_EXPANSION,
    PHONOPY_HEAT_CAPACITY_CONSTANT_P,
    PHONOPY_THERMAL_GRUNEISEN,
    PHONOPY_BULK_MODULUS_QHA,
    PHONOPY_COMPUTE_QHA_GIBBS,
    PHONOPY_COMPUTE_BULK_MODULUS_QHA,
    PHONOPY_COMPUTE_THERMAL_EXPANSION,
    PHONOPY_COMPUTE_HEAT_CAPACITY_P,
    PHONOPY_CONTRACT_THERMAL_GRUNEISEN,
)

__all__ = [
    "PHONOPY_QHA_GIBBS_ENERGY",
    "PHONOPY_THERMAL_EXPANSION",
    "PHONOPY_HEAT_CAPACITY_CONSTANT_P",
    "PHONOPY_THERMAL_GRUNEISEN",
    "PHONOPY_BULK_MODULUS_QHA",
    "PHONOPY_COMPUTE_QHA_GIBBS",
    "PHONOPY_COMPUTE_BULK_MODULUS_QHA",
    "PHONOPY_COMPUTE_THERMAL_EXPANSION",
    "PHONOPY_COMPUTE_HEAT_CAPACITY_P",
    "PHONOPY_CONTRACT_THERMAL_GRUNEISEN",
]
