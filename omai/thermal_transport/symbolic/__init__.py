"""Lattice thermal-transport: the abstract DAG.

  * `nodes`  — twelve States (observables / constants in the DAG)
  * `edges`  — eleven Operations (calculations in the DAG, with sympy formulas)

States are pure declarations: type, observables, conventions, indices. No
sympy, no calculation. Edges live in their own file because they carry the
substantive symbolic content (sympy expressions, indexed sums, equations);
mixing them with state declarations would conflate "what exists" with "how
it's computed."

This module re-exports both for convenience.
"""

from omai.thermal_transport.symbolic.edges import (
    EDGES,
    compute_dispersion,
    compute_dynamical_matrix,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_group_velocity,
    compute_heat_capacity,
    compute_linewidth,
    contract_kappa,
    provide_potential,
    provide_temperature,
    solve_bte,
)
from omai.thermal_transport.symbolic.nodes import (
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT,
    NODES,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_STATE,
)

__all__ = [
    "DYNAMICAL_MATRIX",
    "EDGES",
    "EIGENVECTORS",
    "FORCE_CONSTANTS_2",
    "FORCE_CONSTANTS_3",
    "FREQUENCY_STATE",
    "GROUP_VELOCITY",
    "HEAT_CAPACITY",
    "LINEWIDTH",
    "MEAN_FREE_DISPLACEMENT",
    "NODES",
    "POTENTIAL",
    "TEMPERATURE_STATE",
    "THERMAL_CONDUCTIVITY_STATE",
    "compute_dispersion",
    "compute_dynamical_matrix",
    "compute_force_constants_2",
    "compute_force_constants_3",
    "compute_group_velocity",
    "compute_heat_capacity",
    "compute_linewidth",
    "contract_kappa",
    "provide_potential",
    "provide_temperature",
    "solve_bte",
]
