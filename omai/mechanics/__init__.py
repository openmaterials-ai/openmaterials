"""The mechanics domain: ElasticConstants, BulkModulus, ShearModulus, Pressure.

The continuum mechanical response of a material: the full rank-4 elastic
stiffness tensor, its isotropic Voigt moduli, and the mechanical pressure. The
elastic tensor is grounded by the LAMMPS ELASTIC finite-strain workflow and the
mat-elasticity AtomisticSkills skill; it enters the map through the protocol
gates as the next structural contribution after the DFT ground state.
"""
