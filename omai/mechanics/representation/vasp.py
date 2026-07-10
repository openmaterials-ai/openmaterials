r"""VASP adapter specs for the mechanics domain.

VASP as AtomisticSkills (arXiv 2605.24002) reads it for elasticity, anchored in
`scans/atomate2-vasp-atomistic-skills.json` (review 2026-07-09). VASP is a
SECOND representation of the ElasticConstants node the pymatgen / matcalc route
already grounds: the two are an EXPECTED_AGREE pair (DFT elastic tensor vs MLIP
elastic tensor).

  operator Space    VASP artifact                                 units
  ----------------  --------------------------------------------  --------
  ElasticConstants  Outcar.elastic_modulus (IBRION=6 direct) /    kbar
                    atomate2 ElasticMaker (stress-strain fit)

Convention traps this module pins down (review-verified):

  * Outcar.elastic_modulus parses the VASP header 'TOTAL ELASTIC MODULI
    (kBar)' (pymatgen outputs.py:2824, regex verified): kbar, the IBRION=6
    finite-differences DIRECT modulus. kbar -> GPa via *0.1 (exact); this is
    the modulus curvature, no sign flip on it.
  * The pymatgen ElasticTensor.from_independent_strains(vasp=True) STRESS-FIT
    route is DIFFERENT: it applies c_ij *= -0.1 (elastic.py:518-519, kbar +
    the VASP-stress sign flip) because it fits the raw compression-positive
    VASP stress; the direct OUTCAR modulus needs only *0.1.
  * The mapped matcalc route (pymatgen mechanics rail) fits MLIP stresses in
    eV/A^3 (canonical 160.21766339999996 -> GPa); this OUTCAR/kbar route is an
    alternate representation, an EXPECTED_AGREE with it.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.mechanics.operator.edges import compute_elastic_constants
from omai.mechanics.operator.nodes import ELASTIC_CONSTANTS


VASP_ELASTIC_CONSTANTS = SpaceRepresentationSpec(
    space=ELASTIC_CONSTANTS,
    representation_name="vasp",
    observable_units={"C": "kbar"},
    code_api={
        "C": "pymatgen Outcar.elastic_modulus (VASP IBRION=6 'TOTAL ELASTIC MODULI (kBar)'), kbar; atomate2 ElasticMaker",
    },
    notes=(
        "The elastic stiffness tensor as VASP emits it in kbar, the 6x6 "
        "'TOTAL ELASTIC MODULI (kBar)' block pymatgen Outcar.elastic_modulus "
        "parses (outputs.py:2824 header regex verified; "
        "vasp_parser.py:124). This is the IBRION=6 finite-differences DIRECT "
        "modulus: kbar -> GPa via *0.1 (exact), no sign flip (a modulus is a "
        "curvature). DISTINCT from the pymatgen "
        "from_independent_strains(vasp=True) STRESS-FIT route, which applies "
        "c_ij *= -0.1 (elastic.py:518-519) to flip the raw "
        "compression-positive VASP stress it fits. An ALTERNATE "
        "representation of the same node the matcalc/MLIP route grounds in "
        "eV/A^3 (pymatgen mechanics rail, canonical 160.21766339999996 -> "
        "GPa): the two are an EXPECTED_AGREE pair (DFT vs MLIP elastic "
        "tensor). atomate2's ElasticMaker (atomate2.vasp.flows.elastic, "
        "VERIFIED present in the 0.1.4 wheel as ElasticMaker(BaseElasticMaker)) "
        "is the workflow route, though the AtomisticSkills DFT scripts read "
        "OUTCAR.elastic_modulus directly rather than driving that flow."
    ),
)


VASP_COMPUTE_ELASTIC_CONSTANTS = OperatorRepresentationSpec(
    operator=compute_elastic_constants,
    representation_name="vasp",
    discretization_choices={
        "route": (
            "OUTCAR Outcar.elastic_modulus (IBRION=6 direct finite-difference "
            "modulus, kbar) vs the atomate2 ElasticMaker stress-strain fit; "
            "AtomisticSkills reads the direct OUTCAR modulus"
        ),
        "ion_relaxation": (
            "clamped-ion vs relaxed-ion elastic constants (whether the "
            "IBRION=6 run includes the ionic relaxation contribution); a "
            "scheme distinction recorded in conditions"
        ),
    },
    notes=(
        "VASP realizes compute_elastic_constants either as the IBRION=6 "
        "direct finite-difference elastic tensor (Outcar.elastic_modulus, "
        "kbar, the AtomisticSkills path) or via the atomate2 ElasticMaker "
        "stress-strain fit (VERIFIED in the wheel). Both are the DFT ground "
        "truth for the same node the matcalc MLIP stress-fit grounds, an "
        "EXPECTED_AGREE across the DFT and MLIP producers; the kbar-vs-GPa "
        "and sign facts live on the VASP_ELASTIC_CONSTANTS space spec."
    ),
)
