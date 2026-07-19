import pytest

from fixtures_distance import diamond_si, permuted, translated
from omdc.adapters import structure_key, to_structure
from omdc.errors import MissingExtraError


def test_to_structure_passthrough_and_ase(diamond):
    assert to_structure(diamond) is diamond
    from pymatgen.io.ase import AseAtomsAdaptor

    atoms = AseAtomsAdaptor.get_atoms(diamond)
    assert len(to_structure(atoms)) == len(diamond)


def test_to_structure_rejects_junk():
    with pytest.raises(TypeError, match="expected pymatgen Structure"):
        to_structure(42)


def test_structure_key_stable_under_site_order_and_wrap(diamond):
    k = structure_key(diamond)
    assert len(k) == 64
    assert structure_key(permuted(diamond)) == k
    assert structure_key(translated(diamond, (1.0, 0.0, 0.0))) == k


def test_structure_key_distinguishes(diamond):
    assert structure_key(diamond) != structure_key(diamond_si(5.5))


def test_missing_extra_error_message():
    err = MissingExtraError("the MACE encoder", "mace")
    assert "pip install 'openmaterials-ai[distance,mace]'" in str(err)
    assert "silent fallback" in str(err)
