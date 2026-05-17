"""lammps adapter specs for the thermal-transport DAG.

LAMMPS (Large-scale Atomic/Molecular Massively Parallel Simulator,
https://www.lammps.org/) is a classical-MD code that also provides phonon
and thermal-transport functionality via its USER-PHONON package and the
heat-flux / non-equilibrium-MD machinery in standard packages.

This adapter targets LAMMPS-as-its-own-code: the code is driven by a
LAMMPS input script (`lmp -in in.lammps`), reads potentials via
`pair_style` declarations, writes outputs to log files and dump files.

LAMMPS-via-ASE — where LAMMPS is used as an in-Python force backend via
`ase.calculators.lammpslib.LAMMPSlib` — is covered by the separate `ase`
adapter, since that path interacts with LAMMPS through the ASE
protocol rather than through LAMMPS's native scripting interface.

Scope in P1 of phase 2:
  * Potential (`pair_style` declaration + coefficients), via
    `provide_potential`.

Out of scope in P1 (will land in P2 / P3 of phase 2):
  * USER-PHONON outputs: dispersion (band.dat), DM via Green's function
    fluctuation method.
  * Native MD heat-current via `compute heat/flux` + `fix ave/correlate`
    → Green-Kubo κ.
  * Müller-Plathe NEMD via `fix thermal/conductivity` → κ_NEMD.
  * Force-constant derivation via the `fix phonon` or external dynaphopy
    workflows.

References:
  * https://docs.lammps.org/pair_style.html — full list of pair_style
    options (tersoff, eam, sw, snap, …).
  * https://docs.lammps.org/Howto_phonon.html — USER-PHONON how-to.
  * https://docs.lammps.org/compute_heat_flux.html — Green-Kubo κ
    pipeline.
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import provide_potential
from omai.thermal_transport.operator.nodes import POTENTIAL


LAMMPS_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="lammps",
    code_api={
        "potential": "LAMMPS input script: pair_style <name> + pair_coeff <args>"
    },
    notes=(
        "LAMMPS-native Potential: declared in the input script via "
        "`pair_style <name>` (tersoff, eam, sw, snap, reax, …) and the "
        "matching `pair_coeff` lines (or external potential files like "
        "Si.tersoff, Cu_u3.eam). The Potential is fully specified by the "
        "input script + any referenced parameter files. For LAMMPS-via-ASE "
        "(in-Python force evaluation through `LAMMPSlib`), see the `ase` "
        "adapter instead — same numerical content, different driving "
        "interface."
    ),
)


LAMMPS_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="lammps",
    notes=(
        "Provides Potential via LAMMPS's native scripting interface. The "
        "Potential's identity (pair_style + parameters) is read from the "
        "input script at LAMMPS startup; subsequent force evaluations are "
        "all driven by that initial configuration. Per-run reproducibility "
        "depends on the parameter files referenced (Si.tersoff, etc.) "
        "being version-pinned."
    ),
)
