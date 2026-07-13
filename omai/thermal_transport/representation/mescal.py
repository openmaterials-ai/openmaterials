"""MESCAL adapter specs for the thermal-transport DAG.

MESCAL: JAX embedding-space Kohn scattering, kALDo's coherent-transport sibling;
Bloch lead channels, direct mode-matching S-matrix, Landauer conductance. Where
kALDo does anharmonic lattice dynamics (and surfaces QHGK), MESCAL does coherent
phonon transport of a device between two semi-infinite periodic leads, going
beyond the elastic Kohn method with an anharmonic optical-potential kernel.

Constructed against the operator DAG in `omai.thermal_transport.operator`.
Cross-code comparison happens at the operator level (Principle 7) via the shared
PhononTransmission / ThermalConductance observables; differences surface as unit
factors (MESCAL emits nW/K; the canonical is W/K) and convention mismatches.

Precision: MESCAL runs the Bloch-channel solver and S-matrix in complex128 on
CPU (the source of truth) and complex64 on GPU (the batched fast path, validated
within 1e-3 of the CPU result). Cross-code comparison should reference the CPU
complex128 values.

Validation provenance: MESCAL reproduces the published coherent-transport
results of Duchemin and Donadio, Phys. Rev. B 84, 115423 (2011) (bulk silicon
Fig. 4 within digitization noise; the 2 nm wire junction within 10% of Fig. 2b
at 300 K). Manuscript in preparation.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import (
    PHONON_TRANSMISSION,
    THERMAL_CONDUCTANCE_LANDAUER,
)


MESCAL_PHONON_TRANSMISSION = SpaceRepresentationSpec(
    space=PHONON_TRANSMISSION,
    representation_name="mescal",
    observable_units={"T_trans": "dimensionless"},
    code_api={"T_trans": "Transport(...).transmission"},
    notes=(
        "Transport(System(dev, lead, lead, vl, vr), nu_grid).transmission: the "
        "per-frequency transmission T(nu) over the requested frequency grid "
        "(dimensionless), from the direct mode-matching S-matrix of the Bloch "
        "lead channels. Computed in complex128 on CPU (source of truth), "
        "complex64 on GPU (fast path). Integer for the ballistic channel "
        "staircase; fractional under the optional anharmonic optical-potential "
        "attenuation."
    ),
)


MESCAL_THERMAL_CONDUCTANCE_LANDAUER = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTANCE_LANDAUER,
    representation_name="mescal",
    observable_units={"G": "nW_per_K"},
    code_api={"G": "Transport(...).conductance([T])"},
    notes=(
        "Transport(...).conductance([T]): the Landauer thermal conductance G(T) "
        "in nW/K (eskm_tools.landauer, THz in, nW/K out), one value per requested "
        "temperature. The nW/K serving unit carries to_operator 1e-9 to the "
        "canonical W/K. Integrates the transmission against the Bose-Einstein "
        "energy window."
    ),
)
