"""Per-code adapter specs for the DFT ground-state domain.

Each submodule holds the SpaceRepresentationSpec and OperatorRepresentationSpec
instances for one code (QE first). All instances are constructed against the
shared operator DAG in `omai.dft_ground_state.operator`, so cross-code
agreement is checked at the operator level (per Principle 7).

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

__all__ = [
    "QE_FORCES",
    "QE_SOLVE_GROUND_STATE",
    "QE_STRESS",
    "QE_STRUCTURE",
    "QE_TOTAL_ENERGY",
]
