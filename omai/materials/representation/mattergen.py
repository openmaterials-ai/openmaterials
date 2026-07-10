r"""MatterGen adapter spec for the materials domain (a Structure PRODUCER rail).

The structure-generation scan (scans/structure-gen-atomistic-skills.json)
catalogs MatterGen (ml-generative-mattergen), a diffusion model that SAMPLES
novel inorganic crystal structures (unconditional, or conditioned on a chemical
system or a scalar property). Under the orchestrator ruling, a generated
structure is a REPRESENTATION-ONLY provenance annotation on the Structure node,
NOT a producing edge: Structure stays a pure SOURCE node (it has zero inbound
links in the committed graph), and a generator is a source annotation exactly
parallel to how mp-api database structures enter (source object + material tag).

STANDING RULING (recorded here so the topology decision is explicit): a
generator NEVER gets a producing edge into Structure. A generated structure is
an INPUT ARTIFACT whose provenance rides in evidence (prose-first in an
instance's source.ref / source.detail per the review's shape finding), because
in every skill the generated CIF is immediately RELAXED by an MLIP, then
E_hull-screened, then DFT-refined: the generator's raw output is never itself a
physics result. Making a generate_structure edge first-class would INVERT the
source topology for an artifact that is always relaxed away, and would mis-model
the conditioning (a training / steering LABEL) as a consumed field. If Phase 2
ever wants a first-class edge it is a deliberate KERNEL decision, and even then
the honest edge is generator -> Structure with conditioning as a LABEL, never an
edge from a property node.

The generator-provenance SCHEMA carried by the notes below: {checkpoint /
model_name, conditioning (chemical_system | property | none), sampler scheme
(guidance_scale), seed}. Under the committed instance schema these fold into a
material tag (e.g. "Li2ZrCl6 (mattergen:chemical_system)") plus a structured
source object (source.kind='simulation', source.ref='...mattergen', the
checkpoint / conditioning / guidance / seed as source.detail prose), exactly as
mat-db-mp folds its retrieval provenance today.

Anchored: mattergen_wrapper.py:78,130-145 (from_hf_hub, generate ->
struct.to(cif)); mattergen_server.py:35-100 (guidance_scale 0.0 unconditional;
chemical_system model, guidance 1.0). MatterGen is git-only (not pip-importable
locally); every fact is anchored to committed AtomisticSkills usage.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.shared_primitives import STRUCTURE


MATTERGEN_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="mattergen",
    code_api={
        "structure": "MatterGen generator.generate(batch_size, num_batches, output_dir) -> pymatgen Structures written to CIF (mattergen_wrapper.py:130-145); dimensionless generated artifact",
    },
    notes=(
        "MatterGen diffusion-sampled crystal structures as a REPRESENTATION-"
        "ONLY provenance annotation on the Structure SOURCE node, NOT a "
        "producing edge (Structure stays a pure source; a generator NEVER gets "
        "an inbound producing edge, the standing topology ruling). The public "
        "pretrained checkpoints (mattergen_base, mp_20_base, dft_mag_density, "
        "chemical_system; mattergen_wrapper.py:34-39, loaded via from_hf_hub at "
        ":78) sample either UNCONDITIONALLY (guidance_scale 0.0, mattergen_"
        "server.py:42) or CONDITIONED on a chemical system or a scalar property "
        "(guidance_scale bumped to 1.0, properties={'chemical_system':...} or "
        "{'dft_mag_density':...}, server.py:81-94). GENERATOR-PROVENANCE SCHEMA "
        "(rides in evidence, prose-first per the review): {checkpoint / "
        "model_name, conditioning (chemical_system | property | none), sampler "
        "scheme (guidance_scale), seed}; under the committed instance schema a "
        "material tag ('...(mattergen:chemical_system)') plus source.kind="
        "'simulation', source.ref='...mattergen', the rest as source.detail "
        "prose, parallel to mat-db-mp. TRAPS: chemical_system controls the "
        "ELEMENTS not the exact stoichiometry (Li-Zr-Cl may yield LiCl / ZrCl4 "
        "or omit Li; a post-filter is mandatory, SKILL.md:131-145); guidance_"
        "scale is a sampler / steering knob, NOT a physics field. The generated "
        "CIF is always immediately relaxed by an MLIP then E_hull-screened, so "
        "it is an INPUT ARTIFACT, not a physics result."
    ),
)
