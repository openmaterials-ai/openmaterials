"""Unified map data builders over one or more Domains."""
from __future__ import annotations

import importlib
import json
import pkgutil
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import sympy as sp

from omai.operator.identity import edge_id, node_id, parameter_node_id
from omai.operator.operator import Operator
from omai.operator.space import ObservableSpace, Space

_DOCS = Path(__file__).resolve().parents[1] / "docs"


@dataclass(frozen=True)
class Domain:
    """One physics domain's contribution to the unified map."""
    name: str
    nodes: tuple[Space, ...]
    edges: tuple[Operator, ...]
    symbols: dict[str, str]
    # (node_id, latex_symbol, sympy_symbol_or_indexedbase[, dimension_name]) promoted to parameter nodes
    param_promotions: tuple[tuple[str, str, object], ...]
    representation_package: ModuleType
    # Ordered (tier_name, one_line_description) in domain order; drives the
    # map's band order. Default empty for domains that declare no tiers.
    tiers: tuple[tuple[str, str], ...] = ()


def _layers(domains: tuple[Domain, ...]) -> dict[str, int]:
    producer = {}
    for d in domains:
        for op in d.edges:
            for out in op.outputs:
                producer[out.name] = op
    cache: dict[str, int] = {}

    def layer_of(name: str) -> int:
        if name in cache:
            return cache[name]
        op = producer.get(name)
        if op is None or not getattr(op, "inputs", None):
            cache[name] = 0
            return 0
        cache[name] = 1 + max(layer_of(i.name) for i in op.inputs)
        return cache[name]

    for d in domains:
        for s in d.nodes:
            layer_of(s.name)
    return cache


def build_graph_dict(domains: tuple[Domain, ...]) -> dict:
    layers = _layers(domains)
    symbols: dict[str, str] = {}
    for d in domains:
        symbols.update(d.symbols)

    # All producing formulas per node (Pattern C nodes have several producers;
    # the site must show every branch, labeled by its operator). "formula"
    # stays the first producer's latex for back-compat consumers.
    target_formula: dict[str, str] = {}
    target_formulas: dict[str, list[dict]] = {}
    for d in domains:
        for op in d.edges:
            try:
                latex = sp.latex(op.formula) if getattr(op, "formula", None) is not None else None
            except Exception:
                latex = None
            for o in op.outputs:
                if latex:
                    if o.name not in target_formula:
                        target_formula[o.name] = latex
                    target_formulas.setdefault(o.name, []).append(
                        {"op": op.name, "latex": latex})

    nodes, seen = [], set()
    for d in domains:
        for s in d.nodes:
            if s.name in seen:
                continue
            seen.add(s.name)
            nodes.append({
                "id": s.name,
                "type": "observable" if isinstance(s, ObservableSpace) else "hidden",
                "layer": layers.get(s.name, 0),
                "kind": "symbolic",
                "symbol": symbols.get(s.name, s.name),
                "formula": target_formula.get(s.name),
                "formulas": target_formulas.get(s.name, []),
                "tier": s.tier,
                "uid": node_id(s),
            })

    # Content-addressed edge uid per operator name, per domain. Several links
    # can share an operator (a multi-input edge emits one link per input-output
    # pair); those links carry the same uid because the uid identifies the
    # OPERATOR, not the individual arrow.
    links: list[dict] = []
    seen_links: set[tuple] = set()
    for d in domains:
        edge_uid = {op.name: edge_id(op, node_id) for op in d.edges}
        for op in d.edges:
            for i in op.inputs:
                for o in op.outputs:
                    key = (i.name, o.name, op.name)
                    if key not in seen_links:
                        seen_links.add(key)
                        links.append({"source": i.name, "target": o.name,
                                      "op": op.name, "uid": edge_uid[op.name]})

    def _uses(formula, sym):
        if formula is None:
            return False
        if sym in formula.free_symbols:
            return True
        return isinstance(sym, sp.IndexedBase) and sym in formula.atoms(sp.IndexedBase)

    for d in domains:
        for pid, psym, sobj, *rest in d.param_promotions:
            if pid in seen:
                continue
            consumers, seen_c = [], set()
            for op in d.edges:
                if _uses(getattr(op, "formula", None), sobj):
                    for o in op.outputs:
                        if o.name not in seen_c:
                            seen_c.add(o.name)
                            consumers.append(o.name)
            if not consumers:
                continue
            seen.add(pid)
            dim_name = rest[0] if rest else None
            nodes.append({"id": pid, "type": "parameter", "layer": 0,
                          "kind": "symbolic", "symbol": psym, "formula": None,
                          "tier": "Sources", "uid": parameter_node_id(pid, dim_name)})
            for c in consumers:
                param_key = (pid, c, "provide_" + pid)
                if param_key not in seen_links:
                    seen_links.add(param_key)
                    # Parameter links are presentation artifacts of promotion,
                    # not operators, so they carry no edge uid.
                    links.append({"source": pid, "target": c, "op": "provide_" + pid,
                                  "kind": "param", "uid": None})

    tiers, seen_tiers = [], set()
    for d in domains:
        for name, desc in d.tiers:
            if name in seen_tiers:
                continue
            seen_tiers.add(name)
            tiers.append({"name": name, "order": len(tiers), "description": desc})

    return {"nodes": nodes, "links": links, "tiers": tiers}


def build_codes(domains: tuple[Domain, ...]) -> dict:
    from omai.representation.adapter import SpaceRepresentationSpec
    codes: dict[str, dict[str, dict]] = {}
    for d in domains:
        pkg = d.representation_package
        for m in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"{pkg.__name__}.{m.name}")
            for attr in dir(mod):
                if attr.startswith("_"):
                    continue
                obj = getattr(mod, attr)
                if isinstance(obj, SpaceRepresentationSpec):
                    api = next(iter(obj.code_api.values()), None) if obj.code_api else None
                    unit = next(iter(obj.observable_units.values()), None) if obj.observable_units else None
                    codes.setdefault(obj.representation_name, {})[obj.space.name] = {"api": api, "unit": unit}
    return codes


def build_instances(instances_dir: Path | None = None) -> list[dict]:
    instances_dir = instances_dir or (_DOCS / "data" / "instances")
    # Name -> content-addressed uid over the unified map (spaces + promoted
    # parameters). Each instance is pinned to the uid of the node its variable
    # names, so a value can follow the element through supersede chains.
    name_to_uid = {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}
    out = []
    for f in sorted(instances_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        for key in ("variable", "material", "conditions", "value", "units", "source"):
            if key not in rec:
                raise ValueError(f"{f.name}: missing '{key}'")
        if rec["source"].get("kind") not in ("simulation", "measurement"):
            raise ValueError(f"{f.name}: source.kind must be simulation|measurement")
        if rec["variable"] not in name_to_uid:
            raise ValueError(f"{f.name}: unknown variable {rec['variable']!r}")
        rec["node_uid"] = name_to_uid[rec["variable"]]
        out.append(rec)
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def record_instance(*, domains, variable, material, value, units, source_kind,
                    source_ref, conditions=None, uncertainty=None, detail=None,
                    instances_dir=None):
    known = {n["id"] for n in build_graph_dict(domains)["nodes"]}
    if variable not in known:
        raise ValueError(f"unknown variable {variable!r}")
    if source_kind not in ("simulation", "measurement"):
        raise ValueError("source_kind must be 'simulation' or 'measurement'")
    instances_dir = Path(instances_dir) if instances_dir else (_DOCS / "data" / "instances")
    instances_dir.mkdir(parents=True, exist_ok=True)
    rec = {"variable": variable, "material": material, "conditions": conditions or {},
           "value": value, "units": units, "uncertainty": uncertainty,
           "source": {"kind": source_kind, "ref": source_ref, "detail": detail}}
    path = instances_dir / (_slug(f"{material}-{variable}-{source_ref}") + ".json")
    path.write_text(json.dumps(rec))
    return path


_DOMAINS_CACHE: tuple[Domain, ...] | None = None


def _domains() -> tuple[Domain, ...]:
    """Return the cached tuple of all domains, building it on first call.

    Built lazily (not at module top level) because omai.thermal_transport.domain
    and omai.materials.domain both do `from omai.map_data import Domain` at import
    time; constructing the tuple eagerly here would import those modules before
    map_data finished initialising and cause a circular import.
    """
    global _DOMAINS_CACHE
    if _DOMAINS_CACHE is None:
        from omai.thermal_transport.domain import THERMAL_TRANSPORT
        from omai.dft_ground_state.domain import DFT_GROUND_STATE
        from omai.mechanics.domain import MECHANICS
        from omai.stability.domain import STABILITY
        from omai.materials.domain import MATERIALS
        _DOMAINS_CACHE = (THERMAL_TRANSPORT, DFT_GROUND_STATE, MECHANICS,
                          STABILITY, MATERIALS)
    return _DOMAINS_CACHE


def __getattr__(name: str):  # noqa: N807  (module-level __getattr__)
    # PEP 562 module-level __getattr__: `DOMAINS` is exposed lazily via _domains()
    # for the circular-import reason documented there. Any other name is a real
    # AttributeError.
    if name == "DOMAINS":
        return _domains()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def write_graph(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "graph.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_graph_dict(_domains())))
    return path


def write_codes(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "codes.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_codes(_domains())))
    return path


def write_instances(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "instances.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_instances()))
    return path


def build_catalog(domains: tuple[Domain, ...]) -> list[dict]:
    g = build_graph_dict(domains)
    space_by_name = {}
    for d in domains:
        for s in d.nodes:
            space_by_name[s.name] = s

    # Build a map of promoted-parameter id -> dimension name (4-tuple entries only)
    param_dim: dict[str, str] = {}
    for d in domains:
        for p in d.param_promotions:
            if len(p) >= 4 and p[3]:
                param_dim[p[0]] = p[3]

    out = []
    for n in g["nodes"]:
        s = space_by_name.get(n["id"])
        # Collect all distinct field dimensions for this space
        dims: list[str] = []
        if s and s.fields:
            for f in s.fields:
                if f.dimension.name not in dims:
                    dims.append(f.dimension.name)
        dim = ", ".join(dims) if dims else None
        # Promoted-parameter dimensions override/fill in the space-derived value
        dim = param_dim.get(n["id"], dim)
        desc = (s.description if s else "") or ""
        out.append({
            "id": n["id"],
            "symbol": n["symbol"],
            "type": n["type"],
            "dimension": dim,
            "description": desc,
        })
    return out


def write_catalog(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "catalog.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_catalog(_domains())))
    return path


def write_version(path: Path | None = None) -> Path:
    """Write the P5 provenance stamp the site reads: the store head the data
    was generated against, next to the frozen genesis hash."""
    from omai.store import Store

    path = path or (_DOCS / "data" / "version.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    store_root = Path(__file__).resolve().parents[1] / "map"
    payload = {
        "version": Store(store_root).head,
        "genesis": (store_root / "GENESIS").read_text().strip(),
    }
    path.write_text(json.dumps(payload))
    return path


if __name__ == "__main__":
    print("wrote", write_graph())
    print("wrote", write_instances())
    print("wrote", write_codes())
    print("wrote", write_catalog())
    print("wrote", write_version())
