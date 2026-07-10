r"""ASE adapter spec for the DFT ground-state domain: the relaxed Structure.

The matcalc/ASE scan (arXiv 2605.24002, scans/matcalc-ase-atomistic-skills)
records ASE as a producer of a relaxed Structure beyond hosting a calculator.
The Structure node lives in this (dft ground-state / materials) domain, so its
ase representation spec lives here; the ase Potential and Trajectory specs (both
thermal-transport nodes) live in omai.thermal_transport.representation.ase.
Together they are the one "ase" rail (build_codes merges specs across all
domains' representation packages).

A relaxed Structure is produced by an ase.optimize optimizer (FIRE default,
BFGS) driving the atoms (optionally wrapped in an ase.filters cell filter,
FrechetCellFilter or ExpCellFilter, for cell relaxation) to force convergence
at fmax. matcalc RelaxCalc's final_structure is exactly this (the equilibrium
structure every other matcalc calc relaxes to first); the optimizer /
cell_filter / fmax choices are representation-level schemes, not node identity.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.shared_primitives import STRUCTURE


ASE_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="ase",
    code_api={
        "structure": "ase.optimize optimizer (FIRE / BFGS) + ase.filters cell filter (FrechetCellFilter / ExpCellFilter) -> relaxed ase.Atoms / pymatgen Structure",
    },
    notes=(
        "ASE produces a relaxed Structure beyond hosting a calculator: an "
        "ase.optimize optimizer (FIRE default, BFGS) drives the atoms "
        "(optionally wrapped in an ase.filters cell filter, FrechetCellFilter "
        "or ExpCellFilter, for cell relaxation) to force convergence at fmax, "
        "returning a relaxed geometry (matcalc RelaxCalc final_structure is "
        "this; _relaxation.py, backend/_ase.py:119-154). The relaxed cell is "
        "what elastic / EOS / phonon calculators then deform. The optimizer / "
        "cell_filter / fmax choices are representation-level schemes on the "
        "relaxation, not node identity; the opaque input Structure and this "
        "relaxed Structure share the node. Angstrom (opaque)."
    ),
)
