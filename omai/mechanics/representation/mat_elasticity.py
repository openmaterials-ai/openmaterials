r"""mat-elasticity skill as a representation over the mechanics DAG.

The AtomisticSkills mat-elasticity skill (omai/materials/skills_catalog.json)
computes the elastic response by finite-strain stress fitting
(C_{ij} = d sigma_i / d eps_j) with an MLIP, via matcalc / MACE / MatGL /
FairChem. Its `produces` map onto the mechanics nodes where they match:

  catalog quantity     symbol   -> mechanics node        units
  -------------------  -------  ----------------------  -----
  elastic_tensor       C_{ij}   -> ElasticConstants       GPa
  bulk_modulus_vrh     B_{VRH}  -> BulkModulus             GPa
  shear_modulus_vrh    G_{VRH}  -> ShearModulus            GPa
  youngs_modulus       E        -> (catalog-only: no node, skipped)
  poissons_ratio       nu       -> (catalog-only: no node, skipped)

Young's modulus and Poisson's ratio are further isotropic combinations of K and
G; they have no map node yet, so they are deliberately not represented here (the
skill still produces them; the map simply does not carry them). The VRH label is
the Voigt-Reuss-Hill (Hill) average, a scheme distinct from the Voigt-only
contraction the mechanics contract_bulk_modulus / contract_shear_modulus edges
encode; that distinction is recorded in the notes rather than as a numeric
conversion, since both are averages of the same stiffness tensor.
"""
from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.mechanics.operator.nodes import (
    BULK_MODULUS,
    ELASTIC_CONSTANTS,
    SHEAR_MODULUS,
)

MAT_ELASTICITY_ELASTIC_CONSTANTS = SpaceRepresentationSpec(
    space=ELASTIC_CONSTANTS,
    representation_name="mat-elasticity",
    observable_units={"C": "GPa"},
    code_api={"C": "matcalc ElasticityCalc elastic_tensor (Voigt 6x6), GPa"},
    notes=(
        "The elastic stiffness tensor C_{ij} from finite-strain stress fitting "
        "(operation 'finite-strain stress fitting', closed form "
        "C_{ij} = d sigma_i / d eps_j) with an MLIP (matcalc over MACE / MatGL "
        "/ FairChem potentials). Emitted as the Voigt 6x6 matrix in GPa; the "
        "map node is the full rank-4 tensor it packs."
    ),
)

MAT_ELASTICITY_BULK_MODULUS = SpaceRepresentationSpec(
    space=BULK_MODULUS,
    representation_name="mat-elasticity",
    observable_units={"K": "GPa"},
    code_api={"K": "matcalc ElasticityCalc bulk_modulus_vrh (B_VRH), GPa"},
    notes=(
        "The bulk modulus reported as the Voigt-Reuss-Hill (Hill) average "
        "B_{VRH}, in GPa. VRH is the mean of the Voigt (uniform-strain) and "
        "Reuss (uniform-stress) bounds; the mechanics contract_bulk_modulus "
        "edge encodes the Voigt member (average=voigt), so a VRH value differs "
        "from the pure-Voigt K by the Reuss contribution (a scheme distinction, "
        "not a unit conversion)."
    ),
)

MAT_ELASTICITY_SHEAR_MODULUS = SpaceRepresentationSpec(
    space=SHEAR_MODULUS,
    representation_name="mat-elasticity",
    observable_units={"G": "GPa"},
    code_api={"G": "matcalc ElasticityCalc shear_modulus_vrh (G_VRH), GPa"},
    notes=(
        "The shear modulus reported as the Voigt-Reuss-Hill (Hill) average "
        "G_{VRH}, in GPa. As with the bulk modulus, VRH is the Voigt-Reuss "
        "mean; the mechanics contract_shear_modulus edge encodes the Voigt "
        "member (average=voigt), so VRH and the pure-Voigt G differ by the "
        "Reuss contribution."
    ),
)
