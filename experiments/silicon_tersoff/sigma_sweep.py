"""Sweep Gaussian broadening sigma in both kaldo and phono3py.

Re-runs only the kappa stage of each code with FC2/FC3 cached from disk
where possible. Outputs runs/silicon_tersoff/comparison/sigma_sweep.csv
and prints a small table.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

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


SIGMAS_THZ = [0.05, 0.10, 0.20, 0.50, 1.00]
OUT = RUNS_DIR / "comparison"
OUT.mkdir(parents=True, exist_ok=True)


def kaldo_kappa_for_sigma(sigma: float) -> tuple[float, float]:
    """Compute kaldo (RTA, inverse) kappa for a given Gaussian sigma."""
    from kaldo.conductivity import Conductivity
    from kaldo.forceconstants import ForceConstants
    from kaldo.phonons import Phonons

    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()
    fc_folder = RUNS_DIR / "kaldo" / "fc"
    fc = ForceConstants(
        atoms=atoms,
        supercell=np.array(SUPERCELL_FC2),
        third_supercell=np.array(SUPERCELL_FC3),
        folder=str(fc_folder),
    )
    fc.second.calculate(calc, delta_shift=FD_DISPLACEMENT)
    fc.third.calculate(calc, delta_shift=FD_DISPLACEMENT)
    ph = Phonons(
        forceconstants=fc,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=sigma,
        broadening_shape="gauss",
        folder=str(RUNS_DIR / "kaldo" / "phonons" / f"sigma_{sigma}"),
        storage="memory",
    )
    rta = Conductivity(phonons=ph, method="rta", n_iterations=0).conductivity.sum(axis=0)
    inv = Conductivity(phonons=ph, method="inverse").conductivity.sum(axis=0)
    return float(np.mean(np.diag(rta))), float(np.mean(np.diag(inv)))


def phono3py_kappa_for_sigma(sigma: float, ph3) -> tuple[float, float]:
    """Compute phono3py (RTA, LBTE) kappa for a given Gaussian sigma. ph3 reuses cached FCs."""
    ph3.sigmas = [sigma]
    ph3.run_thermal_conductivity(
        is_LBTE=False,
        temperatures=[TEMPERATURE],
        is_isotope=False,
        write_kappa=False,
    )
    rta = np.asarray(ph3.thermal_conductivity.kappa).reshape(-1)[:6]
    rta_diag = float(np.mean(rta[:3]))
    ph3.run_thermal_conductivity(
        is_LBTE=True,
        temperatures=[TEMPERATURE],
        is_isotope=False,
        write_kappa=False,
    )
    lbte = np.asarray(ph3.thermal_conductivity.kappa).reshape(-1)[:6]
    lbte_diag = float(np.mean(lbte[:3]))
    return rta_diag, lbte_diag


def main() -> None:
    # Build phono3py once (FCs once), then loop sigmas
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

    rows = []
    print()
    print(f"{'sigma (THz)':>12s}  {'kaldo RTA':>10s}  {'phono3py RTA':>13s}  {'ratio':>6s}  "
          f"{'kaldo inv':>10s}  {'phono3py LBTE':>13s}  {'ratio':>6s}")
    print("-" * 90)
    for sigma in SIGMAS_THZ:
        ph3.init_phph_interaction()
        t0 = time.time()
        k_rta, k_inv = kaldo_kappa_for_sigma(sigma)
        p_rta, p_lbte = phono3py_kappa_for_sigma(sigma, ph3)
        dt = time.time() - t0
        print(
            f"{sigma:12.4f}  {k_rta:10.3f}  {p_rta:13.3f}  {k_rta / p_rta:6.3f}  "
            f"{k_inv:10.3f}  {p_lbte:13.3f}  {k_inv / p_lbte:6.3f}"
        )
        rows.append({
            "sigma_THz": sigma,
            "kaldo_rta": k_rta, "phono3py_rta": p_rta, "ratio_rta": k_rta / p_rta,
            "kaldo_inv": k_inv, "phono3py_lbte": p_lbte, "ratio_dir": k_inv / p_lbte,
            "wallclock_s": dt,
        })

    csv_path = OUT / "sigma_sweep.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
