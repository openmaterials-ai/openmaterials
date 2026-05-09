"""phono3py path for the silicon-Tersoff experiment.

Steps:
  1. Build the silicon Atoms and the LAMMPS-Tersoff calculator (from seed.py).
  2. Phono3py generates FC2 and FC3 displaced supercells.
  3. Loop: ASE calculator computes forces on each.
  4. Phono3py builds FC2 and FC3.
  5. Run thermal_conductivity at the chosen mesh, RTA.

Outputs land in runs/silicon_tersoff/phono3py/.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from phono3py import Phono3py
from phonopy.structure.atoms import PhonopyAtoms

from seed import (
    BROADENING_SIGMA_THZ,
    FD_DISPLACEMENT,
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    TEMPERATURE,
    build_silicon_primitive,
    make_tersoff_calculator,
)


OUT = RUNS_DIR / "phono3py"
OUT.mkdir(parents=True, exist_ok=True)


def ase_to_phonopy(atoms) -> PhonopyAtoms:
    return PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )


def phonopy_to_ase(supercell: PhonopyAtoms):
    from ase import Atoms
    return Atoms(
        symbols=supercell.symbols,
        cell=supercell.cell,
        scaled_positions=supercell.scaled_positions,
        pbc=True,
    )


def compute_forces(supercells, calc) -> np.ndarray:
    """Return (n_supercells, n_atoms, 3) forces."""
    out = []
    for i, sc in enumerate(supercells):
        if sc is None:
            # Phono3py marks duplicates this way; skip
            out.append(None)
            continue
        ase_sc = phonopy_to_ase(sc)
        ase_sc.calc = calc
        f = ase_sc.get_forces()
        out.append(f)
        if (i + 1) % 25 == 0 or i == 0:
            print(
                f"          force {i+1}/{len(supercells)}: "
                f"max |F| = {np.abs(f).max():.4f} eV/A"
            )
    return out


def main() -> None:
    t0 = time.time()
    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()

    print(
        f"[phono3py] supercell FC2 {SUPERCELL_FC2}, FC3 {SUPERCELL_FC3}, "
        f"kmesh {KMESH}, FD delta {FD_DISPLACEMENT} A"
    )

    unitcell = ase_to_phonopy(atoms)
    fc3_super = np.diag(SUPERCELL_FC3)
    fc2_super = np.diag(SUPERCELL_FC2)
    ph3 = Phono3py(
        unitcell,
        supercell_matrix=fc3_super,            # used for FC3 displacements
        phonon_supercell_matrix=fc2_super,     # used for FC2 displacements
    )

    # ----- FC2 displacements + forces -----
    ph3.generate_fc2_displacements(distance=FD_DISPLACEMENT)
    fc2_supercells = ph3.phonon_supercells_with_displacements
    print(f"[phono3py] FC2 displacements: {len(fc2_supercells)}")
    print("[phono3py] computing FC2 forces ...")
    t1 = time.time()
    fc2_forces = compute_forces(fc2_supercells, calc)
    ph3.phonon_forces = np.array(fc2_forces)
    print(f"[phono3py]   FC2 forces done in {time.time() - t1:.1f} s")

    # ----- FC3 displacements + forces -----
    ph3.generate_displacements(distance=FD_DISPLACEMENT)
    fc3_supercells = ph3.supercells_with_displacements
    print(f"[phono3py] FC3 displacements: {len(fc3_supercells)}")
    print("[phono3py] computing FC3 forces ...")
    t2 = time.time()
    fc3_forces_list = compute_forces(fc3_supercells, calc)
    fc3_forces = np.array([f for f in fc3_forces_list if f is not None])
    # phono3py expects forces as ndarray indexed by displacement index
    ph3.forces = fc3_forces
    print(f"[phono3py]   FC3 forces done in {time.time() - t2:.1f} s")

    # ----- Build FC2 and FC3 -----
    print("[phono3py] producing FC2 ...")
    t3 = time.time()
    ph3.produce_fc2()
    print(f"[phono3py]   FC2 done in {time.time() - t3:.1f} s")

    print("[phono3py] producing FC3 ...")
    t4 = time.time()
    ph3.produce_fc3()
    print(f"[phono3py]   FC3 done in {time.time() - t4:.1f} s")

    np.save(OUT / "fc2.npy", np.asarray(ph3.fc2))
    np.save(OUT / "fc3.npy", np.asarray(ph3.fc3))

    # ----- Thermal conductivity (RTA) -----
    print("[phono3py] running thermal conductivity (RTA) ...")
    t5 = time.time()
    ph3.mesh_numbers = list(KMESH)
    ph3.sigmas = [BROADENING_SIGMA_THZ]   # Gaussian broadening, matched to kaldo
    ph3.init_phph_interaction()
    ph3.run_thermal_conductivity(
        is_LBTE=False,            # RTA
        temperatures=[TEMPERATURE],
        is_isotope=False,
        write_kappa=False,
    )
    print(f"[phono3py]   kappa (RTA) done in {time.time() - t5:.1f} s")

    tc = ph3.thermal_conductivity
    # tc.kappa: leading dims include temperature (and possibly grid index);
    # last dim is Voigt-6 (xx, yy, zz, yz, xz, xy). Squeeze to a flat 6-vector.
    kappa_rta_voigt = np.asarray(tc.kappa).reshape(-1)[:6]
    np.save(OUT / "kappa_rta_voigt_WmK.npy", kappa_rta_voigt)
    kappa_rta_diag_avg = float(np.mean(kappa_rta_voigt[:3]))  # avg of xx,yy,zz

    print(f"[phono3py] kappa (RTA, avg of xx/yy/zz): {kappa_rta_diag_avg:.3f} W/m/K")

    # ----- Direct (LBTE / direct inversion) -----
    print("[phono3py] running thermal conductivity (LBTE / direct) ...")
    t6 = time.time()
    try:
        ph3.run_thermal_conductivity(
            is_LBTE=True,
            temperatures=[TEMPERATURE],
            is_isotope=False,
            write_kappa=False,
        )
        tc_lbte = ph3.thermal_conductivity
        kappa_lbte_voigt = np.asarray(tc_lbte.kappa).reshape(-1)[:6]
        np.save(OUT / "kappa_lbte_voigt_WmK.npy", kappa_lbte_voigt)
        kappa_lbte_diag_avg = float(np.mean(kappa_lbte_voigt[:3]))
        print(f"[phono3py]   LBTE done in {time.time() - t6:.1f} s")
        print(f"[phono3py] kappa (LBTE, avg of xx/yy/zz): {kappa_lbte_diag_avg:.3f} W/m/K")
    except Exception as e:
        print(f"[phono3py]   LBTE failed: {e}")
        kappa_lbte_diag_avg = float("nan")

    summary = (
        f"phono3py silicon-Tersoff run\n"
        f"----------------------------\n"
        f"supercell FC2       : {SUPERCELL_FC2}\n"
        f"supercell FC3       : {SUPERCELL_FC3}\n"
        f"k/q-mesh            : {KMESH}\n"
        f"FD displacement     : {FD_DISPLACEMENT} A\n"
        f"temperature         : {TEMPERATURE} K\n"
        f"n_FC2_displacements : {len(fc2_supercells)}\n"
        f"n_FC3_displacements : {len([f for f in fc3_forces_list if f is not None])}\n"
        f"kappa RTA  (W/m/K)  : {kappa_rta_diag_avg:.3f}\n"
        f"kappa LBTE (W/m/K)  : {kappa_lbte_diag_avg:.3f}\n"
        f"total wallclock     : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
