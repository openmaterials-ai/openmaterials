"""phonopy path for the silicon-Tersoff experiment.

Steps:
  1. Build the silicon Atoms and the LAMMPS-Tersoff calculator (from seed.py).
  2. Use phonopy to generate displaced supercells.
  3. Loop: attach calculator to each displaced supercell, collect forces.
  4. Phonopy assembles 2nd-order force constants.
  5. Compute dispersion (frequencies, eigenvectors, group velocities) on the q-mesh.

Outputs land in runs/silicon_tersoff/phonopy/.
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
    build_silicon_primitive,
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
    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()

    print(f"[phonopy] supercell {SUPERCELL_FC2}, kmesh {KMESH}, FD delta {FD_DISPLACEMENT} A")

    # ----- Set up phonopy with the unit cell and supercell choice -----
    unitcell = ase_to_phonopy(atoms)
    supercell_matrix = np.diag(SUPERCELL_FC2)
    phonon = Phonopy(unitcell, supercell_matrix=supercell_matrix)

    # ----- Generate symmetry-reduced displacements -----
    phonon.generate_displacements(distance=FD_DISPLACEMENT)
    supercells = phonon.supercells_with_displacements
    print(f"[phonopy] generated {len(supercells)} symmetry-reduced displaced supercells")

    # ----- Compute forces on each displacement using the ASE calculator -----
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

    # ----- Assemble force constants and produce dispersion -----
    phonon.forces = forces_list
    print("[phonopy] producing FC2 ...")
    t2 = time.time()
    phonon.produce_force_constants()
    print(f"[phonopy]   FC2 done in {time.time() - t2:.1f} s")

    # ----- Sample on the same q-mesh kaldo uses (Monkhorst-Pack-style grid) -----
    # phonopy's run_mesh produces frequencies on a grid; we then extract eigenvectors
    # by computing the dynamical matrix at each q.
    print("[phonopy] computing dispersion on q-mesh ...")
    t3 = time.time()
    phonon.run_mesh(
        mesh=list(KMESH),
        with_eigenvectors=True,
        with_group_velocities=True,
        is_mesh_symmetry=False,  # match kaldo's full grid (no symmetry reduction)
        is_gamma_center=True,    # match kaldo's Gamma-included MP grid
    )
    mesh_dict = phonon.get_mesh_dict()
    q_points = mesh_dict["qpoints"]              # (n_q, 3) in reduced units
    frequencies = mesh_dict["frequencies"]       # (n_q, n_modes), THz
    eigenvectors = mesh_dict["eigenvectors"]     # (n_q, n_modes, n_modes), complex
    group_velocities = mesh_dict["group_velocities"]  # (n_q, n_modes, 3), THz·Å (phonopy units)
    print(f"[phonopy]   dispersion done in {time.time() - t3:.1f} s")

    print(
        f"[phonopy] frequencies shape={frequencies.shape}, "
        f"min={frequencies.min():.4f} THz, "
        f"max={frequencies.max():.4f} THz"
    )

    # ----- Save outputs -----
    np.save(OUT / "frequencies_THz.npy", frequencies)
    np.save(OUT / "eigenvectors.npy", eigenvectors)
    np.save(OUT / "group_velocities_AT.npy", group_velocities)
    np.save(OUT / "q_points.npy", q_points)
    # also save the FC2 tensor itself for any future direct comparison
    np.save(OUT / "fc2.npy", phonon.force_constants)

    summary = (
        f"phonopy silicon-Tersoff run\n"
        f"--------------------------\n"
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
