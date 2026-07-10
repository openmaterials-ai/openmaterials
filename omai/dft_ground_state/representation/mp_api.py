r"""mp-api / Materials Project adapter specs for the DFT ground-state domain.

The map's FIRST database rail. Every other rail is an ENGINE (QE, VASP, LAMMPS,
a MACE checkpoint): you run it and it produces a value. Materials Project is a
DATABASE: its artifacts are document-model records that mp_api.client.MPRester
retrieves, each carrying an already-computed value for a mapped quantity. Those
values were themselves produced by VASP DFT workflows (MP's provenance is the
atomate2/VASP stack the vasp rail catalogs), so MP is a RETRIEVAL representation
of nodes the map already grounds, not a new producer.

Anchored in `scans/mp-api-atomistic-skills.json` (+ .md, deep review
2026-07-09; every emmet document field opened and read from the installed
source). Pins: mp-api 0.41.2 / emmet-core 0.85.1. This is the DFT-ground-state
slice of the cross-domain mp-api rail (dft, stability, mechanics, thermal share
the one rail, exactly as the vasp rail does):

  operator Space   MP record field (endpoint)                     units
  ---------------  ---------------------------------------------  --------
  Structure        SummaryDoc.structure / get_structure_by_id     angstrom
  MagneticMoment   MagnetismDoc.magmoms (per-site list)           mu_B
  BandGap          SummaryDoc.band_gap                            eV

Convention traps this module pins down (all source-verified against
emmet-core 0.85.1):

  * MAGNETIZATION (headline). magmoms is a PER-SITE list in mu_B
    (magnetism.py:52-55) and matches the per-site MagneticMoment node. The
    per-cell total_magnetization is a DIFFERENT quantity: it is abs()-ed at
    populate time (magnetism.py:81-83, sign LOST, ferri/antiferromagnetic
    sign structure unrecoverable), and it is NOT per-site and NOT per-formula-
    unit (the per-f.u. value is the separate total_magnetization_normalized_
    formula_units field, mu_B/f.u.). Do not feed total_magnetization to this
    node. MP magmoms are also CollinearMagneticStructureAnalyzer-rounded
    (round_magmoms=True), so the per-cell total need not equal their sum.
  * BAND_GAP is the Kohn-Sham gap in eV (summary.py:209-211), NOT the
    fundamental quasiparticle gap; semilocal functionals underestimate it, so
    it rides with the thermo_type / functional provenance. Its provenance is
    the summary thermo (default GGA_GGA+U i.e. PBE for the summary route).
  * emmet units contract: field names and units are read from the pinned
    emmet-core 0.85.1; a future emmet could re-normalize a default, so an
    encode relying on a field's units pins that emmet version.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.dft_ground_state.operator.nodes import (
    BAND_GAP,
    MAGNETIC_MOMENT_STATE,
)
from omai.materials.operator.shared_primitives import STRUCTURE


MP_API_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="mp-api",
    code_api={
        "structure": "mpr.materials.summary.search(fields=['structure']).structure / mpr.materials.get_structure_by_material_id(material_id) -> pymatgen Structure, angstrom",
    },
    notes=(
        "The lowest-energy relaxed crystal structure MP serves as a database "
        "record: a pymatgen Structure (SummaryDoc.structure, summary.py:422-426 "
        "'The lowest energy structure for this material.'), lattice and "
        "positions in angstrom, the same opaque Structure node QE grounds via "
        "CELL_PARAMETERS and VASP as CONTCAR. get_structure_by_material_id "
        "hands it back directly (get_structure_by_id.py:43); AtomisticSkills "
        "serializes it to CIF via pymatgen CifWriter. A RETRIEVAL of a "
        "precomputed VASP structure, not a fresh solve. Opaque at the operator "
        "layer: an artifact, not a numeric unit, and (being non-scalar) not an "
        "instance-store value, though its material_id is the provenance handle "
        "the scalar MP records share."
    ),
)


MP_API_MAGNETIC_MOMENT = SpaceRepresentationSpec(
    space=MAGNETIC_MOMENT_STATE,
    representation_name="mp-api",
    observable_units={"m": "mu_B"},
    code_api={
        "m": "mpr.materials.magnetism.search().magmoms[i] (per-site list, mu_B); MagnetismDoc.magmoms",
    },
    notes=(
        "Per-site magnetic moments in Bohr magnetons from MP's spin-polarized "
        "ground state: MagnetismDoc.magmoms, a per-site list (magnetism.py:"
        "52-55), the same per-site MagneticMoment node VASP (Outcar) and the "
        "pymatgen / matgl rails ground. MAGNETIZATION TRAP (this module's "
        "headline): the per-cell total_magnetization is a DIFFERENT quantity, "
        "NOT this node. It is abs()-ed at populate time (magnetism.py:81-83, "
        "in-source comment 'not necessarily == sum(magmoms)'), so the SIGN is "
        "lost and ferrimagnetic / antiferromagnetic sign structure cannot be "
        "recovered from it; it is per-cell (not per-site) and not per-formula-"
        "unit (the per-f.u. value is the separate "
        "total_magnetization_normalized_formula_units field, mu_B/f.u., and "
        "the per-volume value is total_magnetization_normalized_vol, "
        "mu_B/A^3). Only the per-site magmoms feed this node. MP magmoms are "
        "CollinearMagneticStructureAnalyzer-rounded (round_magmoms=True, "
        "magnetism.py:84-88); the FM/AFM/FiM/NM ordering is a downstream label "
        "over these moments, not part of the node."
    ),
)


MP_API_BAND_GAP = SpaceRepresentationSpec(
    space=BAND_GAP,
    representation_name="mp-api",
    observable_units={"E_gap": "ev"},
    code_api={
        "E_gap": "mpr.materials.summary.search(fields=['band_gap']).band_gap, eV; also bs.get_band_gap()['energy'] from the electronic-structure endpoint",
    },
    notes=(
        "The electronic band gap in eV MP serves as a database record: "
        "SummaryDoc.band_gap (summary.py:209-211 'Band gap energy in eV'), the "
        "single most-used MP electronic field (mat-db-mp query_mp.py:9, "
        "mat-electronic-structure get_mp_electronic_structure.py:57-84 via "
        "bs.get_band_gap()['energy']). This is the Kohn-Sham eigenvalue gap, "
        "the KS gap (quantity=ks_gap), NOT the fundamental (quasiparticle) "
        "gap: semilocal functionals underestimate it, so it is strongly "
        "exchange-correlation-functional dependent and rides with the "
        "thermo_type provenance (the summary route's default thermo is "
        "GGA_GGA+U, i.e. PBE). is_metal, is_gap_direct, cbm/vbm, and efermi "
        "are downstream labels over the same band structure, not part of this "
        "scalar node; the band structure E(k) and electronic DOS are hidden "
        "electronic intermediates. A RETRIEVAL representation of the BandGap "
        "node VASP grounds via BSVasprun; the committed AtomisticSkills "
        "li_s_stable.json is a real MP band_gap instance source (Li2S 3.3862 "
        "eV, LiS4 2.1989 eV)."
    ),
)
