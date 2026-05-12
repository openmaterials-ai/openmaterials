"""Operations (edges) of the lattice thermal-transport DAG.

Each Operation declares its inputs, output(s), parameters, algorithmic
conventions, and a sympy formula stating what it computes. The sympy
symbols and IndexedBase used by the formulas live in this module too —
they are the substantive content of "what is computed", and the indices
they use match the index signatures declared on observables in `nodes`.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import FREQUENCY, TEMPERATURE
from omai.operator.operation import Operation, Parameter
from omai.thermal_transport.operator.nodes import (
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    GRUNEISEN,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    MOLAR_HEAT_CAPACITY,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    VOLUMETRIC_HEAT_CAPACITY,
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


# Auxiliary structural definition of |V₃|² (Maradudin-Fein form). The
# main formula above uses |V₃|² as an opaque kernel; this auxiliary
# equation makes the eigenvector / FC3 / mass dependence explicit, so
# the same kernel can be reused verbatim in the LBTE collision matrix
# Ξ (see _M_DEFINITION below). i, j, k run over atoms in the primitive
# cell; R, R' over lattice vectors.
_e = sp.IndexedBase("e")
_m = sp.IndexedBase("m")
_V3sq_definition_rhs = (
    sp.Abs(
        sp.Sum(
            _Phi3[_i, _j, _k, _R, _Rp]
            * _e[_i, _q, _nu] * _e[_j, _qp, _nu_p] * _e[_k, _q - _qp, _nu_pp]
            / sp.sqrt(_m[_i] * _m[_j] * _m[_k]),
            (_i, 1, _N_modes), (_j, 1, _N_modes), (_k, 1, _N_modes),
            (_R, 1, _N_q), (_Rp, 1, _N_q),
        )
    ) ** 2
    / (8 * _omega[_q, _nu] * _omega[_qp, _nu_p] * _omega[_q - _qp, _nu_pp])
)
_V3SQ_DEFINITION = sp.Eq(_V3, _V3sq_definition_rhs)

# RTA closed form: F^α_{q,ν} = v^α_{q,ν} / (2 Γ_{q,ν})
_BTE_RTA_FORMULA = sp.Eq(
    _F[_alpha, _q, _nu],
    _v[_alpha, _q, _nu] / (2 * _Gamma[_q, _nu]),
)

# LBTE / direct-inverse: Σ_{q'ν'} M_{qν,q'ν'} F^α_{q'ν'} = c_{qν} v^α_{qν}
#
# The collision matrix M is built from the same three-phonon |V₃|² used in
# compute_linewidth, but with the second mode index (q'ν') held free
# rather than summed. Explicit form:
#
#   M_{qν, q'ν'} = (2 Γ_{qν} / ℏ) δ_{qν,q'ν'}  −  Ξ_{qν, q'ν'}
#
# The diagonal term is the RTA scattering rate (2Γ/ℏ with our canonical
# Γ = Im Σ; the factor 2 comes from the linewidth-vs-scattering-rate
# relation 1/τ = 2Γ in angular-frequency units). The off-diagonal term Ξ
# is the "scattering-in" matrix: the same |V₃|² × occupation × energy-δ
# expression as in Γ_qν, but with q' held free instead of summed.
# Momentum conservation fixes q'' = q − q' (decay channel) or q'' = q + q'
# (absorption channel, modulo a reciprocal-lattice vector). Coefficients
# in front of (1 + n + n) and (n − n) match the standard linearized form
# (Omini-Sparavigna 1995, Broido et al. 2007); they're scaled relative to
# Γ_qν's prefactors by a factor of 2 because Ξ contributes through F^α_{q'ν'}
# in the matrix equation rather than appearing inside the rate at q,ν.
_om_p = _omega[_qp, _nu_p]
_om_pp_decay = _omega[_q - _qp, _nu_pp]
_om_pp_absorption = _omega[_q - _qp, _nu_pp]  # same q'' index under our sign convention
_n_p_ratio = _n_BE(_om_p / _T)
_n_pp_ratio = _n_BE(_om_pp_decay / _T)
_V3_decay = _V3sq(_q, _nu, _qp, _nu_p, _q - _qp, _nu_pp)
_V3_absorption = _V3sq(_q, _nu, _qp, _nu_p, _q - _qp, _nu_pp)
_om = _omega[_q, _nu]

_XI_qq = sp.pi / (_N_atoms * _hbar**2) * sp.Sum(
    _V3_decay * 2 * (1 + _n_p_ratio + _n_pp_ratio)
    * _delta(_om - _om_p - _om_pp_decay)
    + _V3_absorption * 4 * (_n_p_ratio - _n_pp_ratio)
    * _delta(_om + _om_p - _om_pp_absorption),
    (_nu_pp, 1, _N_modes),
)

_M_DEFINITION = sp.Eq(
    _M_collision[_q, _nu, _qp, _nu_p],
    (2 * _Gamma[_q, _nu] / _hbar) * sp.KroneckerDelta(_q, _qp) * sp.KroneckerDelta(_nu, _nu_p)
    - _XI_qq,
)

_BTE_DIRECT_FORMULA_SYSTEM = sp.Eq(
    sp.Sum(
        _M_collision[_q, _nu, _qp, _nu_p] * _F[_alpha, _qp, _nu_p],
        (_qp, 1, _N_q),
        (_nu_p, 1, _N_modes),
    ),
    _c[_q, _nu] * _v[_alpha, _q, _nu],
)

# The Operation's formula carries the linear-system equation. The full
# definition of M is available as `_M_DEFINITION` for any consumer that
# wants to render or symbolically substitute it. Together they fully pin
# down the linearized BTE — modulo the BZ-summation strategy for the
# inner Σ_{ν''} and the outer Σ_{q'}, which remains an honest
# discretization choice (declared on per-code OperationAdapterSpecs).
_BTE_DIRECT_FORMULA = _BTE_DIRECT_FORMULA_SYSTEM

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
    algorithmic_conventions={"symmetry_group": "C1"},
    formula=_FC2_FORMULA,
    description=(
        "Second derivative of the potential at equilibrium, after harmonic "
        "truncation. The space-group symmetry G of the crystal acts on the "
        "Cartesian indices and lattice vectors, Φ²_{ij}(R) = "
        "R(g)_{ii'} R(g)_{jj'} Φ²_{i'j'}(g·R); declaring symmetry_group=G "
        "asserts that the computed tensor is averaged over G, equivalent to "
        "evaluating only on the irreducible set of displacements. "
        "symmetry_group=C1 means no reduction (independent calculation on "
        "every Cartesian displacement)."
    ),
)

compute_force_constants_3 = Operation(
    name="compute_force_constants[order=3]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_3,),
    algorithmic_conventions={"symmetry_group": "C1"},
    formula=_FC3_FORMULA,
    description=(
        "Third derivative of the potential at equilibrium, after cubic "
        "truncation. Space-group symmetry G enters analogously to the "
        "harmonic case, now reducing the set of inequivalent atomic "
        "triplets (i,j,k; R,R'). symmetry_group=C1 means the full "
        "non-symmetry-reduced triplet set is sampled."
    ),
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
    algorithmic_conventions={"gv_method": "hellmann_feynman"},
    formula=_GV_FORMULA,
    description=(
        "Hellmann-Feynman applied to the eigenvalue equation. The alternative "
        "is finite-difference of ω(q); both converge but disagree at degenerate "
        "subspaces, where the analytic form requires diagonalising ∂D/∂q in the "
        "degenerate subspace and the finite-difference form silently picks an "
        "arbitrary basis."
    ),
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
        "symmetry_group": "C1",
    },
    formula=_LW_FORMULA,
    auxiliary_formulas=(_V3SQ_DEFINITION,),
    description=(
        "Imaginary self-energy from three-phonon scattering (Fermi's golden "
        "rule). The kernel |V₃|² is the Maradudin-Fein matrix element "
        "(auxiliary_formulas[0]): a triple sum of Φ³ contracted with "
        "eigenvectors and mass factors, scaled by 1/(8 ω ω' ω''). The same "
        "kernel appears in the LBTE collision matrix Ξ (see "
        "solve_bte_direct.auxiliary_formulas[0]). Energy delta is replaced "
        "by a Gaussian of canonical width σ = stdev. n_BE(ω/T) = (e^{ℏω/k_B "
        "T} - 1)^{-1}. q'' is fixed by crystal momentum conservation: "
        "q'' = q - q' (mod a reciprocal lattice vector). Under crystal "
        "symmetry G ⊂ O(3), the BZ sum Σ_{q'} can be restricted to the "
        "irreducible wedge BZ/G with multiplicity weights |G·q'|; "
        "symmetry_group=G asserts this reduction. symmetry_group=C1 means "
        "the full ordered grid is summed."
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
    algorithmic_conventions={
        "bte_solver": "direct_inverse",
        "symmetry_group": "C1",
    },
    formula=_BTE_DIRECT_FORMULA,
    auxiliary_formulas=(_M_DEFINITION,),
    description=(
        "Full linearized BTE: solve M·F = c·v for F, where M is the "
        "linearized three-phonon collision matrix. M has a diagonal (RTA) "
        "part 2Γ/ℏ and off-diagonal scattering-in terms Ξ built from the "
        "same |V₃|² as compute_linewidth (see auxiliary_formulas[0] for "
        "the explicit definition). Off-diagonals capture inter-mode "
        "redistribution that RTA drops; κ obtained from this F is "
        "gauge-invariant. Under crystal symmetry G the matrix M "
        "block-diagonalizes on the irreducible q-set BZ/G, so the linear "
        "system can be solved on the reduced space and unfolded by G; "
        "symmetry_group=G asserts this. symmetry_group=C1 means M is "
        "inverted on the full grid. At finite q-grid, the BZ-summation "
        "strategy (full vs irreducible) leaks into κ; convergence study "
        "in supercell+q-mesh is the resolution."
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


# C_V_vol(T) = (1/V_cell N_q) Σ_qν c_qν(T)
_C_V_vol = sp.Symbol(r"C_V^{vol}")
_C_V_mol = sp.Symbol(r"C_V^{mol}")
_N_A = sp.Symbol("N_A", positive=True)

_CV_VOL_FORMULA = sp.Eq(
    _C_V_vol,
    sp.Sum(_c[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / (_V_cell * _N_q),
)

# C_V_mol(T) = (N_A / N_q) Σ_qν c_qν(T)  (per mole of primitive cells)
_CV_MOL_FORMULA = sp.Eq(
    _C_V_mol,
    _N_A * sp.Sum(_c[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / _N_q,
)


contract_volumetric_heat_capacity = Operation(
    name="contract_volumetric_heat_capacity",
    inputs=(HEAT_CAPACITY,),
    outputs=(VOLUMETRIC_HEAT_CAPACITY,),
    formula=_CV_VOL_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode heat capacity, divided by cell "
        "volume. Gauge-invariant (no Linewidth or eigenvector input). "
        "ShengBTE emits this directly; kaldo/phono3py reach it by "
        "contracting their per-mode arrays."
    ),
)


contract_molar_heat_capacity = Operation(
    name="contract_molar_heat_capacity",
    inputs=(HEAT_CAPACITY,),
    outputs=(MOLAR_HEAT_CAPACITY,),
    formula=_CV_MOL_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode heat capacity, multiplied by "
        "Avogadro's number and divided by N_q (so the result is C_V per "
        "mole of primitive unit cells). Phonopy emits this in its "
        "harmonic thermal_properties output (J/K/mol)."
    ),
)


# ---------------------------------------------------------------------------
# Additional derived observables: density of states, Grüneisen, phase space.
# ---------------------------------------------------------------------------


_omega_bin = sp.Symbol(r"\omega")
_g_DOS = sp.Symbol("g")
_gammaG = sp.IndexedBase(r"\gamma_G")
_P3_state = sp.IndexedBase(r"P_3")

# g(ω) = (1/N_q) Σ_qν δ(ω − ω_qν)
_DOS_FORMULA = sp.Eq(
    _g_DOS,
    sp.Sum(
        _delta(_omega_bin - _omega[_q, _nu]),
        (_q, 1, _N_q),
        (_nu, 1, _N_modes),
    ) / _N_q,
)

# γ_qν = −(1 / (6 ω_qν² M)) Σ_{ij,Δ} Φ³_{ijk,R,R'} · r_k^Δ · e*_iqν e_jqν
# (Maradudin-Fein, schematic): not fully expanded — references the
# standard derivative of ω wrt volume.
_GRUNEISEN_FORMULA = sp.Eq(
    _gammaG[_q, _nu],
    -sp.Sum(_Phi3[_i, _j, _k, _R, _Rp], (_i, 1, _N_modes), (_j, 1, _N_modes)) /
    (6 * _omega[_q, _nu] ** 2),
)

# P3_qν = (1/N) Σ_{q'ν'ν''} [δ(ω − ω' − ω'') + 2 δ(ω + ω' − ω'')]
_P3_FORMULA = sp.Eq(
    _P3_state[_q, _nu],
    sp.Sum(
        _delta(_omega[_q, _nu] - _omega[_qp, _nu_p] - _omega[_q - _qp, _nu_pp])
        + 2 * _delta(_omega[_q, _nu] + _omega[_qp, _nu_p] - _omega[_q - _qp, _nu_pp]),
        (_qp, 1, _N_q),
        (_nu_p, 1, _N_modes),
        (_nu_pp, 1, _N_modes),
    ) / _N_q,
)


compute_dos = Operation(
    name="compute_dos",
    inputs=(FREQUENCY_STATE,),
    outputs=(PHONON_DOS,),
    algorithmic_conventions={"dos_broadening": "gaussian"},
    formula=_DOS_FORMULA,
    description=(
        "Histogram / smeared sum of phonon frequencies into a 1-D density "
        "of states. The δ is usually replaced by a Gaussian or tetrahedron "
        "weight at finite q-mesh; dos_broadening records the choice. "
        "Independent of eigenvectors → gauge-invariant."
    ),
)


compute_gruneisen = Operation(
    name="compute_gruneisen",
    inputs=(FORCE_CONSTANTS_2, FORCE_CONSTANTS_3, FREQUENCY_STATE, EIGENVECTORS),
    outputs=(GRUNEISEN,),
    algorithmic_conventions={"gruneisen_method": "maradudin_fein"},
    formula=_GRUNEISEN_FORMULA,
    description=(
        "Mode Grüneisen parameter from FC2, FC3 and the harmonic eigensystem "
        "(Maradudin-Fein closed form). The alternative is finite-difference: "
        "rerun the harmonic problem at slightly deformed cells and finite-"
        "difference ω(V). Both converge but the two estimators have different "
        "noise / convergence behaviour at small q-mesh, so gruneisen_method "
        "records which one a code emits. Per-mode γ is gauge-invariant: it "
        "depends on ω_qν, not on the eigenvector phase."
    ),
)


compute_phase_space_3phonon = Operation(
    name="compute_phase_space_3phonon",
    inputs=(FREQUENCY_STATE,),
    outputs=(PHASE_SPACE_3PH,),
    algorithmic_conventions={"delta_broadening": "gaussian"},
    formula=_P3_FORMULA,
    description=(
        "Three-phonon kinematic phase space: counts the (q',ν',ν'') channels "
        "satisfying energy + crystal-momentum conservation for the given "
        "(q, ν). |V₃|² is not included — this is purely a measure of "
        "scattering availability. delta_broadening records how the energy δ "
        "is realised at finite q-mesh (Gaussian, Lorentzian, tetrahedron)."
    ),
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
    contract_volumetric_heat_capacity,
    contract_molar_heat_capacity,
    compute_dos,
    compute_gruneisen,
    compute_phase_space_3phonon,
)
