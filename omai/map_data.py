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
            # Consumers are collected across EVERY domain's edges, not only the
            # promoting domain's: a promoted parameter (e.g. CellVolume) may be
            # read by a formula in another domain (e.g. the thermodynamic-identity
            # V_m = N_A V_cell), and its provide_ presentation link must still be
            # drawn to that cross-domain consumer.
            consumers, seen_c = [], set()
            for dd in domains:
                for op in dd.edges:
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
    # Every code rail we represent must be cited (paper/DOI) and carry its
    # license (Giuseppe's rule). credits.CODE_CREDITS is the single source of
    # truth; a rail missing from it gets license "UNKNOWN" here AND the
    # enforcement test (tests/test_code_credits.py) fails, so no rail can land
    # uncredited. Credits attach to every per-space entry of the rail so the
    # site can read them from any of a rail's rows.
    from omai.representation.adapter import SpaceRepresentationSpec
    from omai.representation.credits import CODE_CREDITS
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
                    cr = CODE_CREDITS.get(obj.representation_name)
                    entry = {"api": api, "unit": unit}
                    if cr is not None:
                        entry["citation"] = cr["citation"]
                        entry["doi"] = cr.get("doi")
                        entry["license"] = cr["license"]
                        entry["url"] = cr.get("url")
                    else:
                        entry["citation"] = ""
                        entry["doi"] = None
                        entry["license"] = "UNKNOWN"
                        entry["url"] = None
                    codes.setdefault(obj.representation_name, {})[obj.space.name] = entry
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


def _canonical_axis(domains: tuple[Domain, ...], variable: str):
    """The CanonicalAxis a node's representation declares, or None.

    Scans every domain's representation package for a SpaceRepresentationSpec
    whose space is `variable` and that carries a canonical_axis. This is the
    source of truth the spectrum bridge validates a record's axis and value
    units against. Returns the first declaration found (a node's canonical axis
    is a single physical convention; no two specs should disagree)."""
    from omai.representation.adapter import SpaceRepresentationSpec

    for d in domains:
        pkg = d.representation_package
        for m in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"{pkg.__name__}.{m.name}")
            for attr in dir(mod):
                if attr.startswith("_"):
                    continue
                obj = getattr(mod, attr)
                if (isinstance(obj, SpaceRepresentationSpec)
                        and obj.space.name == variable
                        and obj.canonical_axis is not None):
                    return obj.canonical_axis
    return None


def _validate_spectrum(rec: dict, *, name_to_uid: dict, axis_by_var, where: str):
    """Shared spectrum validation for both the write bridge and the bundler.

    Enforces the spectrum contract: required keys present; source.kind in the
    instance vocabulary; variable resolves to a node; the node declares a
    canonical axis; the axis unit is registered and dimensionally consistent
    with that declaration; the value unit (when the declaration pins one, or the
    record supplies one) is registered and dimensionally consistent; the axis is
    strictly monotonic; the array lengths agree; and every axis and value entry
    is a real finite number (the same real-values-only bar as instances)."""
    from omai.representation.units import UNITS

    for key in ("variable", "material", "conditions", "axis", "values", "units", "source"):
        if key not in rec:
            raise ValueError(f"{where}: missing '{key}'")
    if rec["source"].get("kind") not in ("simulation", "measurement"):
        raise ValueError(f"{where}: source.kind must be simulation|measurement")
    variable = rec["variable"]
    if variable not in name_to_uid:
        raise ValueError(f"{where}: unknown variable {variable!r}")

    axis = rec["axis"]
    for key in ("name", "units", "values"):
        if key not in axis:
            raise ValueError(f"{where}: axis missing '{key}'")

    canon = axis_by_var(variable)
    if canon is None:
        raise ValueError(
            f"{where}: {variable!r} declares no canonical axis; it is not a "
            f"spectrum-capable node (add a CanonicalAxis to its representation)")

    # Axis unit: always registered. When the declaration PINS an axis unit
    # (canon.unit is not None, e.g. PhononDOS's linear_THz), the record's axis
    # unit must also share its dimension. When the declaration leaves the axis
    # OPEN (canon.unit is None, the first case being PotentialOfMeanForce over a
    # collective variable, whose unit is heterogeneous across records: a distance,
    # an angle, a coordination number), no canonical axis dimension is enforced -
    # the axis unit only has to be a registered unit. This is the axis analog of
    # the open value_unit below.
    if axis["units"] not in UNITS:
        raise ValueError(f"{where}: axis unit {axis['units']!r} is not registered")
    if canon.unit is not None and (
            UNITS[axis["units"]].dimension != UNITS[canon.unit].dimension):
        raise ValueError(
            f"{where}: axis unit {axis['units']!r} "
            f"({UNITS[axis['units']].dimension.name}) is dimensionally "
            f"inconsistent with the canonical axis unit {canon.unit!r} "
            f"({UNITS[canon.unit].dimension.name})")

    # Value unit: consistent with the declaration. When the declaration pins a
    # value_unit, the record's units must be registered and share its dimension.
    # When the declaration leaves it open (value_unit is None, e.g. a DOS
    # density), the record's units are a free string (the normalization rides in
    # conditions), but if it happens to name a registered unit that unit must
    # still match a pinned value_unit (there is none), so any string passes.
    if canon.value_unit is not None:
        if rec["units"] not in UNITS:
            raise ValueError(f"{where}: value unit {rec['units']!r} is not registered")
        if UNITS[rec["units"]].dimension != UNITS[canon.value_unit].dimension:
            raise ValueError(
                f"{where}: value unit {rec['units']!r} "
                f"({UNITS[rec['units']].dimension.name}) is dimensionally "
                f"inconsistent with the canonical value unit {canon.value_unit!r} "
                f"({UNITS[canon.value_unit].dimension.name})")

    axis_vals, vals = axis["values"], rec["values"]
    unc = rec.get("uncertainty")

    def _all_real(seq):
        import math as _math
        return all(isinstance(x, (int, float)) and not isinstance(x, bool)
                   and _math.isfinite(x) for x in seq)

    if not axis_vals or not vals:
        raise ValueError(f"{where}: axis and values must be non-empty")
    if not _all_real(axis_vals) or not _all_real(vals):
        raise ValueError(f"{where}: axis and values must be real finite numbers")
    if unc is not None and not _all_real(unc):
        raise ValueError(f"{where}: uncertainty must be real finite numbers or null")
    if len(axis_vals) != len(vals):
        raise ValueError(
            f"{where}: axis has {len(axis_vals)} points but values has {len(vals)}")
    if unc is not None and len(unc) != len(vals):
        raise ValueError(
            f"{where}: uncertainty has {len(unc)} points but values has {len(vals)}")

    strictly_up = all(b > a for a, b in zip(axis_vals, axis_vals[1:]))
    strictly_down = all(b < a for a, b in zip(axis_vals, axis_vals[1:]))
    if not (strictly_up or strictly_down):
        raise ValueError(f"{where}: axis must be strictly monotonic")


def record_instance(*, domains, variable, material, value, units, source_kind,
                    source_ref, conditions=None, uncertainty=None, detail=None,
                    configuration=None, instances_dir=None, slug_hint=None):
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
    # Optional link to a configuration record (spec section 5). material stays
    # the display string; configuration is the canonical uid when known.
    if configuration is not None:
        rec["configuration"] = configuration
    # The slug is (material, variable, source_ref) plus an optional caller
    # hint (k-mesh, cell size...). One paper legitimately reports several
    # values on the same node for the same material, so an existing file with
    # DIFFERENT content must never be silently overwritten: identical
    # re-records stay idempotent (same path back); different records get a
    # numeric suffix.
    base = f"{material}-{variable}-{source_ref}" + (f"-{slug_hint}" if slug_hint else "")
    payload = json.dumps(rec)
    path = instances_dir / (_slug(base) + ".json")
    n = 1
    while path.exists() and path.read_text() != payload:
        n += 1
        path = instances_dir / (_slug(base) + f"-{n}.json")
    path.write_text(payload)
    return path


def build_spectra(spectra_dir: Path | None = None) -> list[dict]:
    """The uid-pinned spectrum index (docs/data/spectra.json).

    A spectrum is function-valued evidence: an array of ordinates against a
    strictly monotonic axis, attached to a spectrum-capable node. Each record is
    validated and pinned to the live node uid of its variable, exactly like an
    instance, so the function follows the element through supersede chains."""
    spectra_dir = spectra_dir or (_DOCS / "data" / "spectra")
    domains = _domains()
    name_to_uid = {n["id"]: n["uid"] for n in build_graph_dict(domains)["nodes"]}
    out = []
    if not spectra_dir.exists():
        return out
    for f in sorted(spectra_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        _validate_spectrum(
            rec, name_to_uid=name_to_uid,
            axis_by_var=lambda v: _canonical_axis(domains, v), where=f.name)
        rec["node_uid"] = name_to_uid[rec["variable"]]
        # The record's own file, so the site can link the panel line to the raw
        # per-spectrum JSON under docs/data/spectra/.
        rec["file"] = f.name
        out.append(rec)
    return out


def record_spectrum(*, domains, variable, material, axis_name, axis_units,
                    axis_values, values, units, source_kind, source_ref,
                    conditions=None, uncertainty=None, detail=None,
                    spectra_dir=None):
    """Validate a function-valued record and write it under docs/data/spectra/.

    The sibling of record_instance: the scalar {value} is replaced by an axis +
    ordinate array. Validation (shared with the bundler) requires the variable
    to resolve to a spectrum-capable node, the axis and value units to be
    registered and dimensionally consistent with that node's canonical-axis
    declaration, the axis strictly monotonic, the arrays equal-length, and every
    number real and finite."""
    name_to_uid = {n["id"]: n["uid"] for n in build_graph_dict(domains)["nodes"]}
    rec = {"variable": variable, "material": material, "conditions": conditions or {},
           "axis": {"name": axis_name, "units": axis_units, "values": list(axis_values)},
           "values": list(values), "units": units, "uncertainty": uncertainty,
           "source": {"kind": source_kind, "ref": source_ref, "detail": detail}}
    _validate_spectrum(
        rec, name_to_uid=name_to_uid,
        axis_by_var=lambda v: _canonical_axis(domains, v), where=f"{material}/{variable}")
    spectra_dir = Path(spectra_dir) if spectra_dir else (_DOCS / "data" / "spectra")
    spectra_dir.mkdir(parents=True, exist_ok=True)
    path = spectra_dir / (_slug(f"{material}-{variable}-{source_ref}") + ".json")
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
        from omai.thermochemistry.domain import THERMOCHEMISTRY
        from omai.quasiharmonic.domain import QUASIHARMONIC
        from omai.molecular.domain import MOLECULAR
        from omai.electronic_transport.domain import ELECTRONIC_TRANSPORT
        from omai.materials.domain import MATERIALS
        from omai.thermodynamic_identities.domain import THERMODYNAMIC_IDENTITIES
        _DOMAINS_CACHE = (THERMAL_TRANSPORT, DFT_GROUND_STATE, MECHANICS,
                          STABILITY, THERMOCHEMISTRY, QUASIHARMONIC,
                          MOLECULAR, ELECTRONIC_TRANSPORT, MATERIALS,
                          THERMODYNAMIC_IDENTITIES)
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


def write_spectra(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "spectra.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_spectra()))
    return path


# Above this many atoms a configuration's full structure dict is dropped from
# the bundle (kept only in the per-record file): the bundle stays light so the
# site can load every configuration at once.
_BUNDLE_INLINE_ATOM_LIMIT = 100


def build_configurations(config_dir: Path | None = None) -> list[dict]:
    """The uid-pinned configuration index (docs/data/configurations.json).

    A configuration is structure-valued evidence: the atomic cell that a
    Structure value names. Each record is pinned to the live Structure node uid
    (so it follows the node through supersede chains, exactly like an instance)
    and carries its own content-addressed canonical uid. To keep the bundle
    light, the full pymatgen structure dict is dropped for cells above
    ``_BUNDLE_INLINE_ATOM_LIMIT`` atoms (the per-record file under
    docs/data/configurations/ keeps it); the canonical block, name, formula,
    provenance, and external ids always ride in the bundle so the site can
    search and label without opening a file.
    """
    config_dir = config_dir or (_DOCS / "data" / "configurations")
    structure_uid = {n["id"]: n["uid"]
                     for n in build_graph_dict(_domains())["nodes"]}.get("Structure")
    out = []
    if not config_dir.exists():
        return out
    for f in sorted(config_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        # The as-given cell size decides whether the full dict rides along; fall
        # back to the primitive count for older records without natoms.
        natoms = rec.get("natoms")
        if natoms is None:
            natoms = rec.get("canonical", {}).get("natoms_primitive")
        bundle = {
            "name": rec.get("name"),
            "formula": rec.get("formula"),
            "natoms": rec.get("natoms"),
            "canonical": rec.get("canonical", {}),
            "external_ids": rec.get("external_ids", {}),
            "provenance": rec.get("provenance", []),
            "files": rec.get("files"),
            "node_uid": structure_uid,
            "file": f.name,
        }
        payload = rec.get("structure")
        # Keep the full structure dict only for small ordered cells; larger cells
        # drop it from the bundle (the per-record file keeps it) so the bundle
        # stays light enough for the site to load every configuration at once.
        is_full = isinstance(payload, dict) and "@class" in payload
        if payload is not None and (
                not is_full or (natoms is not None
                                and natoms <= _BUNDLE_INLINE_ATOM_LIMIT)):
            bundle["structure"] = payload
        out.append(bundle)
    return out


def write_configurations(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "configurations.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_configurations()))
    return path


# Source / parameter nodes that carry a value INTO a calculation rather than
# recording an evidence-worthy result of one. A claim landing on any of these is
# CONTEXT (a condition), never a minted value instance (spec section 6). Tier is
# not the discriminator (the Sources tier also holds measured evidence targets
# like BornCharges); this explicit set is, reviewable in one place. Structure is
# here because its evidence home is the configuration record, not a scalar
# instance.
_NON_EVIDENCE_NODES = frozenset({
    "Structure",
    "Temperature",
    "Potential",
    "CellVolume",
    "AtomicMass",
    "AtomCount",
    "IsotopeAbundances",
    "AssessedDatabase",
    "CarrierDensity",
})


def build_catalog(domains: tuple[Domain, ...]) -> list[dict]:
    g = build_graph_dict(domains)
    space_by_name = {}
    for d in domains:
        for s in d.nodes:
            space_by_name[s.name] = s

    # Build a map of promoted-parameter id -> dimension name (4-tuple entries only)
    # and -> one-line description (5-tuple entries carry it).
    param_dim: dict[str, str] = {}
    param_desc: dict[str, str] = {}
    for d in domains:
        for p in d.param_promotions:
            if len(p) >= 4 and p[3]:
                param_dim[p[0]] = p[3]
            if len(p) >= 5 and p[4]:
                param_desc[p[0]] = p[4]

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
        # A promoted parameter carries its own one-liner (the space lookup does
        # not see it).
        desc = param_desc.get(n["id"], desc)
        out.append({
            "id": n["id"],
            "symbol": n["symbol"],
            "type": n["type"],
            "dimension": dim,
            "description": desc,
            "evidence_target": n["id"] not in _NON_EVIDENCE_NODES,
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
    print("wrote", write_spectra())
    print("wrote", write_configurations())
    print("wrote", write_codes())
    print("wrote", write_catalog())
    print("wrote", write_version())
