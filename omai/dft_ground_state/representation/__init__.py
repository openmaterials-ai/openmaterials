"""Per-code adapter specs for the DFT ground-state domain.

Each submodule holds the SpaceRepresentationSpec and OperatorRepresentationSpec
instances for one code (QE first; pymatgen joined with the 2026-07-09 scan).
All instances are constructed against the shared operator DAG in
`omai.dft_ground_state.operator`, so cross-code agreement is checked at the
operator level (per Principle 7).

Re-exports the per-code spec instances for convenience; the canonical location
is the corresponding submodule (e.g. `omai.dft_ground_state.representation.qe`).
"""

from omai.dft_ground_state.representation.qe import (
    QE_FORCES,
    QE_SOLVE_GROUND_STATE,
    QE_STRESS,
    QE_STRUCTURE,
    QE_TOTAL_ENERGY,
)
from omai.dft_ground_state.representation.pymatgen import (
    PYMATGEN_COMPUTE_MAGNETIC_MOMENTS,
    PYMATGEN_MAGNETIC_MOMENT,
    PYMATGEN_STRESS,
    PYMATGEN_STRUCTURE,
    PYMATGEN_TOTAL_ENERGY,
)
from omai.dft_ground_state.representation.mace import (
    MACE_FORCES,
    MACE_POTENTIAL,
    MACE_SOLVE_GROUND_STATE,
    MACE_STRESS,
    MACE_TOTAL_ENERGY,
)
from omai.dft_ground_state.representation.matgl import (
    MATGL_FORCES,
    MATGL_MAGNETIC_MOMENT,
    MATGL_POTENTIAL,
    MATGL_SOLVE_GROUND_STATE,
    MATGL_STRESS,
    MATGL_TOTAL_ENERGY,
)
from omai.dft_ground_state.representation.fairchem import (
    FAIRCHEM_FORCES,
    FAIRCHEM_POTENTIAL,
    FAIRCHEM_SOLVE_GROUND_STATE,
    FAIRCHEM_STRESS,
    FAIRCHEM_TOTAL_ENERGY,
)

__all__ = [
    "QE_FORCES",
    "QE_SOLVE_GROUND_STATE",
    "QE_STRESS",
    "QE_STRUCTURE",
    "QE_TOTAL_ENERGY",
    "PYMATGEN_COMPUTE_MAGNETIC_MOMENTS",
    "PYMATGEN_MAGNETIC_MOMENT",
    "PYMATGEN_STRESS",
    "PYMATGEN_STRUCTURE",
    "PYMATGEN_TOTAL_ENERGY",
    "MACE_FORCES",
    "MACE_POTENTIAL",
    "MACE_SOLVE_GROUND_STATE",
    "MACE_STRESS",
    "MACE_TOTAL_ENERGY",
    "MATGL_FORCES",
    "MATGL_MAGNETIC_MOMENT",
    "MATGL_POTENTIAL",
    "MATGL_SOLVE_GROUND_STATE",
    "MATGL_STRESS",
    "MATGL_TOTAL_ENERGY",
    "FAIRCHEM_FORCES",
    "FAIRCHEM_POTENTIAL",
    "FAIRCHEM_SOLVE_GROUND_STATE",
    "FAIRCHEM_STRESS",
    "FAIRCHEM_TOTAL_ENERGY",
]
