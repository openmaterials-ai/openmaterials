"""The distance registry: named, versioned distances with machine-readable
metadata, and the default alias.

Doctrine: `default` resolves at call time (today: env-ot@1). Anything stored
or published records the resolved full id, never the alias. A distance whose
optional dependency is missing raises MissingExtraError; no silent fallback."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from omdc.adapters import to_structure
from omdc.encoders import get_encoder
from omdc.envset import embed as _embed

DEFAULT_ALIAS = "env-ot@1"
DEFAULT_ENCODER = "mace"  # the traversal encoder; "hist" is the dependency-free reference

_GEOM = frozenset({"rotation", "translation", "permutation", "supercell", "continuity"})


@dataclass(frozen=True)
class DistanceSpec:
    id: str
    version: int
    description: str
    metric: bool
    ann_indexable: bool
    invariances: frozenset
    cost: str  # "fast" | "medium" | "heavy"
    extra: str | None  # pip extra its default configuration needs
    needs_encoder: bool
    fn: Callable[..., float] = field(repr=False)
    # What the two inputs ARE: "structure" (default), "spectrum" (mass curve
    # (x, y)), "curve" (function curve (x, y)), "trajectory" (sequence of
    # structures). Metadata for callers; each fn validates its own inputs.
    input: str = "structure"
    # Full ids this distance certifiably lower-bounds (on symmetry-exact
    # sets); machine-readable so a funnel search can be assembled from the
    # registry alone.
    lower_bounds: tuple = ()

    @property
    def full_id(self) -> str:
        return f"{self.id}@{self.version}"


def _env_ot(s1, s2, encoder):
    from omdc.metrics.ot import env_ot

    enc = get_encoder(encoder)
    return env_ot(_embed(to_structure(s1), enc), _embed(to_structure(s2), enc))


def _latent(s1, s2, encoder):
    from omdc.metrics.pooled import pooled_cosine

    enc = get_encoder(encoder)
    return pooled_cosine(_embed(to_structure(s1), enc), _embed(to_structure(s2), enc))


def _comp(s1, s2):
    from omdc.metrics.comp import elmd

    return elmd(to_structure(s1).composition, to_structure(s2).composition)


def _amd(s1, s2):
    from omdc.metrics.amdmetric import amd_distance

    return amd_distance(to_structure(s1), to_structure(s2))


def _exact(s1, s2):
    from omdc.metrics.exact import exact_rmsd

    return exact_rmsd(to_structure(s1), to_structure(s2))


def _latent_lb(s1, s2, encoder):
    from omdc.metrics.pooled import latent_lb

    enc = get_encoder(encoder)
    return latent_lb(_embed(to_structure(s1), enc), _embed(to_structure(s2), enc))


def _spectrum(s1, s2):
    from omdc.metrics.spectrum import spectrum_w1

    return spectrum_w1(s1, s2)


def _curve(s1, s2):
    from omdc.metrics.spectrum import curve_rel

    return curve_rel(s1, s2)


def _traj(s1, s2, encoder):
    from omdc.metrics.traj import traj_ot

    return traj_ot(s1, s2, encoder=encoder)


DISTANCES: dict[str, DistanceSpec] = {
    s.full_id: s
    for s in [
        DistanceSpec("env-ot", 1, "optimal transport between weighted local-environment sets", True, False, _GEOM, "heavy", "mace", True, _env_ot),
        DistanceSpec("latent", 1, "cosine over pooled environment vectors, the ANN index key", False, True, _GEOM, "medium", "mace", True, _latent),
        DistanceSpec("comp", 1, "Element Mover's Distance on the Pettifor scale, chemistry only", True, True, _GEOM | {"geometry"}, "fast", None, False, _comp),
        DistanceSpec("amd", 1, "Average Minimum Distance, Chebyshev; geometry only, species-blind", True, True, _GEOM, "fast", "amd", False, _amd),
        DistanceSpec("exact", 1, "StructureMatcher RMSD, inf when cells do not match; re-rank only", False, False, _GEOM, "heavy", None, False, _exact),
        DistanceSpec("latent-lb", 1, "euclidean between weighted-mean environment vectors; certified lower bound of env-ot on symmetry-exact sets", True, True, _GEOM, "medium", "mace", True, _latent_lb, lower_bounds=("env-ot@1",)),
        DistanceSpec("spectrum", 1, "Wasserstein-1 between 1D mass distributions (DOS, spectra); mass-normalized", True, True, frozenset(), "fast", None, False, _spectrum, input="spectrum"),
        DistanceSpec("curve", 1, "symmetric relative L2 between property curves on the shared x range", False, False, frozenset(), "fast", None, False, _curve, input="curve"),
        DistanceSpec("traj-ot", 1, "sqrt energy distance between trajectories over frame embeddings", True, False, _GEOM, "heavy", "mace", True, _traj, input="trajectory"),
    ]
}


def resolve(name: str | None = None) -> DistanceSpec:
    name = name or "default"
    if name == "default":
        name = DEFAULT_ALIAS
    if name in DISTANCES:
        return DISTANCES[name]
    versions = [s for s in DISTANCES.values() if s.id == name]
    if versions:
        return max(versions, key=lambda s: s.version)
    raise KeyError(f"unknown distance {name!r}; known: {sorted(DISTANCES)}")


def distance(s1, s2, metric: str | None = None, encoder: str | None = None) -> float:
    spec = resolve(metric)
    if spec.needs_encoder:
        return spec.fn(s1, s2, encoder or DEFAULT_ENCODER)
    return spec.fn(s1, s2)
