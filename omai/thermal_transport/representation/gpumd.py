"""gpumd adapter specs for the thermal-transport DAG.

GPUMD (Graphics Processing Units Molecular Dynamics,
https://github.com/brucefan1983/GPUMD) is a CUDA-accelerated classical-MD
code optimised for thermal-transport workflows. It ships dedicated drivers
for the homogeneous non-equilibrium MD method (HNEMD), Green-Kubo via the
heat-current autocorrelation function (HAC), and the spectral
decomposition of κ. Its native potential format is NEP (neuro-evolution
potentials), trained against DFT references; classical pair / tersoff /
EAM forms are also supported.

GPUMD is not driven through ASE — it has its own input format (`run.in`)
and its potentials live in their own files (`nep.txt`, `eam.fs`, …). This
adapter therefore targets the *native* GPUMD interface.

Scope in P1 of phase 2:
  * Potential (NEP / EAM / Tersoff file), via `provide_potential`.

Out of scope in P1 (will land in P3 of phase 2):
  * HNEMD κ via `compute hnemd` + heat-current spectra → κ_HNEMD.
  * Green-Kubo κ via the HAC route → κ_GK.
  * EMD κ via tighter ensemble averaging.
  * Heat-current spectral decomposition (per-frequency κ contributions).
  * Spectrally-resolved phonon transport (SRP).

References:
  * GPUMD user manual — https://gpumd.org/
  * NEP training / GPUMD inference — Fan et al., J. Chem. Phys. 157,
    114801 (2022).
  * HNEMD methodology — Fan et al., Phys. Rev. B 99, 064308 (2019).
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import provide_potential
from omai.thermal_transport.operator.nodes import POTENTIAL


GPUMD_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="gpumd",
    code_api={
        "potential": "nep.txt (default) | EAM/Tersoff/SW potential file referenced from run.in"
    },
    notes=(
        "GPUMD's Potential is declared in `run.in` via the `potential` "
        "keyword pointing at an on-disk file. Default and most common is "
        "NEP (neuro-evolution potential, `nep.txt` written by `nep`'s "
        "training run); EAM, Tersoff, SW are also supported as classical "
        "alternatives. NEP files carry the trained weights and the "
        "elemental-pair cutoffs; the file *is* the Potential."
    ),
)


GPUMD_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="gpumd",
    notes=(
        "Provides Potential by referencing an on-disk potential file in "
        "GPUMD's `run.in`. NEP is the canonical GPUMD potential format "
        "(trained against DFT energies + forces + virials via the `nep` "
        "trainer); classical forms read the same way."
    ),
)
