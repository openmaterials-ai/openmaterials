r"""materialscodegraph as a representation over the harmonic MolarHeatCapacity node.

The materialscodegraph molecular-thermo tool computes the gas-phase harmonic
molar heat capacity of a molecule from GFN2-xTB (xtb) frequencies under the
rigid-rotor / harmonic-oscillator (RRHO) approximation. Its C_p(T) output maps
onto the thermal-transport MolarHeatCapacity node:

  mcg molecular_thermo call                         symbol      -> node                 units
  -----------------------------------------------  ----------  --------------------  -----------
  molecular_thermo.cp_harmonic_J_per_molK(...)      C_V_mol     -> MolarHeatCapacity   J/(K mol)

The polymer-vertical eval baseline is the DGEBA monomer at 300 K, pinned at
397.7 J/(K mol) with a tolerance of 8 J/(K mol) (mcg/evals/paper_targets.yaml
dgeba_cp300_gfn2), the pin the committed evidence instance and its conformance
target both carry. The MolarHeatCapacity node is per mole of the entity in the
record's conditions (here per mole of DGEBA molecules); the harmonic RRHO model
and the xtb version ride in those conditions. materialscodegraph's citation and
Apache-2.0 license are recorded once on its credits entry (the effective-medium
rail introduced it); this spec adds a second node to the same rail.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import MOLAR_HEAT_CAPACITY

MCG_MOLAR_HEAT_CAPACITY = SpaceRepresentationSpec(
    space=MOLAR_HEAT_CAPACITY,
    representation_name="materialscodegraph",
    observable_units={"C_V_mol": "J_per_K_per_mol"},
    code_api={"C_V_mol": "molecular_thermo.cp_harmonic_J_per_molK (GFN2-xTB RRHO)"},
    notes=(
        "The gas-phase harmonic molar heat capacity from GFN2-xTB (xtb) "
        "frequencies under the rigid-rotor / harmonic-oscillator (RRHO) "
        "approximation (materialscodegraph molecular_thermo, return field "
        "cp_harmonic_J_per_molK), in J/(K mol). The DGEBA monomer at 300 K is "
        "the polymer-vertical eval baseline: 397.7 J/(K mol), pinned by the mcg "
        "eval target (mcg/evals/paper_targets.yaml dgeba_cp300_gfn2, tolerance "
        "8 J/(K mol), which covers xtb-version drift in the low-frequency "
        "modes). The temperature, phase (gas), RRHO approximation, and xtb "
        "version ride in the record conditions."
    ),
)
