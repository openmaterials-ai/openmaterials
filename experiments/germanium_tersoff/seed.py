"""Shared seed for the germanium-Tersoff experiment.

Diamond-cubic Ge with the Mahdizadeh-Akhlamadi 2017 Tersoff
parameterisation (J. Mol. Graph. Model. 72, 1-5). Mirrors
`experiments/silicon_tersoff/seed.py` so the same run_*.py drivers and
the framework's spec-derived audits apply with no other changes.

The framework treats material identity as data — change `seed.py`, the
operator-layer code and the representation adapters stay byte-identical.
That portability is the property this second material is here to
exercise.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.calculators.lammpslib import LAMMPSlib


EXP_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXP_DIR.parent.parent
RUNS_DIR = REPO_ROOT / "runs" / "germanium_tersoff"
TERSOFF_FILE = EXP_DIR / "Ge.tersoff"


# Diamond Ge, 2-atom primitive cell. a = 5.658 Å is the experimental
# value (Mahdizadeh-Akhlamadi 2017 returns a relaxed lattice constant
# very close to it).
LATTICE_CONSTANT = 5.658  # Å


def build_germanium_primitive() -> Atoms:
    """Return the 2-atom primitive diamond-Ge unit cell as ASE Atoms."""
    return bulk("Ge", "diamond", a=LATTICE_CONSTANT, cubic=False)


def make_tersoff_calculator() -> LAMMPSlib:
    """LAMMPSlib calculator configured with the Mahdizadeh Ge Tersoff."""
    cmds = [
        "pair_style tersoff",
        f"pair_coeff * * {TERSOFF_FILE} Ge",
    ]
    return LAMMPSlib(
        lmpcmds=cmds,
        atom_types={"Ge": 1},
        keep_alive=True,
        log_file=str(RUNS_DIR / "lammps.log"),
    )


# Discretization — same supercells and q-mesh as silicon_tersoff so the
# diagnostics line up.
SUPERCELL_FC2 = (4, 4, 4)
SUPERCELL_FC3 = (3, 3, 3)
KMESH = (8, 8, 8)
FD_DISPLACEMENT = 0.01  # Å

TEMPERATURE = 300  # K
BROADENING_SIGMA_THZ = 0.1


if __name__ == "__main__":
    atoms = build_germanium_primitive()
    print(f"Germanium primitive cell:")
    print(f"  formula        : {atoms.get_chemical_formula()}")
    print(f"  cell           : {atoms.cell.array}")
    print(f"  positions (Å)  :")
    for s, p in zip(atoms.symbols, atoms.positions):
        print(f"    {s} {p}")
    print()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    atoms.calc = make_tersoff_calculator()

    e = atoms.get_potential_energy()
    f = atoms.get_forces()
    s = atoms.get_stress(voigt=False)

    print(f"Tersoff calculator:")
    print(f"  energy (eV)    : {e:.6f}")
    print(f"  forces (eV/Å)  : max |F| = {np.abs(f).max():.3e}")
    print(f"  stress (eV/Å³) :")
    print(f"    diag = {np.diag(s)}")
    print()
    print(f"Discretization:")
    print(f"  supercell FC2  : {SUPERCELL_FC2}")
    print(f"  supercell FC3  : {SUPERCELL_FC3}")
    print(f"  k-mesh         : {KMESH}")
    print(f"  FD displacement: {FD_DISPLACEMENT} Å")
