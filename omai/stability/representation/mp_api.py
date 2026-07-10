r"""mp-api / Materials Project adapter specs for the stability domain.

The stability slice of the map's first DATABASE rail (see the module docstring
in `omai.dft_ground_state.representation.mp_api` for what "database rail" means:
MP retrieves precomputed VASP-workflow values, it does not run the producing
operators). Anchored in `scans/mp-api-atomistic-skills.json` (deep review
2026-07-09; emmet-core 0.85.1 fields read from source). Pins: mp-api 0.41.2 /
emmet-core 0.85.1.

  operator Space   MP record field (endpoint)                      units
  ---------------  ----------------------------------------------  --------
  FormationEnergy  SummaryDoc.formation_energy_per_atom (summary)  eV/atom
  EnergyAboveHull  SummaryDoc.energy_above_hull (summary/thermo)   eV/atom
  SurfaceEnergy    SummaryDoc.weighted_surface_energy (summary)    J/m^2
  Voltage          InsertionElectrodeDoc.average_voltage           V

Convention traps this module pins down (all source-verified):

  * FormationEnergy uses MP-fitted elemental references + MP2020 corrections
    (distinct from uncorrected_energy_per_atom); its reference state differs
    from the MLIP mat-* route, so a cross-source EXPECTED_AGREE must account
    for the reference and correction scheme. The MP2020 correction state
    belongs in conditions.
  * EnergyAboveHull provenance is the WHOLE hull (a SET of competing-phase
    energies), all at one thermo_type; a GGA hull and an R2SCAN hull give
    different E_hull for the same material, so thermo_type is mandatory
    conditions.
  * SurfaceEnergy: MP serves the Wulff-WEIGHTED aggregate over all facets
    (weighted_surface_energy J/m^2 summary.py:370-373, and
    weighted_surface_energy_EV_PER_ANG2 eV/A^2 summary.py:365-368), NOT a
    single (hkl) facet. So it is a different (aggregate) quantity from the
    per-facet slab records and is not a direct EXPECTED_AGREE with any one
    cu-1XX facet. MP-HAS-IT-BUT-UNUSED: AtomisticSkills computes surface
    energy via MLIP slabs, not MP.
  * Voltage: MP serves average_voltage directly in V (electrode.py:62-64).
    MP-HAS-IT-BUT-UNUSED: an EXPECTED_AGREE partner for the MLIP
    mat-intercalation-voltage route. eV/e = 1 V exactly, no Faraday factor.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.stability.operator.nodes import (
    ENERGY_ABOVE_HULL,
    FORMATION_ENERGY,
    SURFACE_ENERGY,
    VOLTAGE_STATE,
)


MP_API_FORMATION_ENERGY = SpaceRepresentationSpec(
    space=FORMATION_ENERGY,
    representation_name="mp-api",
    observable_units={"dH_f": "ev_per_atom"},
    code_api={
        "dH_f": "mpr.materials.summary.search(fields=['formation_energy_per_atom']).formation_energy_per_atom, eV/atom",
    },
    notes=(
        "Formation energy per atom MP serves directly as a database record: "
        "SummaryDoc.formation_energy_per_atom (summary.py:167-170 'The "
        "formation energy per atom in eV/atom.'), the per-atom phase-diagram "
        "currency, the same FormationEnergy node the pymatgen route grounds "
        "via PhaseDiagram.get_form_energy_per_atom. TRAP: MP's value uses "
        "MP-fitted elemental references + MP2020 anion/+U corrections (distinct "
        "from the raw uncorrected_energy_per_atom), a different reference state "
        "from the AtomisticSkills MLIP mat-* route; a cross-source "
        "EXPECTED_AGREE must account for the reference and correction scheme, "
        "and the MP2020 correction state belongs in conditions. The cleanest "
        "MP-as-instance-source scalar; committed li_s_stable.json carries real "
        "values (Li2S mp-1153 -1.503453288055556, LiS4 mp-995393 "
        "-0.612184769666665 eV/atom)."
    ),
)


MP_API_ENERGY_ABOVE_HULL = SpaceRepresentationSpec(
    space=ENERGY_ABOVE_HULL,
    representation_name="mp-api",
    observable_units={"E_hull": "ev_per_atom"},
    code_api={
        "E_hull": "mpr.materials.summary.search(fields=['energy_above_hull']).energy_above_hull, eV/atom; also mpr.materials.thermo.search(thermo_types=[...])",
    },
    notes=(
        "Convex-hull distance per atom MP serves directly: "
        "SummaryDoc.energy_above_hull (summary.py:172-175 'The energy above "
        "the hull in eV/Atom.'), zero on the hull (is_stable). The same "
        "EnergyAboveHull node the pymatgen route grounds via "
        "PhaseDiagram.get_e_above_hull (mat-stability reports meV/atom, a "
        "factor 1000). PROVENANCE is the WHOLE hull (a SET of competing "
        "phases), all at one thermo_type; a GGA hull and an R2SCAN hull give "
        "different E_hull for the same material, so thermo_type is mandatory "
        "conditions. Committed li_s_stable.json: Li2S (mp-1153) and LiS4 "
        "(mp-995393) both 0.0 eV/atom (on the hull). EXPECTED_AGREE partner "
        "for the mat-stability MLIP route (distinct reference + correction "
        "scheme)."
    ),
)


MP_API_SURFACE_ENERGY = SpaceRepresentationSpec(
    space=SURFACE_ENERGY,
    representation_name="mp-api",
    observable_units={"gamma": "J_per_m2"},
    code_api={
        "gamma": "mpr.materials.summary.search(fields=['weighted_surface_energy']).weighted_surface_energy, J/m^2 (Wulff-weighted aggregate)",
    },
    notes=(
        "Surface energy MP serves as the Wulff-WEIGHTED aggregate over all "
        "facets: weighted_surface_energy in J/m^2 (summary.py:370-373) with "
        "the sibling weighted_surface_energy_EV_PER_ANG2 in eV/A^2 "
        "(summary.py:365-368, 1 eV/A^2 = 16.021766339999996 J/m^2), plus "
        "surface_anisotropy and shape_factor. IMPORTANT distinction: this is "
        "the Wulff aggregate over the whole morphology, NOT a single (hkl) "
        "facet gamma, so it is a different (aggregate) quantity from the "
        "per-facet SurfaceEnergy slab records (e.g. the committed Cu "
        "(100)/(110)/(111) MLIP instances) and is NOT a direct EXPECTED_AGREE "
        "with any one facet. MP-HAS-IT-BUT-UNUSED: AtomisticSkills computes "
        "surface energy via MLIP slabs (mat-surface-energy), not MP; cataloged "
        "here so the encode knows MP can back-fill DFT-database evidence."
    ),
)


MP_API_VOLTAGE = SpaceRepresentationSpec(
    space=VOLTAGE_STATE,
    representation_name="mp-api",
    observable_units={"V_avg": "volt"},
    code_api={
        "V_avg": "mpr.materials.insertion_electrodes.search(working_ion=...).average_voltage, V",
    },
    notes=(
        "Average intercalation voltage MP serves directly in volts: "
        "InsertionElectrodeDoc.average_voltage (electrode.py:62-64 'The "
        "average voltage in V for a particular voltage step.'), the same "
        "Voltage node the pymatgen mat-intercalation-voltage route grounds "
        "in-skill from full/empty/metal cell energies. eV/e = 1 V exactly, no "
        "Faraday factor. Companion fields capacity_grav (mAh/g), capacity_vol "
        "(mAh/cc), energy_grav (Wh/kg), energy_vol (Wh/l) have no map analog. "
        "MP-HAS-IT-BUT-UNUSED: AtomisticSkills computes voltage via MLIP, not "
        "the insertion_electrodes endpoint, so the MP record is a DFT-database "
        "instance source and an EXPECTED_AGREE partner for the committed MLIP "
        "LiFePO4 record; the working_ion is provenance in conditions."
    ),
)
