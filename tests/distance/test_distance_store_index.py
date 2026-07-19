import numpy as np
import pytest

import omdc
from fixtures_distance import diamond_si, glass, pristine_216, vacancy
from omdc.index import MotifIndex, PooledIndex, outliers
from omdc.store import load, save


def _es(s):
    return omdc.embed(s, encoder="hist")


def test_store_roundtrip(tmp_path, diamond):
    entries = {
        omdc.structure_key(diamond): _es(diamond),
        omdc.structure_key(glass(1, rep=3)): _es(glass(1, rep=3)),
    }
    p = tmp_path / "cache.parquet"
    save(p, entries)
    back = load(p)
    assert set(back) == set(entries)
    for k, es in entries.items():
        np.testing.assert_allclose(back[k].vectors, es.vectors, atol=1e-6)
        np.testing.assert_allclose(back[k].weights, es.weights, atol=1e-12)
        np.testing.assert_allclose(back[k].pooled, es.pooled, atol=1e-6)
        assert back[k].pin == es.pin
        assert back[k].sampled == es.sampled


def test_pooled_index_finds_self_first(diamond):
    idx = PooledIndex()
    items = {"diamond": _es(diamond), "glass": _es(glass(1, rep=3)), "vac": _es(vacancy(0))}
    for k, es in items.items():
        idx.add(k, es)
    hits = idx.search(items["diamond"], k=3)
    assert hits[0][0] == "diamond" and hits[0][1] == pytest.approx(0, abs=1e-8)
    assert hits[1][0] == "vac"  # a vacancy supercell is nearer to diamond than a glass


def test_pristine_has_no_outliers_vacancy_and_dopant_do():
    from fixtures_distance import doped

    assert len(outliers(_es(pristine_216()))) == 0
    assert len(outliers(_es(vacancy(0)))) >= 1
    assert len(outliers(_es(doped()))) >= 1  # substitutional P in Si is visible


def test_glass_has_no_host_so_no_outliers():
    assert len(outliers(_es(glass(1, rep=3)))) == 0


def test_motif_search_lands_on_the_defect():
    idx = MotifIndex()
    idx.add("pristine", _es(pristine_216()))
    vac_es = _es(vacancy(0))
    idx.add("vac", vac_es)
    probe = vac_es.vectors[outliers(vac_es)[0]]
    hits = idx.search(probe, k=1)
    assert hits[0][0] == "vac" and hits[0][2] == pytest.approx(0, abs=1e-8)
