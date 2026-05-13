"""Lattice thermal-transport: the operator DAG.

  * `nodes`  — twenty-two States (observables / hidden states in the DAG)
  * `edges`  — twenty-two Operations (calculations in the DAG, with sympy formulas)

States are pure declarations: type, fields, conventions, indices, gauge-
invariance kind (Observable vs HiddenState). No sympy, no calculation. Edges
live in their own file because they carry the substantive operator content
(sympy expressions, indexed sums, equations); mixing them with state
declarations would conflate "what exists" with "how it's computed."

MeanFreeDisplacement and ThermalConductivity are parameterized by
`bte_solver`: the RTA variants are HiddenStates (the approximation breaks
gauge invariance), the direct/iterative LBTE variants are Observables.

This module re-exports both for convenience.
"""

from omai.thermal_transport.operator.edges import (
    EDGES,
    apply_nac_correction,
    compute_dispersion,
    compute_dos,
    compute_dynamical_matrix,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_group_velocity,
    compute_gruneisen,
    compute_heat_capacity,
    compute_linewidth,
    compute_phase_space_3phonon,
    contract_kappa_direct,
    contract_kappa_rta,
    contract_molar_heat_capacity,
    contract_volumetric_heat_capacity,
    identity_dm,
    provide_born_charges,
    provide_dielectric_tensor,
    provide_potential,
    provide_temperature,
    solve_bte_direct,
    solve_bte_rta,
)
from omai.thermal_transport.operator.nodes import (
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    GRUNEISEN,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    MOLAR_HEAT_CAPACITY,
    NODES,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    VOLUMETRIC_HEAT_CAPACITY,
)

__all__ = [
    "BARE_DYNAMICAL_MATRIX",
    "BORN_CHARGES",
    "DIELECTRIC_TENSOR",
    "DYNAMICAL_MATRIX",
    "EDGES",
    "EIGENVECTORS",
    "FORCE_CONSTANTS_2",
    "FORCE_CONSTANTS_3",
    "FREQUENCY_STATE",
    "GROUP_VELOCITY",
    "GRUNEISEN",
    "HEAT_CAPACITY",
    "LINEWIDTH",
    "MEAN_FREE_DISPLACEMENT_DIRECT",
    "MEAN_FREE_DISPLACEMENT_RTA",
    "MOLAR_HEAT_CAPACITY",
    "NODES",
    "PHASE_SPACE_3PH",
    "PHONON_DOS",
    "POTENTIAL",
    "TEMPERATURE_STATE",
    "THERMAL_CONDUCTIVITY_DIRECT",
    "THERMAL_CONDUCTIVITY_RTA",
    "VOLUMETRIC_HEAT_CAPACITY",
    "apply_nac_correction",
    "compute_dispersion",
    "compute_dos",
    "compute_dynamical_matrix",
    "compute_force_constants_2",
    "compute_force_constants_3",
    "compute_group_velocity",
    "compute_gruneisen",
    "compute_heat_capacity",
    "compute_linewidth",
    "compute_phase_space_3phonon",
    "contract_kappa_direct",
    "contract_kappa_rta",
    "contract_molar_heat_capacity",
    "contract_volumetric_heat_capacity",
    "identity_dm",
    "provide_born_charges",
    "provide_dielectric_tensor",
    "provide_potential",
    "provide_temperature",
    "solve_bte_direct",
    "solve_bte_rta",
]
