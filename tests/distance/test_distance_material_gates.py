"""Spec gates 4, 5, 6: amorphous statistical identity, defect visibility,
ordering sanity. Pseudo-glasses are seeded rattles of a diamond supercell:
they exercise the machinery; the physics benchmark on real a-Si runs on the
corpus, not in CI. The full strained < polymorph < glass chain needs real
a-Si, so the chain here asserts only the two robust inequalities."""
import pytest

import omdc
from fixtures_distance import diamond_si, doped, fcc_si, glass, pristine_216, strained, vacancy


def _ot(a, b):
    return omdc.distance(a, b, metric="env-ot", encoder="hist")


def test_gate4_amorphous_statistical_identity():
    d_realization = _ot(glass(1), glass(2))
    d_size = _ot(glass(1, rep=3), glass(3, rep=4))
    d_ref = _ot(glass(1), diamond_si())
    assert d_realization < 0.3 * d_ref
    assert d_size < 0.5 * d_ref


def test_gate5_defect_small_but_visible_and_site_invariant():
    pristine = pristine_216()
    d_vac = _ot(pristine, vacancy(0))
    d_ref = _ot(pristine, glass(1))
    assert 0 < d_vac < d_ref
    assert _ot(vacancy(0), vacancy(100)) < 0.2 * max(d_vac, 1e-9) + 1e-9


def test_gate6_ordering_sanity(diamond):
    d_strain = _ot(diamond, strained(diamond))
    d_poly = _ot(diamond, fcc_si())
    d_glass = _ot(diamond, glass(1))
    assert d_strain < d_poly
    assert d_strain < d_glass
    assert omdc.distance(diamond, fcc_si(), metric="comp") == 0.0
    assert omdc.distance(pristine_216(), doped(), metric="comp") > 0.0
