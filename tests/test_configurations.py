"""Tests for the configuration layer (omai/configurations.py).

Canonicalization determinism, the StructureMatcher dedup gate, from_file
round-trips against committed POSCAR/CIF fixtures, from_mp mocked offline, and
the reduced-metadata / file-backed path for large cells. Offline only:
from_mp's network call is monkeypatched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai import configurations as cfg

pytest.importorskip("pymatgen")

_FIX = Path(__file__).resolve().parent / "fixtures" / "configurations"


def _primitive_si():
    from pymatgen.core import Lattice, Structure

    a = 5.468
    lat = Lattice([[0, a / 2, a / 2], [a / 2, 0, a / 2], [a / 2, a / 2, 0]])
    return Structure(lat, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])


# --------------------------------------------------------------------------
# Canonicalization determinism (spec section 8).
# --------------------------------------------------------------------------

def test_shuffled_sites_hash_identically():
    from pymatgen.core import Structure

    si = _primitive_si()
    shuffled = Structure.from_sites(list(reversed(list(si))))
    assert cfg.canonical_uid(si) == cfg.canonical_uid(shuffled)


def test_supercell_of_primitive_hashes_identically():
    si = _primitive_si()
    supercell = si * (2, 2, 2)
    assert len(supercell) == 16
    assert cfg.canonical_uid(si) == cfg.canonical_uid(supercell)


def test_strained_cell_hashes_differently():
    from pymatgen.core import Lattice, Structure

    si = _primitive_si()
    a = 5.468 * 1.02
    lat = Lattice([[0, a / 2, a / 2], [a / 2, 0, a / 2], [a / 2, a / 2, 0]])
    strained = Structure(lat, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    assert cfg.canonical_uid(si) != cfg.canonical_uid(strained)


def test_uid_is_deterministic_across_calls():
    si = _primitive_si()
    assert cfg.canonical_uid(si) == cfg.canonical_uid(si)
    assert len(cfg.canonical_uid(si)) == 64


# --------------------------------------------------------------------------
# from_file round-trips (POSCAR and CIF fixtures) to the SAME uid.
# --------------------------------------------------------------------------

def test_from_file_poscar_and_cif_agree_with_builder():
    poscar = cfg.from_file(_FIX / "si_mp149.poscar")
    cif = cfg.from_file(_FIX / "si_mp149.cif")
    builder = _primitive_si()
    u_poscar = cfg.canonical_uid(poscar)
    assert u_poscar == cfg.canonical_uid(cif)
    assert u_poscar == cfg.canonical_uid(builder)


def test_from_file_missing_raises():
    with pytest.raises(cfg.ConfigurationError):
        cfg.from_file(_FIX / "does_not_exist.poscar")


# --------------------------------------------------------------------------
# record_configuration writes, round-trips through load, and is content-addressed.
# --------------------------------------------------------------------------

def test_record_configuration_round_trips(tmp_path):
    si = _primitive_si()
    uid = cfg.record_configuration(
        si, name="Si diamond primitive",
        provenance=[{"kind": "database", "ref": "materials-project",
                     "detail": "mp-149, GGA"}],
        external_id={"materials_project": "mp-149"},
        config_dir=tmp_path)
    assert uid == cfg.canonical_uid(si)

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    record = json.loads(written[0].read_text())
    assert record["name"] == "Si diamond primitive"
    assert record["formula"] == "Si"
    assert record["canonical"]["uid"] == uid
    assert record["canonical"]["spacegroup"] == 227
    assert record["canonical"]["natoms_primitive"] == 2
    assert record["external_ids"] == {"materials_project": "mp-149"}
    assert record["structure"]["@class"] == "Structure"

    loaded = cfg.load(uid, config_dir=tmp_path)
    assert cfg.canonical_uid(loaded) == uid


def test_record_from_poscar_path_matches_from_mp_builder(tmp_path):
    """The acceptance identity: the POSCAR fixture and the builder Si (the same
    cell from_mp would return) mint the SAME canonical uid."""
    uid_file = cfg.record_configuration(
        _FIX / "si_mp149.poscar", name="Si from POSCAR",
        provenance=[{"kind": "paper", "ref": "paper:test", "detail": "fixture"}],
        config_dir=tmp_path)
    assert uid_file == cfg.canonical_uid(_primitive_si())


# --------------------------------------------------------------------------
# The dedup gate.
# --------------------------------------------------------------------------

def test_hash_identical_resubmission_appends_provenance(tmp_path):
    si = _primitive_si()
    uid1 = cfg.record_configuration(
        si, name="Si diamond primitive",
        provenance=[{"kind": "database", "ref": "materials-project",
                     "detail": "mp-149, GGA"}],
        config_dir=tmp_path)
    # A shuffled resubmission (same cell, different site order) hashes identically
    # and appends provenance instead of minting a second record.
    from pymatgen.core import Structure

    shuffled = Structure.from_sites(list(reversed(list(si))))
    uid2 = cfg.record_configuration(
        shuffled, name="Si diamond primitive",
        provenance=[{"kind": "paper", "ref": "paper:esfarjani-2011",
                     "detail": "Sec. II"}],
        config_dir=tmp_path)
    assert uid1 == uid2
    assert len(list(tmp_path.glob("*.json"))) == 1
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert len(record["provenance"]) == 2


def test_matcher_equivalent_but_not_hash_identical_flags_duplicate(tmp_path):
    """A cell that StructureMatcher accepts as equivalent but whose canonical
    hash differs (a slightly perturbed cell within matcher tolerance) is FLAGGED
    for review, never silently merged."""
    from pymatgen.core import Lattice, Structure

    si = _primitive_si()
    cfg.record_configuration(
        si, name="Si diamond primitive",
        provenance=[{"kind": "database", "ref": "materials-project",
                     "detail": "mp-149"}],
        config_dir=tmp_path)

    # A 0.5% uniformly scaled cell: StructureMatcher normalizes cell volume, so
    # it accepts the scaled cell as equivalent, but the lattice constant differs
    # at 6 decimals so the canonical hash differs. Matcher-equivalent, different
    # uid: the human-review path.
    a = 5.468 * 1.005
    lat = Lattice([[0, a / 2, a / 2], [a / 2, 0, a / 2], [a / 2, a / 2, 0]])
    scaled = Structure(lat, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    assert cfg.canonical_uid(scaled) != cfg.canonical_uid(si)
    with pytest.raises(cfg.DuplicateFlag) as exc:
        cfg.record_configuration(
            scaled, name="Si scaled",
            provenance=[{"kind": "paper", "ref": "paper:x", "detail": "y"}],
            config_dir=tmp_path)
    assert exc.value.uid == cfg.canonical_uid(si)
    # Only the first record on disk; the perturbed one was not written.
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_distinct_material_mints_a_second_record(tmp_path):
    from pymatgen.core import Lattice, Structure

    si = _primitive_si()
    cfg.record_configuration(
        si, name="Si diamond primitive",
        provenance=[{"kind": "database", "ref": "mp", "detail": "mp-149"}],
        config_dir=tmp_path)
    # Primitive Ge (same diamond structure, different element): not a duplicate.
    a = 5.76
    lat = Lattice([[0, a / 2, a / 2], [a / 2, 0, a / 2], [a / 2, a / 2, 0]])
    ge = Structure(lat, ["Ge", "Ge"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    cfg.record_configuration(
        ge, name="Ge diamond primitive",
        provenance=[{"kind": "database", "ref": "mp", "detail": "mp-32"}],
        config_dir=tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 2


# --------------------------------------------------------------------------
# from_mp mocked offline.
# --------------------------------------------------------------------------

def test_from_mp_mocked(tmp_path, monkeypatch):
    si = _primitive_si()

    class _FakeMPRester:
        def __init__(self, key):
            assert key == "fake-key"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_structure_by_material_id(self, mp_id):
            assert mp_id == "mp-149"
            return si

    import mp_api.client as mpc

    monkeypatch.setattr(mpc, "MPRester", _FakeMPRester)
    monkeypatch.setenv("MP_API_KEY", "fake-key")
    uid = cfg.from_mp("mp-149", config_dir=tmp_path)
    assert uid == cfg.canonical_uid(si)
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["external_ids"] == {"materials_project": "mp-149"}


def test_from_mp_without_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MP_API_KEY", raising=False)
    monkeypatch.delenv("PMG_MAPI_KEY", raising=False)
    # Point the env loader at an empty file so the real .env cannot supply a key.
    import omai.paper_parser.env as env

    monkeypatch.setattr(env, "load_env", lambda *a, **k: None)
    with pytest.raises(cfg.ConfigurationError):
        cfg.from_mp("mp-149", config_dir=tmp_path)


# --------------------------------------------------------------------------
# Molecule (non-periodic) envelope.
# --------------------------------------------------------------------------

def test_molecule_records_non_periodic(tmp_path):
    from pymatgen.core import Molecule

    h2o = Molecule(["O", "H", "H"],
                   [[0, 0, 0], [0.758, 0.586, 0], [-0.758, 0.586, 0]])
    uid = cfg.record_configuration(
        h2o, name="Water molecule",
        provenance=[{"kind": "manual", "ref": "test", "detail": "H2O"}],
        config_dir=tmp_path)
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["structure"]["@class"] == "Molecule"
    loaded = cfg.load(uid, config_dir=tmp_path)
    assert cfg.canonical_uid(loaded) == uid


# --------------------------------------------------------------------------
# Large cell: file-backed reduced metadata inline.
# --------------------------------------------------------------------------

def test_large_cell_stores_reduced_metadata(tmp_path):
    si = _primitive_si()
    big = si * (10, 10, 6)  # 1200 atoms, over INLINE_ATOM_LIMIT
    assert len(big) > cfg.INLINE_ATOM_LIMIT
    uid = cfg.record_configuration(
        big, name="Si large supercell",
        provenance=[{"kind": "simulation", "ref": "md", "detail": "big"}],
        file_ref={"path": "structures/si_big.extxyz", "sha256": "deadbeef"},
        config_dir=tmp_path)
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    # Inline payload is reduced metadata, not the full site list.
    assert "@class" not in record["structure"]
    assert "lattice" in record["structure"]
    assert record["structure"]["natoms"] == len(big)
    assert record["files"] == {"path": "structures/si_big.extxyz",
                               "sha256": "deadbeef"}
    # load() cannot reconstruct a file-backed cell from inline metadata.
    with pytest.raises(cfg.ConfigurationError):
        cfg.load(uid, config_dir=tmp_path)
