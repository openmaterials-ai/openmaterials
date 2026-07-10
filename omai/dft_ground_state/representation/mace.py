r"""MACE (mace-torch) adapter specs for the DFT ground-state domain.

A MACE checkpoint IS a representation of the opaque Potential node: a
parameterized Born-Oppenheimer PES fit to DFT, wrapped as an ASE calculator.
AtomisticSkills (arXiv 2605.24002) drives it through
`src/utils/mlips/mace/mace_wrapper.py:create_calculator()`; from the single ASE
calculator the whole ground-state tier is fed:

  operator Space   MACE artifact                                       ASE API
  ---------------  --------------------------------------------------  --------------------
  Potential        the trained checkpoint (mace_mp / MACECalculator /  wrapper.create_calculator()
                   mace_off / mace_omol / mace_anicc), an ASE calc
  TotalEnergy      model energy head, eV per cell                      get_potential_energy()
  Forces           autograd -dE/dr, eV/A                               get_forces()
  Stress           autograd virial, eV/A^3, ASE Voigt 6-vector         get_stress()

Anchored in `scans/mlip-family-atomistic-skills.json` (deep review 2026-07-09,
package-source-verified against the pip-downloaded mace_torch-0.3.16 wheel:
mace/calculators/mace.py read directly).

Convention traps this module pins down (all source-verified):

  * ASE units project-wide (base.py:643-644 explicit comment "we standardize to
    eV/A^3 across the project"): energy eV/cell, forces eV/A, stress eV/A^3.
  * Stress is tensile-positive (ASE sigma = (1/V) dU/deps), the OPPOSITE sign of
    the store's compression-positive sigma_store: the store-convention factor is
    -1 (per the atomate2-vasp scan's verified sign chain). MACE emits
    full_3x3_to_voigt_6_stress (mace.py:726).
  * ASE Voigt order (xx, yy, zz, yz, xz, xy), DIFFERENT from LAMMPS
    (xx, yy, zz, xy, xz, yz): a cross-engine agreement must renormalize order.
  * MACE forces are conservative (autograd off the energy graph,
    mace.py:610 "differentiate energy w.r.t. displacement").
  * Committee uncertainty (energy_var / forces_var) is available when
    num_models > 1 (mace.py:704-717), recorded as a deferred node candidate, NOT
    encoded here.
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


MACE_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="mace",
    code_api={
        "potential": "src/utils/mlips/mace/mace_wrapper.py create_calculator() -> ASE Calculator (mace_mp / MACECalculator / mace_off / mace_omol / mace_anicc, mace_wrapper.py:144-242)",
    },
    notes=(
        "A MACE checkpoint IS the Potential: a parameterized Born-Oppenheimer "
        "PES fit to DFT, surfaced as an ASE calculator; the artifact is the "
        "trained model file, not a numeric unit (opaque at the operator "
        "layer, like the ase Atoms.calc Potential). MODEL PROVENANCE (the "
        "discriminant so distinct checkpoints do not false-merge): "
        "model_type='mace'; model_name is the canonical checkpoint id after "
        "alias resolution (wrapper default MACE -> MACE-MH-1; families "
        "MACE-MH-{0,1}, MACE-MP-{small,medium,large}[-0b/-0b2/-0b3], MACE-MPA-0, "
        "MACE-OMAT-0-{small,medium}, MACE-MATPES-{PBE,R2SCAN}-0, "
        "MACE-OFF23-{small,medium,large}, MACE-OMOL-extra-large, MACE-ANI-CC; "
        "mace_wrapper.py:17-50); head selects the training-data domain and "
        "therefore the functional (default 'omat_pbe' for multi-head MH models, "
        "mace_wrapper.py:203-212), a required provenance field; is_fine_tuned "
        "distinguishes foundation from fine-tuned (base.py:321). The MCP-tool "
        "default (MACE-OMAT-0-small, mace_server.py:40) differs from the wrapper "
        "class default, so an instance's model_name must be read from the actual "
        "call, not assumed. force_type is 'conservative' (forces/stress are "
        "autograd off the energy graph, mace.py:610). COMMITTEE UNCERTAINTY: a "
        "MACECalculator built from N checkpoints populates calc.results["
        "'energy_var'] and ['forces_var'] when num_models>1 (mace.py:704-717, "
        "torch.var unbiased=False), a representation-quality diagnostic on this "
        "Potential and a DEFERRED node candidate (energy_uncertainty / "
        "force_uncertainty, meV/atom, meV/A), NOT encoded here. CROSS-ENGINE: "
        "mat-lammps-md compiles the SAME checkpoint into a LAMMPS pair style "
        "(examples/mace/*.sh, *-lammps.pt), so the lammps Potential "
        "representation and this one realize the same PES via two engines: an "
        "EXPECTED_AGREE candidate on E/F/S (normalize the Voigt order, tolerate "
        "the ~1e-8 CODATA-generation difference between ASE units.GPa "
        "(CODATA-2014) and the LAMMPS constant). PROVENANCE CHAIN: mat-elasticity "
        "drives MACE via matcalc (load_wrapper -> create_calculator -> "
        "ElasticityCalc, calculate_elasticity.py:40,61,68); the committed "
        "mat-elasticity Cu instances were computed with a MACE checkpoint, "
        "recorded here in notes until a future instance-schema slice carries the "
        "(model_name, head, is_fine_tuned) tuple on the instance."
    ),
)


MACE_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="mace",
    observable_units={"E_tot": "ev"},
    code_api={
        "E_tot": "atoms.get_potential_energy() with a MACE ASE calculator (eV per cell, base.py:635)",
    },
    notes=(
        "MACE-predicted total energy of the configuration, eV per cell "
        "(atoms.get_potential_energy(), base.py:635). Matches the map's "
        "TotalEnergy canonical (eV per simulation cell); QE grounds the same "
        "node in Ry. PER-ATOM TRAP: the raw calculator returns per-cell eV, but "
        "benchmark (run_benchmark.py:119) and stability flows divide by "
        "num_atoms (eV/atom). PROVENANCE CAVEAT: the absolute energy zero is "
        "model + functional specific (the head fixes the training data and its "
        "reference energies), so cross-model or cross-functional agreement must "
        "be on RELATIVE energies, not absolute."
    ),
)


MACE_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="mace",
    observable_units={"F": "eV_per_A"},
    code_api={
        "F": "atoms.get_forces() with a MACE ASE calculator (eV/A, shape (n_atoms, 3), base.py:636)",
    },
    notes=(
        "Per-atom Cartesian forces, eV/A (atoms.get_forces(), base.py:636). "
        "MACE forces are CONSERVATIVE: F = -dE/dr computed by autograd off the "
        "energy graph (mace.py:610 'differentiate energy w.r.t. displacement'), "
        "so energy is conserved in NVE. force_type='conservative' (contrast the "
        "fairchem esen-*-direct checkpoints, whose forces are a separate head). "
        "QE grounds Forces in Ry/bohr."
    ),
)


MACE_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="mace",
    observable_units={"sigma": "eV_per_A3"},
    code_api={
        "sigma": "atoms.get_stress() with a MACE ASE calculator (eV/A^3, ASE Voigt 6-vector, base.py:642)",
    },
    notes=(
        "Cell-averaged stress, eV/A^3, ASE Voigt 6-vector in order "
        "(xx, yy, zz, yz, xz, xy) (atoms.get_stress(), base.py:642; MACE emits "
        "full_3x3_to_voigt_6_stress, mace.py:726). UNIT: eV/A^3, standardized "
        "project-wide (base.py:643-644), NOT GPa. SIGN: ASE stress is "
        "TENSILE-POSITIVE (sigma = (1/V) dU/deps), the OPPOSITE sign of the map "
        "store's compression-positive sigma_store; the factor to the store "
        "convention is -1 (per the atomate2-vasp scan's verified sign chain, the "
        "same -1 the ml-mlip-benchmark applies to VASP kbar targets, "
        "run_benchmark.py:139). ORDER: ASE Voigt (xx,yy,zz,yz,xz,xy) DIFFERS "
        "from LAMMPS (xx,yy,zz,xy,xz,yz); a cross-engine EXPECTED_AGREE against "
        "the lammps Potential/Stress must renormalize the Voigt order."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how a MACE checkpoint realizes the solve)
# ---------------------------------------------------------------------------

MACE_SOLVE_GROUND_STATE = OperatorRepresentationSpec(
    operator=solve_ground_state,
    representation_name="mace",
    discretization_choices={
        "model_name": (
            "the MACE checkpoint id after alias resolution (wrapper default "
            "MACE -> MACE-MH-1); selects the PES the model was trained to "
            "reproduce (mace_wrapper.py:17-50)"
        ),
        "head": (
            "for multi-head (MH) models the training-data head, default "
            "'omat_pbe' (mace_wrapper.py:203-212); it fixes the functional and "
            "reference energies, so it is provenance, not cosmetic"
        ),
        "is_fine_tuned": (
            "foundation checkpoint vs a fine-tuned one (base.py:321); changes "
            "the PES, recorded in instance conditions"
        ),
    },
    notes=(
        "A MACE checkpoint realizes solve_ground_state not as an SCF loop but "
        "as a single forward/backward pass of a trained message-passing "
        "network: the energy head plus its autograd forces and stress. Unlike "
        "the QE realization there is no k-mesh / smearing / conv_thr; the "
        "discretization of THIS operator is the model choice itself "
        "(model_name, head, is_fine_tuned), which fixes the PES being "
        "represented. Two instances with different checkpoints or heads realize "
        "DIFFERENT Potentials and must record them in the conditions."
    ),
)
