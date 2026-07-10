r"""pymatgen adapter specs for the mechanics domain.

pymatgen 2025.6.14 (the version importable in the scan environment), as used by
the AtomisticSkills mat-* skills and anchored in the scan catalog
`scans/pymatgen-atomistic-skills.json` (review 2026-07-09, every factor
CODATA-verified). pymatgen's `analysis.elasticity.elastic.ElasticTensor` owns
the whole isotropic family:

  operator Space    pymatgen artifact                              units
  ----------------  ---------------------------------------------  --------
  ElasticConstants  ElasticTensor (rank 4); .voigt (6x6 packing)   eV/A^3
  BulkModulus       ElasticTensor.k_vrh (0.5*(k_voigt + k_reuss))  eV/A^3
  ShearModulus      ElasticTensor.g_vrh (0.5*(g_voigt + g_reuss))  eV/A^3
  YoungsModulus     ElasticTensor.y_mod (9.0e9 * KG/(3K+G))        Pa (SI!)
  PoissonRatio      ElasticTensor.homogeneous_poisson              1

Convention traps this module pins down (all review-verified):

  * ElasticTensor is stored in eV/A^3 (elastic.py:130-136 'in units of
    eV/A^3'), NOT GPa. 1 eV/A^3 = 160.21766339999996 GPa, verified two ways
    (scipy CODATA and pymatgen's own Unit conversion, elastic.py:52). A
    consumer reading .voigt as GPa is off by 160x.
  * .voigt is not a plain reshape: the fixed reverse map
    [[0,5,4],[5,1,3],[4,3,2]] (tensors.py:381) with a _vscale factor
    (tensors.py:355) that bites on the COMPLIANCE round-trip S = C^-1
    (factor 2/4 on shear off-diagonals); for the stiffness C_ij itself the
    160x factor is the only conversion.
  * y_mod returns SI Pa (elastic.py:199-204, a 9.0e9 factor over the eV/A^3
    moduli), while every mat-* skill quotes GPa: a 1e9 trap.
  * from_independent_strains(vasp=True) multiplies by -0.1 (elastic.py:519),
    the VASP kbar-opposite-sign correction; the MLIP path AtomisticSkills
    uses feeds eV/A^3 stress directly and must NOT take that branch.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.mechanics.operator.edges import (
    compute_elastic_constants,
    contract_poisson_ratio,
    contract_youngs_modulus,
)
from omai.mechanics.operator.nodes import (
    BULK_MODULUS,
    ELASTIC_CONSTANTS,
    POISSON_RATIO,
    SHEAR_MODULUS,
    YOUNGS_MODULUS,
)


PYMATGEN_ELASTIC_CONSTANTS = SpaceRepresentationSpec(
    space=ELASTIC_CONSTANTS,
    representation_name="pymatgen",
    observable_units={"C": "eV_per_A3"},
    code_api={
        "C": "pymatgen.analysis.elasticity.elastic.ElasticTensor (.voigt 6x6), eV/A^3",
    },
    notes=(
        "The elastic stiffness tensor as pymatgen 2025.6.14 stores it: "
        "rank-4 in eV/A^3 (elastic.py:130-136 'in units of eV/A^3'), with "
        ".voigt packing to the 6x6 via the fixed reverse map "
        "[[0,5,4],[5,1,3],[4,3,2]] (tensors.py:381). UNIT TRAP: eV/A^3, not "
        "GPa; 1 eV/A^3 = 160.21766339999996 GPa (CODATA-verified in the scan "
        "review two ways; mat-elasticity multiplies by the truncated "
        "160.2176634). The _vscale factor on .voigt (tensors.py:355) only "
        "bites if the compliance S = C^-1 is round-tripped; k_voigt/g_voigt "
        "index the stiffness 6x6 directly (elastic.py:163-172). Built from "
        "MLIP stresses by ElasticTensor.from_independent_strains via "
        "matcalc.ElasticityCalc."
    ),
)


PYMATGEN_BULK_MODULUS = SpaceRepresentationSpec(
    space=BULK_MODULUS,
    representation_name="pymatgen",
    observable_units={"K": "eV_per_A3"},
    code_api={
        "K": "pymatgen ElasticTensor.k_vrh (= 0.5*(k_voigt + k_reuss)), eV/A^3",
    },
    notes=(
        "Bulk modulus as the Voigt-Reuss-Hill average k_vrh, in eV/A^3 like "
        "the tensor it contracts (elastic.py:163-165 k_voigt = "
        "voigt[:3,:3].mean(), :189-191 k_vrh). Same 160.21766339999996 "
        "eV/A^3 -> GPa factor as the tensor. VRH is a scheme distinction "
        "from the map's Voigt-only contract_bulk_modulus edge (average="
        "voigt), recorded here as provenance, not a unit conversion."
    ),
)


PYMATGEN_SHEAR_MODULUS = SpaceRepresentationSpec(
    space=SHEAR_MODULUS,
    representation_name="pymatgen",
    observable_units={"G": "eV_per_A3"},
    code_api={
        "G": "pymatgen ElasticTensor.g_vrh (= 0.5*(g_voigt + g_reuss)), eV/A^3",
    },
    notes=(
        "Shear modulus as the Voigt-Reuss-Hill average g_vrh, in eV/A^3 "
        "(elastic.py:167-172 g_voigt, :193-196 g_vrh). Same eV/A^3 -> GPa "
        "trap and VRH scheme provenance as the bulk modulus."
    ),
)


PYMATGEN_YOUNGS_MODULUS = SpaceRepresentationSpec(
    space=YOUNGS_MODULUS,
    representation_name="pymatgen",
    observable_units={"E_Y": "Pa"},
    code_api={
        "E_Y": "pymatgen ElasticTensor.y_mod (= 9.0e9 * k_vrh*g_vrh/(3k+g)), SI Pa",
    },
    notes=(
        "UNIT TRAP (review-verified): y_mod returns SI pascal "
        "(elastic.py:199-204, the 9.0e9 factor converting the eV/A^3-scale "
        "GPa moduli to Pa), while mat-elasticity recomputes E in GPa from "
        "GPa moduli. A node equating the two readings is off by 1e9. The "
        "identity is the same contract_youngs_modulus formula "
        "E_Y = 9KG/(3K + G), over VRH moduli."
    ),
)


PYMATGEN_POISSON_RATIO = SpaceRepresentationSpec(
    space=POISSON_RATIO,
    representation_name="pymatgen",
    observable_units={"nu": "dimensionless"},
    code_api={
        "nu": "pymatgen ElasticTensor.homogeneous_poisson, dimensionless",
    },
    notes=(
        "Poisson's ratio as ElasticTensor.homogeneous_poisson "
        "(elastic.py:403), dimensionless, the (3K - 2G)/(2(3K + G)) identity "
        "of the contract_poisson_ratio edge over the VRH moduli."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how pymatgen realizes the edges)
# ---------------------------------------------------------------------------

PYMATGEN_COMPUTE_ELASTIC_CONSTANTS = OperatorRepresentationSpec(
    operator=compute_elastic_constants,
    representation_name="pymatgen",
    discretization_choices={
        "strain_states": (
            "the DeformedStructureSet strain magnitudes matcalc.ElasticityCalc "
            "applies before fitting (default +/-0.5% normal, +/-1% shear)"
        ),
        "fitting": (
            "least-squares fit of stress vs strain per independent component "
            "(ElasticTensor.from_independent_strains, elastic.py:490-519)"
        ),
        "vasp_branch": (
            "from_independent_strains(vasp=True) multiplies c_ij by -0.1 "
            "(elastic.py:519), the VASP kbar-with-opposite-sign correction; "
            "the MLIP eV/A^3 stress path used by AtomisticSkills must NOT "
            "take this branch or every constant flips sign and scale"
        ),
    },
    notes=(
        "pymatgen realizes compute_elastic_constants as a least-squares "
        "finite-strain stress fit (ElasticTensor.from_independent_strains "
        "over a DeformedStructureSet), the same C = -d(sigma)/d(strain) "
        "estimator as the LAMMPS ELASTIC workflow, with the raw stresses "
        "supplied by an external calculator (MLIP or VASP): pymatgen "
        "represents and fits the stress, it never computes it."
    ),
)


PYMATGEN_CONTRACT_YOUNGS_MODULUS = OperatorRepresentationSpec(
    operator=contract_youngs_modulus,
    representation_name="pymatgen",
    scheme_overrides={},
    notes=(
        "ElasticTensor.y_mod (elastic.py:199-204) is this contraction "
        "literally, 9 k_vrh g_vrh / (3 k_vrh + g_vrh), times 9.0e9 into SI "
        "Pa; the VRH inputs are its averaging provenance. The output unit "
        "trap (Pa vs the skills' GPa) lives on the space spec."
    ),
)


PYMATGEN_CONTRACT_POISSON_RATIO = OperatorRepresentationSpec(
    operator=contract_poisson_ratio,
    representation_name="pymatgen",
    scheme_overrides={},
    notes=(
        "ElasticTensor.homogeneous_poisson (elastic.py:403) is this "
        "contraction literally, (3K - 2G)/(2(3K + G)) over the VRH moduli; "
        "dimensionless, no unit trap."
    ),
)
