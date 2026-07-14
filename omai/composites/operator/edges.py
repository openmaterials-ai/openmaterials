r"""Operators (edges) of the composites (effective-medium) domain.

Five edges implementing the composite effective thermal conductivity of a
filled matrix with interfacial (Kapitza) resistance:

  depolarization_factors          : () -> DepolarizationFactor
  nan_effective_kappa             : (matrix, filler, interface, fraction,
                                     depolarization) -> effective[orientation=random]
  nan_effective_kappa_aligned     : (matrix, filler, interface, fraction,
                                     depolarization) -> effective[orientation=aligned]
  hasselman_johnson               : (matrix, filler, interface, fraction)
                                     -> effective[orientation=random]  (2nd producer)
  resolve_effective_conductivity  : (effective[orientation=random])
                                     -> ThermalConductivity (neutral observable)

Physics (Nan et al., J. Appl. Phys. 81, 6692 (1997)) with the interface as a
per-direction series film (Nan et al., Appl. Phys. Lett. 85, 3549 (2004) form):
the interface-corrected filler conductivity along axis i is
kc_ii = k_ii / (1 + 2 R k_ii / d_i) with R = 1/G the interface resistance and
d_i the full inclusion dimension. The Bruggeman-Nan beta terms are
beta_ii = (kc_ii - km) / (km + L_ii (kc_ii - km)); the randomly-oriented scalar
and the perfectly-aligned tensor are the two mixing formulas. At aspect ratio 1
(a sphere, isotropic filler) the Nan random result reduces EXACTLY to the
Hasselman-Johnson sphere formula (J. Compos. Mater. 21, 508 (1987)); the domain
test pins that equality to machine precision.

Executability and the dimensional gate. Four of the five edges are explicit
closed-form sympy Eqs written INLINE (kc_ii, beta_ii substituted), so the
dimensional gate PROVES them: every sub-ratio is dimensionless (the interface
term 2 (1/G) k_ii / d_i is dimensionless because 1/G is m^2 K / W, k_ii is
W/(m K), d_i is m; beta_ii is a ratio of two THERMAL_CONDUCTIVITY quantities),
so the effective kappa carries km's THERMAL_CONDUCTIVITY exactly. The
depolarization_factors edge is a sp.Piecewise closed form in the dimensionless
aspect ratio; the gate SKIPS it (Piecewise is not in the dimension recursion),
which is acceptable: the dimensional gate only needs the dimensionless SHAPE,
and the numeric branches are exercised by the domain test and served by the
representation adapter. resolve_effective_conductivity is the identity edge that
anchors the composite result onto the neutral ThermalConductivity observable
(the connectivity bridge to the pre-existing map, the resolve_thermal_conductivity
precedent).

Symbols (all bound in dimensions_registry so the gate proves the four closed
forms): k_m (THERMAL_CONDUCTIVITY, matrix), the filler tensor kappa_f[alpha,beta]
whose diagonal gives k_{11} = kappa_f[1,1] and k_{33} = kappa_f[3,3]
(THERMAL_CONDUCTIVITY), G_{int} (INTERFACE_CONDUCTANCE), d_1 / d_3 (LENGTH),
f_{vol} / L_{11} / L_{33} (DIMENSIONLESS), and the outputs kappa_c
(THERMAL_CONDUCTIVITY). The Hasselman-Johnson edge additionally uses a_{rad}
(LENGTH, the sphere radius) and reads the filler diagonal k_{33} (= k_{11} for
the isotropic sphere it models).
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.composites.operator.nodes import (
    DEPOLARIZATION_FACTOR,
    EFFECTIVE_CONDUCTIVITY_ALIGNED,
    EFFECTIVE_CONDUCTIVITY_RANDOM,
    FILLER_CONDUCTIVITY,
    FILLER_VOLUME_FRACTION,
    INTERFACE_CONDUCTANCE_NODE,
    MATRIX_CONDUCTIVITY,
)
from omai.thermal_transport.operator.nodes import THERMAL_CONDUCTIVITY


# ---------------------------------------------------------------------------
# Symbols. Every base name is bound in this domain's dimensions_registry (or is
# a pure-number constant), so the dimensional gate proves the four closed forms.
# ---------------------------------------------------------------------------

_km = sp.Symbol("k_m", positive=True)             # matrix kappa, THERMAL_CONDUCTIVITY
_kf = sp.IndexedBase("k_f")                        # filler kappa tensor, diagonal read below
_k11 = _kf[1, 1]                                    # transverse (in-plane) filler kappa
_k33 = _kf[3, 3]                                    # axial (through-plane) filler kappa
_G = sp.Symbol("G_{int}", positive=True)           # interface conductance, INTERFACE_CONDUCTANCE
_d1 = sp.Symbol("d_1", positive=True)              # equatorial dimension, LENGTH
_d3 = sp.Symbol("d_3", positive=True)              # polar dimension, LENGTH
_f = sp.Symbol("f_{vol}", nonnegative=True)        # filler volume fraction, DIMENSIONLESS
_L11 = sp.Symbol("L_{11}")                          # depolarization factor, DIMENSIONLESS
_L33 = sp.Symbol("L_{33}")                          # depolarization factor, DIMENSIONLESS
_kappa_c = sp.Symbol(r"\kappa_c", positive=True)   # composite effective kappa, THERMAL_CONDUCTIVITY
_p = sp.Symbol("p", positive=True)                 # aspect ratio d3/d1, DIMENSIONLESS
_a = sp.Symbol("a_{rad}", positive=True)           # sphere radius (HJ), LENGTH

# Interface resistance R = 1/G and the per-direction interface-corrected filler
# conductivity kc_ii = k_ii / (1 + 2 R k_ii / d_i). Written inline so the gate
# proves the effective-kappa closed forms.
_R = 1 / _G
_kc11 = _k11 / (1 + 2 * _R * _k11 / _d1)
_kc33 = _k33 / (1 + 2 * _R * _k33 / _d3)
_beta11 = (_kc11 - _km) / (_km + _L11 * (_kc11 - _km))
_beta33 = (_kc33 - _km) / (_km + _L33 * (_kc33 - _km))


# ---------------------------------------------------------------------------
# Depolarization factors (closed form; sp.Piecewise, gate-skipped by design).
# L33(p) has an atanh branch for prolate p>1, an atan branch for oblate p<1, and
# the sphere value 1/3 at p=1; L11 = (1 - L33)/2 (the sum rule 2 L11 + L33 = 1).
# ---------------------------------------------------------------------------

_e_prolate = sp.sqrt(1 - 1 / _p**2)
_e_oblate = sp.sqrt(1 / _p**2 - 1)
_L33_expr = sp.Piecewise(
    (sp.Rational(1, 3), sp.Eq(_p, 1)),
    (((1 - _e_prolate**2) / _e_prolate**3) * (sp.atanh(_e_prolate) - _e_prolate), _p > 1),
    (((1 + _e_oblate**2) / _e_oblate**3) * (_e_oblate - sp.atan(_e_oblate)), True),
)

depolarization_factors = Operator(
    name="depolarization_factors",
    inputs=(),
    outputs=(DEPOLARIZATION_FACTOR,),
    formula=sp.Eq(_L33, _L33_expr),
    auxiliary_formulas=(sp.Eq(_L11, (1 - _L33) / 2),),
    description=(
        "Spheroid depolarization (Eshelby) factors (L11, L33) of an "
        "axially-symmetric inclusion (polar axis 3) from the aspect ratio "
        "p = d3/d1: a closed form, L33(p) with an atanh branch for prolate p>1 "
        "(fiber), an atan branch for oblate p<1 (platelet), and the sphere value "
        "1/3 at p=1, with L11 = (1 - L33)/2 enforcing the sum rule 2 L11 + L33 = "
        "1. Analytic limits sphere (1/3, 1/3), long fiber (1/2, 0), thin disk "
        "(0, 1). The aspect ratio rides in the record conditions (this is a "
        "geometry-from-conditions producer, nullary at the store level, like the "
        "source provide_ edges). Formula is a sp.Piecewise: the dimensional gate "
        "SKIPS it (the output is dimensionless by construction and the gate only "
        "needs the shape), and the numeric branches are pinned by the domain test."
    ),
)


# ---------------------------------------------------------------------------
# Nan effective conductivity, randomly oriented filler (the scalar observable).
# kappa_c = km (3 + f (2 beta11 (1-L11) + beta33 (1-L33)))
#              / (3 - f (2 beta11 L11 + beta33 L33)),  written inline -> gate PROVES.
# ---------------------------------------------------------------------------

_nan_random_rhs = _km * (
    3 + _f * (2 * _beta11 * (1 - _L11) + _beta33 * (1 - _L33))
) / (
    3 - _f * (2 * _beta11 * _L11 + _beta33 * _L33)
)

nan_effective_kappa = Operator(
    name="nan_effective_kappa",
    inputs=(MATRIX_CONDUCTIVITY, FILLER_CONDUCTIVITY, INTERFACE_CONDUCTANCE_NODE,
            FILLER_VOLUME_FRACTION, DEPOLARIZATION_FACTOR),
    outputs=(EFFECTIVE_CONDUCTIVITY_RANDOM,),
    formula=sp.Eq(_kappa_c, _nan_random_rhs),
    auxiliary_formulas=(
        sp.Eq(sp.Symbol("kc_{11}"), _kc11),
        sp.Eq(sp.Symbol("kc_{33}"), _kc33),
        sp.Eq(sp.Symbol(r"\beta_{11}"), _beta11),
        sp.Eq(sp.Symbol(r"\beta_{33}"), _beta33),
    ),
    description=(
        "Nan-type effective-medium thermal conductivity for RANDOMLY oriented "
        "filler with a per-direction interfacial (Kapitza) series film "
        "(Nan et al., J. Appl. Phys. 81, 6692 (1997)): the isotropic scalar "
        "kappa_c = km (3 + f (2 beta11 (1-L11) + beta33 (1-L33))) / (3 - f (2 "
        "beta11 L11 + beta33 L33)), with the interface-corrected filler "
        "conductivities kc_ii = k_ii / (1 + 2 R k_ii / d_i) (R = 1/G) and the "
        "Bruggeman-Nan terms beta_ii = (kc_ii - km) / (km + L_ii (kc_ii - km)) "
        "substituted INLINE. The dimensional gate PROVES it: every sub-ratio is "
        "dimensionless (2 (1/G) k_ii / d_i = (m^2 K/W)(W/mK)/m = 1; beta_ii is a "
        "ratio of two W/(m K) quantities), so kappa_c carries km's "
        "THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0). Zero loading (f=0) returns km. "
        "Below the Kapitza radius a_K = km/G a conductive filler LOWERS kappa_c. "
        "The reference DGEBA epoxy + 5 vol% GNP (km=0.2, k11=1200, k33=6, d1=5um, "
        "d3=0.02um, G=25 MW/m2K, f=0.05) gives kappa_c = 1.2452 W/(m K)."
    ),
)


# ---------------------------------------------------------------------------
# Nan effective conductivity, perfectly aligned filler (anisotropic tensor).
# Declared closed form is the AXIAL (through-plane) component al33; the transverse
# al11 is its L11 / beta11 companion (documented, rides in conditions).
# al33 = km (1 + f beta33 (1-L33)) / (1 - f beta33 L33),  inline -> gate PROVES.
# ---------------------------------------------------------------------------

_nan_aligned33_rhs = _km * (1 + _f * _beta33 * (1 - _L33)) / (1 - _f * _beta33 * _L33)

nan_effective_kappa_aligned = Operator(
    name="nan_effective_kappa_aligned",
    inputs=(MATRIX_CONDUCTIVITY, FILLER_CONDUCTIVITY, INTERFACE_CONDUCTANCE_NODE,
            FILLER_VOLUME_FRACTION, DEPOLARIZATION_FACTOR),
    outputs=(EFFECTIVE_CONDUCTIVITY_ALIGNED,),
    formula=sp.Eq(_kappa_c, _nan_aligned33_rhs),
    auxiliary_formulas=(
        sp.Eq(sp.Symbol(r"\kappa_c^{al11}"),
              _km * (1 + _f * _beta11 * (1 - _L11)) / (1 - _f * _beta11 * _L11)),
    ),
    description=(
        "Nan-type effective conductivity for PERFECTLY ALIGNED filler "
        "(Nan et al. 1997), a different mixing formula from the random "
        "orientation: the anisotropic composite tensor whose AXIAL "
        "(through-plane, along the alignment axis 3) component is the declared "
        "closed form al33 = km (1 + f beta33 (1-L33)) / (1 - f beta33 L33), and "
        "whose TRANSVERSE (in-plane, transverse to axis 3) component is the "
        "L11/beta11 companion al11 = km (1 + f beta11 (1-L11)) / (1 - f beta11 "
        "L11) (the auxiliary formula; it rides in instance conditions, the "
        "elastic-constants precedent for tensor components). Same inline kc_ii / "
        "beta_ii substitution, so the gate PROVES al33 carries km's "
        "THERMAL_CONDUCTIVITY. Aligned platelets are the enhancement geometry a "
        "thermal-interface material targets."
    ),
)


# ---------------------------------------------------------------------------
# Hasselman-Johnson sphere cross-check (J. Compos. Mater. 21, 508 (1987)), a
# SECOND PRODUCER (Pattern C) of the random effective-kappa node. For an
# isotropic spherical filler (kp = k11 = k33, radius a) with interfacial
# resistance, alpha = a_K / a = (km/G)/a (dimensionless), and
# kappa_c = km [kp(1+2a) + 2km + 2f(kp(1-a)-km)] / [kp(1+2a) + 2km - f(kp(1-a)-km)].
# At aspect 1 the Nan random result reduces to this EXACTLY; the domain test pins
# the agreement to machine precision. Written inline -> the gate PROVES it.
# ---------------------------------------------------------------------------

_alpha_hj = (_km / _G) / _a
_hj_diff = _k33 * (1 - _alpha_hj) - _km
_hj_rhs = _km * (
    _k33 * (1 + 2 * _alpha_hj) + 2 * _km + 2 * _f * _hj_diff
) / (
    _k33 * (1 + 2 * _alpha_hj) + 2 * _km - _f * _hj_diff
)

hasselman_johnson = Operator(
    name="hasselman_johnson",
    inputs=(MATRIX_CONDUCTIVITY, FILLER_CONDUCTIVITY, INTERFACE_CONDUCTANCE_NODE,
            FILLER_VOLUME_FRACTION),
    outputs=(EFFECTIVE_CONDUCTIVITY_RANDOM,),
    formula=sp.Eq(_kappa_c, _hj_rhs),
    description=(
        "Hasselman-Johnson effective conductivity for spherical filler with "
        "interfacial (Kapitza) resistance (J. Compos. Mater. 21, 508 (1987)), an "
        "INDEPENDENT cross-check: for an isotropic sphere (kp = k11 = k33, radius "
        "a) with alpha = a_K / a = (km/G)/a the Kapitza-radius-to-radius ratio "
        "(dimensionless), kappa_c = km [kp(1+2 alpha) + 2 km + 2 f (kp(1-alpha) - "
        "km)] / [kp(1+2 alpha) + 2 km - f (kp(1-alpha) - km)]. Reads the filler "
        "diagonal k33 (= k11 for the isotropic sphere it models). SECOND PRODUCER "
        "(Pattern C) of the random effective-kappa node alongside "
        "nan_effective_kappa: at aspect ratio 1 (a sphere) the Nan random formula "
        "reduces to THIS one EXACTLY, so the two must agree numerically (the "
        "redundant-route pattern BulkModulus's three producers already bless); the "
        "domain test pins the agreement to machine precision. The dimensional gate "
        "PROVES it: alpha is dimensionless (km/G is a length, over the radius a), "
        "so kappa_c carries km's THERMAL_CONDUCTIVITY."
    ),
)


# ---------------------------------------------------------------------------
# Resolve onto the method-neutral observable. The composite effective
# conductivity IS a thermal conductivity: a measurement of the composite reports
# THIS observable, and the effective-medium route is its estimator. This edge
# anchors the random effective-kappa onto the neutral ThermalConductivity node
# (the resolve_thermal_conductivity precedent), which also connects this domain
# to the pre-existing map (connectivity: the neutral node is a pre-existing store
# node). Identity Eq, marked executable like resolve_thermal_conductivity.
# ---------------------------------------------------------------------------

_kappa_obs = sp.IndexedBase(r"\kappa")

resolve_effective_conductivity = Operator(
    name="resolve_effective_conductivity",
    inputs=(EFFECTIVE_CONDUCTIVITY_RANDOM,),
    outputs=(THERMAL_CONDUCTIVITY,),
    formula=sp.Eq(_kappa_obs[sp.Symbol("alpha"), sp.Symbol("beta")],
                  _kappa_obs[sp.Symbol("alpha"), sp.Symbol("beta")]),
    is_executable_in_sympy_override=True,
    description=(
        "Identity: the randomly-oriented composite effective conductivity is the "
        "physical thermal conductivity a measurement of the composite reports "
        "(isotropic, so its scalar sits on the diagonal of the neutral kappa "
        "tensor). This edge anchors the composite result onto the method-neutral "
        "ThermalConductivity observable, the home for measured and "
        "method-unspecified kappa: the Nan effective-medium route (and the "
        "Hasselman-Johnson second producer) are ESTIMATORS of this observable, "
        "related by the shared thermal_conductivity tag, exactly the "
        "resolve_thermal_conductivity precedent that anchors the lattice LBTE "
        "kappa. It also bridges this domain to the pre-existing map (the neutral "
        "node already exists in the store)."
    ),
)

EDGES: tuple[Operator, ...] = (
    depolarization_factors,
    nan_effective_kappa,
    nan_effective_kappa_aligned,
    hasselman_johnson,
    resolve_effective_conductivity,
)
