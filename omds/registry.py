"""The simulation-distance registry: the lineage record is the encoder.

Distance decomposes over the typed lineage fields: node (BFS on the
published map graph), material (delegated to omdc's comp channel),
conditions and params (dimension-blind bounded numerics), execution (code
and template, categorical). Every channel is bounded to [0, 1], so
lineage@1, the weighted sum with versioned weights, is too. divergence()
returns the per-channel breakdown sorted, largest first: not a distance but
the localization tool ("where do two simulations part ways").

Same doctrine as omdc: `default` is an alias resolved at call time, stored
results record concrete ids, and the registry reuses omdc's DistanceSpec so
metadata is machine-readable in one shape across both layers."""
from __future__ import annotations

from omdc.registry import DistanceSpec

from omds.fields import categorical, mapping_distance, material_distance
from omds.mapgraph import default_graph
from omds.records import normalize_record

DEFAULT_ALIAS = "lineage@1"

# Versioned channel weights of lineage@1; they sum to 1.
WEIGHTS = {
    "node": 0.35,
    "material": 0.30,
    "conditions": 0.15,
    "params": 0.10,
    "execution": 0.10,
}


def breakdown(a: dict, b: dict) -> dict[str, float]:
    ra, rb = normalize_record(a), normalize_record(b)
    return {
        "node": default_graph().distance(ra["node"], rb["node"]),
        "material": material_distance(ra["material"], rb["material"]),
        "conditions": mapping_distance(ra["conditions"], rb["conditions"]),
        "params": mapping_distance(ra["params"], rb["params"]),
        "execution": 0.5 * categorical(ra["code"], rb["code"])
        + 0.5 * categorical(ra["template"], rb["template"]),
    }


def divergence(a: dict, b: dict) -> list[tuple[str, float]]:
    bd = breakdown(a, b)
    return sorted(bd.items(), key=lambda kv: -kv[1])


def _lineage(a, b):
    bd = breakdown(a, b)
    return sum(WEIGHTS[k] * v for k, v in bd.items())


def _channel(name):
    def fn(a, b):
        return breakdown(a, b)[name]

    return fn


_LIN = frozenset({"record-order"})

DISTANCES: dict[str, DistanceSpec] = {
    s.full_id: s
    for s in [
        DistanceSpec("lineage", 1, "weighted sum over the lineage channels (weights are versioned)", False, True, _LIN, "fast", None, False, _lineage, input="lineage"),
        DistanceSpec("lineage-node", 1, "BFS distance on the published map graph, capped and normalized", False, True, _LIN, "fast", None, False, _channel("node"), input="lineage"),
        DistanceSpec("lineage-material", 1, "material channel, delegated to omdc comp and squashed to [0, 1]", False, True, _LIN, "fast", None, False, _channel("material"), input="lineage"),
        DistanceSpec("lineage-conditions", 1, "bounded relative difference over the union of condition keys", False, True, _LIN, "fast", None, False, _channel("conditions"), input="lineage"),
        DistanceSpec("lineage-params", 1, "bounded relative difference over params, hyperparameters, values", False, True, _LIN, "fast", None, False, _channel("params"), input="lineage"),
        DistanceSpec("lineage-execution", 1, "categorical over code and template", False, True, _LIN, "fast", None, False, _channel("execution"), input="lineage"),
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


def distance(a: dict, b: dict, metric: str | None = None) -> float:
    return resolve(metric).fn(a, b)
