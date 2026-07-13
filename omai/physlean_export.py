"""PhysLean export (Tier 1): the map's dimensional layer, type-checked in Lean.

PhysLean (Joseph Tooby-Smith, Apache 2.0) formalizes physical dimensions as a
rational-exponent vector in Lean 4 / Mathlib. Our operator layer proves, for
every executable edge, that the output's dimension equals the product of the
input dimensions. This module exports that proven layer as a Lean file: each
node a dimensioned constant, each dimension-gate-PROVEN edge a lemma closed by
`decide` (dimension equality over rationals is decidable). The generated file
type-checks against PhysLean, so the claim "the map's dimensions are
machine-verified in a proof assistant" becomes literally true, not aspirational.

The bridge is honest about its boundary. PhysLean's Dimension has five base
fields (length, time, mass, charge, temperature); ours has seven
(M, L, T, Th, N, I, J). The four shared bases map directly. Nodes whose
dimension uses amount-of-substance (mole, N) or luminous intensity (J), which
PhysLean lacks, are OMITTED and recorded, not silently mangled: extending
PhysLean's Dimension with a mole base is an upstreamable contribution for a
later tier. Current (I) maps onto PhysLean's charge base only up to the
charge-vs-current convention, so I-bearing nodes are omitted here too.

CLI:  python -m omai.physlean_export   ->  writes physlean/OpenMaterials.lean
"""
from __future__ import annotations

import re
from pathlib import Path

from omai.map_data import DOMAINS, build_graph_dict

_REPO = Path(__file__).resolve().parent.parent

# our base order (M, L, T, Th, N, I, J) -> PhysLean field name, for the four we share.
# Index in our exponent tuple -> PhysLean Dimension field. None = no PhysLean home.
_OUR_BASE = ("M", "L", "T", "Th", "N", "I", "J")
_PHYSLEAN_FIELD = {
    0: "mass",         # M
    1: "length",       # L
    2: "time",         # T
    3: "temperature",  # Th
    4: None,           # N  (amount of substance): PhysLean has no mole base
    5: None,           # I  (current): PhysLean has charge, not current; omit for now
    6: None,           # J  (luminous intensity): no PhysLean base
}


def _lean_ident(name: str) -> str:
    """A node/edge id -> a valid Lean identifier (labels flattened)."""
    s = re.sub(r"[\[\]=,]", "_", name)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "n_" + s
    return s or "unnamed"


def _q(n: int) -> str:
    """A Lean rational literal for an integer exponent (Dimension fields are Q)."""
    return f"({n} : ℚ)" if n < 0 else f"{n}"


def _dimension_expr(exps: tuple[int, ...]) -> str | None:
    """A PhysLean `Dimension` literal ⟨length, time, mass, charge, temperature⟩,
    or None if the exponents use a base PhysLean lacks."""
    fields = {"length": 0, "time": 0, "mass": 0, "charge": 0, "temperature": 0}
    for i, e in enumerate(exps):
        if e == 0:
            continue
        pf = _PHYSLEAN_FIELD.get(i)
        if pf is None:
            return None  # uses mole / current / luminous: no PhysLean home
        fields[pf] = e
    return "⟨{length}, {time}, {mass}, {charge}, {temperature}⟩".format(
        length=_q(fields["length"]), time=_q(fields["time"]), mass=_q(fields["mass"]),
        charge=_q(fields["charge"]), temperature=_q(fields["temperature"]))


def _node_dimensions():
    """Every node id -> (exponents, physlean_expr_or_None), from the live domains."""
    out = {}
    for dom in DOMAINS:
        for n in dom.nodes:
            if not getattr(n, "fields", None):
                continue
            exps = n.fields[0].dimension.exponents
            if exps is None:
                continue  # opaque dimension: no dimensional content to prove
            out[n.name] = (exps, _dimension_expr(exps))
    return out


def build_export():
    """Return (lean_source, stats). stats records what was exported vs omitted."""
    graph = build_graph_dict(DOMAINS)
    node_dims = _node_dimensions()

    exported_nodes, omitted_nodes = {}, []
    for name, (exps, expr) in sorted(node_dims.items()):
        if expr is None:
            omitted_nodes.append(name)
        else:
            exported_nodes[name] = expr

    # An edge's dimensional claim: output dimension = product of input dimensions.
    # We assert it only for edges every one of whose endpoints exported (so the
    # Lean statement is well-typed) and whose product actually holds (the
    # dimensional gate already proved this for executable edges; here we restate
    # it as a Lean lemma closed by decide).
    producers = {}
    for l in graph["links"]:
        if l.get("op"):
            producers.setdefault((l["op"], l["target"]), set()).add(l["source"])

    lemmas, skipped_edges = [], 0
    for (op, target), sources in sorted(producers.items()):
        if op.startswith("provide_"):
            continue  # parameter-promotion presentation links, not operators
        srcs = sorted(sources)
        if target not in exported_nodes or any(s not in exported_nodes for s in srcs):
            skipped_edges += 1
            continue
        # dimensional identity: does sum of source exponents == target exponents?
        tgt_exps = node_dims[target][0]
        acc = [0] * len(tgt_exps)
        for s in srcs:
            for i, e in enumerate(node_dims[s][0]):
                acc[i] += e
        if tuple(acc) != tuple(tgt_exps):
            skipped_edges += 1  # not a pure dimensional product (contraction / parameterized): skip
            continue
        prod = " * ".join(_lean_ident(s) for s in srcs)
        lemmas.append((op, target, srcs, prod))

    src = _render_lean(exported_nodes, lemmas, node_dims)
    stats = {
        "nodes_exported": len(exported_nodes),
        "nodes_omitted": len(omitted_nodes),
        "omitted_examples": omitted_nodes[:6],
        "lemmas": len(lemmas),
        "edges_skipped": skipped_edges,
        "map_version": (json_version() or "")[:12],
    }
    return src, stats


def json_version():
    import json
    p = _REPO / "docs" / "data" / "version.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("version")
        except Exception:
            return None
    return None


def _render_lean(nodes: dict, lemmas: list, node_dims: dict) -> str:
    ver = (json_version() or "unknown")[:12]
    lines = [
        "/-",
        "  OpenMaterials: the map's dimensional layer, type-checked in Lean.",
        "",
        "  Generated by omai.physlean_export from map version " + ver + ".",
        "  Each node is a PhysLean Dimension; each lemma states that an edge's",
        "  output dimension equals the product of its input dimensions, closed by",
        "  `decide` (dimension equality over rationals is decidable). Nodes whose",
        "  dimension uses amount-of-substance, current, or luminous intensity are",
        "  omitted: PhysLean's Dimension has no base for them (see the module).",
        "",
        "  PhysLean (c) Joseph Tooby-Smith, Apache 2.0.",
        "-/",
        "import PhysLean.Physlib.Units.Dimension",
        "",
        "namespace OpenMaterials",
        "",
        "open Dimension",
        "",
        "-- Nodes as dimensioned constants (PhysLean field order: length, time, mass, charge, temperature).",
    ]
    for name in sorted(nodes):
        lines.append(f"def {_lean_ident(name)} : Dimension := {nodes[name]}  -- {name}")
    lines.append("")
    lines.append("-- Edge dimensional identities: output = product of inputs, verified by decide.")
    for op, target, srcs, prod in lemmas:
        lem = "edge_" + _lean_ident(op) + "__to__" + _lean_ident(target)
        lines.append(f"theorem {lem} : {_lean_ident(target)} = {prod} := by decide")
    lines.append("")
    lines.append("end OpenMaterials")
    lines.append("")
    return "\n".join(lines)


def build_lean_index():
    """A browser-consumable index of the Lean export, so the frontend can show
    the actual Lean for the element you are looking at. Keyed by node id and by
    edge op; a node/edge absent from the index simply was not exported (uses a
    base PhysLean lacks, or is not a pure dimensional product)."""
    graph = build_graph_dict(DOMAINS)
    node_dims = _node_dimensions()

    nodes = {}
    for name, (exps, expr) in node_dims.items():
        if expr is not None:
            nodes[name] = {"lean": f"def {_lean_ident(name)} : Dimension := {expr}"}

    # reuse the lemma selection from build_export by re-deriving it identically
    producers = {}
    for l in graph["links"]:
        if l.get("op"):
            producers.setdefault((l["op"], l["target"]), set()).add(l["source"])
    edges = {}
    for (op, target), sources in producers.items():
        if op.startswith("provide_") or target not in nodes:
            continue
        srcs = sorted(sources)
        if any(s not in nodes for s in srcs):
            continue
        acc = [0] * len(node_dims[target][0])
        for s in srcs:
            for i, e in enumerate(node_dims[s][0]):
                acc[i] += e
        if tuple(acc) != tuple(node_dims[target][0]):
            continue
        prod = " * ".join(_lean_ident(s) for s in srcs)
        lem = "edge_" + _lean_ident(op) + "__to__" + _lean_ident(target)
        edges[op] = {"lean": f"theorem {lem} : {_lean_ident(target)} = {prod} := by decide"}

    return {
        "version": (json_version() or "")[:12],
        "nodes": nodes,   # id -> {lean}
        "edges": edges,   # op -> {lean}
    }


def write_export(out: Path | None = None, index_out: Path | None = None):
    out = out or (_REPO / "physlean" / "OpenMaterials.lean")
    out.parent.mkdir(parents=True, exist_ok=True)
    src, stats = build_export()
    out.write_text(src)
    # the browser index (docs/data/lean.json), so the frontend can surface Lean
    import json
    index_out = index_out or (_REPO / "docs" / "data" / "lean.json")
    index_out.parent.mkdir(parents=True, exist_ok=True)
    index_out.write_text(json.dumps(build_lean_index(), separators=(",", ":"), sort_keys=True))
    return out, stats


if __name__ == "__main__":  # pragma: no cover - CLI
    path, stats = write_export()
    print(f"wrote {path}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
