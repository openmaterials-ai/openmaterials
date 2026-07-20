import importlib.util

import pytest

from omdc.benchmark import default_corpus, run, score_encoder

HAS_MACE = importlib.util.find_spec("mace") is not None


def test_hist_passes_the_gate():
    row = score_encoder("hist")
    assert row["pass"], row
    assert row["encoder"] == "hist@1"
    assert row["separation"] > 2.0


def test_corpus_is_deterministic():
    a, b = default_corpus(), default_corpus()
    assert all(a[k] == b[k] for k in a)


def test_unknown_encoder_fails_loudly():
    with pytest.raises(KeyError, match="unknown encoder"):
        run(["nope"])


@pytest.mark.skipif(not HAS_MACE, reason="mace extra not installed")
def test_mace_scores():
    row = score_encoder("mace")
    assert row["encoder"].startswith("mace-mp-0")
    assert all(k in row for k in ("realization", "size", "defect", "polymorph", "separation"))
