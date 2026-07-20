"""The encoder benchmark: the gate that pins env-ot@1's production encoder.

Four criteria, each a ratio of a should-be-small distance to a should-be-
large reference, on an a-Si-shaped corpus (glass realizations, sizes,
crystal counterpoints, dilute defects). Lower is better everywhere; a
criterion under 1.0 means the encoder orders that regime correctly, and
`separation` is the safety margin (same-glass vs glass-vs-crystal).

    realization  d(glass seed A, glass seed B) / d(glass, crystal)
    size         d(glass at N, glass at 2N)    / d(glass, crystal)
    defect       d(pristine, vacancy) / d(pristine, glass), sane in (0, 1)
    polymorph    d(diamond, strained) / d(diamond, fcc), sane in (0, 1)

The corpus is synthetic by default (seeded rattles, deterministic) so the
benchmark runs anywhere; pass real a-Si structure files to score the
production corpus. Encoders are compared on identical structures with
identical estimators; only the environment vectors differ.

Run: PYTHONPATH=. python -m omdc.benchmark [--encoders hist,mace] [--rep 3]
MatterSim joins by name once an adapter lands; unknown encoder names fail
loudly, never silently skip."""
from __future__ import annotations

import json

import numpy as np
from pymatgen.core import Lattice, Structure

from omdc.encoders import get_encoder
from omdc.envset import embed
from omdc.metrics.ot import env_ot


def _diamond(a: float = 5.43) -> Structure:
    return Structure.from_spacegroup("Fd-3m", Lattice.cubic(a), ["Si"], [[0, 0, 0]])


def _fcc(a: float = 3.87) -> Structure:
    return Structure.from_spacegroup("Fm-3m", Lattice.cubic(a), ["Si"], [[0, 0, 0]])


def _rattle(s: Structure, sigma: float, seed: int) -> Structure:
    rng = np.random.default_rng(seed)
    return Structure(
        s.lattice,
        s.species,
        s.cart_coords + rng.normal(0.0, sigma, (len(s), 3)),
        coords_are_cartesian=True,
    )


def default_corpus(rep: int = 3) -> dict[str, Structure]:
    big = _diamond() * (rep, rep, rep)
    bigger = _diamond() * (rep + 1, rep + 1, rep + 1)
    vac = big.copy()
    vac.remove_sites([0])
    strained = _diamond().copy()
    strained.apply_strain(0.01)
    return {
        "crystal": _diamond(),
        "fcc": _fcc(),
        "strained": strained,
        "glass-a": _rattle(big, 0.5, 1),
        "glass-b": _rattle(big, 0.5, 2),
        "glass-big": _rattle(bigger, 0.5, 3),
        "vacancy": vac,
        "pristine": big,
    }


def score_encoder(name: str, corpus: dict[str, Structure] | None = None) -> dict:
    enc = get_encoder(name)
    corpus = corpus or default_corpus()
    es = {k: embed(s, enc) for k, s in corpus.items()}
    d = lambda a, b: env_ot(es[a], es[b])
    ref = d("glass-a", "crystal")
    out = {
        "encoder": enc.pin.full_id,
        "hyperparams": enc.pin.hyperparams_hash[:12],
        "realization": d("glass-a", "glass-b") / ref,
        "size": d("glass-a", "glass-big") / ref,
        "defect": d("pristine", "vacancy") / d("pristine", "glass-a"),
        "polymorph": d("crystal", "strained") / d("crystal", "fcc"),
        "separation": ref / max(d("glass-a", "glass-b"), 1e-12),
    }
    out["pass"] = bool(
        out["realization"] < 0.5
        and out["size"] < 0.5
        and 0.0 < out["defect"] < 1.0
        and 0.0 < out["polymorph"] < 1.0
    )
    return out


def run(encoders: list[str], rep: int = 3) -> list[dict]:
    corpus = default_corpus(rep)
    return [score_encoder(name, corpus) for name in encoders]


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--encoders", default="hist", help="comma-separated encoder names")
    ap.add_argument("--rep", type=int, default=3, help="glass supercell repetition")
    args = ap.parse_args(argv)
    rows = run([e.strip() for e in args.encoders.split(",") if e.strip()], rep=args.rep)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
