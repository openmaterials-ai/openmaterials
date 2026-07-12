"""Operators (edges) of the lattice thermal-transport DAG.

Each Operator declares its inputs, output(s), parameters, schemes, and a
sympy formula stating what it computes. The sympy symbols and IndexedBase
used by the formulas live in this module too — they are the substantive
content of "what is computed", and the indices they use match the index
signatures declared on the spaces in `nodes`.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import FREQUENCY, LENGTH, TEMPERATURE, VOLUME
from omai.operator.operator import Operator, Parameter
from omai.thermal_transport.operator.nodes import (
    ANHARMONIC_LINEWIDTH,
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    BOUNDARY_LINEWIDTH,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    ENTROPY,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    HELMHOLTZ_FREE_ENERGY,
    GRUNEISEN,
    INTERNAL_ENERGY,
    ISOTOPE_ABUNDANCES,
    ISOTOPIC_LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    MOLAR_ENTROPY,
    MOLAR_HEAT_CAPACITY,
    MOLAR_HELMHOLTZ_FREE_ENERGY,
    MOLAR_INTERNAL_ENERGY,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    CUMULATIVE_KAPPA_MFP,
    CUMULATIVE_KAPPA_OMEGA,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_QHGK,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_WIGNER,
    THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    TOTAL_LINEWIDTH,
    VOLUMETRIC_HEAT_CAPACITY,
    # MD primitives (phase 2 P2)
    TRAJECTORY,
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    VELOCITY_AUTOCORRELATION,
    MEAN_SQUARED_DISPLACEMENT,
    # MD-based κ (phase 2 P3)
    THERMAL_CONDUCTIVITY_GREEN_KUBO,
    THERMAL_CONDUCTIVITY_NEMD,
    THERMAL_CONDUCTIVITY_HNEMD,
    # Amorphous / localization diagnostics (kaldo delta scan, records 208-211)
    PARTICIPATION_RATIO,
    MODAL_DIFFUSIVITY,
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

# D_bare_{ij}(q) = (1/√(M_i M_j)) Σ_R Φ²_{ij}(R) exp(i q·R)
_D_bare = sp.IndexedBase(r"D^{bare}")
_DM_BARE_FORMULA = sp.Eq(
    _D_bare[_i, _j, _q],
    sp.Sum(_Phi2[_i, _j, _R] * sp.exp(sp.I * _q * _R), (_R, -sp.oo, sp.oo))
    / sp.sqrt(_M[_i] * _M[_j]),
)

# Non-polar branch: D(q) = D_bare(q) (identity pass-through).
_DM_IDENTITY_FORMULA = sp.Eq(_D[_i, _j, _q], _D_bare[_i, _j, _q])

# Polar branch: D(q) = D_bare(q) + D_NAC(q, Z*, ε∞)
# where the NAC term diverges non-analytically as q→0:
#   D^NAC_{iα,jβ}(q) = (4π/V_cell √(M_i M_j))
#                      × (Σ_γ q_γ Z*_{i,γα}) (Σ_δ q_δ Z*_{j,δβ})
#                      / (Σ_γδ q_γ ε∞_{γδ} q_δ)
_Z_star = sp.IndexedBase(r"Z^*")
_eps_inf = sp.IndexedBase(r"\varepsilon_\infty")
_gamma_idx, _delta_idx = sp.symbols(r"\gamma \delta", integer=True)

# Use a free vector q with three Cartesian components for the limit; the
# symbol here is schematic — the substantive content is that the correction
# is bilinear in (q · Z*) and inversely bilinear in (q · ε∞ · q).
_q_alpha = sp.Symbol(r"q^\alpha")
_q_beta = sp.Symbol(r"q^\beta")

_DM_NAC_TERM = (
    (4 * sp.pi / (_V_cell * sp.sqrt(_M[_i] * _M[_j])))
    * sp.Sum(_q_alpha * _Z_star[_i, _gamma_idx, _alpha],
             (_gamma_idx, 1, 3))
    * sp.Sum(_q_beta * _Z_star[_j, _delta_idx, _beta],
             (_delta_idx, 1, 3))
    / sp.Sum(_q_alpha * _eps_inf[_gamma_idx, _delta_idx] * _q_beta,
             (_gamma_idx, 1, 3), (_delta_idx, 1, 3))
)
_DM_NAC_FORMULA = sp.Eq(
    _D[_i, _j, _q],
    _D_bare[_i, _j, _q] + _DM_NAC_TERM,
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


# Per-mode harmonic thermodynamics. _x = ℏω / (k_B T) is the standard
# dimensionless variable, and n_BE takes exactly this dimensionless
# argument (matching the sibling free-energy / heat-capacity forms, which
# already spell out ℏω/(k_B T) inside their log / sinh). The canonical
# forms below are then:
#   f_qν(T) = (ℏω/2) + k_B T ln(1 - e^{-x})
#   s_qν(T) = (ℏω/T) · n_BE(x) − k_B ln(1 - e^{-x})
#   e_qν(T) = ℏω · (1/2 + n_BE(x))
_f_mode = sp.IndexedBase("f")
_s_mode = sp.IndexedBase("s")
_e_mode = sp.IndexedBase("e")

_x_hw = _hbar * _omega[_q, _nu] / (_kB * _T)

_FREE_ENERGY_FORMULA = sp.Eq(
    _f_mode[_q, _nu],
    (_hbar * _omega[_q, _nu]) / 2
    + _kB * _T * sp.log(1 - sp.exp(-_x_hw)),
)

_ENTROPY_FORMULA = sp.Eq(
    _s_mode[_q, _nu],
    _hbar * _omega[_q, _nu] / _T * _n_BE(_x_hw)
    - _kB * sp.log(1 - sp.exp(-_x_hw)),
)

_INTERNAL_ENERGY_FORMULA = sp.Eq(
    _e_mode[_q, _nu],
    _hbar * _omega[_q, _nu] * (sp.Rational(1, 2) + _n_BE(_x_hw)),
)


# Molar contractions: (N_A / N_q) Σ_qν · per-mode form
_N_A = sp.Symbol("N_A", positive=True)
_F_mol_sym = sp.Symbol(r"F_{mol}")
_S_mol_sym = sp.Symbol(r"S_{mol}")
_E_mol_sym = sp.Symbol(r"E_{mol}")

_MOLAR_FREE_ENERGY_FORMULA = sp.Eq(
    _F_mol_sym,
    _N_A * sp.Sum(_f_mode[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / _N_q,
)

_MOLAR_ENTROPY_FORMULA = sp.Eq(
    _S_mol_sym,
    _N_A * sp.Sum(_s_mode[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / _N_q,
)

_MOLAR_INTERNAL_ENERGY_FORMULA = sp.Eq(
    _E_mol_sym,
    _N_A * sp.Sum(_e_mode[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / _N_q,
)

# Γ_{q,ν} = (π/Nℏ²) Σ_{q', ν', ν''} |V_3|² × [
#     (1 + n' + n'') δ(ω - ω' - ω'')
#   + 2 (n' - n'') δ(ω + ω' - ω'')
# ]   (q'' = q - q' implicit by crystal momentum conservation)
_om = _omega[_q, _nu]
_om_p = _omega[_qp, _nu_p]
_om_pp = _omega[_q - _qp, _nu_pp]
# n_BE takes the dimensionless ℏω/(k_B T), same convention as the harmonic
# thermodynamics forms above.
_n_p = _n_BE(_hbar * _om_p / (_kB * _T))
_n_pp = _n_BE(_hbar * _om_pp / (_kB * _T))
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
# n_BE takes the dimensionless ℏω/(k_B T), same convention as compute_linewidth.
_n_p_ratio = _n_BE(_hbar * _om_p / (_kB * _T))
_n_pp_ratio = _n_BE(_hbar * _om_pp_decay / (_kB * _T))
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

# The Operator's formula carries the linear-system equation. The full
# definition of M is available as `_M_DEFINITION` for any consumer that
# wants to render or symbolically substitute it. Together they fully pin
# down the linearized BTE — modulo the BZ-summation strategy for the
# inner Σ_{ν''} and the outer Σ_{q'}, which remains an honest
# discretization choice (declared on per-code OperatorRepresentationSpecs).
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
# Operators
# ---------------------------------------------------------------------------

provide_potential = Operator(
    name="provide_potential",
    inputs=(),
    outputs=(POTENTIAL,),
    formula=sp.Eq(_V_pot(_u_set), _V_provided),
    description="Source: an opaque label for the chosen potential (Tersoff, PBE, ...).",
)

provide_temperature = Operator(
    name="provide_temperature",
    inputs=(),
    outputs=(TEMPERATURE_STATE,),
    parameters=(Parameter("temperature", TEMPERATURE),),
    formula=sp.Eq(_T, _T_provided),
    description="Source: the temperature at which subsequent T-dependent observables are evaluated.",
)


_Z_star_provided = sp.Symbol(r"Z^*_{provided}")
_eps_provided = sp.Symbol(r"\varepsilon_{\infty,provided}")

provide_born_charges = Operator(
    name="provide_born_charges",
    inputs=(),
    outputs=(BORN_CHARGES,),
    formula=sp.Eq(_Z_star[_i, _gamma_idx, _alpha], _Z_star_provided),
    description=(
        "Source: per-atom Born effective-charge tensor Z*_{i,αβ}. Typically "
        "read from a BORN file produced by a DFT linear-response calculation. "
        "Required only for polar materials; non-polar runs do not consume "
        "BornCharges anywhere downstream."
    ),
)


provide_dielectric_tensor = Operator(
    name="provide_dielectric_tensor",
    inputs=(),
    outputs=(DIELECTRIC_TENSOR,),
    formula=sp.Eq(_eps_inf[_gamma_idx, _delta_idx], _eps_provided),
    description=(
        "Source: macroscopic (electronic) dielectric tensor ε∞. Usually read "
        "from the same BORN file alongside the Born charges. Used only by "
        "the polar branch of the DM construction."
    ),
)

compute_force_constants_2 = Operator(
    name="compute_force_constants[order=2]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_2,),
    schemes={"symmetry_group": "C1"},
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

compute_force_constants_3 = Operator(
    name="compute_force_constants[order=3]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_3,),
    schemes={"symmetry_group": "C1"},
    formula=_FC3_FORMULA,
    description=(
        "Third derivative of the potential at equilibrium, after cubic "
        "truncation. Space-group symmetry G enters analogously to the "
        "harmonic case, now reducing the set of inequivalent atomic "
        "triplets (i,j,k; R,R'). symmetry_group=C1 means the full "
        "non-symmetry-reduced triplet set is sampled."
    ),
)

compute_dynamical_matrix = Operator(
    name="compute_dynamical_matrix",
    inputs=(FORCE_CONSTANTS_2,),
    outputs=(BARE_DYNAMICAL_MATRIX,),
    formula=_DM_BARE_FORMULA,
    description=(
        "Bloch sum over lattice vectors, mass-weighted. Produces the "
        "analytic (bare) dynamical matrix; the downstream DynamicalMatrix "
        "is reached either via identity_dm (non-polar) or via "
        "apply_nac_correction (polar). The split is needed because the "
        "non-analytic correction adds a q-direction-dependent term at "
        "q→0 that cannot be expressed as a real-space Bloch sum."
    ),
)


identity_dm = Operator(
    name="identity_dm",
    inputs=(BARE_DYNAMICAL_MATRIX,),
    outputs=(DYNAMICAL_MATRIX,),
    formula=_DM_IDENTITY_FORMULA,
    # Closed-form pass-through; the heuristic flunks it on shared index
    # symbols (i, j, q), but the formula is literally LHS = RHS_other_base
    # and lambdifies trivially.
    is_executable_in_sympy_override=True,
    description=(
        "Non-polar branch: the downstream DynamicalMatrix is just the bare "
        "Bloch sum, unchanged. This edge exists to keep the DAG acyclic "
        "while letting compute_dispersion (and everything below) consume "
        "a single DynamicalMatrix node regardless of whether the run is "
        "polar or non-polar."
    ),
)


apply_nac_correction = Operator(
    name="apply_nac_correction",
    inputs=(BARE_DYNAMICAL_MATRIX, BORN_CHARGES, DIELECTRIC_TENSOR),
    outputs=(DYNAMICAL_MATRIX,),
    schemes={"nac_scheme": "gonze_lee"},
    formula=_DM_NAC_FORMULA,
    description=(
        "Polar branch: adds the non-analytic correction (LO-TO splitting) "
        "to the bare dynamical matrix using Born effective charges Z* and "
        "the macroscopic dielectric tensor ε∞. The correction term is "
        "bilinear in (q · Z*) and inversely bilinear in (q · ε∞ · q), so "
        "it depends on the q-direction in the q→0 limit and produces the "
        "LO-TO splitting at Γ. Default nac_scheme is gonze_lee (a "
        "Gaussian-truncated reciprocal-space sum, the form phonopy "
        "implements via Phonopy(nac_method='gonze')); the parry_brigham / "
        "Wang Ewald summation is an alternative."
    ),
)

compute_dispersion = Operator(
    name="compute_dispersion",
    inputs=(DYNAMICAL_MATRIX,),
    outputs=(FREQUENCY_STATE, EIGENVECTORS),
    formula=_DISP_FORMULA,
    description=(
        "Eigendecomposition of D(q): produces ω_qν and orthonormal e_qν. "
        "Implicit equation; degenerate subspaces have rotation freedom on e."
    ),
)

compute_group_velocity = Operator(
    name="compute_group_velocity",
    inputs=(DYNAMICAL_MATRIX, FREQUENCY_STATE, EIGENVECTORS),
    outputs=(GROUP_VELOCITY,),
    schemes={"gv_method": "hellmann_feynman"},
    formula=_GV_FORMULA,
    description=(
        "Hellmann-Feynman applied to the eigenvalue equation. The alternative "
        "is finite-difference of ω(q); both converge but disagree at degenerate "
        "subspaces, where the analytic form requires diagonalising ∂D/∂q in the "
        "degenerate subspace and the finite-difference form silently picks an "
        "arbitrary basis."
    ),
)

compute_heat_capacity = Operator(
    name="compute_heat_capacity",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(HEAT_CAPACITY,),
    formula=_HC_FORMULA,
    # Closed-form: c(ω,T) = (ℏω)² / (4 k_B T² sinh²(ℏω/2k_BT)).
    # Heuristic flunks on shared (q, ν) index symbols; formula lambdifies cleanly.
    is_executable_in_sympy_override=True,
    description="Quantum (Bose-Einstein) per-mode heat capacity at temperature T.",
)


compute_free_energy = Operator(
    name="compute_free_energy",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(HELMHOLTZ_FREE_ENERGY,),
    formula=_FREE_ENERGY_FORMULA,
    # Closed-form: f(ω,T) = ℏω/2 + k_B T log(1 - exp(-ℏω/k_B T)).
    is_executable_in_sympy_override=True,
    description=(
        "Per-mode Helmholtz free energy at temperature T (sibling of "
        "compute_heat_capacity). Includes the zero-point ℏω/2 contribution "
        "plus the k_B T log term."
    ),
)


compute_entropy = Operator(
    name="compute_entropy",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(ENTROPY,),
    formula=_ENTROPY_FORMULA,
    # Closed-form per-mode entropy. Uses an n_BE Function symbol that is
    # not directly lambdifiable to numpy; the executor must substitute the
    # explicit Bose-Einstein form before lambdifying.
    is_executable_in_sympy_override=True,
    description=(
        "Per-mode entropy at temperature T. Equivalent to -∂f/∂T; the "
        "explicit form uses n_BE(ℏω/(k_B T)) and the log of the partition "
        "factor."
    ),
)


compute_internal_energy = Operator(
    name="compute_internal_energy",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(INTERNAL_ENERGY,),
    formula=_INTERNAL_ENERGY_FORMULA,
    # Closed-form per-mode internal energy: ℏω(1/2 + n_BE(ℏω/(k_B T))).
    # Same n_BE caveat as entropy.
    is_executable_in_sympy_override=True,
    description=(
        "Per-mode internal energy at temperature T, ℏω(1/2 + n_BE)."
    ),
)

compute_anharmonic_linewidth = Operator(
    name="compute_linewidth[channel=anharmonic_3ph]",
    inputs=(FREQUENCY_STATE, EIGENVECTORS, FORCE_CONSTANTS_3, TEMPERATURE_STATE),
    outputs=(ANHARMONIC_LINEWIDTH,),
    parameters=(Parameter("broadening_sigma", FREQUENCY),),
    schemes={
        "broadening_param": "stdev",
        "symmetry_group": "C1",
    },
    formula=_LW_FORMULA,
    auxiliary_formulas=(_V3SQ_DEFINITION,),
    description=(
        "Anharmonic 3-phonon linewidth: imaginary self-energy from "
        "Fermi's golden rule. The kernel |V₃|² is the Maradudin-Fein "
        "matrix element (auxiliary_formulas[0]): a triple sum of Φ³ "
        "contracted with eigenvectors and mass factors, scaled by "
        "1/(8 ω ω' ω''). The same kernel appears in the LBTE collision "
        "matrix Ξ (see solve_bte_direct.auxiliary_formulas[0]). Energy "
        "delta is replaced by a Gaussian of canonical width σ = stdev. "
        "n_BE(x) = (e^{x} - 1)^{-1} with x = ℏω/(k_B T). q'' is fixed by crystal "
        "momentum conservation: q'' = q - q' (mod a reciprocal lattice "
        "vector). Under crystal symmetry G ⊂ O(3), the BZ sum Σ_{q'} "
        "can be restricted to the irreducible wedge BZ/G with "
        "multiplicity weights |G·q'|; symmetry_group=G asserts this "
        "reduction. symmetry_group=C1 means the full ordered grid is "
        "summed."
    ),
)


# Tamura isotope-disorder scattering:
#   Γ_iso(qν) = (π/2) ω_qν² Σ_i g_i (e*_iqν · e_iqν') δ(ω_qν - ω_qν')
# summed over (q', ν') in the BZ. The 1/2 cancels the standard 2-from-Fermi-rule
# factor so Γ_iso has the same gamma_definition convention as Γ_anharmonic.
_ISO_FORMULA = sp.Eq(
    sp.IndexedBase(r"\Gamma^{iso}")[_q, _nu],
    sp.pi / 2 * _omega[_q, _nu] ** 2 * sp.Sum(
        sp.IndexedBase("g")[_i]
        * sp.Abs(sp.Sum(
            sp.conjugate(_e[_i, _q, _nu]) * _e[_i, _qp, _nu_p],
            (_i, 1, _N_atoms),
        )) ** 2
        * _delta(_omega[_q, _nu] - _omega[_qp, _nu_p]),
        (_qp, 1, _N_q), (_nu_p, 1, _N_modes),
    ),
)

compute_isotope_scattering = Operator(
    name="compute_isotope_scattering",
    inputs=(FREQUENCY_STATE, EIGENVECTORS, ISOTOPE_ABUNDANCES),
    outputs=(ISOTOPIC_LINEWIDTH,),
    schemes={"delta_broadening": "gaussian"},
    formula=_ISO_FORMULA,
    description=(
        "Isotopic disorder scattering rate per mode (Tamura model). "
        "Linear in the per-atom mass-variance factor g_i and quadratic "
        "in ω; couples mode (q,ν) to all (q',ν') with matching frequency "
        "through the eigenvector overlap. Gauge-dependent per-element "
        "(inherits eigenvector basis at degenerate ω); the BZ-summed "
        "total is the observable. delta_broadening records how the "
        "energy δ is realized at finite q-mesh."
    ),
)


# Casimir / boundary scattering (Matthiessen form):
#   Γ_boundary(qν) = |v_qν| / L
# where L is a length parameter for the sample size / mean free path cap.
_L_boundary = sp.Symbol("L", positive=True)
_BOUNDARY_FORMULA = sp.Eq(
    sp.IndexedBase(r"\Gamma^{bnd}")[_q, _nu],
    sp.sqrt(sp.Sum(
        _v[_alpha, _q, _nu] ** 2, (_alpha, 1, 3),
    )) / _L_boundary,
)

compute_boundary_scattering = Operator(
    name="compute_boundary_scattering",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY),
    outputs=(BOUNDARY_LINEWIDTH,),
    parameters=(Parameter("boundary_length_scale", LENGTH),),
    formula=_BOUNDARY_FORMULA,
    description=(
        "Casimir boundary scattering rate: Γ = |v| / L, with L a "
        "user-supplied sample / mean-free-path length scale. Linear in "
        "the group-velocity magnitude; independent of temperature. "
        "Inherits GroupVelocity's gauge-dependence at degenerate ω."
    ),
)


# Matthiessen sum: Γ_total = Γ_anharmonic + Γ_isotope + Γ_boundary
_GAMMA_total = sp.IndexedBase(r"\Gamma^{tot}")
_GAMMA_anh = sp.IndexedBase(r"\Gamma^{anh}")
_GAMMA_iso = sp.IndexedBase(r"\Gamma^{iso}")
_GAMMA_bnd = sp.IndexedBase(r"\Gamma^{bnd}")
_SUM_LINEWIDTHS_FORMULA = sp.Eq(
    _GAMMA_total[_q, _nu],
    _GAMMA_anh[_q, _nu] + _GAMMA_iso[_q, _nu] + _GAMMA_bnd[_q, _nu],
)

sum_linewidths = Operator(
    name="sum_linewidths",
    inputs=(ANHARMONIC_LINEWIDTH, ISOTOPIC_LINEWIDTH, BOUNDARY_LINEWIDTH),
    outputs=(TOTAL_LINEWIDTH,),
    formula=_SUM_LINEWIDTHS_FORMULA,
    # Closed-form Matthiessen sum Γ_tot = Γ_anh + Γ_iso + Γ_bnd; the
    # heuristic flunks on the shared (q, ν) index symbols.
    is_executable_in_sympy_override=True,
    description=(
        "Matthiessen sum of all scattering channels. The BTE solver "
        "consumes the total; runs that don't model a channel feed zero "
        "on that input."
    ),
)


provide_isotope_abundances = Operator(
    name="provide_isotope_abundances",
    inputs=(),
    outputs=(ISOTOPE_ABUNDANCES,),
    formula=sp.Eq(
        sp.IndexedBase("g")[_i],
        sp.Symbol("g_{provided}"),
    ),
    description=(
        "Source: per-atom isotopic mass-variance factor g_i. Either "
        "natural-abundance defaults (computed from a periodic-table "
        "lookup) or user-supplied values for isotopically enriched "
        "samples."
    ),
)

solve_bte_rta = Operator(
    name="solve_bte[bte_solver=rta]",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, TOTAL_LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT_RTA,),
    schemes={"bte_solver": "rta"},
    formula=_BTE_RTA_FORMULA,
    description=(
        "Relaxation-time approximation: F = v / (2Γ). Closed-form per "
        "mode. Drops the off-diagonal terms of the collision matrix, so "
        "κ_RTA inherits Linewidth's gauge-dependence."
    ),
)

solve_bte_direct = Operator(
    name="solve_bte[bte_solver=direct_inverse]",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, HEAT_CAPACITY, TOTAL_LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT_DIRECT,),
    schemes={
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

contract_kappa_rta = Operator(
    name="contract_kappa[bte_solver=rta]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_RTA),
    outputs=(THERMAL_CONDUCTIVITY_RTA,),
    formula=_KAPPA_FORMULA,
    description=(
        "Per-mode contraction with F from RTA. The 1/Γ non-linearity "
        "propagates Linewidth's gauge-dependence into κ_RTA."
    ),
)

contract_kappa_direct = Operator(
    name="contract_kappa[bte_solver=direct_inverse]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT),
    outputs=(THERMAL_CONDUCTIVITY_DIRECT,),
    parameters=(Parameter("V_{cell}", VOLUME),),
    formula=_KAPPA_FORMULA,
    description="Per-mode contraction with the LBTE F; result is gauge-invariant.",
    # κ[α,β] shares the α,β index symbols across LHS/RHS — those are dummy
    # contraction indices, not the unknown — so the default disjoint-free-
    # symbol heuristic false-negatives. The contraction is closed-form
    # (an einsum), evaluable by the general Sum evaluator.
    is_executable_in_sympy_override=True,
)


# Wigner κ. Populations channel is the LBTE-like piece (numerically close to
# κ_LBTE); coherences channel couples bands at the same q through a
# Lorentzian-weighted mode-overlap. Both depend on the per-mode linewidth as
# the broadening width.
_v_alpha_qν = _v[_alpha, _q, _nu]
_v_beta_qνp = _v[_beta, _q, _nu_p]

# κ_W^pop ≈ (1/(V N_q)) Σ_qν c_qν v^α_qν v^β_qν τ_qν, equivalent to κ_LBTE
# under the populations-only restriction. We use the same form here for
# uniformity; the cross-code comparison rests on identical sympy.
_KAPPA_WIGNER_POP_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^{W,pop}")[_alpha, _beta],
    sp.Sum(_c[_q, _nu] * _v[_alpha, _q, _nu] * _F[_beta, _q, _nu],
           (_q, 1, _N_q), (_nu, 1, _N_modes)) / (_V_cell * _N_q),
)

# κ_W^coh = (1/(V N_q)) Σ_qνν' (ω_qν + ω_qν')/2 · (c_qν/ω_qν + c_qν'/ω_qν')
#                              · v^α_qν,qν' v^β_qν',qν
#                              · Γ_qν + Γ_qν' / [(ω_qν - ω_qν')² + (Γ_qν + Γ_qν')²]
#
# The mode-pair specific-heat weighting is the frequency-weighted Simoncelli
# form (ω+ω')/2 · (c/ω + c'/ω'), transcribed from the vendored phono3py SMM19
# solver phono3py/phono3py/conductivity/ms_smm19/kappa_solvers.py:122-126
# (prefactor = 0.25·(ℏω_s+ℏω_s')·(C_s/ℏω_s + C_s'/ℏω_s')), cross-checked
# against kaldo's off-diagonal C_{ss'}/(4 ω_s ω_s') QHGK kernel
# (kaldo/kaldo/conductivity.py:44-45, observables/harmonic_with_q_temp.py:77-81).
# This carries one fewer power of frequency than the earlier (c+c')/2·(ω+ω')/2
# encoding, restoring κ_C to the thermal-conductivity dimension. The Lorentzian
# is kept in the (Γ+Γ')/[(Δω)²+(Γ+Γ')²] convention shared with the QHGK sibling.
_KAPPA_WIGNER_COH_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^{W,coh}")[_alpha, _beta],
    sp.Sum(
        (_omega[_q, _nu] + _omega[_q, _nu_p]) / 2
        * (_c[_q, _nu] / _omega[_q, _nu] + _c[_q, _nu_p] / _omega[_q, _nu_p])
        * _v_alpha_qν * _v_beta_qνp
        * (_GAMMA_anh[_q, _nu] + _GAMMA_anh[_q, _nu_p])
        / ((_omega[_q, _nu] - _omega[_q, _nu_p]) ** 2
           + (_GAMMA_anh[_q, _nu] + _GAMMA_anh[_q, _nu_p]) ** 2),
        (_q, 1, _N_q), (_nu, 1, _N_modes), (_nu_p, 1, _N_modes),
    ) / (_V_cell * _N_q),
)

_KAPPA_WIGNER_TOTAL_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^W")[_alpha, _beta],
    sp.IndexedBase(r"\kappa^{W,pop}")[_alpha, _beta]
    + sp.IndexedBase(r"\kappa^{W,coh}")[_alpha, _beta],
)


compute_kappa_wigner_populations = Operator(
    name="compute_kappa[transport_model=wigner_populations]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT),
    outputs=(THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,),
    schemes={"transport_model": "wigner_populations"},
    formula=_KAPPA_WIGNER_POP_FORMULA,
    description=(
        "Populations (particle-like) component of the Wigner κ. Uses the "
        "LBTE F (gauge-invariant); numerically close to κ_LBTE."
    ),
)


compute_kappa_wigner_coherences = Operator(
    name="compute_kappa[transport_model=wigner_coherences]",
    inputs=(HEAT_CAPACITY, FREQUENCY_STATE, GROUP_VELOCITY, TOTAL_LINEWIDTH),
    outputs=(THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,),
    schemes={"transport_model": "wigner_coherences"},
    formula=_KAPPA_WIGNER_COH_FORMULA,
    description=(
        "Coherences (wave-like) component of the Wigner κ. Lorentzian-"
        "weighted band-overlap at fixed q; dominant when mode spacings "
        "approach Γ. The mode-pair specific-heat weighting is the "
        "frequency-weighted Simoncelli form (ω+ω')/2·(c/ω + c'/ω') "
        "transcribed from the vendored phono3py Wigner (SMM19) solver "
        "phono3py/phono3py/conductivity/ms_smm19/kappa_solvers.py:122-126 "
        "(prefactor 0.25·(ℏω_s+ℏω_s')·(C_s/ℏω_s + C_s'/ℏω_s')), "
        "cross-checked against kaldo's off-diagonal C_{ss'}/(4 ω_s ω_s') "
        "QHGK kernel (kaldo/kaldo/conductivity.py:44-45, "
        "observables/harmonic_with_q_temp.py:77-81). This is the "
        "Simoncelli, Marzari, Mauri, Nat. Phys. 15, 809 (2019) coherence "
        "conductivity κ_C."
    ),
)


combine_kappa_wigner = Operator(
    name="combine_kappa_wigner",
    inputs=(THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
            THERMAL_CONDUCTIVITY_WIGNER_COHERENCES),
    outputs=(THERMAL_CONDUCTIVITY_WIGNER,),
    formula=_KAPPA_WIGNER_TOTAL_FORMULA,
    # Closed-form κ_W = κ_pop + κ_coh; heuristic flunks on shared (α, β).
    is_executable_in_sympy_override=True,
    description=(
        "Sum of populations + coherences channels into the unified "
        "Wigner κ."
    ),
)


# QHGK κ. Green-Kubo time integral with Lorentzian-broadened modes.
# κ_QHGK = (1/(V N_q)) Σ_qνν' c_qν v^α_qν,qν' v^β_qν',qν · Lorentzian(ω-ω', Γ).
_KAPPA_QHGK_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^{QHGK}")[_alpha, _beta],
    sp.Sum(
        _c[_q, _nu] * _v_alpha_qν * _v_beta_qνp
        * (_GAMMA_anh[_q, _nu] + _GAMMA_anh[_q, _nu_p])
        / ((_omega[_q, _nu] - _omega[_q, _nu_p]) ** 2
           + (_GAMMA_anh[_q, _nu] + _GAMMA_anh[_q, _nu_p]) ** 2),
        (_q, 1, _N_q), (_nu, 1, _N_modes), (_nu_p, 1, _N_modes),
    ) / (_V_cell * _N_q),
)


compute_kappa_qhgk = Operator(
    name="compute_kappa[transport_model=qhgk]",
    inputs=(HEAT_CAPACITY, FREQUENCY_STATE, GROUP_VELOCITY, TOTAL_LINEWIDTH, TEMPERATURE_STATE),
    outputs=(THERMAL_CONDUCTIVITY_QHGK,),
    schemes={"transport_model": "qhgk"},
    formula=_KAPPA_QHGK_FORMULA,
    description=(
        "Quasi-harmonic Green-Kubo κ: time-integrated heat-flux "
        "autocorrelation with Lorentzian mode broadening. Bypasses the "
        "BTE; uses Γ directly as the broadening width rather than as "
        "the inverse of a relaxation time. Used primarily for amorphous "
        "and complex-crystal systems."
    ),
)


# Cumulative κ distributions: thresholded sums over the per-mode κ
# integrand. wrt=omega bins by phonon frequency; wrt=mfp bins by mean
# free path magnitude.
_omega_c = sp.Symbol(r"\omega_c", positive=True)
_lambda_c = sp.Symbol(r"\Lambda_c", positive=True)
_heaviside = sp.Function(r"\theta")
_F_mag = sp.sqrt(sp.Sum(_F[_alpha, _q, _nu] ** 2, (_alpha, 1, 3)))

_CUMULATIVE_KAPPA_OMEGA_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^{cum}_\omega")[_alpha, _beta, _omega_c],
    sp.Sum(
        _c[_q, _nu] * _v[_alpha, _q, _nu] * _F[_beta, _q, _nu]
        * _heaviside(_omega_c - _omega[_q, _nu]),
        (_q, 1, _N_q), (_nu, 1, _N_modes),
    ) / (_V_cell * _N_q),
)

_CUMULATIVE_KAPPA_MFP_FORMULA = sp.Eq(
    sp.IndexedBase(r"\kappa^{cum}_\Lambda")[_alpha, _beta, _lambda_c],
    sp.Sum(
        _c[_q, _nu] * _v[_alpha, _q, _nu] * _F[_beta, _q, _nu]
        * _heaviside(_lambda_c - _F_mag),
        (_q, 1, _N_q), (_nu, 1, _N_modes),
    ) / (_V_cell * _N_q),
)


contract_cumulative_kappa_omega = Operator(
    name="contract_cumulative_kappa[wrt=omega]",
    inputs=(HEAT_CAPACITY, FREQUENCY_STATE, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT),
    outputs=(CUMULATIVE_KAPPA_OMEGA,),
    schemes={"binning": "linear"},
    formula=_CUMULATIVE_KAPPA_OMEGA_FORMULA,
    description=(
        "Cumulative κ vs frequency threshold ω_c. Saturates at κ_LBTE "
        "for ω_c → max ω. The binning convention captures how the "
        "frequency axis is discretized (linear / log)."
    ),
)


contract_cumulative_kappa_mfp = Operator(
    name="contract_cumulative_kappa[wrt=mfp]",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT_DIRECT),
    outputs=(CUMULATIVE_KAPPA_MFP,),
    schemes={"binning": "log"},
    formula=_CUMULATIVE_KAPPA_MFP_FORMULA,
    description=(
        "Cumulative κ vs mean-free-path threshold Λ_c. Heavily used "
        "for nanoscale design (the Λ at which κ_cum = κ/2 is the "
        "characteristic transport length). Conventionally on a log-Λ "
        "axis since mode mean-free-paths span many orders of magnitude."
    ),
)


# C_V_vol(T) = (1/V_cell N_q) Σ_qν c_qν(T)
_C_V_vol = sp.Symbol(r"C_V^{vol}")
_C_V_mol = sp.Symbol(r"C_V^{mol}")
# _N_A already defined above with the harmonic-thermo molar formulas.

_CV_VOL_FORMULA = sp.Eq(
    _C_V_vol,
    sp.Sum(_c[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / (_V_cell * _N_q),
)

# C_V_mol(T) = (N_A / N_q) Σ_qν c_qν(T)  (per mole of primitive cells)
_CV_MOL_FORMULA = sp.Eq(
    _C_V_mol,
    _N_A * sp.Sum(_c[_q, _nu], (_q, 1, _N_q), (_nu, 1, _N_modes)) / _N_q,
)


contract_volumetric_heat_capacity = Operator(
    name="contract_volumetric_heat_capacity",
    inputs=(HEAT_CAPACITY,),
    outputs=(VOLUMETRIC_HEAT_CAPACITY,),
    parameters=(Parameter("V_{cell}", VOLUME),),
    formula=_CV_VOL_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode heat capacity, divided by cell "
        "volume. Gauge-invariant (no Linewidth or eigenvector input). "
        "ShengBTE emits this directly; kaldo/phono3py reach it by "
        "contracting their per-mode arrays."
    ),
)


contract_molar_heat_capacity = Operator(
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


contract_molar_free_energy = Operator(
    name="contract_molar_free_energy",
    inputs=(HELMHOLTZ_FREE_ENERGY,),
    outputs=(MOLAR_HELMHOLTZ_FREE_ENERGY,),
    formula=_MOLAR_FREE_ENERGY_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode Helmholtz free energy, N_A/N_q. "
        "Phonopy emits this as thermal_properties['free_energy'] in kJ/mol."
    ),
)


contract_molar_entropy = Operator(
    name="contract_molar_entropy",
    inputs=(ENTROPY,),
    outputs=(MOLAR_ENTROPY,),
    formula=_MOLAR_ENTROPY_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode entropy, N_A/N_q. Phonopy emits "
        "this as thermal_properties['entropy'] in J/(K·mol)."
    ),
)


contract_molar_internal_energy = Operator(
    name="contract_molar_internal_energy",
    inputs=(INTERNAL_ENERGY,),
    outputs=(MOLAR_INTERNAL_ENERGY,),
    formula=_MOLAR_INTERNAL_ENERGY_FORMULA,
    description=(
        "BZ-and-mode sum of the per-mode internal energy, N_A/N_q. "
        "Phonopy emits this as thermal_properties['internal_energy'] in "
        "kJ/mol."
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


compute_dos = Operator(
    name="compute_dos",
    inputs=(FREQUENCY_STATE,),
    outputs=(PHONON_DOS,),
    schemes={"dos_broadening": "gaussian"},
    formula=_DOS_FORMULA,
    description=(
        "Histogram / smeared sum of phonon frequencies into a 1-D density "
        "of states. The δ is usually replaced by a Gaussian or tetrahedron "
        "weight at finite q-mesh; dos_broadening records the choice. "
        "Independent of eigenvectors → gauge-invariant."
    ),
)


compute_gruneisen = Operator(
    name="compute_gruneisen",
    inputs=(FORCE_CONSTANTS_2, FORCE_CONSTANTS_3, FREQUENCY_STATE, EIGENVECTORS),
    outputs=(GRUNEISEN,),
    schemes={"gruneisen_method": "maradudin_fein"},
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


compute_phase_space_3phonon = Operator(
    name="compute_phase_space_3phonon",
    inputs=(FREQUENCY_STATE,),
    outputs=(PHASE_SPACE_3PH,),
    schemes={"delta_broadening": "gaussian"},
    formula=_P3_FORMULA,
    description=(
        "Three-phonon kinematic phase space: counts the (q',ν',ν'') channels "
        "satisfying energy + crystal-momentum conservation for the given "
        "(q, ν). |V₃|² is not included — this is purely a measure of "
        "scattering availability. delta_broadening records how the energy δ "
        "is realised at finite q-mesh (Gaussian, Lorentzian, tetrahedron)."
    ),
)


# ---------------------------------------------------------------------------
# MD primitives (phase 2 P2)
# ---------------------------------------------------------------------------

_t_idx = sp.Symbol("t", integer=True)
_tau = sp.Symbol(r"\tau", positive=True)
_dt = sp.Symbol(r"\Delta t", positive=True)
_n_lag = sp.Symbol(r"n_{lag}", positive=True, integer=True)
_n_atoms_md = sp.Symbol(r"N_{atoms}", positive=True, integer=True)
# IndexedBases for the MD primitives. Index signatures match the
# corresponding output State's first field declaration: Trajectory r/v
# carry (i, α, t); HeatCurrent J carries (α, t); HeatCurrentACF Jcorr
# carries (α, β, τ); VAF Cv and MSD M carry (τ,); PhononDOS g carries
# (ω,). These are schematic *forms* — production loops iterate time and
# correlate over origins, and the formulas are not sympy-executable:
# `is_executable_in_sympy_default` returns False for stateful / time-
# integrated recurrences, and the executor raises ExternalSolveRequired
# pointing at the LAMMPS or GPUMD adapter.
_r_traj = sp.IndexedBase("r")
_v_traj = sp.IndexedBase("v")
_F_md = sp.IndexedBase("F^{md}")
_E_per_atom = sp.IndexedBase("E")
_J_heat = sp.IndexedBase("J")
_Jcorr = sp.IndexedBase("Jcorr")
_Cv_corr = sp.IndexedBase("Cv")
_MSD_sym = sp.IndexedBase("M")
_g_DOS_md = sp.IndexedBase("g")
_omega_bin_md = sp.Symbol(r"\omega")

# run_md: one Velocity-Verlet step (schematic — production loop iterates
# n_steps times after equilibration; thermostat applied as auxiliary).
_RUN_MD_FORMULA = sp.Eq(
    _r_traj[_i, _alpha, _t_idx + 1],
    _r_traj[_i, _alpha, _t_idx]
    + _v_traj[_i, _alpha, _t_idx] * _dt
    + _F_md[_i, _alpha, _t_idx] * _dt**2 / 2,
)

# compute_heat_current: Irving-Kirkwood form (condensed).
# J_α(t) = (1/V) [ Σ_i E_i(t) v_{iα}(t) + (1/2) Σ_i r_{iα}(t) F_{iα}(t) v_{iα}(t) ]
# The pair-sum form is the textbook IK; this single-atom condensation is
# the schematic the validator can check against the output field's (α,t)
# index signature.
_HEAT_CURRENT_FORMULA = sp.Eq(
    _J_heat[_alpha, _t_idx],
    (
        sp.Sum(
            _E_per_atom[_i, _t_idx] * _v_traj[_i, _alpha, _t_idx],
            (_i, 1, _n_atoms_md),
        )
        + sp.Sum(
            _r_traj[_i, _alpha, _t_idx]
            * _F_md[_i, _alpha, _t_idx]
            * _v_traj[_i, _alpha, _t_idx],
            (_i, 1, _n_atoms_md),
        ) / 2
    ) / _V_cell,
)

# autocorrelate_heat_current: Jcorr_αβ(τ) = (1/n_lag) Σ_t J_α(t) J_β(t+τ).
_AUTOCORRELATE_HEAT_CURRENT_FORMULA = sp.Eq(
    _Jcorr[_alpha, _beta, _tau],
    sp.Sum(
        _J_heat[_alpha, _t_idx] * _J_heat[_beta, _t_idx + _tau],
        (_t_idx, 1, _n_lag),
    ) / _n_lag,
)

# compute_velocity_autocorrelation: Cv(τ) = (1/(N·n_lag)) Σ_i Σ_α Σ_t v_{iα}(t)·v_{iα}(t+τ).
_COMPUTE_VELOCITY_AUTOCORRELATION_FORMULA = sp.Eq(
    _Cv_corr[_tau],
    sp.Sum(
        sp.Sum(
            sp.Sum(
                _v_traj[_i, _alpha, _t_idx] * _v_traj[_i, _alpha, _t_idx + _tau],
                (_alpha, 1, 3),
            ),
            (_i, 1, _n_atoms_md),
        ),
        (_t_idx, 1, _n_lag),
    ) / (_n_atoms_md * _n_lag),
)

# compute_msd: M(τ) = (1/(N·n_lag)) Σ_i Σ_α Σ_t |r_{iα}(t+τ) − r_{iα}(t)|².
_COMPUTE_MSD_FORMULA = sp.Eq(
    _MSD_sym[_tau],
    sp.Sum(
        sp.Sum(
            sp.Sum(
                (_r_traj[_i, _alpha, _t_idx + _tau] - _r_traj[_i, _alpha, _t_idx]) ** 2,
                (_alpha, 1, 3),
            ),
            (_i, 1, _n_atoms_md),
        ),
        (_t_idx, 1, _n_lag),
    ) / (_n_atoms_md * _n_lag),
)

# fourier_to_dos: g(ω) = (1/π) ∫₀^∞ Cv(τ) cos(ωτ) dτ (Wiener-Khinchin).
_FOURIER_TO_DOS_FORMULA = sp.Eq(
    _g_DOS_md[_omega_bin_md],
    sp.Integral(
        _Cv_corr[_tau] * sp.cos(_omega_bin_md * _tau),
        (_tau, 0, sp.oo),
    ) / sp.pi,
)


run_md = Operator(
    name="run_md",
    inputs=(POTENTIAL, TEMPERATURE_STATE),
    outputs=(TRAJECTORY,),
    parameters=(
        Parameter("time_step", FREQUENCY),  # 1/τ-style scale; concrete unit declared by adapter
        Parameter("n_steps", FREQUENCY),    # placeholder dim; truly a count
    ),
    schemes={
        "ensemble": "NVE",
        "thermostat": "none",
        "integrator": "velocity_verlet",
    },
    formula=_RUN_MD_FORMULA,
    description=(
        "Integrate the classical equations of motion under the chosen "
        "ensemble + thermostat. The formula spells out one Velocity-Verlet "
        "step; the production loop iterates n_steps times after "
        "n_equilibration_steps of equilibration. ensemble ∈ {NVE, NVT, NPT, "
        "NEMD} controls boundary / driving-force conditions; thermostat ∈ "
        "{berendsen, langevin, nose_hoover, csvr, none} controls how T is "
        "imposed; integrator ∈ {velocity_verlet, leapfrog, …} is the "
        "time-stepping scheme."
    ),
)

compute_heat_current = Operator(
    name="compute_heat_current",
    inputs=(TRAJECTORY,),
    outputs=(HEAT_CURRENT,),
    schemes={"definition": "irving_kirkwood"},
    formula=_HEAT_CURRENT_FORMULA,
    description=(
        "Per-timestep heat current J_α(t) from the MD trajectory. The "
        "canonical decomposition is Irving-Kirkwood: convective term "
        "Σ_i E_i v_{i,α} plus the pair virial contribution (1/2) Σ_{i≠j} "
        "r_{ij,α} (F_{ij}·v_i). Alternatives ('hardy', 'virial') differ in "
        "how the per-atom energy E_i is decomposed for many-body "
        "potentials; the scheme `definition` records the "
        "choice. Stays a HiddenSpace per-element (MD noise); the "
        "gauge-invariant content is the time correlation."
    ),
)

autocorrelate_heat_current = Operator(
    name="autocorrelate_heat_current",
    inputs=(HEAT_CURRENT,),
    outputs=(HEAT_CURRENT_ACF,),
    formula=_AUTOCORRELATE_HEAT_CURRENT_FORMULA,
    description=(
        "Time-correlation tensor ⟨J_α(0) J_β(τ)⟩ from a stationary segment "
        "of the heat-current trajectory. Implementations are numerically "
        "equivalent under the periodic-padding assumption — direct O(n_lag "
        "· n_origins) double sum or O(n log n) FFT via the Wiener-Khinchin "
        "theorem; both produce the same Green-Kubo κ integrand. The output "
        "is the Green-Kubo κ integrand."
    ),
)

compute_velocity_autocorrelation = Operator(
    name="compute_velocity_autocorrelation",
    inputs=(TRAJECTORY,),
    outputs=(VELOCITY_AUTOCORRELATION,),
    formula=_COMPUTE_VELOCITY_AUTOCORRELATION_FORMULA,
    description=(
        "Velocity autocorrelation function ⟨v(0)·v(τ)⟩ averaged over atoms "
        "and time origins. The FT of Cv(τ) yields the phonon DOS — see the "
        "`fourier_to_dos` edge."
    ),
)

compute_msd = Operator(
    name="compute_msd",
    inputs=(TRAJECTORY,),
    outputs=(MEAN_SQUARED_DISPLACEMENT,),
    schemes={"unwrap_pbc": "true"},
    formula=_COMPUTE_MSD_FORMULA,
    description=(
        "Mean-squared displacement ⟨|r(t+τ) − r(t)|²⟩ averaged over atoms "
        "and origins. `unwrap_pbc` MUST be true for the M(τ) = 2·d·D·τ "
        "diffusion limit to be meaningful; with PBC-wrapped Δr, M(τ) "
        "saturates at L²/3 instead of growing linearly. Codes that emit a "
        "pre-unwrapped trajectory inherit the convention from the upstream "
        "MD run."
    ),
)

fourier_to_dos = Operator(
    name="fourier_to_dos",
    inputs=(VELOCITY_AUTOCORRELATION,),
    outputs=(PHONON_DOS,),
    schemes={"dos_broadening": "gaussian"},
    formula=_FOURIER_TO_DOS_FORMULA,
    description=(
        "Classical-MD route to the phonon DOS via the Wiener-Khinchin "
        "theorem: g(ω) = (1/π) ∫₀^∞ Cv(τ) cos(ωτ) dτ. Pattern-C "
        "alternative producer of PhononDOS alongside the harmonic-tier "
        "compute_dos edge — both target the same PhononDOS state, but the "
        "MD route is anharmonic-inclusive (broadened by lifetime effects) "
        "while compute_dos is the harmonic δ-sum."
    ),
)


# ---------------------------------------------------------------------------
# MD-based κ paths (phase 2 P3). Three contraction edges, each producing a
# Pattern-A `transport_model` variant of ThermalConductivity.
# ---------------------------------------------------------------------------

_kappa_md = sp.IndexedBase(r"\kappa^{MD}")
_F_drive = sp.IndexedBase("F_e")
_tau_max = sp.Symbol(r"\tau_{max}", positive=True)
_grad_T = sp.IndexedBase(r"\nabla T")

# Classical Green-Kubo: κ_αβ = V/(k_B T²) ∫₀^{τ_max} ⟨J_α(0) J_β(τ)⟩ dτ.
# The lower limit is 0 by convention; in practice users introduce a
# `tau_min` to skip the first few uncorrelated steps where Jcorr is noisy.
_CONTRACT_KAPPA_GREEN_KUBO_FORMULA = sp.Eq(
    _kappa_md[_alpha, _beta],
    sp.Integral(_Jcorr[_alpha, _beta, _tau], (_tau, 0, _tau_max))
    * _V_cell / (_kB * _T**2),
)

# Direct NEMD (or Müller-Plathe): κ = −⟨J_α⟩ / (∂T/∂x_β). The negative sign
# follows Fourier's law sign convention; ⟨J⟩ is the time-averaged
# HeatCurrent and ∇T is read off the binned-temperature profile slope.
_CONTRACT_KAPPA_NEMD_FORMULA = sp.Eq(
    _kappa_md[_alpha, _beta],
    -_J_heat[_alpha, _t_idx] / _grad_T[_beta],
)

# HNEMD: κ_αβ = ⟨J_α⟩ / (T · V · F_e^β), in the linear-response limit.
# F_e is the imposed driving force applied homogeneously to every atom.
_CONTRACT_KAPPA_HNEMD_FORMULA = sp.Eq(
    _kappa_md[_alpha, _beta],
    _J_heat[_alpha, _t_idx] / (_T * _V_cell * _F_drive[_beta]),
)

contract_kappa_green_kubo = Operator(
    name="contract_kappa[transport_model=green_kubo]",
    inputs=(HEAT_CURRENT_ACF, TEMPERATURE_STATE),
    outputs=(THERMAL_CONDUCTIVITY_GREEN_KUBO,),
    parameters=(
        Parameter("tau_max", FREQUENCY),
        Parameter("tau_min", FREQUENCY),
    ),
    schemes={"transport_model": "green_kubo"},
    formula=_CONTRACT_KAPPA_GREEN_KUBO_FORMULA,
    description=(
        "Classical Green-Kubo κ from the heat-flux ACF: κ_αβ = "
        "V/(k_B T²) ∫₀^{τ_max} ⟨J_α(0) J_β(τ)⟩ dτ. The integration tail "
        "dominates the noise; production runs use multiple ensemble "
        "repeats and a τ_max well past the ACF zero-crossing. `tau_min` "
        "is the lower bound (often 0); set to a few steps to skip the "
        "uncorrelated-noise spike at very short lag."
    ),
)

contract_kappa_nemd = Operator(
    name="contract_kappa[transport_model=nemd]",
    inputs=(HEAT_CURRENT, TEMPERATURE_STATE),
    outputs=(THERMAL_CONDUCTIVITY_NEMD,),
    parameters=(
        Parameter("imposed_gradient", TEMPERATURE),
        Parameter("imposed_flux", FREQUENCY),
    ),
    schemes={"nemd_method": "muller_plathe"},
    formula=_CONTRACT_KAPPA_NEMD_FORMULA,
    description=(
        "Direct NEMD κ from steady-state ⟨J⟩ and dT/dz. Three method "
        "variants: `direct_two_reservoir` imposes T_hot/T_cold and "
        "measures J; `muller_plathe` imposes the swap-rate flux and "
        "measures dT/dz; `ehex` is an energy-conserving alternative to "
        "Müller-Plathe. Finite-size scaling (κ vs 1/L_z) is required to "
        "extract bulk κ; left to user post-processing. `imposed_gradient` "
        "and `imposed_flux` are alternatives — direct uses the former, "
        "Müller-Plathe the latter."
    ),
)

contract_kappa_hnemd = Operator(
    name="contract_kappa[transport_model=hnemd]",
    inputs=(HEAT_CURRENT, TEMPERATURE_STATE),
    outputs=(THERMAL_CONDUCTIVITY_HNEMD,),
    parameters=(
        Parameter("driving_force_magnitude", FREQUENCY),
        Parameter("driving_direction", FREQUENCY),
    ),
    schemes={"transport_model": "hnemd"},
    formula=_CONTRACT_KAPPA_HNEMD_FORMULA,
    description=(
        "Homogeneous-NEMD κ: a uniform F_e applied to every atom biases "
        "the heat current; in the linear-response limit, "
        "κ_αβ = ⟨J_α⟩/(T · V · F_e^β). GPUMD's signature thermal-"
        "transport method. Avoids the boundary thermostats that introduce "
        "finite-size and reservoir artefacts in direct NEMD. "
        "`driving_force_magnitude` sets |F_e|; `driving_direction` "
        "picks the Cartesian axis the heat current is read along."
    ),
)


# ---------------------------------------------------------------------------
# Amorphous / localization diagnostics (kaldo delta scan, records 208-211).
# ---------------------------------------------------------------------------

# ParticipationRatio: the Bell/Dean 1/N inverse participation ratio.
#   PR_qν = 1 / (N sum_i a_i²),   a_i = sum_cart |e_i,qν|²
# The main formula is written over the per-atom (cartesian-summed) squared
# amplitude a_i, a DIMENSIONLESS IndexedBase (eigenvectors are dimensionless,
# so a_i is too). This makes the dimensional gate PROVE the ratio dimensionless
# (N dimensionless, sum of dimensionless dimensionless, reciprocal dimensionless,
# LHS p dimensionless) rather than SKIP on the globally-unregistered eigenvector
# symbol e. The auxiliary formula records that a_i is the cartesian-summed
# squared eigenvector amplitude (uses e; auxiliary formulas are not gated).
_p_PR = sp.IndexedBase("p")
_a_amp = sp.IndexedBase("a")

_PARTICIPATION_RATIO_FORMULA = sp.Eq(
    _p_PR[_q, _nu],
    1 / (_N_atoms * sp.Sum(_a_amp[_i, _q, _nu] ** 2, (_i, 1, _N_atoms))),
)

# a_i,qν = sum_α |e_{i,α,qν}|²: the per-atom amplitude, summed over the three
# cartesian components of atom i (harmonic_with_q.py:341). Reuses the
# eigenvector IndexedBase e; α runs 1..3 over cartesian components.
_PARTICIPATION_RATIO_AMPLITUDE = sp.Eq(
    _a_amp[_i, _q, _nu],
    sp.Sum(sp.Abs(_e[_i, _q, _nu]) ** 2, (_alpha, 1, 3)),
)

compute_participation_ratio = Operator(
    name="compute_participation_ratio",
    inputs=(EIGENVECTORS,),
    outputs=(PARTICIPATION_RATIO,),
    schemes={"normalization": "bell_dean_1_over_N"},
    formula=_PARTICIPATION_RATIO_FORMULA,
    auxiliary_formulas=(_PARTICIPATION_RATIO_AMPLITUDE,),
    description=(
        "Per-mode Bell/Dean inverse participation ratio from the harmonic "
        "eigenvectors: PR_qν = 1 / (N sum_i a_i²) with a_i = sum_cart "
        "|e_i,qν|² the cartesian-summed squared amplitude on atom i "
        "(auxiliary_formulas[0]). The 1/N normalization (scheme "
        "normalization=bell_dean_1_over_N) makes PR range from 1/N "
        "(single-atom-localized) to 1 (uniformly extended). Dimensionless; the "
        "localization diagnostic of the amorphous / QHGK regime. kaldo "
        "calculate_participation_ratio (harmonic_with_q.py:335-344), "
        "Phys. Rev. B 53, 11469."
    ),
)


# ModalDiffusivity: the QHGK / Allen-Feldman per-mode heat diffusivity.
#   D_qν = D^{QHGK}[ω, e, Γ^{tot}]
# Implicit: the QHGK diffusivity kernel is an off-diagonal flux-operator
# overlap summed over mode pairs with a Lorentzian energy-conservation weight
# (kaldo conductivity.py:27-49), assembled from the frequencies, the
# eigenvector-projected flux S_ij (derived from the eigenvectors), and the
# total per-mode linewidth as the pair broadening. Opaque applied function, so
# not sympy-executable; the dimensional gate SKIPS it (the kaldo unit chain
# fixes it at mm^2/s, L^2 T^-1, on the rail).
_D_mode = sp.Symbol("D_{mode}")
_D_qhgk_fn = sp.Function("D^{QHGK}")
_omega_arg = sp.Symbol(r"\omega")
_e_arg = sp.Symbol("e")
_Gamma_tot_arg = sp.Symbol(r"\Gamma^{tot}")

_MODAL_DIFFUSIVITY_FORMULA = sp.Eq(
    _D_mode,
    _D_qhgk_fn(_omega_arg, _e_arg, _Gamma_tot_arg),
)

compute_modal_diffusivity = Operator(
    name="compute_modal_diffusivity",
    inputs=(FREQUENCY_STATE, EIGENVECTORS, TOTAL_LINEWIDTH),
    outputs=(MODAL_DIFFUSIVITY,),
    schemes={"method": "qhgk", "scope": "qhgk_only"},
    formula=_MODAL_DIFFUSIVITY_FORMULA,
    is_executable_in_sympy_override=False,
    description=(
        "Per-mode QHGK / Allen-Feldman heat-mode diffusivity D_qν = "
        "D^{QHGK}[ω, e, Γ^{tot}]: the mode-resolved decomposition of "
        "kappa_QHGK, D_qν = (1/3) trace_a sum_ν' S^a_qν,qν' S^a_qν',qν "
        "Lorentzian(ω_qν - ω_qν', 2(Γ_qν + Γ_qν')) / (4 ω_qν ω_qν') "
        "(kaldo conductivity.py:27-49,434). D^{QHGK} is opaque over the "
        "frequencies ω (the Lorentzian centres and the 1/(4 ωω') weight), the "
        "eigenvectors e (through the flux operator S_ij = e† (∂D/∂q) e, whose "
        "diagonal is the GroupVelocity), and the total linewidth Γ^{tot} (the "
        "mode-pair broadening 2(Γ+Γ') in the Lorentzian). Served in mm^2/s. "
        "SHARES the L^2 T^-1 dimension with the mass-transport Diffusivity node "
        "but is a DIFFERENT quantity, kept apart by name and tag, per-mode vs "
        "scalar. QHGK-scoped (scheme scope=qhgk_only): kaldo populates "
        ".diffusivity only in the method='qhgk' branch. Implicit (the QHGK "
        "kernel), so not sympy-executable."
    ),
)


EDGES: tuple[Operator, ...] = (
    provide_potential,
    provide_temperature,
    provide_born_charges,
    provide_dielectric_tensor,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_dynamical_matrix,
    identity_dm,
    apply_nac_correction,
    compute_dispersion,
    compute_group_velocity,
    compute_heat_capacity,
    compute_free_energy,
    compute_entropy,
    compute_internal_energy,
    compute_anharmonic_linewidth,
    compute_isotope_scattering,
    compute_boundary_scattering,
    sum_linewidths,
    provide_isotope_abundances,
    solve_bte_rta,
    solve_bte_direct,
    contract_kappa_rta,
    contract_kappa_direct,
    compute_kappa_wigner_populations,
    compute_kappa_wigner_coherences,
    combine_kappa_wigner,
    compute_kappa_qhgk,
    contract_volumetric_heat_capacity,
    contract_molar_heat_capacity,
    contract_molar_free_energy,
    contract_molar_entropy,
    contract_molar_internal_energy,
    compute_dos,
    compute_gruneisen,
    compute_phase_space_3phonon,
    contract_cumulative_kappa_omega,
    contract_cumulative_kappa_mfp,
    # MD primitives (phase 2 P2)
    run_md,
    compute_heat_current,
    autocorrelate_heat_current,
    compute_velocity_autocorrelation,
    compute_msd,
    fourier_to_dos,
    # MD-based κ (phase 2 P3)
    contract_kappa_green_kubo,
    contract_kappa_nemd,
    contract_kappa_hnemd,
    # Amorphous / localization diagnostics (kaldo delta scan, records 208-211)
    compute_participation_ratio,
    compute_modal_diffusivity,
)
