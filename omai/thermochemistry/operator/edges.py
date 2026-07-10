r"""Operators (edges) of the thermochemistry domain.

Seven edges. Six are implicit (is_executable_in_sympy_override=False): a Gibbs
minimization over an assessed database and the T-derivative / equilibrium
quantities read off it. Each carries an opaque applied function of its inputs
(the global free-energy minimization, the Legendre derivative, the composition
derivative, the lever rule, the boundary locus, the entropy T-derivative) with
the selection recorded as schemes, exactly like the stability domain's
energy-difference edges. The seventh, contract_gibbs_hts, is EXECUTABLE sympy
the dimensional gate PROVES: the exact Gibbs identity G_m = H_m - T S_m.

  solve_equilibrium            : (AssessedDatabase, Temperature) -> MolarGibbsEnergy
  compute_molar_enthalpy       : (AssessedDatabase, Temperature) -> MolarEnthalpy
  compute_chemical_potentials  : (MolarGibbsEnergy,)             -> ChemicalPotential
  compute_phase_fractions      : (AssessedDatabase, Temperature) -> PhaseFraction
  compute_transition_temperature : (PhaseFraction, Temperature)  -> TransitionTemperature
  compute_calphad_entropy      : (AssessedDatabase, Temperature) -> CalphadMolarEntropy
  contract_gibbs_hts           : (MolarEnthalpy, Temperature, CalphadMolarEntropy)
                                     -> MolarGibbsEnergy  (EXECUTABLE; second producer)

contract_gibbs_hts is the SECOND producer (Pattern C) of MolarGibbsEnergy,
alongside solve_equilibrium: the direct Gibbs minimization and the H - T S
identity are two routes to the SAME assessed G_m that must agree numerically,
the redundant-route pattern the map already blesses (BulkModulus has three
producers, PhononDOS two). The dimensional gate PROVES it: T S_m is
TEMPERATURE (0,0,0,1,0,0,0) times ENERGY_PER_TEMPERATURE_PER_MOLE
(1,2,-2,-1,-1,0,0) = ENERGY_PER_MOLE (1,2,-2,0,-1,0,0), so H_m - T S_m is an
Add of two equal ENERGY_PER_MOLE dimensions, matching G_m.

Connectivity. Temperature (the thermal-transport Sources node) is
pre-existing in the store; AssessedDatabase arrives in this contribution.
Every edge touches one or both, so the six added nodes plus five edges form
ONE weakly connected component, and at least one edge (in fact three) touches
the pre-existing Temperature, satisfying the connectivity gate.

The AssessedDatabase input stands for the assessed model (the TDB plus its
provenance); the composition of the system (comps, v.X) and the pressure
(v.P) are opaque context of the minimization, the CALPHAD analog of the
hull's competing-phase set, recorded in the schemes / conditions rather than
promoted to input nodes for this slice.

Symbols. Every field symbol is new and collision-checked: G_m, H_m, mu, NP,
T_trans (T_trans, not the bare T of the input Temperature). The opaque solver
functions (G^{min}, H^{eq}, mu^{eq}, f^{eq}, T^{trans}) are applied
functions, invisible to the free-symbol check, so they need no vocabulary
entries; their arguments D_tdb (AssessedDatabase) and T (Temperature) are
registered on those nodes' spaces.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.thermochemistry.operator.nodes import (
    ASSESSED_DATABASE,
    CALPHAD_MOLAR_ENTROPY,
    CHEMICAL_POTENTIAL,
    MOLAR_ENTHALPY,
    MOLAR_GIBBS_ENERGY,
    PHASE_FRACTION,
    TRANSITION_TEMPERATURE,
)
from omai.thermal_transport.operator.nodes import TEMPERATURE_STATE


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

_G_m = sp.Symbol("G_m")
_H_m = sp.Symbol("H_m")
_S_m = sp.Symbol("S_m")
_mu = sp.Symbol(r"\mu")
_NP = sp.Symbol("NP")
_T_trans = sp.Symbol(r"T_{\mathrm{trans}}")
_D_tdb = sp.Symbol(r"\mathcal{D}")
_T = sp.Symbol("T")
# Opaque solver functions (applied functions, not free symbols).
_G_min = sp.Function(r"G^{\min}")
_H_eq = sp.Function(r"H^{eq}")
_S_eq = sp.Function(r"S^{eq}")
_mu_eq = sp.Function(r"\mu^{eq}")
_f_eq = sp.Function(r"f^{eq}")
_T_trans_f = sp.Function(r"T^{trans}")


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

solve_equilibrium = Operator(
    name="solve_equilibrium",
    inputs=(ASSESSED_DATABASE, TEMPERATURE_STATE),
    outputs=(MOLAR_GIBBS_ENERGY,),
    schemes={"method": "gibbs_minimization"},
    formula=sp.Eq(_G_m, _G_min(_D_tdb, _T)),
    is_executable_in_sympy_override=False,
    description=(
        "Molar Gibbs energy G_m = G^{min}[D, T]: the global free-energy "
        "minimization pycalphad.equilibrium(dbf, comps, phases, conds) "
        "performs at fixed (N, P, T, X) over the assessed database D, "
        "returning the equilibrium GM per mole of atoms. G^{min} is an "
        "opaque solver over the assessed Gibbs functions (GHSER* lattice "
        "stabilities plus Redlich-Kister excess plus magnetic / Einstein "
        "terms) minimized over the sublattice site fractions; the method "
        "scheme records the minimization (Gibbs minimization at constant "
        "P, the v.N:1 per-mole-of-atoms basis). The AssessedDatabase input "
        "stands for the model plus its provenance; composition and pressure "
        "are opaque conditions of the solve. Implicit (a global minimization "
        "over an assessed model), so not sympy-executable."
    ),
)

compute_molar_enthalpy = Operator(
    name="compute_molar_enthalpy",
    inputs=(ASSESSED_DATABASE, TEMPERATURE_STATE),
    outputs=(MOLAR_ENTHALPY,),
    schemes={"method": "legendre_derivative"},
    formula=sp.Eq(_H_m, _H_eq(_D_tdb, _T)),
    is_executable_in_sympy_override=False,
    description=(
        "Molar enthalpy H_m = H^{eq}[D, T]: the assessed enthalpy channel of "
        "the equilibrium, pycalphad's HM = GM - T dGM/dT (the Legendre "
        "relation), per mole of atoms at constant pressure. H^{eq} is an "
        "opaque function over the assessed database D and temperature T "
        "(evaluated through the same Model that carries the Gibbs energy); "
        "the method scheme records the Legendre T-derivative construction. "
        "Implicit (a derivative of the assessed model at equilibrium), so "
        "not sympy-executable."
    ),
)

compute_chemical_potentials = Operator(
    name="compute_chemical_potentials",
    inputs=(MOLAR_GIBBS_ENERGY,),
    outputs=(CHEMICAL_POTENTIAL,),
    schemes={"method": "partial_molar_derivative"},
    formula=sp.Eq(_mu, _mu_eq(_G_m)),
    is_executable_in_sympy_override=False,
    description=(
        "Chemical potentials mu_c = mu^{eq}[G_m]: the partial molar Gibbs "
        "energies, pycalphad's MU, the common-tangent hyperplane of the "
        "minimization (one per non-vacancy component). mu^{eq} is the opaque "
        "composition-derivative of the molar Gibbs energy at equilibrium (the "
        "Lagrange multipliers of the mass-balance constraints); the "
        "composition is opaque context of the derivative, the CALPHAD analog "
        "of the hull's competing phases. The method scheme records the "
        "partial-molar (composition-derivative) construction. Implicit (a "
        "constrained derivative of the equilibrium free energy), so not "
        "sympy-executable."
    ),
)

compute_phase_fractions = Operator(
    name="compute_phase_fractions",
    inputs=(ASSESSED_DATABASE, TEMPERATURE_STATE),
    outputs=(PHASE_FRACTION,),
    schemes={"method": "lever_rule"},
    formula=sp.Eq(_NP, _f_eq(_D_tdb, _T)),
    is_executable_in_sympy_override=False,
    description=(
        "Phase fractions NP_p = f^{eq}[D, T]: the equilibrium molar amount "
        "of each stable phase, pycalphad's eq.NP paired with eq.Phase, the "
        "lever rule over the equilibrium assemblage of the assessed database "
        "D at temperature T. f^{eq} is the opaque per-phase molar-amount "
        "output of the same global minimization (the property-diagram "
        "skill's headline output, plotted vs T); the method scheme records "
        "the lever-rule assemblage split. Composition and pressure are "
        "opaque conditions. Implicit (a global minimization plus assemblage "
        "bookkeeping), so not sympy-executable."
    ),
)

compute_transition_temperature = Operator(
    name="compute_transition_temperature",
    inputs=(PHASE_FRACTION, TEMPERATURE_STATE),
    outputs=(TRANSITION_TEMPERATURE,),
    schemes={"method": "boundary_locus"},
    formula=sp.Eq(_T_trans, _T_trans_f(_NP, _T)),
    is_executable_in_sympy_override=False,
    description=(
        "Transition temperature T_trans = T^{trans}[NP, T]: the temperature "
        "at which a phase fraction crosses 0 or 1 (a liquidus / solidus / "
        "solvus point) or three phases coexist (an invariant point), read as "
        "the locus of the phase-fraction sweep over temperature. T^{trans} "
        "is the opaque boundary-locus function over the phase fractions NP "
        "and the temperature axis T (the binplot boundary set, drawn by "
        "sweeping equilibrium over the T-x grid); the method scheme records "
        "the boundary-locus extraction. Implicit (a swept-equilibrium "
        "boundary detection), so not sympy-executable."
    ),
)

compute_calphad_entropy = Operator(
    name="compute_calphad_entropy",
    inputs=(ASSESSED_DATABASE, TEMPERATURE_STATE),
    outputs=(CALPHAD_MOLAR_ENTROPY,),
    schemes={"method": "gibbs_temperature_derivative"},
    formula=sp.Eq(_S_m, _S_eq(_D_tdb, _T)),
    is_executable_in_sympy_override=False,
    description=(
        "Molar entropy S_m = S^{eq}[D, T]: the assessed entropy channel of "
        "the equilibrium, pycalphad's SM = -dGM/dT (the constant-P Gibbs "
        "temperature derivative), per mole of atoms at constant pressure, SER "
        "reference. S^{eq} is an opaque function over the assessed database D "
        "and temperature T (evaluated through the same Model that carries the "
        "Gibbs energy); the method scheme records the "
        "gibbs_temperature_derivative construction. The entropy factor of the "
        "executable Gibbs identity contract_gibbs_hts (G_m = H_m - T S_m). "
        "Implicit (a T-derivative of the assessed model at equilibrium), so "
        "not sympy-executable."
    ),
)

contract_gibbs_hts = Operator(
    name="contract_gibbs_hts",
    inputs=(MOLAR_ENTHALPY, TEMPERATURE_STATE, CALPHAD_MOLAR_ENTROPY),
    outputs=(MOLAR_GIBBS_ENERGY,),
    formula=sp.Eq(_G_m, _H_m - _T * _S_m),
    description=(
        "The executable Gibbs identity G_m = H_m - T S_m: the assessed molar "
        "Gibbs energy from the molar enthalpy, the temperature, and the "
        "constant-P assessed molar entropy, the exact thermodynamic definition "
        "of the Gibbs free energy the CALPHAD model itself carries "
        "(H_m = G_m + T S_m, so G_m = H_m - T S_m). SECOND PRODUCER (Pattern C) "
        "of MolarGibbsEnergy alongside solve_equilibrium (the direct global "
        "Gibbs minimization that returns GM): two routes to the SAME assessed "
        "G_m that MUST agree numerically (H_m and S_m are themselves GM's "
        "Legendre transform and T-derivative), the redundant-route pattern "
        "BulkModulus (three producers) and PhononDOS (two) already bless. The "
        "gate PROVES it: T S_m = (0,0,0,1,0,0,0) . (1,2,-2,-1,-1,0,0) = "
        "(1,2,-2,0,-1,0,0) = ENERGY_PER_MOLE, so H_m - T S_m is an Add of two "
        "equal ENERGY_PER_MOLE dimensions, matching G_m. All three "
        "energy-side quantities are on the SAME CALPHAD basis (per mole of "
        "atoms, constant P, SER), so the identity is basis-honest. Closed-form "
        "and sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    solve_equilibrium,
    compute_molar_enthalpy,
    compute_chemical_potentials,
    compute_phase_fractions,
    compute_transition_temperature,
    compute_calphad_entropy,
    contract_gibbs_hts,
)
