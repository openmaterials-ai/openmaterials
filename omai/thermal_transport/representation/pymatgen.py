r"""pymatgen adapter specs for the thermal-transport domain.

pymatgen 2025.6.14 as the AtomisticSkills mat-phonon / mat-raman-spectra /
mat-dielectric-response skills use it, anchored in
`scans/pymatgen-atomistic-skills.json` (review 2026-07-09). In this domain
pymatgen is a REPRESENTATION of quantities other engines compute: it
retrieves MP's DFPT phonons and parses VASP OUTCAR response tensors; it does
not run the phonon or response calculation itself.

  operator Space          pymatgen artifact                            units
  ----------------------  -------------------------------------------  ---------
  Frequency               phonon.bandstructure.PhononBandStructure     linear THz
                          (SymmLine), retrieved via mp_api
  PhononDOS               phonon.dos.PhononDos (axis linear THz)       states/THz
  ForceConstants[order=2] MP field ph_force_constants (MontyEncoder)   eV/A^2
  BornCharges             io.vasp.outputs.Outcar.born                  e (dimensionless)
  DielectricTensor        io.vasp.outputs.Outcar.dielectric_tensor     dimensionless

Convention notes (review-settled):

  * pymatgen/MP phonon frequencies are LINEAR THz, the map's canonical
    Frequency unit: CONSISTENT, no 2pi correction (the registry's
    'angular omega_qnu' wording is a description-level label). mat-raman
    converts THz to cm^-1 by 33.3564 (full precision 33.3564095198152).
  * MP ph_force_constants are phonopy-convention eV/A^2 TOTAL force
    constants; QE flfrc are short-range only (Ry/bohr^2, factor
    48.58681221205054, the review-corrected CODATA value).
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.thermal_transport.operator.nodes import (
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    FORCE_CONSTANTS_2,
    FREQUENCY_STATE,
    PHONON_DOS,
)


PYMATGEN_FREQUENCY = SpaceRepresentationSpec(
    space=FREQUENCY_STATE,
    representation_name="pymatgen",
    observable_units={"omega": "linear_THz"},
    code_api={
        "omega": "pymatgen.phonon.bandstructure.PhononBandStructureSymmLine (mp_api retrieval), linear THz",
    },
    notes=(
        "Phonon dispersion as retrieved from Materials Project DFPT "
        "(mpr.materials.phonon.get_bandstructure_from_material_id) and "
        "plotted by PhononBSPlotter. LINEAR THz, matching the map's "
        "canonical Frequency unit exactly: no 2pi correction (settled in "
        "the scan review; ANGULAR_THZ exists only as an adapter-declared "
        "alternative). mat-raman converts to cm^-1 via the truncated "
        "33.3564 (CODATA 33.3564095198152). Representation/retrieval only: "
        "the DFPT engine computed these."
    ),
)


PYMATGEN_PHONON_DOS = SpaceRepresentationSpec(
    space=PHONON_DOS,
    representation_name="pymatgen",
    code_api={
        "g": "pymatgen.phonon.dos.PhononDos (mp_api retrieval), densities against a linear-THz axis",
    },
    notes=(
        "Phonon density of states as retrieved from MP and plotted by "
        "PhononDosPlotter: densities on a LINEAR THz frequency axis (the "
        "map's PhononDOS convention is QE's states/cm^-1 axis, a "
        "33.3564095198152 axis rescale away). No unit is declared for the "
        "density itself: the DOS normalization (per cell vs per formula "
        "unit) rides with the retrieved document and belongs in instance "
        "conditions."
    ),
)


PYMATGEN_FORCE_CONSTANTS_2 = SpaceRepresentationSpec(
    space=FORCE_CONSTANTS_2,
    representation_name="pymatgen",
    observable_units={"phi": "eV_per_A2"},
    code_api={
        "phi": "MP field ph_force_constants via mpr.materials.phonon.get_data_by_id; pymatgen MontyEncoder serialization, eV/A^2",
    },
    notes=(
        "Second-order force constants as the MP ph_force_constants field, "
        "phonopy-convention eV/A^2, serialized/deserialized by pymatgen's "
        "MontyEncoder: representation only. Cross-code traps: QE flfrc "
        "stores Ry/bohr^2 (factor 48.58681221205054, the review-CORRECTED "
        "CODATA value; an earlier draft's 48.5829 was wrong in the 4th "
        "significant figure), and for polar solids phonopy-side FCs are the "
        "TOTAL force constants while QE flfrc are short-range only."
    ),
)


PYMATGEN_BORN_CHARGES = SpaceRepresentationSpec(
    space=BORN_CHARGES,
    representation_name="pymatgen",
    observable_units={"Z_star": "dimensionless"},
    code_api={
        "Z_star": "pymatgen.io.vasp.outputs.Outcar.born (shape (n_atoms, 3, 3)), units of e",
    },
    notes=(
        "Born effective charges parsed from VASP OUTCAR (Outcar.born), "
        "dimensionless in units of the elementary charge, consumed by "
        "mat-raman's Raman-tensor contraction (Z*_k contracted with the "
        "mass-weighted mode displacement). Same node QE grounds via zeu; "
        "pymatgen's role is the parse."
    ),
)


PYMATGEN_DIELECTRIC_TENSOR = SpaceRepresentationSpec(
    space=DIELECTRIC_TENSOR,
    representation_name="pymatgen",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={
        "epsilon_infinity": "pymatgen.io.vasp.outputs.Outcar.dielectric_tensor (3x3), dimensionless",
    },
    notes=(
        "Clamped-ion (electronic) dielectric tensor parsed from VASP OUTCAR "
        "(Outcar.dielectric_tensor), dimensionless, feeding the mat-raman "
        "and mat-dielectric-response flows. Same node QE grounds via "
        "eps_inf; pymatgen's role is the parse."
    ),
)
