r"""Operators (edges) of the DFT ground-state domain.

Four edges, all implicit (is_executable_in_sympy_override=False): the
Kohn-Sham SCF solve, the two response derivatives (Hellmann-Feynman forces,
cell stress) a DFT engine reports alongside the energy, and the
finite-displacement route from Forces to the second-order force constants
(Pattern C alternative producer, knitting the ground-state tier into the
thermal-transport chain).

Symbol choices are deliberately distinct from the thermal domain's globals to
avoid collisions in the shared dimension / vocabulary registries: E_{tot} and
E_{KS} for the energy, \mathcal{S} for the structure, V for the potential
argument, F^{at} / R^{at} for the atomic forces and positions, \sigma /
\varepsilon^{str} for the stress and strain. V_{cell} is the existing global
cell-volume symbol (already VOLUME in the dimension registry).
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.dft_ground_state.operator.nodes import (
    FORCES,
    STRESS,
    STRUCTURE,
    TOTAL_ENERGY,
)
from omai.thermal_transport.operator.nodes import FORCE_CONSTANTS_2, POTENTIAL


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

_E_tot = sp.Symbol("E_{tot}")
_E_KS = sp.Function("E_{KS}")
_S = sp.Symbol(r"\mathcal{S}")
_V_sym = sp.Symbol("V")
_F_at = sp.IndexedBase(r"F^{at}")
_R_at = sp.IndexedBase(r"R^{at}")
_sigma = sp.IndexedBase(r"\sigma")
_eps_str = sp.IndexedBase(r"\varepsilon^{str}")
_V_cell = sp.Symbol("V_{cell}", positive=True)
_i, _alpha, _beta = sp.symbols(r"i \alpha \beta", integer=True)
_j = sp.Symbol("j", integer=True)
_R = sp.Symbol(r"\mathbf{R}")
_Phi2 = sp.IndexedBase(r"\Phi^{(2)}")
# Displacement / displaced-force labels, matching the thermal FC2 formula's
# schematic convention (u_i(0) is a registered global constant there).
_F_jR = sp.Symbol("F_j(R)")
_u_i0 = sp.Symbol("u_i(0)")


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

solve_ground_state = Operator(
    name="solve_ground_state",
    inputs=(STRUCTURE, POTENTIAL),
    outputs=(TOTAL_ENERGY,),
    schemes={"method": "kohn_sham_scf"},
    formula=sp.Eq(_E_tot, _E_KS(_S, _V_sym)),
    is_executable_in_sympy_override=False,
    description=(
        "Kohn-Sham self-consistent minimization: E_tot = E_KS[S, V], the "
        "converged SCF total energy of the Structure S under the Potential V. "
        "Implicit (an external SCF solve), so not sympy-executable. The "
        "Potential is the existing source node; for a DFT run its provenance "
        "is the pseudopotential + XC functional + plane-wave cutoffs, exactly "
        "as the QE representation records."
    ),
)

compute_forces_hf = Operator(
    name="compute_forces_hf",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(FORCES,),
    formula=sp.Eq(_F_at[_i, _alpha], -sp.Derivative(_E_tot, _R_at[_i, _alpha])),
    is_executable_in_sympy_override=False,
    description=(
        "Hellmann-Feynman forces F^{at}_{i,alpha} = -dE_tot/dR^{at}_{i,alpha}: "
        "the derivative of the ground-state total energy with respect to "
        "atomic positions. In a pseudopotential plane-wave code the bare "
        "Hellmann-Feynman term carries Pulay / non-local corrections; QE "
        "reports the corrected total. Implicit (derivative of the SCF "
        "functional), so not sympy-executable."
    ),
)

compute_stress_cell = Operator(
    name="compute_stress_cell",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(STRESS,),
    formula=sp.Eq(
        _sigma[_alpha, _beta],
        -(1 / _V_cell) * sp.Derivative(_E_tot, _eps_str[_alpha, _beta]),
    ),
    is_executable_in_sympy_override=False,
    description=(
        "Cell stress sigma_{alpha,beta} = -(1/V_cell) dE_tot/d(strain)_"
        "{alpha,beta}: the derivative of the ground-state total energy with "
        "respect to a homogeneous strain, normalized by the cell volume. QE "
        "prints it in Ry/bohr^3 and kbar; a positive value is compressive "
        "(pressure convention). Implicit, so not sympy-executable."
    ),
)

compute_fc2_finite_displacement = Operator(
    name="compute_fc2_finite_displacement",
    inputs=(FORCES, STRUCTURE),
    outputs=(FORCE_CONSTANTS_2,),
    schemes={"fc_method": "finite_displacement"},
    formula=sp.Eq(_Phi2[_i, _j, _R], -sp.Derivative(_F_jR, _u_i0)),
    is_executable_in_sympy_override=False,
    description=(
        "Second-order force constants from finite displacements of the "
        "forces: Phi2_{ij}(R) = -dF_j(R)/du_i(0), evaluated by displacing "
        "atom i and reading the force response on atom j (the "
        "phonopy-consuming-pw.x-forces workflow the Si cross-check "
        "exercised). The Forces input stands for the family of displaced-"
        "configuration force evaluations, the same family-of-values "
        "convention fit_arrhenius uses for D(T). Pattern C: an alternative "
        "producer of ForceConstants[order=2] alongside "
        "compute_force_constants[order=2] (the direct potential-derivative "
        "route); downstream consumers are unaware which route fired. "
        "Implicit (a finite-difference estimator), so not sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    solve_ground_state,
    compute_forces_hf,
    compute_stress_cell,
    compute_fc2_finite_displacement,
)
