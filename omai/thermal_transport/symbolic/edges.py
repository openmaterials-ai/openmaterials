"""Operations (edges) of the lattice thermal-transport DAG.

Each Operation declares its inputs, output(s), parameters, algorithmic
conventions, and a sympy formula stating what it computes. The sympy
symbols and IndexedBase used by the formulas live in this module too —
they are the substantive content of "what is computed", and the indices
they use match the index signatures declared on observables in `nodes`.
"""

from __future__ import annotations

import sympy as sp

from omai.symbolic.dimensions import FREQUENCY, TEMPERATURE
from omai.symbolic.operation import Operation, Parameter
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
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
)


# ---------------------------------------------------------------------------
# Symbols and indexed bases used by the formulas below
# ---------------------------------------------------------------------------

_i, _j, _k = sp.symbols("i j k", integer=True)
_alpha, _beta = sp.symbols(r"\alpha \beta", integer=True)
_nu, _nu_p, _nu_pp = sp.symbols(r"\nu \nu' \nu''", integer=True)

_q, _qp = sp.symbols(r"\mathbf{q} \mathbf{q'}")
_R, _Rp = sp.symbols(r"\mathbf{R} \mathbf{R'}")

_T = sp.Symbol("T", positive=True)
_hbar = sp.Symbol(r"\hbar", positive=True)
_kB = sp.Symbol("k_B", positive=True)
_V_cell = sp.Symbol("V_{cell}", positive=True)
_N_atoms = sp.Symbol("N", positive=True, integer=True)
_N_q = sp.Symbol("N_q", positive=True, integer=True)
_N_modes = 3 * _N_atoms

_M = sp.IndexedBase("M")
_Phi2 = sp.IndexedBase(r"\Phi^{(2)}")
_Phi3 = sp.IndexedBase(r"\Phi^{(3)}")
_D = sp.IndexedBase("D")
_dDdq = sp.IndexedBase(r"\partial D/\partial q")
_omega = sp.IndexedBase(r"\omega")
_e = sp.IndexedBase("e")
_v = sp.IndexedBase("v")
_c = sp.IndexedBase("c")
_Gamma = sp.IndexedBase(r"\Gamma")
_F = sp.IndexedBase("F")
_kappa = sp.IndexedBase(r"\kappa")
_M_collision = sp.IndexedBase(r"\mathcal{M}")

_V_pot = sp.Function("V")
_u_set = sp.Symbol(r"\{u\}")
_u_i_0 = sp.Symbol("u_i(0)")
_u_j_R = sp.Symbol("u_j(R)")
_u_k_Rp = sp.Symbol("u_k(R')")
_n_BE = sp.Function("n_{BE}")
_delta = sp.Function(r"\delta")
_V3sq = sp.Function("|V_3|^2")
_V_provided = sp.Symbol(r"V_{\mathrm{provided}}")
_T_provided = sp.Symbol(r"T_{\mathrm{provided}}", positive=True)


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------

# Φ²_{ij}(R) = ∂²V/(∂u_i(0) ∂u_j(R)) at u=0
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

# Σ_j D_{ij}(q) e_{j,q,ν} = ω²_{q,ν} e_{i,q,ν}  (free i)
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

# RTA closed form: F^α_{q,ν} = v^α_{q,ν} / (2 Γ_{q,ν})
_BTE_RTA_FORMULA = sp.Eq(
    _F[_alpha, _q, _nu],
    _v[_alpha, _q, _nu] / (2 * _Gamma[_q, _nu]),
)

# LBTE / direct-inverse implicit equation: Σ_{q'ν'} M_{qν, q'ν'} F^α_{q'ν'} = c_{qν} v^α_{qν}
# M is the full collision matrix; the off-diagonals capture inter-mode redistribution
# that RTA drops. Solving M·F = c·v preserves κ's gauge invariance.
_BTE_DIRECT_FORMULA = sp.Eq(
    sp.Sum(
        _M_collision[_q, _nu, _qp, _nu_p] * _F[_alpha, _qp, _nu_p],
        (_qp, 1, _N_q),
        (_nu_p, 1, _N_modes),
    ),
    _c[_q, _nu] * _v[_alpha, _q, _nu],
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
# Operations
# ---------------------------------------------------------------------------

provide_potential = Operation(
    name="provide_potential",
    inputs=(),
    outputs=(POTENTIAL,),
    formula=sp.Eq(_V_pot(_u_set), _V_provided),
    description="Source: an opaque label for the chosen potential (Tersoff, PBE, ...).",
)

provide_temperature = Operation(
    name="provide_temperature",
    inputs=(),
    outputs=(TEMPERATURE_STATE,),
    parameters=(Parameter("temperature", TEMPERATURE),),
    formula=sp.Eq(_T, _T_provided),
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
    algorithmic_conventions={"broadening_param": "stdev"},
    formula=_LW_FORMULA,
    description=(
        "Imaginary self-energy from three-phonon scattering (Fermi's golden "
        "rule). Energy delta is replaced by a Gaussian of canonical width "
        "σ = stdev. n_BE(ω/T) = (e^{ℏω/k_B T} - 1)^{-1}. q'' is fixed by "
        "crystal momentum conservation: q'' = q - q' (mod a reciprocal "
        "lattice vector)."
    ),
)

solve_bte_rta = Operation(
    name="solve_bte[bte_solver=rta]",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT_RTA,),
    algorithmic_conventions={"bte_solver": "rta"},
    formula=_BTE_RTA_FORMULA,
    description=(
        "Relaxation-time approximation: F = v / (2Γ). Closed-form per "
        "mode. Drops the off-diagonal terms of the collision matrix, so "
        "κ_RTA inherits Linewidth's gauge-dependence."
    ),
)

solve_bte_direct = Operation(
    name="solve_bte[bte_solver=direct_inverse]",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT_DIRECT,),
    algorithmic_conventions={"bte_solver": "direct_inverse"},
    formula=_BTE_DIRECT_FORMULA,
    description=(
        "Full linearized BTE: solve M·F = c·v for F, where M is the full "
        "collision matrix. The off-diagonals capture inter-mode "
        "redistribution; κ obtained from this F is gauge-invariant."
    ),
)

contract_kappa_rta = Operation(
    name="contract_kappa[bte_solver=rta]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_RTA),
    outputs=(THERMAL_CONDUCTIVITY_RTA,),
    formula=_KAPPA_FORMULA,
    description=(
        "Per-mode contraction with F from RTA. The 1/Γ non-linearity "
        "propagates Linewidth's gauge-dependence into κ_RTA."
    ),
)

contract_kappa_direct = Operation(
    name="contract_kappa[bte_solver=direct_inverse]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT),
    outputs=(THERMAL_CONDUCTIVITY_DIRECT,),
    formula=_KAPPA_FORMULA,
    description="Per-mode contraction with the LBTE F; result is gauge-invariant.",
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
    solve_bte_rta,
    solve_bte_direct,
    contract_kappa_rta,
    contract_kappa_direct,
)
