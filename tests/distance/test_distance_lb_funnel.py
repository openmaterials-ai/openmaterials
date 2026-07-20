import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

import omdc
from fixtures_distance import diamond_si, fcc_si, strained
from omdc.index import funnel_search
from omdc.metrics.ot import env_ot
from omdc.metrics.pooled import latent_lb


def _zoo():
    rs = Structure.from_spacegroup
    zoo = {
        "diamond": diamond_si(),
        "diamond-5.5": diamond_si(5.5),
        "diamond-5.6": diamond_si(5.6),
        "strain+1": strained(diamond_si(), 0.01),
        "strain+2": strained(diamond_si(), 0.02),
        "fcc": fcc_si(),
        "fcc-4.0": fcc_si(4.0),
        "gaas": rs("F-43m", Lattice.cubic(5.65), ["Ga", "As"], [[0, 0, 0], [0.25, 0.25, 0.25]]),
        "nacl": rs("Fm-3m", Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]),
        "mgo": rs("Fm-3m", Lattice.cubic(4.21), ["Mg", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]]),
        "sic": rs("F-43m", Lattice.cubic(4.36), ["Si", "C"], [[0, 0, 0], [0.25, 0.25, 0.25]]),
        "bcc-fe": rs("Im-3m", Lattice.cubic(2.87), ["Fe"], [[0, 0, 0]]),
    }
    return {k: omdc.embed(s, encoder="hist") for k, s in zoo.items()}


def test_latent_lb_is_a_lower_bound_on_exact_sets():
    sets = _zoo()
    assert all(not es.sampled for es in sets.values())  # all crystals collapse
    keys = list(sets)
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            assert latent_lb(sets[a], sets[b]) <= env_ot(sets[a], sets[b]) + 1e-9


def test_funnel_matches_brute_force_and_prunes():
    sets = _zoo()
    query = sets.pop("strain+1")
    brute = sorted((env_ot(query, es), k) for k, es in sets.items())[:4]
    stats = {}
    got = funnel_search(query, sets, k=4, stats=stats)
    assert [(k, pytest.approx(d)) for d, k in brute] == [(k, pytest.approx(d)) for k, d in got]
    assert stats["exact_evals"] < len(sets)


def test_registry_metadata_links_the_bound():
    spec = omdc.resolve("latent-lb")
    assert spec.metric and spec.ann_indexable
    assert "env-ot@1" in spec.lower_bounds
    assert omdc.resolve("env-ot").lower_bounds == ()
