"""Node distance on the published map: BFS over docs/data/graph.json.

The map's derivation graph is the encoder for the node field: two quantities
are near when few operators separate them. Distance is the shortest
undirected path, capped at MAX_HOPS and normalized to [0, 1]. A qualified id
that is not itself a node falls back to its base name; two ids sharing only
the base name differ by QUALIFIER_PENALTY. Off-map ids compare as strings
(0 or 1): honest degradation, never a guess. The graph is read-only here;
metric bindings never touch the map files."""
from __future__ import annotations

import json
from collections import deque
from functools import lru_cache
from pathlib import Path

MAX_HOPS = 6
QUALIFIER_PENALTY = 0.15

_DEFAULT_GRAPH = Path(__file__).resolve().parents[1] / "docs" / "data" / "graph.json"


def _base(node_id: str) -> str:
    return node_id.split("[", 1)[0]


class MapGraph:
    def __init__(self, path: str | Path | None = None):
        p = Path(path) if path else _DEFAULT_GRAPH
        self.adj: dict[str, set[str]] = {}
        if p.exists():
            g = json.loads(p.read_text())
            for n in g.get("nodes", []):
                self.adj.setdefault(n["id"], set())
            for link in g.get("links", []):
                a, b = link.get("source"), link.get("target")
                if a in self.adj and b in self.adj:
                    self.adj[a].add(b)
                    self.adj[b].add(a)

    def _resolve(self, node_id: str) -> str | None:
        if node_id in self.adj:
            return node_id
        base = _base(node_id)
        if base in self.adj:
            return base
        return None

    def hops(self, a: str, b: str) -> int | None:
        ra, rb = self._resolve(a), self._resolve(b)
        if ra is None or rb is None:
            return None
        if ra == rb:
            return 0
        seen = {ra}
        queue = deque([(ra, 0)])
        while queue:
            cur, d = queue.popleft()
            if d >= MAX_HOPS:
                continue
            for nxt in self.adj[cur]:
                if nxt == rb:
                    return d + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, d + 1))
        return MAX_HOPS + 1

    def distance(self, a: str | None, b: str | None) -> float:
        if a is None and b is None:
            return 0.0
        if a is None or b is None:
            return 1.0
        if a == b:
            return 0.0
        h = self.hops(a, b)
        if h is None:
            return 0.0 if a == b else 1.0
        d = min(h, MAX_HOPS) / MAX_HOPS
        if _base(a) == _base(b):
            d = min(d, QUALIFIER_PENALTY)
        return d


@lru_cache(maxsize=4)
def default_graph() -> MapGraph:
    return MapGraph()
