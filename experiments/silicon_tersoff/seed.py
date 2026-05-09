"""Shared seed for the silicon-Tersoff experiment.

Defines a single source of truth for:
  - the silicon structure (ASE Atoms, diamond, 2-atom primitive cell)
  - the LAMMPS-Tersoff calculator
  - the discretization choices (supercell sizes, k/q-meshes)

Both `run_kaldo.py` and `run_phonopy.py` import from here, so they start from
identical inputs. Outputs from each path are written under ../../runs/silicon_tersoff/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.calculators.lammpslib import LAMMPSlib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EXP_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXP_DIR.parent.parent
RUNS_DIR = REPO_ROOT / "runs" / "silicon_tersoff"
TERSOFF_FILE = EXP_DIR / "Si.tersoff"

# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

# Diamond Si, 2-atom primitive cell. a=5.431 Å is the experimental value;
# the Tersoff Si potential's relaxed lattice constant is close to this and
# we don't relax further for this first run (kept simple by intent).
LATTICE_CONSTANT = 5.431  # Å


def build_silicon_primitive() -> Atoms:
    """Return the 2-atom primitive diamond-Si unit cell as ASE Atoms."""
    return bulk("Si", "diamond", a=LATTICE_CONSTANT, cubic=False)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


def make_tersoff_calculator() -> LAMMPSlib:
    """Return a LAMMPSlib calculator configured with the Tersoff Si potential.

    The Tersoff parameter file is the one shipped with LAMMPS; we keep a copy
    in the experiment folder for portability.
    """
    cmds = [
        f"pair_style tersoff",
        f"pair_coeff * * {TERSOFF_FILE} Si",
    ]
    return LAMMPSlib(
        lmpcmds=cmds,
        atom_types={"Si": 1},
        keep_alive=True,
        log_file=str(RUNS_DIR / "lammps.log"),
    )


# ---------------------------------------------------------------------------
# Discretization choices
# ---------------------------------------------------------------------------

# Supercell for 2nd-order force constants (both codes use this).
SUPERCELL_FC2 = (4, 4, 4)

# Supercell for 3rd-order (smaller; not used in the first FC2 + dispersion run).
SUPERCELL_FC3 = (3, 3, 3)

# k-/q-mesh for sampling the Brillouin zone.
KMESH = (8, 8, 8)

# Finite-difference displacement (used when each code runs forces via ASE)
FD_DISPLACEMENT = 0.01  # Å -- phonopy default; reasonable for Si

# Temperature for any thermal property (not used in the first run).
TEMPERATURE = 300  # K


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    atoms = build_silicon_primitive()
    print(f"Silicon primitive cell:")
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
