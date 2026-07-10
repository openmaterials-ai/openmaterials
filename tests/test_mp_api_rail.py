"""The mp-api / Materials Project representation rail (mp-api scan, arXiv 2605.24002).

The map's FIRST database rail: MP is a DATABASE, not an engine. Its artifacts
are document-model records that mp_api.client.MPRester retrieves, each carrying
an already-computed VASP-workflow value for a mapped quantity. The rail is
REPRESENTATION-ONLY (no new nodes, no operator specs: MP retrieves, it does not
run the producing operators) and cross-domain (dft, stability, mechanics,
thermal share the one rail, exactly as the vasp rail does).

Anchored in scans/mp-api-atomistic-skills.json (deep review 2026-07-09,
emmet-core 0.85.1 fields read from source). Two load-bearing unit traps:
MP moduli are GPa DIRECTLY (no 160.2176634 eV/A^3 factor), and young_modulus is
SI Pa (a 1e9 trap); MagneticMoment is the per-site magmoms list (the per-cell
total_magnetization is abs()-ed, sign lost, and is NOT this node).

Evidence: the six MP-retrieved values from the committed AtomisticSkills
mat-db-mp query_mp example (examples/query_mp/li_s_stable.json): band gap,
formation energy, and energy above hull for Li2S (mp-1153) and LiS4 (mp-995393).
"""

from __future__ import annotations

from omai.map_data import DOMAINS, build_codes, build_instances
from omai.operator.identity import node_id


# --------------------------------------------------------------------------
# The rail is a cross-domain DATABASE rail with exactly the review-verified
# space specs and no operator specs.
# --------------------------------------------------------------------------

def test_mp_api_rail_spans_four_domains_in_build_codes():
    """The mp-api rail is cross-domain like the vasp rail: dft
    (Structure/MagneticMoment/BandGap), stability
    (FormationEnergy/EnergyAboveHull/SurfaceEnergy/Voltage), mechanics
    (ElasticConstants/BulkModulus/ShearModulus/YoungsModulus/PoissonRatio),
    thermal (DielectricTensor) = thirteen space specs on one rail."""
    mp = build_codes(DOMAINS)["mp-api"]
    assert set(mp) == {
        "Structure", "MagneticMoment", "BandGap",
        "FormationEnergy", "EnergyAboveHull", "SurfaceEnergy", "Voltage",
        "ElasticConstants", "BulkModulus", "ShearModulus",
        "YoungsModulus", "PoissonRatio",
        "DielectricTensor",
    }


def test_mp_api_declared_units_are_the_review_verified_ones():
    mp = build_codes(DOMAINS)["mp-api"]
    # eV/atom energetics, GPa moduli, SI Pa young_modulus (the 1e9 trap),
    # mu_B per-site moments, eV gap, volts, J/m^2 surface energy, dimensionless
    # poisson / dielectric. Structure is opaque (no numeric unit).
    assert mp["FormationEnergy"]["unit"] == "ev_per_atom"
    assert mp["EnergyAboveHull"]["unit"] == "ev_per_atom"
    assert mp["BulkModulus"]["unit"] == "GPa"
    assert mp["ShearModulus"]["unit"] == "GPa"
    assert mp["ElasticConstants"]["unit"] == "GPa"
    assert mp["YoungsModulus"]["unit"] == "Pa"
    assert mp["PoissonRatio"]["unit"] == "dimensionless"
    assert mp["MagneticMoment"]["unit"] == "mu_B"
    assert mp["BandGap"]["unit"] == "ev"
    assert mp["Voltage"]["unit"] == "volt"
    assert mp["SurfaceEnergy"]["unit"] == "J_per_m2"
    assert mp["DielectricTensor"]["unit"] == "dimensionless"
    assert mp["Structure"]["unit"] is None


def test_mp_api_declares_no_operator_specs():
    """MP retrieves precomputed values; it does not run the producing
    operators, so the rail carries only SpaceRepresentationSpecs (the
    VASP-workflow provenance lives in the spec notes via thermo_type). No
    OperatorRepresentationSpec anywhere in the rail's four modules."""
    import importlib
    import pkgutil

    from omai.representation.adapter import (
        OperatorRepresentationSpec,
        SpaceRepresentationSpec,
    )

    n_space = 0
    for domain in DOMAINS:
        pkg = domain.representation_package
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name != "mp_api":
                continue
            mod = importlib.import_module(f"{pkg.__name__}.{info.name}")
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, OperatorRepresentationSpec):
                    assert obj.representation_name != "mp-api", (
                        f"mp-api rail must not carry operator specs: {attr}"
                    )
                if (isinstance(obj, SpaceRepresentationSpec)
                        and obj.representation_name == "mp-api"):
                    n_space += 1
    assert n_space == 13


# --------------------------------------------------------------------------
# The two headline elasticity unit traps, verified on the actual specs.
# --------------------------------------------------------------------------

def test_mp_api_moduli_are_gpa_not_ev_per_a3():
    """MP serves the moduli in GPa directly; the 160.2176634 eV/A^3 -> GPa
    factor that the raw-pymatgen MLIP route needs must NOT be applied."""
    from omai.mechanics.representation.mp_api import (
        MP_API_BULK_MODULUS,
        MP_API_ELASTIC_CONSTANTS,
        MP_API_SHEAR_MODULUS,
    )

    assert MP_API_BULK_MODULUS.observable_units == {"K": "GPa"}
    assert MP_API_SHEAR_MODULUS.observable_units == {"G": "GPa"}
    assert MP_API_ELASTIC_CONSTANTS.observable_units == {"C": "GPa"}
    for spec in (MP_API_BULK_MODULUS, MP_API_SHEAR_MODULUS,
                 MP_API_ELASTIC_CONSTANTS):
        assert "160.2176634" in spec.notes  # the factor NOT to apply
        assert "GPa" in spec.notes


def test_mp_api_young_modulus_is_si_pascal_the_1e9_trap():
    """young_modulus is SI Pa, DIVIDE by 1e9 for GPa (the pymatgen y_mod
    9.0e9 factor carries GPa -> Pa)."""
    from omai.mechanics.representation.mp_api import MP_API_YOUNGS_MODULUS
    from omai.representation.units import conversion_factor

    assert MP_API_YOUNGS_MODULUS.observable_units == {"E_Y": "Pa"}
    notes = MP_API_YOUNGS_MODULUS.notes
    assert "SI" in notes and "Pa" in notes
    assert "9.0e9" in notes
    assert "1e9" in notes
    # 1 GPa = 1e9 Pa on the shared energy-density dimension.
    assert abs(conversion_factor("GPa", "Pa") - 1e9) < 1e-3


# --------------------------------------------------------------------------
# The magnetization trap: per-site magmoms, NOT the abs()-ed per-cell total.
# --------------------------------------------------------------------------

def test_mp_api_magnetic_moment_is_per_site_magmoms_not_total():
    from omai.dft_ground_state.representation.mp_api import MP_API_MAGNETIC_MOMENT

    assert MP_API_MAGNETIC_MOMENT.observable_units == {"m": "mu_B"}
    notes = MP_API_MAGNETIC_MOMENT.notes
    assert "magmoms" in notes
    assert "per-site" in notes
    assert "total_magnetization" in notes
    assert "abs()" in notes  # the sign-loss caveat
    assert "sign" in notes.lower()


def test_mp_api_band_gap_records_the_ks_gap_caveat():
    from omai.dft_ground_state.representation.mp_api import MP_API_BAND_GAP

    assert MP_API_BAND_GAP.observable_units == {"E_gap": "ev"}
    notes = MP_API_BAND_GAP.notes
    assert "Kohn-Sham" in notes
    assert "NOT the fundamental" in notes
    assert "functional" in notes
    assert "thermo_type" in notes  # the provenance handle


def test_mp_api_is_named_the_first_database_rail():
    """The rail's identity as a DATABASE (not an engine) is stated plainly in
    the notes, per the orchestrator decision."""
    from omai.dft_ground_state.representation.mp_api import MP_API_STRUCTURE

    assert MP_API_STRUCTURE.observable_units == {}  # Structure is opaque
    assert "RETRIEVAL" in MP_API_STRUCTURE.notes
    from omai.dft_ground_state.representation import mp_api as dft_mp_api
    assert "DATABASE" in dft_mp_api.__doc__
    assert "FIRST database rail" in dft_mp_api.__doc__


# --------------------------------------------------------------------------
# The six committed MP-retrieved instance records (evidence).
# --------------------------------------------------------------------------

def test_mp_api_instances_pin_the_live_node_uids_and_values():
    """The six MP-retrieved values recorded verbatim from the committed
    AtomisticSkills mat-db-mp query_mp example (li_s_stable.json): band gap,
    formation energy, and energy above hull for Li2S (mp-1153) and LiS4
    (mp-995393). Following the committed MP-provenance convention: mp-id in
    the material field, ref = the fetching skill, thermo in conditions."""
    from omai.dft_ground_state.operator.nodes import BAND_GAP
    from omai.stability.operator.nodes import (
        ENERGY_ABOVE_HULL,
        FORMATION_ENERGY,
    )

    insts = build_instances()
    mp = [i for i in insts if i["source"]["ref"] == "atomisticskills-mat-db-mp"]
    assert len(mp) == 6

    by_key = {(it["variable"], it["material"]): it for it in mp}

    # Band gaps (the orchestrator-named values), eV, Kohn-Sham.
    gaps = {"Li2S (mp-1153)": 3.3862, "LiS4 (mp-995393)": 2.1989}
    for mat, val in gaps.items():
        it = by_key[("BandGap", mat)]
        assert it["value"] == val
        assert it["units"] == "eV"
        assert it["source"]["kind"] == "simulation"
        assert it["conditions"]["thermo"] == "GGA+U"
        assert it["node_uid"] == node_id(BAND_GAP)

    # Formation energies, eV/atom, MP2020-corrected.
    forms = {
        "Li2S (mp-1153)": -1.503453288055556,
        "LiS4 (mp-995393)": -0.612184769666665,
    }
    for mat, val in forms.items():
        it = by_key[("FormationEnergy", mat)]
        assert it["value"] == val
        assert it["units"] == "eV/atom"
        assert it["conditions"]["correction"] == "MP2020"
        assert it["node_uid"] == node_id(FORMATION_ENERGY)

    # Both on the hull (stable), eV/atom.
    for mat in ("Li2S (mp-1153)", "LiS4 (mp-995393)"):
        it = by_key[("EnergyAboveHull", mat)]
        assert it["value"] == 0.0
        assert it["units"] == "eV/atom"
        assert it["node_uid"] == node_id(ENERGY_ABOVE_HULL)


def test_mp_api_instances_follow_the_committed_provenance_convention():
    """No MP instance uses ref='materials-project' (the not-adopted scanner
    proposal); each puts the mp-id in the material field and names the fetching
    skill as ref, matching the committed li2o-mp-1960 convention."""
    insts = build_instances()
    mp = [i for i in insts if i["source"]["ref"] == "atomisticskills-mat-db-mp"]
    for it in mp:
        assert "materials-project" != it["source"]["ref"]
        assert "mp-" in it["material"]  # mp-id in the material field
        assert it["uncertainty"] is None  # MP serves no per-value uncertainty
        assert "li_s_stable.json" in it["source"]["detail"]
