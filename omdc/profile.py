"""Scale-resolved distance profiles: not "how far" but "far at which scale".

scale_profile: env-ot at a ladder of interaction radii (hist encoder with
matching cutoffs). A strained crystal is near at short range and far at long
range; two realizations of one glass stay near at every range; missing
medium-range order shows up at the 10 A rung and not before.

layer_profile: the same ladder from MACE's receptive fields (layer l sees
roughly l times the model cutoff). Needs the mace extra.

amd_profile lives in omdc.metrics.amdmetric: the AMD vector's k index is
already a length ladder, and its prefix maxima are nested lower bounds of
the full amd distance (monotone in k by construction)."""
from __future__ import annotations

from omdc.adapters import to_structure
from omdc.encoders.histogram import HistogramEncoder
from omdc.envset import embed
from omdc.metrics.ot import env_ot

DEFAULT_RADII = (2.5, 5.0, 10.0)


def scale_profile(s1, s2, radii=DEFAULT_RADII) -> dict[float, float]:
    a, b = to_structure(s1), to_structure(s2)
    out: dict[float, float] = {}
    for r in radii:
        enc = HistogramEncoder(cutoff=float(r))
        out[float(r)] = env_ot(embed(a, enc), embed(b, enc))
    return out


def layer_profile(s1, s2, layers=(1, 2)) -> dict[int, float]:
    from omdc.encoders.mace import MaceEncoder

    a, b = to_structure(s1), to_structure(s2)
    out: dict[int, float] = {}
    for layer in layers:
        enc = MaceEncoder(num_layers=int(layer))
        out[int(layer)] = env_ot(embed(a, enc), embed(b, enc))
    return out
