r"""mp-api / Materials Project adapter specs for the thermal-transport domain.

The thermal-response slice of the map's first DATABASE rail (see
`omai.dft_ground_state.representation.mp_api` for what "database rail" means).
Anchored in `scans/mp-api-atomistic-skills.json` (deep review 2026-07-09;
emmet-core 0.85.1 summary.py read from source). Pins: mp-api 0.41.2 /
emmet-core 0.85.1.

  operator Space     MP record field (summary/dielectric endpoint)   units
  -----------------  ----------------------------------------------  ------
  DielectricTensor   SummaryDoc.e_electronic                         1

Convention trap this module pins down:

  * The map's DielectricTensor node is the ELECTRONIC clamped-ion eps_infinity
    (dimensionless). MP's e_electronic is exactly that electronic contribution,
    a scalar reduction of the tensor. e_total = e_electronic + e_ionic, so
    e_total and e_ionic are DISTINCT quantities the map's electronic-only node
    does NOT represent; the refractive index n ~ sqrt(e_electronic). Do not
    conflate e_total with eps_infinity.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import DIELECTRIC_TENSOR


MP_API_DIELECTRIC_TENSOR = SpaceRepresentationSpec(
    space=DIELECTRIC_TENSOR,
    representation_name="mp-api",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={
        "epsilon_infinity": "mpr.materials.summary.search(fields=['e_electronic']).e_electronic, dimensionless (electronic dielectric constant)",
    },
    notes=(
        "The electronic (clamped-ion) dielectric constant MP serves as a "
        "database record: SummaryDoc.e_electronic (summary.py:338-356, "
        "dimensionless), the electronic contribution ~ eps_infinity, a scalar "
        "isotropic reduction of the map's DielectricTensor node (the electronic "
        "part only). TRAP: e_total = e_electronic + e_ionic, so MP's e_total "
        "and e_ionic are DISTINCT quantities this electronic-only node does "
        "NOT represent (the frequency-dependent dielectric FUNCTION is a "
        "separate deferred node); the refractive index n ~ sqrt(e_electronic). "
        "A RETRIEVAL representation of the same node the vasp LEPSILON route "
        "grounds directly; AtomisticSkills reaches dielectric mainly through "
        "the VASP LEPSILON/LOPTICS path, not this MP field (MP-has-it-but-"
        "unused). The functional (thermo_type) is the conditions provenance."
    ),
)
