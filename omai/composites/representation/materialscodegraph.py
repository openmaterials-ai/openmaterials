r"""materialscodegraph as a representation over the composites (effective-medium) DAG.

The materialscodegraph closed-form composite tool (mcg/tools/composite/emt.py,
ported verbatim to frontend/src/lib/emt.ts so the two cannot drift) computes the
Nan-type effective thermal conductivity of a filled matrix with interfacial
(Kapitza) resistance, plus its Hasselman-Johnson spherical-limit cross-check. Its
outputs map onto the composites nodes where they match:

  emt.py return field            symbol      -> composites node                                              units
  -----------------------------  ----------  ------------------------------------------------------------  -------
  kappa_random_W_per_mK          kappa_c     -> ThermalConductivity[effective_medium=nan,orientation=random]  W/(m K)
  kappa_aligned_33_W_per_mK      kappa_c     -> ThermalConductivity[effective_medium=nan,orientation=aligned]  W/(m K)
  depolarization_factors(p)      (L11, L33)  -> DepolarizationFactor                                          (dimensionless)

The tool is pure and validated: the default DGEBA epoxy + 5 vol% GNP draft
reproduces kappa_random = 1.2452 W/(m K), pinned in the mcg eval target
(mcg/evals/paper_targets.yaml composite_kappa.kappa_random_W_per_mK, tolerance
0.001) and cross-pinned in the frontend test (frontend/src/lib/emt.test.ts) and
the Python unit test (mcg/tests/tools/composite/test_emt.py). The Nan formula
(J. Appl. Phys. 81, 6692 (1997)) and the Hasselman-Johnson cross-check
(J. Compos. Mater. 21, 508 (1987)) are the validated formulas' sources; the
credits entry records them and the repository's Apache-2.0 license.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.composites.operator.nodes import (
    DEPOLARIZATION_FACTOR,
    EFFECTIVE_CONDUCTIVITY_ALIGNED,
    EFFECTIVE_CONDUCTIVITY_RANDOM,
)

MCG_EFFECTIVE_CONDUCTIVITY_RANDOM = SpaceRepresentationSpec(
    space=EFFECTIVE_CONDUCTIVITY_RANDOM,
    representation_name="materialscodegraph",
    observable_units={"kappa_c": "W_per_m_per_K"},
    code_api={"kappa_c": "emt.effective_kappa(...).kappa_random_W_per_mK"},
    notes=(
        "The randomly-oriented composite effective thermal conductivity from the "
        "Nan-type EMT with a per-direction interfacial series film "
        "(mcg/tools/composite/emt.py effective_kappa, return field "
        "kappa_random_W_per_mK), in W/(m K). The default DGEBA epoxy + 5 vol% GNP "
        "draft (km=0.2, k11=1200, k33=6, d1=5um, d3=0.02um, G=25 MW/m2K, f=0.05) "
        "emits 1.2452 W/(m K), pinned by the mcg eval target and cross-checked by "
        "the Hasselman-Johnson sphere formula at aspect ratio 1."
    ),
)

MCG_EFFECTIVE_CONDUCTIVITY_ALIGNED = SpaceRepresentationSpec(
    space=EFFECTIVE_CONDUCTIVITY_ALIGNED,
    representation_name="materialscodegraph",
    observable_units={"kappa_c": "W_per_m_per_K"},
    code_api={"kappa_c": "emt.effective_kappa(...).kappa_aligned_33_W_per_mK"},
    notes=(
        "The perfectly-aligned composite effective thermal conductivity from the "
        "Nan-type EMT (mcg/tools/composite/emt.py effective_kappa), in W/(m K). "
        "The tool returns both aligned tensor components; the declared node "
        "carries the axial (through-plane) kappa_aligned_33_W_per_mK, with the "
        "transverse (in-plane) kappa_aligned_11_W_per_mK its companion in the "
        "record conditions."
    ),
)

MCG_DEPOLARIZATION_FACTOR = SpaceRepresentationSpec(
    space=DEPOLARIZATION_FACTOR,
    representation_name="materialscodegraph",
    observable_units={"L11": "dimensionless", "L33": "dimensionless"},
    code_api={"L11": "emt.depolarization(aspect)[0]",
              "L33": "emt.depolarization(aspect)[1]"},
    notes=(
        "The spheroid depolarization factors (L11, L33) from the closed form in "
        "the aspect ratio p = d3/d1 (mcg/tools/composite/emt.py "
        "depolarization_factors), dimensionless with 2 L11 + L33 = 1: sphere "
        "(1/3, 1/3), long fiber (1/2, 0), thin disk (0, 1)."
    ),
)
