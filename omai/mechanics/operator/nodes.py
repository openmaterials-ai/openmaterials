"""Operator nodes of the mechanics domain.

The continuum mechanical response of a material under the elastic (small-strain)
approximation: the full rank-4 stiffness tensor, its two isotropic Voigt moduli,
and the mechanical pressure. All four are ObservableSpaces (gauge-invariant,
cross-code comparable after unit conversion), all carrying the energy-density
dimension ENERGY_PER_LENGTH_CUBED (the same M L^-1 T^-2 exponents as a pressure).

Node table:

  Node             quantity tag       dimension                indices
  ---------------  -----------------  -----------------------  --------------------------
  ElasticConstants elastic_constants  ENERGY_PER_LENGTH_CUBED  (alpha, beta, gamma, delta)
  BulkModulus      bulk_modulus       ENERGY_PER_LENGTH_CUBED  ()
  ShearModulus     shear_modulus      ENERGY_PER_LENGTH_CUBED  ()
  Pressure         pressure           ENERGY_PER_LENGTH_CUBED  ()

ElasticConstants is the FULL rank-4 Cartesian tensor C_{alpha,beta,gamma,delta}.
The Voigt 6x6 matrix C_ij that codes and papers print is a representation-layer
packing (the pair-index symmetrization alpha,beta -> i and gamma,delta -> j),
recorded on the LAMMPS / mat-elasticity specs, never on the node identity: the
node is the tensor, one object independent of how a code lays it out.

Deferred candidates (mat-elasticity produces them, but they are catalog-only for
now, no node): YoungsModulus and PoissonsRatio (further isotropic combinations of
K and G), plus the Reuss and Hill averages (they arrive as scheme overrides on
the contraction representations, not as new nodes).
"""
from __future__ import annotations

from omai.operator.dimensions import ENERGY_PER_LENGTH_CUBED
from omai.operator.space import Field, ObservableSpace, Space

ELASTIC_CONSTANTS = ObservableSpace(
    name="ElasticConstants",
    fields=(Field("C", ENERGY_PER_LENGTH_CUBED,
                  indices=("alpha", "beta", "gamma", "delta")),),
    tier="Mechanics",
    description=(
        "Rank-4 Cartesian elastic stiffness tensor C_{alpha,beta,gamma,delta} "
        "= d(sigma_{alpha,beta})/d(strain_{gamma,delta}), the second strain "
        "derivative of the energy density. Same physical dimension as a "
        "pressure (M L^-1 T^-2), typed ENERGY_PER_LENGTH_CUBED, conventionally "
        "quoted in GPa. The Voigt 6x6 matrix C_ij that LAMMPS and mat-* codes "
        "print is a representation-layer packing of this tensor (the "
        "symmetric pair indices alpha,beta and gamma,delta collapse to Voigt "
        "legs 1..6), not a different quantity."
    ),
)

BULK_MODULUS = ObservableSpace(
    name="BulkModulus",
    fields=(Field("K", ENERGY_PER_LENGTH_CUBED, indices=()),),
    tier="Mechanics",
    description=(
        "Isotropic bulk modulus K: the material's resistance to a uniform "
        "(hydrostatic) volume change, K = -V dP/dV. Contracted from the "
        "elastic tensor by the Voigt average K_V = C_{aabb}/9 (equivalently "
        "(C11 + C22 + C33 + 2(C12 + C13 + C23))/9 in Voigt notation). Scalar, "
        "in GPa; the Reuss and Hill averages are scheme variants of the same "
        "node."
    ),
)

SHEAR_MODULUS = ObservableSpace(
    name="ShearModulus",
    fields=(Field("G", ENERGY_PER_LENGTH_CUBED, indices=()),),
    tier="Mechanics",
    description=(
        "Isotropic shear modulus G: the material's resistance to a "
        "shape-changing (shear) deformation at fixed volume. Contracted from "
        "the elastic tensor by the Voigt average G_V = (3 C_{abab} - "
        "C_{aabb})/30 (equivalently ((C11 + C22 + C33) - (C12 + C13 + C23) + "
        "3(C44 + C55 + C66))/15 in Voigt notation). Scalar, in GPa; Reuss and "
        "Hill are scheme variants."
    ),
)

PRESSURE = ObservableSpace(
    name="Pressure",
    fields=(Field("P", ENERGY_PER_LENGTH_CUBED, indices=()),),
    tier="Mechanics",
    description=(
        "Mechanical pressure P = trace(sigma)/3, the isotropic (hydrostatic) "
        "part of the stress tensor. With the store's verified stress sign "
        "convention (positive diagonal = compressive, the pressure "
        "convention), P is positive under compression. Scalar, sharing the "
        "energy-density dimension of the stress it contracts."
    ),
)

NODES: tuple[Space, ...] = (
    ELASTIC_CONSTANTS,
    BULK_MODULUS,
    SHEAR_MODULUS,
    PRESSURE,
)
