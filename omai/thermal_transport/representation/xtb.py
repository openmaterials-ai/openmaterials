r"""xtb as a representation over the harmonic MolarHeatCapacity node.

xtb (grimme-lab/xtb) is the semiempirical extended tight-binding program
behind the GFN family of methods. Its `--hess` / `--ohess` runs end in a
THERMO block: vibrational frequencies feed the rigid-rotor /
harmonic-oscillator (RRHO) partition function and the block prints, among
enthalpy and entropy, the molar heat capacity at the requested temperature.
The committed DGEBA evidence instance (397.7 J/(K mol) at 300 K, gas phase,
GFN2-xTB, 0 imaginary modes) names `xtb 6.7.1` in its in-hash conditions;
this rail records the interface that reproduces it.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import MOLAR_HEAT_CAPACITY

XTB_MOLAR_HEAT_CAPACITY = SpaceRepresentationSpec(
    space=MOLAR_HEAT_CAPACITY,
    representation_name="xtb",
    observable_units={"C_V_mol": "J_per_K_per_mol"},
    code_api={"C_V_mol": "xtb <geom> --ohess --temp <T>  (THERMO block, Cp row)"},
    notes=(
        "Gas-phase harmonic molar heat capacity from GFN2-xTB frequencies "
        "under the RRHO approximation: xtb's thermo block prints Cp(T) after "
        "a converged Hessian run with no imaginary modes. The model "
        "(GFN2-xTB), the xtb version, the phase, and the RRHO approximation "
        "ride in the record's conditions."
    ),
)
