r"""fairchem-core (UMA / eSEN) adapter specs for the DFT ground-state domain.

A fairchem-core checkpoint IS a representation of the opaque Potential node: a
parameterized Born-Oppenheimer PES fit to DFT, surfaced as an ASE calculator
(fairchem.core.FAIRChemCalculator). AtomisticSkills (arXiv 2605.24002) drives it
through `src/utils/mlips/fairchem/fairchem_wrapper.py:create_calculator()`; from
the single ASE calculator the whole ground-state tier is fed:

  operator Space   fairchem artifact                                   ASE API
  ---------------  --------------------------------------------------  --------------------
  Potential        the trained checkpoint (UMA universal / eSEN),      wrapper.create_calculator()
                   wrapped as FAIRChemCalculator(task_name=...)
  TotalEnergy      per-task energy head, eV per cell                   get_potential_energy()
  Forces           energy-head autograd OR a direct head, eV/A         get_forces()
  Stress           virial, eV/A^3, ASE Voigt 6-vector                  get_stress()

Anchored in `scans/mlip-family-atomistic-skills.json` (deep review 2026-07-09,
package-source-verified against the pip-downloaded fairchem_core-2.21.0 wheel:
fairchem/core/calculate/ase_calculator.py read directly).

Convention traps this module pins down (all source-verified):

  * ASE units: energy eV/cell, forces eV/A, stress eV/A^3. fairchem emits
    full_3x3_to_voigt_6_stress (ase_calculator.py:254), ASE Voigt order
    (xx, yy, zz, yz, xz, xy).
  * Stress is tensile-positive (ASE convention), the OPPOSITE sign of the
    store's compression-positive sigma_store: the store-convention factor is -1
    (per the atomate2-vasp scan's verified sign chain).
  * force_type in {conservative, direct} is encoded in the CHECKPOINT NAME
    ('esen-md-direct-all-omol' vs 'esen-sm-conserving-all-omol') and the
    MODEL_METADATA, not a calculator kwarg (ase_calculator.py:249-251). A DIRECT
    head predicts forces from a separate head, NOT the exact gradient of the
    energy, so energy is NOT conserved in NVE (an MD / Trajectory gauge concern).
  * task_name in {omat, omol, oc22} is selected at calculator build
    (fairchem_wrapper.py:237-241); omat is the materials/solid task. The task
    changes the reference energies and which of charge/spin are read, so it is a
    required provenance field.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.edges import solve_ground_state
from omai.dft_ground_state.operator.nodes import (
    FORCES,
    STRESS,
    TOTAL_ENERGY,
)
from omai.materials.operator.shared_primitives import POTENTIAL


FAIRCHEM_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="fairchem",
    code_api={
        "potential": "src/utils/mlips/fairchem/fairchem_wrapper.py create_calculator() -> fairchem.core.FAIRChemCalculator(predict_unit=model, task_name=target_task) (fairchem_wrapper.py:222-255)",
    },
    notes=(
        "A fairchem-core checkpoint IS the Potential: a parameterized "
        "Born-Oppenheimer PES fit to DFT, surfaced as an ASE FAIRChemCalculator; "
        "the artifact is the trained model, not a numeric unit (opaque at the "
        "operator layer). MODEL PROVENANCE (the discriminant so distinct "
        "checkpoints do not false-merge): model_type='fairchem'; model_name is "
        "the resolved checkpoint id (families uma-{s,m}-1p{1,2} and uma-s-1 "
        "universal, esen-{md,sm}-{direct,conserving}-all-{omol,oc25}; "
        "fairchem_wrapper.py:23-77); head/task is task_name in {omat, omol, "
        "oc22} selected at calculator build (default 'omat' for non-esen, 'omol' "
        "for esen; fairchem_wrapper.py:237-241), omat being the materials task - "
        "the task changes the reference energies and which of charge/spin are "
        "read, so it is a required provenance field; is_fine_tuned distinguishes "
        "foundation from fine-tuned (fairchem_wrapper.py:201). The MCP-tool "
        "default (uma-s-1p2, fairchem_server.py:48) differs from the class "
        "default (EquiformerV2), so read model_name from the actual call. "
        "FORCE_TYPE in {conservative, direct}: encoded in the checkpoint NAME "
        "('esen-md-direct-all-omol' direct vs 'esen-sm-conserving-all-omol' and "
        "UMA conservative) and the MODEL_METADATA, a property of the loaded "
        "predict_unit, not a calculator kwarg (ase_calculator.py:249-251). A "
        "DIRECT model's forces are a separate head, NOT the exact -dE/dr, so "
        "energy is NOT conserved in NVE - an MD / Trajectory gauge concern that "
        "propagates to any HeatCurrent / Green-Kubo built on the trajectory. "
        "CROSS-ENGINE: mat-lammps-md compiles a FairChem pair style "
        "(examples/fairchem/*.sh), a second realization of the same PES via "
        "LAMMPS - an EXPECTED_AGREE candidate on E/F/S (normalize Voigt order, "
        "tolerate the ~1e-8 CODATA-generation difference)."
    ),
)


FAIRCHEM_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="fairchem",
    observable_units={"E_tot": "ev"},
    code_api={
        "E_tot": "atoms.get_potential_energy() with a FAIRChemCalculator (eV per cell, base.py:635)",
    },
    notes=(
        "fairchem-predicted total energy of the configuration, eV per cell "
        "(atoms.get_potential_energy(), base.py:635). Matches the map's "
        "TotalEnergy canonical (eV per simulation cell); QE grounds the same "
        "node in Ry. PER-ATOM TRAP: the raw calculator returns per-cell eV, but "
        "benchmark and stability flows divide by num_atoms (eV/atom). "
        "PROVENANCE CAVEAT: the absolute energy zero is model + TASK specific "
        "(each task carries its own per-element reference energies, "
        "fairchem_wrapper.py:652-673), so cross-model or cross-task agreement "
        "must be on RELATIVE energies, not absolute."
    ),
)


FAIRCHEM_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="fairchem",
    observable_units={"F": "eV_per_A"},
    code_api={
        "F": "atoms.get_forces() with a FAIRChemCalculator (eV/A, shape (n_atoms, 3), base.py:636)",
    },
    notes=(
        "Per-atom Cartesian forces, eV/A (atoms.get_forces(), base.py:636). "
        "force_type varies by checkpoint: UMA and the 'conserving' eSEN "
        "checkpoints are conservative (forces = autograd of the energy), but "
        "'esen-*-direct' checkpoints predict forces from a SEPARATE direct head "
        "that is NOT the exact gradient of the energy (fairchem_wrapper.py:"
        "51,61), so energy is NOT conserved in NVE. The distinction is in the "
        "checkpoint name / MODEL_METADATA (ase_calculator.py:249-251), a physics "
        "/ gauge trap for MD, not a unit trap. QE grounds Forces in Ry/bohr."
    ),
)


FAIRCHEM_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="fairchem",
    observable_units={"sigma": "eV_per_A3"},
    code_api={
        "sigma": "atoms.get_stress() with a FAIRChemCalculator (eV/A^3, ASE Voigt 6-vector, base.py:642; ase_calculator.py:254)",
    },
    notes=(
        "Cell-averaged stress, eV/A^3, ASE Voigt 6-vector in order "
        "(xx, yy, zz, yz, xz, xy) (atoms.get_stress(), base.py:642; fairchem "
        "emits full_3x3_to_voigt_6_stress, ase_calculator.py:254). UNIT: eV/A^3, "
        "standardized project-wide (base.py:643-644), NOT GPa. SIGN: ASE stress "
        "is TENSILE-POSITIVE, the OPPOSITE sign of the map store's "
        "compression-positive sigma_store; the factor to the store convention is "
        "-1 (per the atomate2-vasp scan's verified sign chain, the same -1 the "
        "ml-mlip-benchmark applies to VASP kbar targets, run_benchmark.py:139). "
        "ORDER: ASE Voigt (xx,yy,zz,yz,xz,xy) DIFFERS from LAMMPS "
        "(xx,yy,zz,xy,xz,yz); a cross-engine EXPECTED_AGREE against the lammps "
        "Potential/Stress must renormalize the Voigt order."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how a fairchem checkpoint realizes the solve)
# ---------------------------------------------------------------------------

FAIRCHEM_SOLVE_GROUND_STATE = OperatorRepresentationSpec(
    operator=solve_ground_state,
    representation_name="fairchem",
    discretization_choices={
        "model_name": (
            "the fairchem checkpoint id (uma-* universal or esen-*); selects "
            "the PES and whether forces are conservative or direct via the name "
            "(fairchem_wrapper.py:23-77)"
        ),
        "task_name": (
            "the prediction task in {omat, omol, oc22} chosen at calculator "
            "build (default omat for non-esen; fairchem_wrapper.py:237-241); it "
            "sets the reference energies and which of charge/spin are read, so "
            "it is provenance, not cosmetic"
        ),
        "is_fine_tuned": (
            "foundation checkpoint vs a fine-tuned one "
            "(fairchem_wrapper.py:201); changes the PES, recorded in conditions"
        ),
    },
    notes=(
        "A fairchem checkpoint realizes solve_ground_state as a single forward "
        "pass of a trained network under a chosen task_name. Unlike QE there is "
        "no k-mesh / smearing / conv_thr; the discretization of THIS operator is "
        "the model choice (model_name, task_name, is_fine_tuned). CRITICAL: "
        "model_name also fixes force_type in {conservative, direct} - a "
        "'direct' checkpoint's forces are not the exact energy gradient, so the "
        "operator it realizes does not conserve energy in NVE, a gauge property "
        "that instances built on its Trajectory must record. "
        "MATCALC-DRIVER DOUBLE-PROVENANCE (matcalc/ASE scan): matcalc's "
        "property calculators (ElasticityCalc, EOSCalc, PhononCalc, "
        "AdsorptionCalc, ...) drive THIS same fairchem checkpoint through the "
        "ASE calculator; each derived node carries a TWO-LAYER provenance, the "
        "matcalc DRIVER + its scheme (strain grid, EOS volume scan n_points, "
        "supercell / mesh / displacement, optimizer / fmax / cell_filter, "
        "matcalc-owned discretizations) AND this fairchem checkpoint (the true "
        "PES). matcalc mints no unit basis of its own, so it earns no rail; the "
        "schemes ride the driven-node operator specs and this checkpoint is the "
        "physics, both required for reproducibility."
    ),
)
