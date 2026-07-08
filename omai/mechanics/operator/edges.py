r"""Operators (edges) of the mechanics domain.

Four edges. The producing edge is the finite-strain elastic-tensor calculation;
the other three are closed-form contractions of the tensor (and of the stress)
into isotropic scalars:

  compute_elastic_constants : (Stress, Structure) -> ElasticConstants
  contract_pressure         : (Stress,)           -> Pressure
  contract_bulk_modulus     : (ElasticConstants,) -> BulkModulus
  contract_shear_modulus    : (ElasticConstants,) -> ShearModulus

Symbols. The stress IndexedBase \sigma and the strain \varepsilon^{str} are the
SAME base names the dft ground-state domain registered (reused so the elastic
tensor differentiates the same stress against the same strain the store already
carries, and the pressure contracts the same stress). The mechanics fields C, K,
G, P are new bare names; none of them collides with an existing global symbol
(verified: no other edge formula references C / K / G / P), and each is bound to
ENERGY_PER_LENGTH_CUBED in the domain's dimensions registry so the dimensional
gate proves all four edges.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.mechanics.operator.nodes import (
    BULK_MODULUS,
    ELASTIC_CONSTANTS,
    PRESSURE,
    SHEAR_MODULUS,
)
from omai.dft_ground_state.operator.nodes import STRESS, STRUCTURE


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

_C = sp.IndexedBase("C")
_K = sp.Symbol("K")
_G = sp.Symbol("G")
_P = sp.Symbol("P")
_sigma = sp.IndexedBase(r"\sigma")     # reused: the dft ground-state cell stress
_eps_str = sp.IndexedBase(r"\varepsilon^{str}")  # reused: the dft homogeneous strain
_a, _b, _g, _d = sp.symbols(r"\alpha \beta \gamma \delta", integer=True)


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

# Sign derivation (why the formula is MINUS d(sigma)/d(strain)):
#   The store's Stress is the pressure convention, verified from the QE source
#   at record 105's edge: sigma_store = -(1/V) dE/d(eps), positive diagonal =
#   compressive. The textbook elastic tensor is defined against the
#   TENSION-positive Cauchy stress sigma_tension = +(1/V) dE/d(eps) =
#   -sigma_store, so
#       C = d(sigma_tension)/d(eps) = -d(sigma_store)/d(eps)
#         = +(1/V) d^2 E / d(eps)^2,
#   and the minus restores positive C11 for stable crystals (a bare
#   +d(sigma_store)/d(eps) would flip the sign of every stiffness). LAMMPS's
#   ELASTIC workflow carries exactly this minus in its own script
#   (in.elastic:75, d_i = -(p_i1 - p_i0)/strain), since its pressure tensor
#   has the same positive-compression sign as the store's sigma.
compute_elastic_constants = Operator(
    name="compute_elastic_constants",
    inputs=(STRESS, STRUCTURE),
    outputs=(ELASTIC_CONSTANTS,),
    schemes={"strain_method": "finite_strain"},
    formula=sp.Eq(
        _C[_a, _b, _g, _d],
        -sp.Derivative(_sigma[_a, _b], _eps_str[_g, _d]),
    ),
    is_executable_in_sympy_override=False,
    description=(
        "Elastic stiffness tensor C_{alpha,beta,gamma,delta} = "
        "-d(sigma_{alpha,beta})/d(strain)_{gamma,delta}: the stress-strain "
        "definition the LAMMPS ELASTIC workflow and mat-elasticity actually "
        "compute (stress differences under imposed strains of the structure; "
        "LAMMPS ELASTIC's own script uses -delta(pressure tensor)/"
        "delta(strain), consistent with this minus). The minus is the sign "
        "correction for the store's stress convention: sigma here is "
        "pressure-convention (positive diagonal = compressive, the negative "
        "of the tension-positive Cauchy stress), so C = d(sigma_tension)/"
        "d(strain) = -d(sigma)/d(strain) = +(1/V_cell) d^2 E_tot/d(strain)^2, "
        "keeping C11 positive for stable crystals (see the sign derivation "
        "comment above). The energy second-derivative route (from "
        "TotalEnergy) is a natural future Pattern C alternative producer of "
        "this node. Implicit (a finite-difference fit), so not "
        "sympy-executable; dimensionally stress / dimensionless strain = "
        "ENERGY_PER_LENGTH_CUBED, which the gate proves."
    ),
)

contract_pressure = Operator(
    name="contract_pressure",
    inputs=(STRESS,),
    outputs=(PRESSURE,),
    formula=sp.Eq(_P, sp.Sum(_sigma[_a, _a], (_a, 1, 3)) / 3),
    description=(
        "Mechanical pressure P = trace(sigma)/3 = (1/3) sum_a sigma_{a,a}. "
        "With the store's verified stress sign convention (positive diagonal "
        "= compressive, the pressure convention established from the QE source "
        "at the Stress node's edge, record 105), the trace is already the "
        "compressive pressure, so P = +trace/3 is the mechanical pressure "
        "(NOT -trace/3: that minus would apply to the tension-positive "
        "continuum-mechanics Cauchy convention, which is not the one the store "
        "records). Closed-form contraction of the stress; both sides carry the "
        "energy-density dimension."
    ),
)

contract_bulk_modulus = Operator(
    name="contract_bulk_modulus",
    inputs=(ELASTIC_CONSTANTS,),
    outputs=(BULK_MODULUS,),
    schemes={"average": "voigt"},
    formula=sp.Eq(
        _K,
        sp.Sum(_C[_a, _a, _b, _b], (_a, 1, 3), (_b, 1, 3)) / 9,
    ),
    description=(
        "Voigt bulk modulus K_V = (1/9) sum_{a,b} C_{a,a,b,b} (equivalently "
        "(C11 + C22 + C33 + 2(C12 + C13 + C23))/9 in Voigt 6x6 notation). The "
        "Voigt average assumes uniform strain; the Reuss (uniform stress) and "
        "Hill (their mean) averages arrive later as scheme overrides on the "
        "representations, not as separate edges. Closed-form; energy density "
        "in, energy density out."
    ),
)

# Voigt shear derivation (why the formula is (3*S2 - S1)/30):
#   Let A  = sum_a C_{a,a,a,a}   (the Voigt C11 + C22 + C33 diagonal),
#       S1 = sum_{a,b} C_{a,a,b,b}  (= A + 2(C12 + C13 + C23)),
#       S2 = sum_{a,b} C_{a,b,a,b}  (= A + 2(C44 + C55 + C66)).
#   The textbook Voigt shear is G_V = (A - B + 3*Cc)/15 with the Voigt
#   auxiliaries B = (S1 - A)/2 and Cc = (S2 - A)/2. Substituting,
#       A - B + 3*Cc = A - (S1 - A)/2 + 3*(S2 - A)/2
#                    = A(1 + 1/2 - 3/2) - S1/2 + 3*S2/2
#                    = (3*S2 - S1)/2   (the A terms cancel exactly),
#   so G_V = (3*S2 - S1)/2 / 15 = (3*S2 - S1)/30. The formula below is that
#   reduced form: 3*Sum(C_{a,b,a,b}) is 3*S2, Sum(C_{a,a,b,b}) is S1.
contract_shear_modulus = Operator(
    name="contract_shear_modulus",
    inputs=(ELASTIC_CONSTANTS,),
    outputs=(SHEAR_MODULUS,),
    schemes={"average": "voigt"},
    formula=sp.Eq(
        _G,
        (3 * sp.Sum(_C[_a, _b, _a, _b], (_a, 1, 3), (_b, 1, 3))
         - sp.Sum(_C[_a, _a, _b, _b], (_a, 1, 3), (_b, 1, 3))) / 30,
    ),
    description=(
        "Voigt shear modulus G_V = (3 sum_{a,b} C_{a,b,a,b} - sum_{a,b} "
        "C_{a,a,b,b})/30 (equivalently ((C11 + C22 + C33) - (C12 + C13 + "
        "C23) + 3(C44 + C55 + C66))/15 in Voigt 6x6 notation). The reduced "
        "(3*S2 - S1)/30 form is the textbook G_V = (A - B + 3C)/15 after the "
        "sum-of-diagonals A = sum_a C_{aaaa} terms cancel (see the module "
        "comment for the derivation). Voigt average; Reuss / Hill are later "
        "scheme variants. Closed-form; energy density in and out."
    ),
)

EDGES: tuple[Operator, ...] = (
    compute_elastic_constants,
    contract_pressure,
    contract_bulk_modulus,
    contract_shear_modulus,
)
