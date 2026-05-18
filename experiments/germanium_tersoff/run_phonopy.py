"""phonopy path for the germanium-Tersoff experiment.

Mirrors silicon_tersoff/run_phonopy.py. The framework's phonopy adapter
is material-agnostic; only `seed.py` differs between the two
experiments.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from phonopy import Phonopy
from phonopy.structure.atoms import PhonopyAtoms

from seed import (
    FD_DISPLACEMENT,
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    build_germanium_primitive,
    make_tersoff_calculator,
)


OUT = RUNS_DIR / "phonopy"
OUT.mkdir(parents=True, exist_ok=True)


def ase_to_phonopy(atoms) -> PhonopyAtoms:
    return PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )


def phonopy_to_ase(unitcell: PhonopyAtoms):
    from ase import Atoms
    return Atoms(
        symbols=unitcell.symbols,
        cell=unitcell.cell,
        scaled_positions=unitcell.scaled_positions,
        pbc=True,
    )


def main() -> None:
    t0 = time.time()
    atoms = build_germanium_primitive()
    calc = make_tersoff_calculator()

    print(f"[phonopy] Ge supercell {SUPERCELL_FC2}, kmesh {KMESH}, FD delta {FD_DISPLACEMENT} A")

    unitcell = ase_to_phonopy(atoms)
    supercell_matrix = np.diag(SUPERCELL_FC2)
    phonon = Phonopy(unitcell, supercell_matrix=supercell_matrix)

    phonon.generate_displacements(distance=FD_DISPLACEMENT)
    supercells = phonon.supercells_with_displacements
    print(f"[phonopy] generated {len(supercells)} symmetry-reduced displaced supercells")

    print("[phonopy] computing forces on each displaced supercell ...")
    t1 = time.time()
    forces_list = []
    for i, sc in enumerate(supercells):
        ase_sc = phonopy_to_ase(sc)
        ase_sc.calc = calc
        f = ase_sc.get_forces()
        forces_list.append(f)
        if (i + 1) % 5 == 0 or i == 0 or i == len(supercells) - 1:
            print(f"[phonopy]   disp {i+1}/{len(supercells)}: max |F| = {np.abs(f).max():.4f} eV/A")
    print(f"[phonopy]   forces done in {time.time() - t1:.1f} s")

    phonon.forces = forces_list
    print("[phonopy] producing FC2 ...")
    t2 = time.time()
    phonon.produce_force_constants()
    print(f"[phonopy]   FC2 done in {time.time() - t2:.1f} s")

    print("[phonopy] computing dispersion on q-mesh ...")
    t3 = time.time()
    phonon.run_mesh(
        mesh=list(KMESH),
        with_eigenvectors=True,
        with_group_velocities=True,
        is_mesh_symmetry=False,
        is_gamma_center=True,
    )
    mesh_dict = phonon.get_mesh_dict()
    q_points = mesh_dict["qpoints"]
    frequencies = mesh_dict["frequencies"]
    eigenvectors = mesh_dict["eigenvectors"]
    group_velocities = mesh_dict["group_velocities"]
    print(f"[phonopy]   dispersion done in {time.time() - t3:.1f} s")

    print(
        f"[phonopy] frequencies shape={frequencies.shape}, "
        f"min={frequencies.min():.4f} THz, max={frequencies.max():.4f} THz"
    )

    np.save(OUT / "frequencies_THz.npy", frequencies)
    np.save(OUT / "eigenvectors.npy", eigenvectors)
    np.save(OUT / "group_velocities_AT.npy", group_velocities)
    np.save(OUT / "q_points.npy", q_points)
    np.save(OUT / "fc2.npy", phonon.force_constants)

    print("[phonopy] computing harmonic thermal properties on a T-grid ...")
    t4 = time.time()
    phonon.run_thermal_properties(t_min=0.0, t_max=1000.0, t_step=10.0)
    td = phonon.get_thermal_properties_dict()
    F_kJ = td["free_energy"]
    S_JK = td["entropy"]
    T_arr = td["temperatures"]
    Cv_JK = td["heat_capacity"]
    internal_energy_J = F_kJ * 1000.0 + T_arr * S_JK
    np.save(OUT / "free_energy_kJ_per_mol.npy", F_kJ)
    np.save(OUT / "entropy_J_per_K_per_mol.npy", S_JK)
    np.save(OUT / "heat_capacity_J_per_K_per_mol.npy", Cv_JK)
    np.save(OUT / "temperatures_K.npy", T_arr)
    np.save(OUT / "internal_energy_J_per_mol.npy", internal_energy_J)
    print(f"[phonopy]   thermal properties done in {time.time() - t4:.1f} s "
          f"(n_T={len(T_arr)})")

    summary = (
        f"phonopy germanium-Tersoff run\n"
        f"------------------------------\n"
        f"supercell FC2     : {SUPERCELL_FC2}\n"
        f"k/q-mesh          : {KMESH}\n"
        f"FD displacement   : {FD_DISPLACEMENT} A\n"
        f"n_displacements   : {len(supercells)}\n"
        f"n_q               : {frequencies.shape[0]}\n"
        f"n_modes           : {frequencies.shape[1]}\n"
        f"freq min / max    : {frequencies.min():.4f} / {frequencies.max():.4f} THz\n"
        f"total wallclock   : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
