#!/usr/bin/env python
"""
Check B (FD-vs-DFPT route): compute phonopy finite-displacement phonon
frequencies at Gamma, X, L from FORCE_SETS, on the SAME primitive cell and
SAME DFT numerics QE used, and print them in cm^-1 for comparison against
QE matdyn interpolated frequencies.

Convention care (from scans/qe-phonon.md):
  * QE matdyn.freq is LINEAR wavenumber cm^-1 (RY_TO_CMM1 route), negative =
    imaginary. phonopy default output is LINEAR THz. Both linear, so a pure
    unit conversion 1 THz = 33.356410 cm^-1 puts them on one axis.
  * QE matdyn q-points are CARTESIAN in 2pi/a units: Gamma(0,0,0), X(1,0,0),
    L(0.5,0.5,0.5). phonopy q-points are in reciprocal CRYSTAL (fractional)
    coords of the primitive cell -> same physical point, different numbers.
    We map QE-cartesian -> phonopy-fractional exactly:
        f_i = a_i(bohr) . k / (2 pi),  k = (2pi/alat) * q_cart
        =>  f = (A_bohr / alat) @ q_cart = A_alat @ q_cart
    where A_alat rows are the primitive vectors in alat units.
  * Masses: phonopy uses amu internally (Si 28.0855). QE text flfrc stored
    the mass in Ry a.u. (28.0855*911.4442) but matdyn divides it back to amu
    on read, so both codes diagonalize with the SAME physical amu mass. We do
    NOT touch masses here; phonopy takes amu from the structure.
"""
import numpy as np
from phonopy import Phonopy
from phonopy.interface.calculator import read_crystal_structure
from phonopy.file_IO import parse_FORCE_SETS

THZ_TO_CM = 1.0e12 / 29979245800.0  # 33.3564095198...
ALAT_BOHR = 10.2625
BOHR = 0.529177210903

# QE matdyn cartesian q in 2pi/alat units
QE_CART = {
    "Gamma": np.array([0.0, 0.0, 0.0]),
    "X":     np.array([1.0, 0.0, 0.0]),
    "L":     np.array([0.5, 0.5, 0.5]),
}

unitcell, _ = read_crystal_structure("si.ph0.in", interface_mode="qe")
ph = Phonopy(unitcell, supercell_matrix=np.diag([2, 2, 2]),
             primitive_matrix="auto")
ph.dataset = parse_FORCE_SETS()
ph.produce_force_constants()

# Primitive vectors phonopy actually uses (Angstrom) -> alat units
prim_ang = ph.primitive.cell           # rows a_i in Angstrom
prim_alat = (prim_ang / BOHR) / ALAT_BOHR

print("# phonopy primitive vectors (alat units), rows a_i:")
for v in prim_alat:
    print("#   ", np.round(v, 6))

for name, qcart in QE_CART.items():
    f = prim_alat @ qcart              # QE-cart 2pi/alat -> phonopy crystal frac
    ph.run_qpoints([f])
    thz = np.array(ph.get_qpoints_dict()["frequencies"][0])
    cm = np.sort(thz) * THZ_TO_CM
    print(f"{name}: qfrac={np.round(f,5).tolist()}  freq_cm={[round(x,4) for x in cm]}")
