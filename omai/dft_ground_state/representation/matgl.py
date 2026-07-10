r"""matgl (M3GNet / CHGNet / TensorNet) adapter specs for the DFT ground-state domain.

A matgl PES checkpoint IS a representation of the opaque Potential node: a
parameterized Born-Oppenheimer PES fit to DFT, surfaced as an ASE calculator
(matgl.ext.ase.PESCalculator). AtomisticSkills (arXiv 2605.24002) drives it
through `src/utils/mlips/matgl/matgl_wrapper.py:create_calculator()`; from the
single ASE calculator the whole ground-state tier is fed, plus CHGNet's
distinguishing per-site magnetic-moment head:

  operator Space   matgl artifact                                      ASE API
  ---------------  --------------------------------------------------  --------------------
  Potential        the trained checkpoint (M3GNet / CHGNet /           wrapper.create_calculator()
                   TensorNet PES), wrapped as PESCalculator
  TotalEnergy      model energy head, eV per cell                      get_potential_energy()
  Forces           autograd -dE/dr, eV/A                               get_forces()
  Stress           virial, eV/A^3 (forced), ASE Voigt 6-vector         get_stress()
  MagneticMoment   CHGNet sitewise readout, mu_B per site              results['magmoms']

Anchored in `scans/mlip-family-atomistic-skills.json` (deep review 2026-07-09,
package-source-verified against the pip-downloaded matgl-4.0.3 wheel:
matgl/ext/ase.py + matgl/apps/pes.py + matgl/models/_chgnet.py read directly).

Convention traps this module pins down (all source-verified):

  * Stress UNIT DEFAULT is GPa: PESCalculator's stress_unit defaults to "GPa"
    (matgl/ext/ase.py:173, Literal["eV/A3","GPa"]="GPa"). The wrapper OVERRIDES
    it to eV/A3 (matgl_wrapper.py:129) - a real 160x trap avoided in-code; a
    consumer that builds PESCalculator without stress_unit='eV/A3' gets GPa.
  * use_voigt DEFAULTS False (matgl/ext/ase.py:175): the calculator writes a
    FULL 3x3 stress into results, not a Voigt-6. The wrapper does NOT pass
    use_voigt=True. Harmless in the AtomisticSkills path because every consumer
    goes through ase.Atoms.get_stress(), which reduces the 3x3 to ASE Voigt-6.
  * Stress is tensile-positive: matgl computes (1/V) dE/deps, documented
    "compressive-negative" (pes.py:53,228) = the ASE convention; the store's
    sigma_store is compression-positive, so the store-convention factor is -1.
  * CHGNet magmom head: the sitewise readout produces g.magmom (_chgnet.py:437),
    surfaced as results['magmoms'] under calc_magmom (ext/ase.py:280-281,
    apps/pes.py:363), mu_B per site. The wrapper MISLABELS its capability key as
    'charges' (matgl_wrapper.py:288); the extra head is magnetic moments, not
    charges. No AtomisticSkills consumer reads the live magmom.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.edges import solve_ground_state
from omai.dft_ground_state.operator.nodes import (
    FORCES,
    MAGNETIC_MOMENT_STATE,
    STRESS,
    TOTAL_ENERGY,
)
from omai.materials.operator.shared_primitives import POTENTIAL


MATGL_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="matgl",
    code_api={
        "potential": "src/utils/mlips/matgl/matgl_wrapper.py create_calculator() -> matgl.ext.ase.PESCalculator(potential=model, stress_unit='eV/A3') (matgl_wrapper.py:123-130)",
    },
    notes=(
        "A matgl PES checkpoint IS the Potential: a parameterized "
        "Born-Oppenheimer PES fit to DFT, surfaced as an ASE PESCalculator; the "
        "artifact is the trained model, not a numeric unit (opaque at the "
        "operator layer). MODEL PROVENANCE (the discriminant so distinct "
        "checkpoints do not false-merge): model_type='matgl'; model_name is the "
        "canonical checkpoint id (wrapper default M3GNet -> "
        "M3GNet-PES-MatPES-PBE-2025.2; CHGNet -> CHGNet-PES-MatPES-PBE-2025.2.10; "
        "families M3GNet-PES-MatPES-{PBE,r2SCAN}-2025.2, "
        "CHGNet-PES-MatPES-{PBE,r2SCAN}-2025.2.10, TensorNet-PES-*, QET-PES-*, "
        "SO3Net-PES-ANI-1x; matgl_wrapper.py:39-81); head is NONE (single-task "
        "PES, the functional PBE vs r2SCAN is encoded in the checkpoint name); "
        "is_fine_tuned distinguishes foundation from fine-tuned "
        "(matgl_wrapper.py:265). The MCP-tool default "
        "(CHGNet-PES-MatPES-PBE-2025.2.10, matgl_server.py:43) differs from the "
        "wrapper class default (M3GNet), so read model_name from the actual "
        "call. force_type is 'conservative' (matgl PES forces/stress are grads "
        "of the energy, apps/pes.py:314-334). CROSS-ENGINE: mat-lammps-md "
        "compiles a MatGL-CHGNet pair style (examples/matgl/*.sh), a second "
        "realization of the same PES via LAMMPS - an EXPECTED_AGREE candidate on "
        "E/F/S (normalize Voigt order, tolerate the ~1e-8 CODATA-generation "
        "difference). PROVENANCE CHAIN: the mat-* physics skills drive matgl via "
        "matcalc (load_wrapper -> create_calculator -> ElasticityCalc / EOSCalc "
        "/ PhononCalc)."
    ),
)


MATGL_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="matgl",
    observable_units={"E_tot": "ev"},
    code_api={
        "E_tot": "atoms.get_potential_energy() with a matgl PESCalculator (eV per cell, base.py:635)",
    },
    notes=(
        "matgl-predicted total energy of the configuration, eV per cell "
        "(atoms.get_potential_energy(), base.py:635). Matches the map's "
        "TotalEnergy canonical (eV per simulation cell); QE grounds the same "
        "node in Ry. PER-ATOM TRAP: the raw calculator returns per-cell eV, but "
        "benchmark and stability flows divide by num_atoms (eV/atom). "
        "PROVENANCE CAVEAT: the absolute energy zero is model + functional "
        "specific (PBE vs r2SCAN, encoded in the checkpoint name), so "
        "cross-model or cross-functional agreement must be on RELATIVE "
        "energies, not absolute."
    ),
)


MATGL_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="matgl",
    observable_units={"F": "eV_per_A"},
    code_api={
        "F": "atoms.get_forces() with a matgl PESCalculator (eV/A, shape (n_atoms, 3), base.py:636)",
    },
    notes=(
        "Per-atom Cartesian forces, eV/A (atoms.get_forces(), base.py:636). "
        "matgl PES forces are CONSERVATIVE: gradients of the energy "
        "(apps/pes.py:314-334), so energy is conserved in NVE. "
        "force_type='conservative'. QE grounds Forces in Ry/bohr."
    ),
)


MATGL_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="matgl",
    observable_units={"sigma": "eV_per_A3"},
    code_api={
        "sigma": "atoms.get_stress() with a matgl PESCalculator built stress_unit='eV/A3' (eV/A^3, ASE Voigt 6-vector, base.py:642; matgl_wrapper.py:128-130)",
    },
    notes=(
        "Cell-averaged stress, eV/A^3, ASE Voigt 6-vector in order "
        "(xx, yy, zz, yz, xz, xy) (atoms.get_stress(), base.py:642). UNIT TRAP: "
        "matgl's PESCalculator NATIVE stress default is GPa (matgl/ext/ase.py:"
        "173, Literal[\"eV/A3\",\"GPa\"]=\"GPa\"), OVERRIDDEN in the wrapper to "
        "eV/A3 (matgl_wrapper.py:129) - so this spec's eV/A^3 holds only through "
        "the wrapper; a consumer building PESCalculator without stress_unit="
        "'eV/A3' gets GPa (a 160x trap). NUANCE: use_voigt DEFAULTS False "
        "(matgl/ext/ase.py:175), so the calculator writes a FULL 3x3 into "
        "results, not a Voigt-6; the wrapper does NOT set use_voigt=True, "
        "harmless because get_stress() reduces the 3x3 to ASE Voigt-6 (a "
        "consumer reading calc.results['stress'] directly gets a 3x3). SIGN: "
        "matgl stress = (1/V) dE/deps, documented 'compressive-negative' "
        "(pes.py:53,228) = the ASE tensile-positive convention (no flip at the "
        "matgl/ASE boundary); this is the OPPOSITE sign of the store's "
        "compression-positive sigma_store, so the store-convention factor is -1 "
        "(per the atomate2-vasp scan's verified sign chain). ORDER: ASE Voigt "
        "(xx,yy,zz,yz,xz,xy) DIFFERS from LAMMPS (xx,yy,zz,xy,xz,yz)."
    ),
)


MATGL_MAGNETIC_MOMENT = SpaceRepresentationSpec(
    space=MAGNETIC_MOMENT_STATE,
    representation_name="matgl",
    observable_units={"m": "mu_B"},
    code_api={
        "m": "results['magmoms'] from a CHGNet PESCalculator under Potential.calc_magmom (matgl/ext/ase.py:280-281), mu_B per site",
    },
    notes=(
        "CHGNet's distinguishing per-site magnetic-moment head, mu_B per site, "
        "indexed by site i. The CHGNet sitewise_readout produces g.magmom "
        "(matgl-4.0.3 matgl/models/_chgnet.py:437), surfaced by PESCalculator "
        "as results['magmoms'] when Potential.calc_magmom is True "
        "(matgl/ext/ase.py:280-281; apps/pes.py:363). Units mu_B "
        "(chgnet documents the head as 'magnetic moments of sites ... in "
        "Bohr'). WRAPPER MISLABEL: matgl_wrapper.py:288 flags CHGNet's "
        "capability as get_model_capabilities()['charges']=True, but the extra "
        "head is magnetic moments (mu_B), NOT charges - calc_magmom "
        "(results['magmoms']) and calc_charge (results['charges']) are separate, "
        "mutually-exclusive paths (apps/pes.py:360-368), so the 'charges' key is "
        "a genuine semantic mislabel. UNCLAIMED OUTPUT: no AtomisticSkills "
        "script reads the live CHGNet magmom; the one skill that parses moments "
        "(mat-magnetic-density) reads them from serialized VASP/MCP output, not "
        "from a live CHGNet run. Maps to the same MagneticMoment node the "
        "pymatgen adapter grounds; CHGNet is a second source for it (mu_B) if "
        "the magnetism flow ever consumes the live head."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how a matgl checkpoint realizes the solve)
# ---------------------------------------------------------------------------

MATGL_SOLVE_GROUND_STATE = OperatorRepresentationSpec(
    operator=solve_ground_state,
    representation_name="matgl",
    discretization_choices={
        "model_name": (
            "the matgl checkpoint id (wrapper default M3GNet -> "
            "M3GNet-PES-MatPES-PBE-2025.2); selects the PES and, via the name, "
            "the functional PBE vs r2SCAN (matgl_wrapper.py:39-81)"
        ),
        "is_fine_tuned": (
            "foundation checkpoint vs a fine-tuned one "
            "(matgl_wrapper.py:265); changes the PES, recorded in conditions"
        ),
        "stress_unit": (
            "the PESCalculator stress unit, which the wrapper forces to 'eV/A3' "
            "(matgl_wrapper.py:129) OVERRIDING matgl's native GPa default "
            "(matgl/ext/ase.py:173); a build without this override emits GPa"
        ),
    },
    notes=(
        "A matgl PES checkpoint realizes solve_ground_state as a single "
        "forward/backward pass of a trained graph network: energy head plus its "
        "gradient forces and virial stress. head is NONE (single-task PES); the "
        "functional is fixed by model_name. Unlike QE there is no k-mesh / "
        "smearing / conv_thr; the discretization of THIS operator is the model "
        "choice (model_name, is_fine_tuned) plus the wrapper's stress_unit "
        "override that keeps the emitted stress in eV/A^3. "
        "MATCALC-DRIVER DOUBLE-PROVENANCE (matcalc/ASE scan): matcalc's "
        "property calculators (ElasticityCalc, EOSCalc, PhononCalc, "
        "AdsorptionCalc, ...) drive THIS same matgl checkpoint through the ASE "
        "calculator; each derived node they produce carries a TWO-LAYER "
        "provenance, the matcalc DRIVER + its scheme (strain grid, EOS volume "
        "scan n_points, supercell / mesh / displacement, optimizer / fmax / "
        "cell_filter, matcalc-owned discretizations) AND this matgl checkpoint "
        "(the true PES). matcalc mints no unit basis of its own, so it earns no "
        "rail; the schemes ride the driven-node operator specs and this "
        "checkpoint is the physics, both required for reproducibility."
    ),
)
