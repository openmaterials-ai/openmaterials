import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fixtures_distance import diamond_si, doped, fcc_si, pristine_216
from omdc.metrics.comp import elmd

POOL = ["Si", "C", "O", "Ga", "As", "P"]
comps = st.dictionaries(st.sampled_from(POOL), st.integers(1, 8), min_size=1, max_size=4)


def test_identity_and_polymorph_blindness():
    assert elmd("Si", "Si") == 0.0
    assert elmd(diamond_si().composition, fcc_si().composition) == 0.0


def test_known_ordering():
    assert 0 < elmd("GaAs", "GaP") < elmd("GaAs", "NaCl")


def test_dilute_doping_is_small_but_nonzero():
    d = elmd(pristine_216().composition, doped().composition)
    assert 0 < d < 0.5


@settings(max_examples=100, deadline=None)
@given(a=comps, b=comps, c=comps)
def test_metric_axioms(a, b, c):
    dab, dba = elmd(a, b), elmd(b, a)
    assert dab >= 0 and dab == pytest.approx(dba, abs=1e-9)
    assert elmd(a, a) == pytest.approx(0, abs=1e-12)
    assert dab <= elmd(a, c) + elmd(c, b) + 1e-9
