"""Abstract DAG for lattice thermal transport.

Twelve nodes (states) and eleven edges (operations) producing the lattice
thermal conductivity κ(T) from the Born-Oppenheimer potential and a chosen
temperature.

Every edge carries a symbolic formula as a sympy expression. Indexed
observables use sympy.IndexedBase; index ranges in BZ sums use sympy.Sum
with explicit dummies. Implicit equations (dispersion eigenvalue problem,
LBTE linear system) use sympy.Eq.

Each Observable is annotated with its index signature so the indices used
in the formulas have an explicit declaration.

This is the Phase 1 substrate target. Adapters (kaldo, phono3py, ShengBTE,
...) declare their unit/convention/discretization choices against these
abstract nodes and operations.
"""

from __future__ import annotations

import sympy as sp

from omai.abstract.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.abstract.operation import Operation, Parameter
from omai.abstract.physics_types import PhysicsType
from omai.abstract.state import Observable, State


# ---------------------------------------------------------------------------
# Symbols and indexed bases used by the formulas below
# ---------------------------------------------------------------------------

# Index dummies (integer-valued; used as bound variables in Sums)
_i, _j, _k = sp.symbols("i j k", integer=True)
_alpha, _beta = sp.symbols(r"\alpha \beta", integer=True)
_nu, _nu_p, _nu_pp = sp.symbols(r"\nu \nu' \nu''", integer=True)

# Wavevector / lattice-vector labels (treated as opaque labels at the
# abstract layer; concrete codes interpret them as 3-vectors over a mesh)
_q, _qp = sp.symbols(r"\mathbf{q} \mathbf{q'}")
_R, _Rp = sp.symbols(r"\mathbf{R} \mathbf{R'}")

# Physical scalars
_T = sp.Symbol("T", positive=True)
_hbar = sp.Symbol(r"\hbar", positive=True)
_kB = sp.Symbol("k_B", positive=True)
_V_cell = sp.Symbol("V_{cell}", positive=True)
_N_atoms = sp.Symbol("N", positive=True, integer=True)  # atoms in the primitive cell
_N_q = sp.Symbol("N_q", positive=True, integer=True)
_N_modes = 3 * _N_atoms

# Indexed observables (each matches the index signature on the corresponding
# Observable below)
_M = sp.IndexedBase("M")                          # M[i]: atomic mass
_Phi2 = sp.IndexedBase(r"\Phi^{(2)}")             # Phi2[i, j, R]
_Phi3 = sp.IndexedBase(r"\Phi^{(3)}")             # Phi3[i, j, k, R, R']
_D = sp.IndexedBase("D")                          # D[i, j, q]
_dDdq = sp.IndexedBase(r"\partial D/\partial q")  # dDdq[i, j, alpha, q]
_omega = sp.IndexedBase(r"\omega")                # omega[q, nu]
_e = sp.IndexedBase("e")                          # e[i, q, nu]
_v = sp.IndexedBase("v")                          # v[alpha, q, nu]
_c = sp.IndexedBase("c")                          # c[q, nu]
_Gamma = sp.IndexedBase(r"\Gamma")                # Gamma[q, nu]
_F = sp.IndexedBase("F")                          # F[alpha, q, nu]
_kappa = sp.IndexedBase(r"\kappa")                # kappa[alpha, beta]

# Auxiliary functions and symbols
_V_pot = sp.Function("V")
_u_set = sp.Symbol(r"\{u\}")
_u_i_0 = sp.Symbol("u_i(0)")
_u_j_R = sp.Symbol("u_j(R)")
_u_k_Rp = sp.Symbol("u_k(R')")
_n_BE = sp.Function("n_{BE}")
_delta = sp.Function(r"\delta")
_V3sq = sp.Function("|V_3|^2")


# ---------------------------------------------------------------------------
# Nodes (states)
# ---------------------------------------------------------------------------

POTENTIAL = State(
    physics_type=PhysicsType.POTENTIAL,
    name="Potential",
    observables=(Observable("potential", OPAQUE, indices=()),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = State(
    physics_type=PhysicsType.TEMPERATURE,
    name="Temperature",
    observables=(Observable("temperature", TEMPERATURE, indices=()),),
)

FORCE_CONSTANTS_2 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=2]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_SQUARED, indices=("i", "j", "R")),),
    type_parameters={"order": 2},
)

FORCE_CONSTANTS_3 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=3]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_CUBED, indices=("i", "j", "k", "R", "R'")),),
    type_parameters={"order": 3},
)

DYNAMICAL_MATRIX = State(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    observables=(Observable("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Entries are dimensionally "
        "frequency² (mass-weighted Hessian); codes typically store the "
        "matrix with eigenvalues that are ω², not ω."
    ),
)

FREQUENCY_STATE = State(
    physics_type=PhysicsType.FREQUENCY,
    name="Frequency",
    observables=(Observable("omega", FREQUENCY, indices=("q", "nu")),),
)

EIGENVECTORS = State(
    physics_type=PhysicsType.EIGENVECTORS,
    name="Eigenvectors",
    observables=(Observable("e", DIMENSIONLESS, indices=("i", "q", "nu")),),
    description=(
        "Per-mode eigenvectors of the dynamical matrix. Phase- and "
        "degenerate-subspace-rotation freedom: not directly comparable across "
        "adapters at the per-mode level."
    ),
)

GROUP_VELOCITY = State(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    observables=(Observable("v", LENGTH_TIMES_FREQUENCY, indices=("alpha", "q", "nu")),),
)

HEAT_CAPACITY = State(
    physics_type=PhysicsType.HEAT_CAPACITY,
    name="HeatCapacity",
    observables=(Observable("c", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
)

LINEWIDTH = State(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth",
    observables=(Observable("Gamma", FREQUENCY, indices=("q", "nu")),),
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
)

MEAN_FREE_DISPLACEMENT = State(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement",
    observables=(Observable("F", LENGTH, indices=("alpha", "q", "nu")),),
    description="Per-mode mean free displacement F_qν entering the BTE solution.",
)

THERMAL_CONDUCTIVITY_STATE = State(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity",
    observables=(Observable("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
)


NODES: tuple[State, ...] = (
    POTENTIAL,
    TEMPERATURE_STATE,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    DYNAMICAL_MATRIX,
    FREQUENCY_STATE,
    EIGENVECTORS,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT,
    THERMAL_CONDUCTIVITY_STATE,
)


# ---------------------------------------------------------------------------
# Formulas (one per derived edge; sources have None)
# ---------------------------------------------------------------------------

# Φ²_{ij}(R) = ∂²V/(∂u_i(0) ∂u_j(R))  evaluated at u=0
_FC2_FORMULA = sp.Eq(
    _Phi2[_i, _j, _R],
    sp.Derivative(_V_pot(_u_set), _u_i_0, _u_j_R),
)

# Φ³_{ijk}(R, R') = ∂³V/(∂u_i(0) ∂u_j(R) ∂u_k(R')) at u=0
_FC3_FORMULA = sp.Eq(
    _Phi3[_i, _j, _k, _R, _Rp],
    sp.Derivative(_V_pot(_u_set), _u_i_0, _u_j_R, _u_k_Rp),
)

# D_{ij}(q) = (1/√(M_i M_j)) Σ_R Φ²_{ij}(R) exp(i q·R)
_DM_FORMULA = sp.Eq(
    _D[_i, _j, _q],
    sp.Sum(_Phi2[_i, _j, _R] * sp.exp(sp.I * _q * _R), (_R, -sp.oo, sp.oo))
    / sp.sqrt(_M[_i] * _M[_j]),
)

# Eigenvalue equation, free i: Σ_j D_{ij}(q) e_{j,q,ν} = ω²_{q,ν} e_{i,q,ν}
_DISP_FORMULA = sp.Eq(
    sp.Sum(_D[_i, _j, _q] * _e[_j, _q, _nu], (_j, 1, _N_modes)),
    _omega[_q, _nu] ** 2 * _e[_i, _q, _nu],
)

# v^α_{q,ν} = (1/2ω_{q,ν}) Σ_{i,j} e*_{i,q,ν} (∂D_{ij}/∂q^α) e_{j,q,ν}
_GV_FORMULA = sp.Eq(
    _v[_alpha, _q, _nu],
    sp.Sum(
        sp.Sum(
            sp.conjugate(_e[_i, _q, _nu]) * _dDdq[_i, _j, _alpha, _q] * _e[_j, _q, _nu],
            (_j, 1, _N_modes),
        ),
        (_i, 1, _N_modes),
    )
    / (2 * _omega[_q, _nu]),
)

# c_{q,ν}(T) = (ℏω)² / (4 k_B T² sinh²(ℏω / 2 k_B T))
_HC_FORMULA = sp.Eq(
    _c[_q, _nu],
    (_hbar * _omega[_q, _nu]) ** 2
    / (4 * _kB * _T**2 * sp.sinh(_hbar * _omega[_q, _nu] / (2 * _kB * _T)) ** 2),
)

# Γ_{q,ν} = (π/Nℏ²) Σ_{q', ν', ν''} |V_3|² × [
#     (1 + n' + n'') δ(ω - ω' - ω'')
#   + 2 (n' - n'') δ(ω + ω' - ω'')
# ]   (q'' = q - q' implicit by crystal momentum conservation)
_om = _omega[_q, _nu]
_om_p = _omega[_qp, _nu_p]
_om_pp = _omega[_q - _qp, _nu_pp]
_n_p = _n_BE(_om_p / _T)
_n_pp = _n_BE(_om_pp / _T)
_V3 = _V3sq(_q, _nu, _qp, _nu_p, _q - _qp, _nu_pp)
_combination = (1 + _n_p + _n_pp) * _delta(_om - _om_p - _om_pp)
_absorption = 2 * (_n_p - _n_pp) * _delta(_om + _om_p - _om_pp)

_LW_FORMULA = sp.Eq(
    _Gamma[_q, _nu],
    sp.pi / (_N_atoms * _hbar**2)
    * sp.Sum(
        _V3 * (_combination + _absorption),
        (_qp, 1, _N_q),
        (_nu_p, 1, _N_modes),
        (_nu_pp, 1, _N_modes),
    ),
)

# F^α_{q,ν} = v^α_{q,ν} / (2 Γ_{q,ν})  [RTA closed form; bte_solver=rta]
# LBTE alternative is an implicit linear system (see description).
_BTE_FORMULA = sp.Eq(
    _F[_alpha, _q, _nu],
    _v[_alpha, _q, _nu] / (2 * _Gamma[_q, _nu]),
)

# κ^{αβ} = (1 / V_cell N_q) Σ_{q,ν} c_{q,ν} v^α_{q,ν} F^β_{q,ν}
_KAPPA_FORMULA = sp.Eq(
    _kappa[_alpha, _beta],
    sp.Sum(
        _c[_q, _nu] * _v[_alpha, _q, _nu] * _F[_beta, _q, _nu],
        (_q, 1, _N_q),
        (_nu, 1, _N_modes),
    )
    / (_V_cell * _N_q),
)


# ---------------------------------------------------------------------------
# Edges (operations)
# ---------------------------------------------------------------------------

provide_potential = Operation(
    name="provide_potential",
    inputs=(),
    outputs=(POTENTIAL,),
    formula=None,
    description="Source: an opaque label for the chosen potential (Tersoff, PBE, ...).",
)

provide_temperature = Operation(
    name="provide_temperature",
    inputs=(),
    outputs=(TEMPERATURE_STATE,),
    parameters=(Parameter("temperature", TEMPERATURE),),
    formula=None,
    description="Source: the temperature at which subsequent T-dependent observables are evaluated.",
)

compute_force_constants_2 = Operation(
    name="compute_force_constants[order=2]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_2,),
    formula=_FC2_FORMULA,
    description="Second derivative of the potential at equilibrium, after harmonic truncation.",
)

compute_force_constants_3 = Operation(
    name="compute_force_constants[order=3]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_3,),
    formula=_FC3_FORMULA,
    description="Third derivative of the potential at equilibrium, after cubic truncation.",
)

compute_dynamical_matrix = Operation(
    name="compute_dynamical_matrix",
    inputs=(FORCE_CONSTANTS_2,),
    outputs=(DYNAMICAL_MATRIX,),
    formula=_DM_FORMULA,
    description="Bloch sum over lattice vectors, mass-weighted.",
)

compute_dispersion = Operation(
    name="compute_dispersion",
    inputs=(DYNAMICAL_MATRIX,),
    outputs=(FREQUENCY_STATE, EIGENVECTORS),
    formula=_DISP_FORMULA,
    description=(
        "Eigendecomposition of D(q): produces ω_qν and orthonormal e_qν. "
        "Implicit equation; degenerate subspaces have rotation freedom on e."
    ),
)

compute_group_velocity = Operation(
    name="compute_group_velocity",
    inputs=(DYNAMICAL_MATRIX, FREQUENCY_STATE, EIGENVECTORS),
    outputs=(GROUP_VELOCITY,),
    formula=_GV_FORMULA,
    description="Hellmann-Feynman applied to the eigenvalue equation.",
)

compute_heat_capacity = Operation(
    name="compute_heat_capacity",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(HEAT_CAPACITY,),
    formula=_HC_FORMULA,
    description="Quantum (Bose-Einstein) per-mode heat capacity at temperature T.",
)

compute_linewidth = Operation(
    name="compute_linewidth",
    inputs=(FREQUENCY_STATE, EIGENVECTORS, FORCE_CONSTANTS_3, TEMPERATURE_STATE),
    outputs=(LINEWIDTH,),
    parameters=(Parameter("broadening_sigma", FREQUENCY),),
    algorithmic_conventions={
        "broadening_param": "stdev",
    },
    formula=_LW_FORMULA,
    description=(
        "Imaginary self-energy from three-phonon scattering (Fermi's golden "
        "rule). Energy delta is replaced by a Gaussian of canonical width "
        "σ = stdev. n_BE(ω/T) = (e^{ℏω/k_B T} - 1)^{-1}. q'' is fixed by "
        "crystal momentum conservation: q'' = q - q' (mod a reciprocal "
        "lattice vector)."
    ),
)

solve_bte = Operation(
    name="solve_bte",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT,),
    algorithmic_conventions={
        "bte_solver": "rta",
    },
    formula=_BTE_FORMULA,
    description=(
        "BTE solution. The formula shown is the RTA closed-form. The "
        "iterative / direct (LBTE) solvers solve the implicit linear "
        "system M·F = c·v over the full collision matrix M; the off-"
        "diagonal terms capture inter-mode redistribution. Choice of "
        "solver is the bte_solver algorithmic convention."
    ),
)

contract_kappa = Operation(
    name="contract_kappa",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT),
    outputs=(THERMAL_CONDUCTIVITY_STATE,),
    formula=_KAPPA_FORMULA,
    description="Per-mode contraction over the BZ to the thermal-conductivity tensor.",
)


EDGES: tuple[Operation, ...] = (
    provide_potential,
    provide_temperature,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_dynamical_matrix,
    compute_dispersion,
    compute_group_velocity,
    compute_heat_capacity,
    compute_linewidth,
    solve_bte,
    contract_kappa,
)
