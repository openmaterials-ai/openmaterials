"""Test the kaldo/phono3py Gaussian-normalization hypothesis.

  phono3py: g(x, sigma) = 1/(sigma * sqrt(2*pi)) * exp(-x^2 / (2*sigma^2))
            -- standard deviation = sigma_p
  kaldo:    g(x, sigma) = 1/(sigma * sqrt(pi))   * exp(-x^2 / sigma^2)
            -- standard deviation = sigma_k / sqrt(2)

For matched effective broadening, set kaldo's nominal sigma to phono3py's
sigma * sqrt(2). Then the standard deviations are equal and the
underlying scattering kernels should give matching kappa.

This script computes kappa for matched stdev across several values and
reports the cross-code ratio. Hypothesis: ratios should be very close
to 1.0, with any residual being downstream physics (e.g., scattering-
matrix normalization, BZ integration weights).
"""

from __future__ import annotations

import csv
import math
import time

import numpy as np

from seed import (
    FD_DISPLACEMENT,
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    TEMPERATURE,
    build_silicon_primitive,
    make_tersoff_calculator,
)


# Effective standard deviations (in THz) to compare at.
# At each, kaldo gets sigma_k = stdev * sqrt(2) and phono3py gets sigma_p = stdev.
EFF_STDEVS_THZ = [0.05, 0.10, 0.15, 0.20]


def kaldo_kappa(sigma_kaldo: float) -> tuple[float, float]:
    from kaldo.conductivity import Conductivity
    from kaldo.forceconstants import ForceConstants
    from kaldo.phonons import Phonons

    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()
    fc = ForceConstants(
        atoms=atoms,
        supercell=np.array(SUPERCELL_FC2),
        third_supercell=np.array(SUPERCELL_FC3),
        folder=str(RUNS_DIR / "kaldo" / "fc"),
    )
    fc.second.calculate(calc, delta_shift=FD_DISPLACEMENT)
    fc.third.calculate(calc, delta_shift=FD_DISPLACEMENT)
    ph = Phonons(
        forceconstants=fc,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=sigma_kaldo,
        broadening_shape="gauss",
        folder=str(RUNS_DIR / "kaldo" / "phonons" / f"normtest_{sigma_kaldo}"),
        storage="memory",
    )
    rta = Conductivity(phonons=ph, method="rta", n_iterations=0).conductivity.sum(axis=0)
    inv = Conductivity(phonons=ph, method="inverse").conductivity.sum(axis=0)
    return float(np.mean(np.diag(rta))), float(np.mean(np.diag(inv)))


def setup_phono3py():
    from phono3py import Phono3py
    from phonopy.structure.atoms import PhonopyAtoms
    from ase import Atoms

    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()
    unitcell = PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )
    ph3 = Phono3py(
        unitcell,
        supercell_matrix=np.diag(SUPERCELL_FC3),
        phonon_supercell_matrix=np.diag(SUPERCELL_FC2),
    )
    ph3.generate_fc2_displacements(distance=FD_DISPLACEMENT)
    fc2_forces = []
    for sc in ph3.phonon_supercells_with_displacements:
        a = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
        a.calc = calc
        fc2_forces.append(a.get_forces())
    ph3.phonon_forces = np.array(fc2_forces)
    ph3.generate_displacements(distance=FD_DISPLACEMENT)
    fc3_forces = []
    for sc in ph3.supercells_with_displacements:
        if sc is None:
            continue
        a = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
        a.calc = calc
        fc3_forces.append(a.get_forces())
    ph3.forces = np.array(fc3_forces)
    ph3.produce_fc2()
    ph3.produce_fc3()
    ph3.mesh_numbers = list(KMESH)
    return ph3


def phono3py_kappa(sigma_phono3py: float, ph3) -> tuple[float, float]:
    ph3.sigmas = [sigma_phono3py]
    ph3.init_phph_interaction()
    ph3.run_thermal_conductivity(is_LBTE=False, temperatures=[TEMPERATURE], is_isotope=False, write_kappa=False)
    rta = np.asarray(ph3.thermal_conductivity.kappa).reshape(-1)[:6]
    rta_d = float(np.mean(rta[:3]))
    ph3.run_thermal_conductivity(is_LBTE=True, temperatures=[TEMPERATURE], is_isotope=False, write_kappa=False)
    lbte = np.asarray(ph3.thermal_conductivity.kappa).reshape(-1)[:6]
    lbte_d = float(np.mean(lbte[:3]))
    return rta_d, lbte_d


def main() -> None:
    ph3 = setup_phono3py()
    rows = []
    print()
    print(
        f"{'stdev (THz)':>12s}  {'kaldo σk=√2·s':>15s}  {'phono3py σp=s':>15s}  "
        f"{'kaldo RTA':>10s}  {'ph3 RTA':>10s}  {'ratio':>7s}  "
        f"{'kaldo inv':>10s}  {'ph3 LBTE':>10s}  {'ratio':>7s}"
    )
    print("-" * 110)
    for stdev in EFF_STDEVS_THZ:
        sigma_k = stdev * math.sqrt(2)
        sigma_p = stdev
        k_rta, k_inv = kaldo_kappa(sigma_k)
        p_rta, p_lbte = phono3py_kappa(sigma_p, ph3)
        print(
            f"{stdev:12.4f}  {sigma_k:15.4f}  {sigma_p:15.4f}  "
            f"{k_rta:10.3f}  {p_rta:10.3f}  {k_rta / p_rta:7.4f}  "
            f"{k_inv:10.3f}  {p_lbte:10.3f}  {k_inv / p_lbte:7.4f}"
        )
        rows.append({
            "effective_stdev_THz": stdev,
            "kaldo_sigma_THz": sigma_k,
            "phono3py_sigma_THz": sigma_p,
            "kaldo_rta": k_rta, "phono3py_rta": p_rta, "ratio_rta": k_rta / p_rta,
            "kaldo_inv": k_inv, "phono3py_lbte": p_lbte, "ratio_dir": k_inv / p_lbte,
        })

    csv_path = RUNS_DIR / "comparison" / "sigma_normalization_test.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
