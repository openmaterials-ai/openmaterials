r"""DiffCSP++ adapter spec for the materials domain (a Structure PRODUCER rail).

The structure-generation scan (scans/structure-gen-atomistic-skills.json)
catalogs DiffCSP++ (ml-generative-diffcsp), a diffusion model that predicts
crystal structures either symmetry-constrained (CSP: exact composition from
space group + Wyckoff letters + atom types, mp_csp / perov_csp / mpts_csp) or
unconditionally (Gen: mp_gen / perov_gen / carbon_gen). Under the same
orchestrator ruling as the mattergen rail, a generated structure is a
REPRESENTATION-ONLY provenance annotation on the Structure SOURCE node, NOT a
producing edge: a generator NEVER gets an inbound producing edge into Structure,
and a generated CIF is an INPUT ARTIFACT (immediately relaxed then E_hull-
screened) whose provenance rides in evidence (prose-first in source.ref /
source.detail per the review's shape finding).

The generator-provenance SCHEMA carried by the notes below: {checkpoint /
model_name, conditioning (spacegroup + Wyckoff + atom_types | none), sampler
scheme (step_lr Langevin step), seed}. The space group + Wyckoff spec is an
INPUT symmetry CONSTRAINT (a categorical label on the generation), NOT a map
node consumed as a field; it stays a representation label, not a new quantity.

PYXTAL WYCKOFF-HELPER FACT: DiffCSP++'s wrapper uses `from pyxtal.symmetry
import Group` (diffcsp_wrapper.py:591); Group(spacegroup)[letter].ops supplies
the Wyckoff affine matrices that build the PyG Data the diffusion consumes. This
is the ONLY functional pyxtal call in the whole AtomisticSkills skill set:
pyxtal is a Wyckoff-operator TABLE inside this producer, it produces nothing on
the map, and its from_random capability is UNUSED. (The AIRSS-style random
search is pymatgen, NOT pyxtal.)

SMACT is env-only: SMACT==3.2.0 is an installed dependency of diffcsp-agent /
adit-agent / mattergen-agent, but has ZERO call sites across all 126 skills (the
.md-verified sense). It is a dimension-free composition-validity FILTER (charge
neutrality AND electronegativity ordering), not a physics quantity and not a
Structure producer, so it earns NO rail; it is recorded only as this note.

Anchored: diffcsp_server.py:54-107 (generate_structures_with_symmetry);
diffcsp_wrapper.py:574-630 (pyxtal Group Wyckoff ops -> PyG Data);
unconditional_generate.py:15,79 (Gen models). DiffCSP++ is git-only (not pip-
importable locally); every fact is anchored to committed AtomisticSkills usage.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.shared_primitives import STRUCTURE


DIFFCSP_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="diffcsp",
    code_api={
        "structure": "DiffCSP++ generate_structures_with_symmetry(spacegroup, wyckoff_letters, atom_types, model_name='mp_csp', step_lr=1e-5) -> CIFs (diffcsp_server.py:54-107); dimensionless generated artifact",
    },
    notes=(
        "DiffCSP++ diffusion-predicted crystal structures as a REPRESENTATION-"
        "ONLY provenance annotation on the Structure SOURCE node, NOT a "
        "producing edge (a generator NEVER gets an inbound producing edge). CSP "
        "models (mp_csp / perov_csp / mpts_csp) predict with EXACT composition "
        "from space group + Wyckoff letters + atom_types (server.py:79-82); Gen "
        "models (mp_gen / perov_gen / carbon_gen) sample UNCONDITIONALLY "
        "(unconditional_generate.py:79). GENERATOR-PROVENANCE SCHEMA (rides in "
        "evidence, prose-first): {checkpoint / model_name, conditioning "
        "(spacegroup + Wyckoff + atom_types | none), sampler scheme (step_lr "
        "Langevin step), seed}; the space-group + Wyckoff spec is an INPUT "
        "symmetry CONSTRAINT / categorical label, never a consumed field. "
        "PYXTAL WYCKOFF-HELPER: `from pyxtal.symmetry import Group` "
        "(diffcsp_wrapper.py:591), Group(sg)[letter].ops gives the Wyckoff "
        "affine matrices for the PyG Data; the ONLY functional pyxtal call in "
        "the whole skill set, a Wyckoff-operator table INSIDE this producer "
        "(pyxtal produces nothing on the map, from_random unused). SMACT is "
        "ENV-ONLY (SMACT==3.2.0 installed, ZERO call sites in the .md-verified "
        "sense): a dimension-free composition-validity FILTER, no rail, this "
        "note only. TRAPS: step_lr is a Langevin sampler knob, NOT physics; the "
        "pre-relaxation CSL / P1 cell need not be in a symmetrized setting. The "
        "generated CIF is always immediately relaxed by an MLIP then E_hull-"
        "screened, so it is an INPUT ARTIFACT, not a physics result."
    ),
)
