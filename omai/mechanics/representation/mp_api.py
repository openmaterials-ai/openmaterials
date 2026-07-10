r"""mp-api / Materials Project adapter specs for the mechanics domain.

The mechanics slice of the map's first DATABASE rail (see
`omai.dft_ground_state.representation.mp_api` for what "database rail" means).
Anchored in `scans/mp-api-atomistic-skills.json` (deep review 2026-07-09;
emmet-core 0.85.1 elasticity.py read from source, the two load-bearing unit
claims verified beyond the docstrings, in the emmet builder / pymatgen math).
Pins: mp-api 0.41.2 / emmet-core 0.85.1.

  operator Space    MP record field (elasticity endpoint)          units
  ----------------  ---------------------------------------------  --------
  ElasticConstants  ElasticityDoc.elastic_tensor.{raw,ieee_format} GPa
  BulkModulus       ElasticityDoc.bulk_modulus.vrh                 GPa
  ShearModulus      ElasticityDoc.shear_modulus.vrh                GPa
  YoungsModulus     ElasticityDoc.young_modulus                    Pa (SI!)
  PoissonRatio      ElasticityDoc.homogeneous_poisson             1

The two headline elasticity unit traps, source-verified beyond the docstrings:

  * MODULI ARE GPa DIRECTLY (bulk_modulus.vrh, shear_modulus.vrh,
    elastic_tensor raw/ieee 6x6): emmet post-processes pymatgen's tensor into
    GPa (elasticity.py:45-58 field descriptions, and the builder feeds Cauchy
    stresses whose expected unit is GPa, elasticity.py:248 'Expected units:
    GPa', so the fitted tensor and its VRH averages are GPa by construction;
    the compliance is *1000 to TPa^-1 'assuming elastic tensor in units of
    GPa', :315-318). This is the OPPOSITE trap direction from raw pymatgen
    ElasticTensor (eV/A^3): do NOT apply the 160.2176634 eV/A^3 -> GPa factor
    to MP fields.
  * YOUNG'S MODULUS IS SI PASCAL, not GPa: young_modulus is populated from
    pymatgen prop_dict['y_mod'] (elasticity.py:625), and pymatgen elastic.py:
    199-204 computes y_mod = 9.0e9 * k_vrh * g_vrh / (3 k_vrh + g_vrh) with
    k_vrh/g_vrh in GPa, so the 9.0e9 factor carries GPa -> Pa (in-source
    comment elasticity.py:706 'young's modulus (note it is in Pa, not GPa)').
    DIVIDE by 1e9 for the map's GPa. Two unit conventions inside one
    elasticity document.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.mechanics.operator.nodes import (
    BULK_MODULUS,
    ELASTIC_CONSTANTS,
    POISSON_RATIO,
    SHEAR_MODULUS,
    YOUNGS_MODULUS,
)


MP_API_ELASTIC_CONSTANTS = SpaceRepresentationSpec(
    space=ELASTIC_CONSTANTS,
    representation_name="mp-api",
    observable_units={"C": "GPa"},
    code_api={
        "C": "mpr.materials.elasticity.search().elastic_tensor.{raw, ieee_format} (Voigt 6x6), GPa",
    },
    notes=(
        "The elastic stiffness tensor MP serves as a database record: "
        "elastic_tensor.raw and .ieee_format, Voigt 6x6 in GPa "
        "(elasticity.py:24-31 'Elastic tensor corresponding to structure/IEEE "
        "orientation (GPa)'). UNIT TRAP: GPa directly, NOT eV/A^3; the "
        "160.2176634 factor the raw-pymatgen MLIP route needs must NOT be "
        "applied to MP fields (emmet's ElasticityDoc pipeline assumes the "
        "tensor is GPa by construction, elasticity.py:248,315-318). Two "
        "orientation representations (raw = structure orientation, ieee_format "
        "= standardized IEEE); declare which. compliance_tensor is served in "
        "1/TPa. A RETRIEVAL representation of the same ElasticConstants node "
        "the pymatgen / matcalc route grounds in eV/A^3 and the vasp OUTCAR "
        "route in kbar: an EXPECTED_AGREE across the three (after unit "
        "canonicalisation). A tensor, not an instance-store scalar; the VRH "
        "moduli below are the instance-friendly reductions."
    ),
)


MP_API_BULK_MODULUS = SpaceRepresentationSpec(
    space=BULK_MODULUS,
    representation_name="mp-api",
    observable_units={"K": "GPa"},
    code_api={
        "K": "mpr.materials.elasticity.search().bulk_modulus.vrh, GPa (nested {voigt, reuss, vrh} dict)",
    },
    notes=(
        "Bulk modulus MP serves as the Voigt-Reuss-Hill average: "
        "ElasticityDoc.bulk_modulus.vrh, a nested {voigt, reuss, vrh} dict in "
        "GPa (elasticity.py:45-51; AtomisticSkills reads doc.bulk_modulus.vrh, "
        "get_elasticity.py:105-107). UNIT TRAP: GPa DIRECTLY, no 160.2176634 "
        "eV/A^3 -> GPa factor (the opposite trap direction from raw pymatgen "
        "ElasticTensor.k_vrh, which is eV/A^3). The same BulkModulus node the "
        "pymatgen route grounds in eV/A^3 and the mat-elasticity skill reports "
        "in GPa: a natural EXPECTED_AGREE with the committed cu-bulkmodulus "
        "MACE-OMAT MLIP record (DFT database vs MLIP). VRH averaging and the "
        "functional (thermo_type) are the conditions provenance."
    ),
)


MP_API_SHEAR_MODULUS = SpaceRepresentationSpec(
    space=SHEAR_MODULUS,
    representation_name="mp-api",
    observable_units={"G": "GPa"},
    code_api={
        "G": "mpr.materials.elasticity.search().shear_modulus.vrh, GPa (nested {voigt, reuss, vrh} dict)",
    },
    notes=(
        "Shear modulus MP serves as the Voigt-Reuss-Hill average: "
        "ElasticityDoc.shear_modulus.vrh, a nested {voigt, reuss, vrh} dict in "
        "GPa (elasticity.py:53-58; doc.shear_modulus.vrh, "
        "get_elasticity.py:108-110). Same GPa-not-eV/A^3 trap as the bulk "
        "modulus (no 160.2176634 factor). EXPECTED_AGREE with the committed "
        "cu-shearmodulus MLIP record; VRH averaging + functional are the "
        "conditions provenance."
    ),
)


MP_API_YOUNGS_MODULUS = SpaceRepresentationSpec(
    space=YOUNGS_MODULUS,
    representation_name="mp-api",
    observable_units={"E_Y": "Pa"},
    code_api={
        "E_Y": "mpr.materials.elasticity.search().young_modulus, SI Pa (DIVIDE by 1e9 for GPa)",
    },
    notes=(
        "UNIT TRAP (verified beyond docstring): MP serves young_modulus in SI "
        "PASCAL, not GPa. Source proof: emmet elasticity.py:625 populates it "
        "from pymatgen prop_dict['y_mod']; pymatgen elastic.py:199-204 "
        "y_mod = 9.0e9 * k_vrh * g_vrh / (3 k_vrh + g_vrh) with k_vrh/g_vrh in "
        "GPa, so the 9.0e9 factor carries GPa -> Pa; corroborated by the "
        "in-source comment elasticity.py:706 'young's modulus (note it is in "
        "Pa, not GPa)'. DIVIDE by 1e9 for the map's GPa convention (1 GPa = "
        "1e9 Pa on the shared energy-density dimension). The same 1e9 mismatch "
        "the pymatgen y_mod carries, but here MP actually serves the Pa value. "
        "The YoungsModulus node is E_Y = 9KG/(3K + G) over the VRH moduli."
    ),
)


MP_API_POISSON_RATIO = SpaceRepresentationSpec(
    space=POISSON_RATIO,
    representation_name="mp-api",
    observable_units={"nu": "dimensionless"},
    code_api={
        "nu": "mpr.materials.elasticity.search().homogeneous_poisson, dimensionless",
    },
    notes=(
        "Poisson ratio MP serves directly: ElasticityDoc.homogeneous_poisson "
        "(elasticity.py:191-194; SummaryDoc.homogeneous_poisson summary.py:334), "
        "dimensionless, the (3K - 2G)/(2(3K + G)) contraction over the VRH "
        "moduli, no unit trap. universal_anisotropy (A_U, dimensionless) sits "
        "alongside in the same document but has no map tag or node (a genuine "
        "elastic-anisotropy new-node candidate, not grounded here)."
    ),
)
