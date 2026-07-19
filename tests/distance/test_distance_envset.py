import numpy as np

from fixtures_distance import diamond_si, glass, vacancy
from omdc.encoders import get_encoder
from omdc.envset import MAX_ENVS, embed


def test_crystal_collapses_to_symmetry_classes(diamond):
    es = embed(diamond, get_encoder("hist"))
    assert len(es.vectors) == 1  # diamond: one unique environment
    assert es.weights.sum() == 1.0
    np.testing.assert_allclose(np.linalg.norm(es.vectors, axis=1), 1.0, atol=1e-6)
    assert es.pooled.shape == (2 * es.vectors.shape[1],)


def test_supercell_pooled_identical(diamond):
    enc = get_encoder("hist")
    a, b = embed(diamond, enc), embed(diamond * (2, 2, 2), enc)
    np.testing.assert_allclose(a.pooled, b.pooled, atol=1e-5)


def test_large_disordered_cell_subsamples():
    es = embed(glass(1), get_encoder("hist"))  # 512 atoms, no symmetry
    assert len(es.vectors) == MAX_ENVS
    assert abs(es.weights.sum() - 1.0) < 1e-9


def test_vacancy_keeps_defect_classes():
    es = embed(vacancy(0), get_encoder("hist"))
    assert len(es.vectors) >= 2  # bulk plus perturbed shells around the vacancy
