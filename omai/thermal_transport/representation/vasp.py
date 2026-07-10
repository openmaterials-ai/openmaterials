r"""VASP adapter specs for the thermal-transport domain.

VASP as AtomisticSkills (arXiv 2605.24002) reads it for the two static
linear-response tensors the non-analytic correction needs, anchored in
`scans/atomate2-vasp-atomistic-skills.json` (review 2026-07-09). These are the
DFT-domain PRODUCERS (VASP LEPSILON directly, via pymatgen Outcar) of the same
BornCharges / DielectricTensor nodes the pymatgen scan catalogs and QE grounds;
a cross-domain rail like the pymatgen encode placed on these thermal nodes.

  operator Space    VASP artifact                                 units
  ----------------  --------------------------------------------  -------------
  BornCharges       Outcar.born (LEPSILON)                        e (dimensionless)
  DielectricTensor  Outcar.dielectric_tensor (LEPSILON, static)   dimensionless

Convention notes (review-verified against pymatgen 2025.6.14):

  * The static clamped-ion eps_inf (LEPSILON) is the map's DielectricTensor
    (the omega->infinity limit). The FREQUENCY-DEPENDENT eps(omega) spectrum
    from LOPTICS / OpticsMaker is a distinct spectroscopic observable the
    atomate2/VASP scan defers (a spectrum-valued type the map lacks), NOT this
    node.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import (
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
)


VASP_BORN_CHARGES = SpaceRepresentationSpec(
    space=BORN_CHARGES,
    representation_name="vasp",
    observable_units={"Z_star": "dimensionless"},
    code_api={
        "Z_star": "pymatgen Outcar.born (VASP LEPSILON, 'BORN EFFECTIVE CHARGES' section), shape (n_atoms, 3, 3), units of e",
    },
    notes=(
        "Born effective charges parsed from the VASP OUTCAR "
        "(pymatgen Outcar.born, 'BORN EFFECTIVE CHARGES' section, "
        "outputs.py:3209-3257; vasp_parser.py:126), dimensionless in units of "
        "the elementary charge, produced by a LEPSILON=.TRUE. static "
        "linear-response run. Same node QE grounds via zeu and the pymatgen "
        "scan catalogs for mat-raman; here VASP is the direct DFT-domain "
        "producer, feeding the non-analytic LO-TO correction."
    ),
)


VASP_DIELECTRIC_TENSOR = SpaceRepresentationSpec(
    space=DIELECTRIC_TENSOR,
    representation_name="vasp",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={
        "epsilon_infinity": "pymatgen Outcar.dielectric_tensor (VASP LEPSILON, static clamped-ion 3x3), dimensionless",
    },
    notes=(
        "The static clamped-ion (electronic) dielectric tensor eps_inf parsed "
        "from the VASP OUTCAR (pymatgen Outcar.dielectric_tensor), "
        "dimensionless, produced by LEPSILON=.TRUE. Same node QE grounds via "
        "eps_inf and the pymatgen scan catalogs; VASP is the direct "
        "DFT-domain producer. It is the omega->infinity limit: the "
        "FREQUENCY-DEPENDENT eps(omega) spectrum from LOPTICS / OpticsMaker "
        "is a distinct spectroscopic observable the scan defers (needs a "
        "spectrum-valued space type), NOT this static tensor."
    ),
)
