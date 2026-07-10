"""The mechanics domain: the elastic tensor, its isotropic scalars, and the pressure.

The continuum mechanical response of a material: the full rank-4 elastic
stiffness tensor, its isotropic moduli (bulk, shear, Young's), the Poisson
ratio, and the mechanical pressure. The elastic tensor is grounded by the
LAMMPS ELASTIC finite-strain workflow and the mat-elasticity AtomisticSkills
skill; pymatgen's ElasticTensor grounds the whole family (eV/A^3 native, GPa
after the 160.2176634 factor). The first four nodes entered the map through
the protocol gates as records 110-117; YoungsModulus and PoissonRatio landed
2026-07-09 from the pymatgen scan as executable contractions of K and G.
"""
