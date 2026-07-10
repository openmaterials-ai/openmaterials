"""Operator nodes of the mechanics domain.

The continuum mechanical response of a material under the elastic (small-strain)
approximation: the full rank-4 stiffness tensor, its isotropic moduli, the
Poisson ratio, and the mechanical pressure. All six are ObservableSpaces
(gauge-invariant, cross-code comparable after unit conversion); every field but
the Poisson ratio carries the energy-density dimension ENERGY_PER_LENGTH_CUBED
(the same M L^-1 T^-2 exponents as a pressure), the Poisson ratio is
DIMENSIONLESS (all-zero exponents).

Node table:

  Node             quantity tag       dimension                indices
  ---------------  -----------------  -----------------------  --------------------------
  ElasticConstants elastic_constants  ENERGY_PER_LENGTH_CUBED  (alpha, beta, gamma, delta)
  BulkModulus      bulk_modulus       ENERGY_PER_LENGTH_CUBED  ()
  ShearModulus     shear_modulus      ENERGY_PER_LENGTH_CUBED  ()
  Pressure         pressure           ENERGY_PER_LENGTH_CUBED  ()
  YoungsModulus    youngs_modulus     ENERGY_PER_LENGTH_CUBED  ()
  PoissonRatio     poisson_ratio      DIMENSIONLESS            ()
  MassDensity      mass_density       MASS_DENSITY             ()

ElasticConstants is the FULL rank-4 Cartesian tensor C_{alpha,beta,gamma,delta}.
The Voigt 6x6 matrix C_ij that codes and papers print is a representation-layer
packing (the pair-index symmetrization alpha,beta -> i and gamma,delta -> j),
recorded on the LAMMPS / mat-elasticity specs, never on the node identity: the
node is the tensor, one object independent of how a code lays it out.

YoungsModulus and PoissonRatio (added 2026-07-09 from the pymatgen scan) are the
two remaining isotropic combinations of K and G, produced by the executable
contract edges E_Y = 9KG/(3K+G) and nu = (3K-2G)/(2(3K+G)). Deferred
candidates: the Reuss and Hill averages (they arrive as scheme overrides on the
contraction representations, not as new nodes).

MassDensity (added 2026-07-10 from the phonopy/LAMMPS delta scan) is the mass
density rho = total cell mass / cell volume, the LAMMPS metal-unit MD thermo
'density' column the mat-lammps-md skill tracks (glass densification on a quench).
A minor scalar readout, carrying the fresh MASS_DENSITY dimension (M L^-3); it is
a derived contraction of the Structure (contract_density), NOT the phonon
density of states. It sits in the Mechanics tier as a bulk-material property
alongside the moduli and pressure.
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    MASS_DENSITY,
)
from omai.operator.space import Field, ObservableSpace, Space

ELASTIC_CONSTANTS = ObservableSpace(
    name="ElasticConstants",
    fields=(Field("C", ENERGY_PER_LENGTH_CUBED,
                  indices=("alpha", "beta", "gamma", "delta")),),
    tier="Mechanics",
    description=(
        "Rank-4 Cartesian elastic stiffness tensor C_{alpha,beta,gamma,delta} "
        "= +(1/V_cell) d^2 E/d(strain)^2, the second strain derivative of the "
        "energy density; against the store's pressure-convention stress "
        "(positive = compressive) this is C = -d(sigma_{alpha,beta})/"
        "d(strain_{gamma,delta}), the minus keeping C11 positive for stable "
        "crystals. Same physical dimension as a pressure (M L^-1 T^-2), typed "
        "ENERGY_PER_LENGTH_CUBED, conventionally quoted in GPa. The Voigt 6x6 "
        "matrix C_ij that LAMMPS and mat-* codes print is a "
        "representation-layer packing of this tensor (the symmetric pair "
        "indices alpha,beta and gamma,delta collapse to Voigt legs 1..6), not "
        "a different quantity."
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

YOUNGS_MODULUS = ObservableSpace(
    name="YoungsModulus",
    fields=(Field("E_Y", ENERGY_PER_LENGTH_CUBED, indices=()),),
    tier="Mechanics",
    description=(
        "Isotropic Young's modulus E_Y: the material's uniaxial stiffness, "
        "the stress-to-strain ratio of a bar pulled along one axis with free "
        "lateral faces. Fully determined by the bulk and shear moduli through "
        "the isotropic identity E_Y = 9KG/(3K + G), an executable contraction "
        "(not a new measurement). Scalar, energy-density dimension, "
        "conventionally quoted in GPa; note pymatgen's ElasticTensor.y_mod "
        "emits SI Pa (a 1e9 trap recorded on the representation)."
    ),
)

POISSON_RATIO = ObservableSpace(
    name="PoissonRatio",
    fields=(Field("nu", DIMENSIONLESS, indices=()),),
    tier="Mechanics",
    description=(
        "Isotropic Poisson ratio nu: the negative transverse-to-axial strain "
        "ratio under uniaxial stress. Fully determined by the bulk and shear "
        "moduli through the isotropic identity nu = (3K - 2G)/(2(3K + G)), an "
        "executable contraction. Dimensionless scalar (all-zero exponents), "
        "bounded (-1, 1/2) for stable isotropic media; about 0.34 for Cu."
    ),
)

MASS_DENSITY_STATE = ObservableSpace(
    name="MassDensity",
    fields=(Field("rho", MASS_DENSITY, indices=()),),
    tier="Mechanics",
    description=(
        "Mass density rho = total cell mass / cell volume, the LAMMPS metal-unit "
        "MD thermo 'density' column (mat-lammps-md tracks it across a melt / "
        "quench / hold to read glass densification, and across the Cu phase "
        "transition). Dimension MASS_DENSITY (1,-3,0,0,0,0,0) = M L^-3, served in "
        "g/cm^3 (the metal serving unit; the SI kg/m^3 = 1e-3 g/cm^3). A derived "
        "contraction of the Structure (contract_density: total mass over cell "
        "volume), NOT a phonon density of states and NOT a first-principles "
        "response: a scalar readout of quantities the Structure already carries, "
        "admitted because the skills track it as a first-class MD output. Scalar, "
        "in the Mechanics tier."
    ),
)

NODES: tuple[Space, ...] = (
    ELASTIC_CONSTANTS,
    BULK_MODULUS,
    SHEAR_MODULUS,
    PRESSURE,
    YOUNGS_MODULUS,
    POISSON_RATIO,
    MASS_DENSITY_STATE,
)
