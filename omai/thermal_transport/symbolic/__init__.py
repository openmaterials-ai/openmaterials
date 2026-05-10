"""Lattice thermal-transport: the abstract DAG.

  * `nodes`  — fourteen States (observables / hidden states in the DAG)
  * `edges`  — thirteen Operations (calculations in the DAG, with sympy formulas)

States are pure declarations: type, fields, conventions, indices, gauge-
invariance kind (Observable vs HiddenState). No sympy, no calculation. Edges
live in their own file because they carry the substantive symbolic content
(sympy expressions, indexed sums, equations); mixing them with state
declarations would conflate "what exists" with "how it's computed."

MeanFreeDisplacement and ThermalConductivity are parameterized by
`bte_solver`: the RTA variants are HiddenStates (the approximation breaks
gauge invariance), the direct/iterative LBTE variants are Observables.

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
    contract_kappa_direct,
    contract_kappa_rta,
    provide_potential,
    provide_temperature,
    solve_bte_direct,
    solve_bte_rta,
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
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    NODES,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
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
    "MEAN_FREE_DISPLACEMENT_DIRECT",
    "MEAN_FREE_DISPLACEMENT_RTA",
    "NODES",
    "POTENTIAL",
    "TEMPERATURE_STATE",
    "THERMAL_CONDUCTIVITY_DIRECT",
    "THERMAL_CONDUCTIVITY_RTA",
    "compute_dispersion",
    "compute_dynamical_matrix",
    "compute_force_constants_2",
    "compute_force_constants_3",
    "compute_group_velocity",
    "compute_heat_capacity",
    "compute_linewidth",
    "contract_kappa_direct",
    "contract_kappa_rta",
    "provide_potential",
    "provide_temperature",
    "solve_bte_direct",
    "solve_bte_rta",
]
