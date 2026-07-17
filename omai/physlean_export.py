"""physlib export (Tier 1): the map's dimensional layer, verified in Lean.

physlib (leanprover-community/physlib, Apache 2.0, the successor of PhysLean
by Joseph Tooby-Smith) formalizes physical dimensions as a rational-exponent
vector in Lean 4 / Mathlib. Our operator layer proves, for every executable
edge, that the output's dimension equals the product of the input dimensions.
This module exports that proven layer as a Lean file: each node a dimensioned
constant, each dimension-proven edge a theorem stating the output dimension
equals the product of the input dimensions, proved by extensionality plus simp
with physlib's `*_mul` lemmas. The generated file COMPILES against physlib
(Lean 4.31.0) as part of the lake package in lean/; the CI test re-checks each
identity in Python so a regression fails fast even where a Lean toolchain is
absent.

The bridge is honest about its boundary. physlib's Dimension has five base
fields (length, time, mass, charge, temperature); ours has seven
(M, L, T, Th, N, I, J). The four shared bases map directly. Nodes whose
dimension uses amount-of-substance (mole, N) or luminous intensity (J), which
physlib lacks, are OMITTED and recorded, not silently mangled: extending
physlib's Dimension with a mole base is an upstreamable contribution for a
later tier. Current (I) maps onto physlib's charge base only up to the
charge-vs-current convention, so I-bearing nodes are omitted here too.

CLI:  python -m omai.physlean_export   ->  writes lean/OpenMaterials.lean
"""
from __future__ import annotations

import re
from pathlib import Path

from omai.map_data import DOMAINS, build_graph_dict

_REPO = Path(__file__).resolve().parent.parent

# our base order (M, L, T, Th, N, I, J) -> physlib field name, for the four we share.
# Index in our exponent tuple -> physlib Dimension field. None = no physlib home.
_OUR_BASE = ("M", "L", "T", "Th", "N", "I", "J")
_PHYSLIB_FIELD = {
    0: "mass",         # M
    1: "length",       # L
    2: "time",         # T
    3: "temperature",  # Th
    4: None,           # N  (amount of substance): physlib has no mole base
    5: None,           # I  (current): physlib has charge, not current; omit for now
    6: None,           # J  (luminous intensity): no physlib base
}


def _lean_ident(name: str) -> str:
    """A node/edge id -> a valid Lean identifier (labels flattened)."""
    s = re.sub(r"[\[\]=,]", "_", name)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "n_" + s
    return s or "unnamed"


def _proof_defs(target, srcs):
    """The def idents a lemma's simp call unfolds: target plus each source."""
    seen, out = set(), []
    for name in [target] + list(srcs):
        i = _lean_ident(name)
        if i not in seen:
            seen.add(i); out.append(i)
    return ", ".join(out)


def _q(n: int) -> str:
    """A Lean rational literal for an integer exponent (Dimension fields are Q)."""
    return f"({n} : ℚ)" if n < 0 else f"{n}"


def _dimension_expr(exps: tuple[int, ...]) -> str | None:
    """A physlib `Dimension` literal ⟨length, time, mass, charge, temperature⟩,
    or None if the exponents use a base physlib lacks."""
    fields = {"length": 0, "time": 0, "mass": 0, "charge": 0, "temperature": 0}
    for i, e in enumerate(exps):
        if e == 0:
            continue
        pf = _PHYSLIB_FIELD.get(i)
        if pf is None:
            return None  # uses mole / current / luminous: no physlib home
        fields[pf] = e
    return "⟨{length}, {time}, {mass}, {charge}, {temperature}⟩".format(
        length=_q(fields["length"]), time=_q(fields["time"]), mass=_q(fields["mass"]),
        charge=_q(fields["charge"]), temperature=_q(fields["temperature"]))


def _node_dimensions():
    """Every node id -> (exponents, physlib_expr_or_None), from the live domains."""
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
    # it as a Lean theorem proved by ext + simp with physlib's *_mul lemmas).
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
        "  OpenMaterials: the map's dimensional layer, verified in Lean.",
        "",
        "  Generated by omai.physlean_export from map version " + ver + ".",
        "  This file COMPILES against physlib (Lean 4.31.0): each node is a",
        "  physlib Dimension and each theorem states an edge's output dimension",
        "  equals the product of its input dimensions, proved by ext + simp. Nodes whose",
        "  dimension uses amount-of-substance, current, or luminous intensity are",
        "  omitted: physlib's Dimension has no base for them (see the module).",
        "",
        "  physlib (leanprover-community/physlib), successor of PhysLean by",
        "  Joseph Tooby-Smith, Apache 2.0.",
        "-/",
        "import Physlib.Units.Dimension",
        "",
        "namespace OpenMaterials",
        "",
        "open Dimension",
        "",
        "-- Nodes as dimensioned constants (physlib field order: length, time, mass, charge, temperature).",
    ]
    for name in sorted(nodes):
        lines.append(f"def {_lean_ident(name)} : Dimension := {nodes[name]}  -- {name}")
    lines.append("")
    lines.append("-- Edge dimensional identities: output dimension = product of input")
    lines.append("-- dimensions. Proved by extensionality on the five Dimension fields, then")
    lines.append("-- simp with physlib's *_mul lemmas and the node definitions.")
    for op, target, srcs, prod in lemmas:
        lem = "edge_" + _lean_ident(op) + "_to_" + _lean_ident(target)
        lines.append(f"theorem {lem} : {_lean_ident(target)} = {prod} := by")
        lines.append(f"  apply Dimension.ext <;> simp [{_proof_defs(target, srcs)}]")
    lines.append("")
    lines.append("end OpenMaterials")
    lines.append("")
    return "\n".join(lines)


def _dim7_expr(exps: tuple[int, ...]) -> str:
    """An OpenMaterials seven-base `Dimension7` literal ⟨M, L, T, Th, N, I, J⟩."""
    return "⟨" + ", ".join(_q(e) for e in exps) + "⟩"


def build_dimensions_export():
    """Return (lean_source, stats) for the Mathlib-only seven-base module.

    The physlib bridge (build_export) omits nodes whose dimension uses
    amount-of-substance, current, or luminous intensity, since physlib's
    Dimension has no base for them. This module covers exactly that remainder:
    a seven-base Dimension7 structure (M, L, T, Th, N, I, J) with its own ext
    lemma and Mul instance, one constant per omitted node, and a theorem per
    dimension-product edge ALL of whose endpoints are omitted nodes (edges with
    any physlib-exported endpoint stay in OpenMaterials.lean; keeping the two
    files' namespaces disjoint means no duplicate declarations)."""
    graph = build_graph_dict(DOMAINS)
    node_dims = _node_dimensions()
    omitted = {name: exps for name, (exps, expr) in node_dims.items() if expr is None}

    producers = {}
    for l in graph["links"]:
        if l.get("op"):
            producers.setdefault((l["op"], l["target"]), set()).add(l["source"])

    lemmas = []
    for (op, target), sources in sorted(producers.items()):
        if op.startswith("provide_"):
            continue  # parameter-promotion presentation links, not operators
        srcs = sorted(sources)
        endpoints = set(srcs) | {target}
        if not endpoints <= set(omitted):
            continue  # physlib-exported endpoints live in OpenMaterials.lean
        tgt_exps = node_dims[target][0]
        acc = [0] * len(tgt_exps)
        for s in srcs:
            for i, e in enumerate(node_dims[s][0]):
                acc[i] += e
        if tuple(acc) != tuple(tgt_exps):
            continue  # not a pure dimensional product
        prod = " * ".join(_lean_ident(s) for s in srcs)
        lemmas.append((op, target, srcs, prod))

    src = _render_dimensions({n: _dim7_expr(e) for n, e in omitted.items()}, lemmas)
    stats = {
        "nodes": len(omitted),
        "lemmas": len(lemmas),
        "map_version": (json_version() or "")[:12],
    }
    return src, stats


def _render_dimensions(nodes: dict, lemmas: list) -> str:
    ver = (json_version() or "unknown")[:12]
    lines = [
        "/-",
        "  OpenMaterials: the seven-base dimensional layer, Mathlib only.",
        "",
        "  Generated by omai.physlean_export from map version " + ver + ".",
        "  physlib's Dimension has five bases, so nodes whose dimension uses",
        "  amount-of-substance (N), electric current (I), or luminous intensity (J)",
        "  are omitted from OpenMaterials.lean. This module defines the map's full",
        "  seven-base dimension vector (M, L, T, Th, N, I, J) and proves the",
        "  dimensional identities for exactly those omitted nodes. Requires only",
        "  Mathlib (Lean 4.31.0).",
        "-/",
        "import Mathlib.Tactic",
        "",
        "namespace OpenMaterials",
        "",
        "/-- The map's seven-base dimension vector, in the map's base order:",
        "    mass, length, time, temperature, amount of substance, electric",
        "    current, luminous intensity. -/",
        "structure Dimension7 where",
        "  /-- The mass dimension (M). -/",
        "  M : ℚ",
        "  /-- The length dimension (L). -/",
        "  L : ℚ",
        "  /-- The time dimension (T). -/",
        "  T : ℚ",
        "  /-- The temperature dimension (Th). -/",
        "  Th : ℚ",
        "  /-- The amount-of-substance dimension (N). -/",
        "  N : ℚ",
        "  /-- The electric-current dimension (I). -/",
        "  I : ℚ",
        "  /-- The luminous-intensity dimension (J). -/",
        "  J : ℚ",
        "",
        "namespace Dimension7",
        "",
        "@[ext]",
        "lemma ext {d1 d2 : Dimension7}",
        "    (hM : d1.M = d2.M) (hL : d1.L = d2.L) (hT : d1.T = d2.T)",
        "    (hTh : d1.Th = d2.Th) (hN : d1.N = d2.N) (hI : d1.I = d2.I)",
        "    (hJ : d1.J = d2.J) : d1 = d2 := by",
        "  cases d1",
        "  cases d2",
        "  congr",
        "",
        "instance : Mul Dimension7 where",
        "  mul d1 d2 := ⟨d1.M + d2.M, d1.L + d2.L, d1.T + d2.T, d1.Th + d2.Th,",
        "    d1.N + d2.N, d1.I + d2.I, d1.J + d2.J⟩",
        "",
    ]
    for f in ("M", "L", "T", "Th", "N", "I", "J"):
        lines.append("@[simp]")
        lines.append(f"lemma {f}_mul (d1 d2 : Dimension7) : (d1 * d2).{f} = d1.{f} + d2.{f} := rfl")
        lines.append("")
    lines.append("end Dimension7")
    lines.append("")
    lines.append("-- The nodes physlib cannot express, as seven-base constants")
    lines.append("-- (map base order: M, L, T, Th, N, I, J).")
    for name in sorted(nodes):
        lines.append(f"def {_lean_ident(name)} : Dimension7 := {nodes[name]}  -- {name}")
    lines.append("")
    lines.append("-- Edge dimensional identities among the omitted nodes: output dimension")
    lines.append("-- = product of input dimensions, by ext + simp, as in OpenMaterials.lean.")
    for op, target, srcs, prod in lemmas:
        lem = "edge_" + _lean_ident(op) + "_to_" + _lean_ident(target)
        lines.append(f"theorem {lem} : {_lean_ident(target)} = {prod} := by")
        lines.append(f"  apply Dimension7.ext <;> simp [{_proof_defs(target, srcs)}]")
    lines.append("")
    lines.append("end OpenMaterials")
    lines.append("")
    return "\n".join(lines)


def build_lean_index():
    """A browser-consumable index of the Lean export, so the frontend can show
    the actual Lean for the element you are looking at. Keyed by node id and by
    edge op; a node/edge absent from the index simply was not exported (uses a
    base physlib lacks, or is not a pure dimensional product)."""
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
        lem = "edge_" + _lean_ident(op) + "_to_" + _lean_ident(target)
        proof = f"apply Dimension.ext <;> simp [{_proof_defs(target, srcs)}]"
        edges[op] = {"lean": f"theorem {lem} :\n  {_lean_ident(target)} = {prod} := by\n  {proof}"}

    # Tier 2: the algebraic composition theorems, keyed by edge op, merged in so
    # an identity edge can show both its dimension proof and its algebra proof.
    identities = {}
    try:
        from omai.lean_identities import build_index as _ids
        identities = _ids()
    except Exception:
        identities = {}

    return {
        "version": (json_version() or "")[:12],
        "nodes": nodes,          # id -> {lean}  (Tier 1 dimensions)
        "edges": edges,          # op -> {lean}  (Tier 1 dimension identities)
        "identities": identities,  # op -> {lean, kind}  (Tier 2 compositions)
    }


def write_export(out: Path | None = None, index_out: Path | None = None):
    out = out or (_REPO / "lean" / "OpenMaterials.lean")
    out.parent.mkdir(parents=True, exist_ok=True)
    src, stats = build_export()
    out.write_text(src)
    # the seven-base companion module for the nodes physlib cannot express
    dim_src, dim_stats = build_dimensions_export()
    (out.parent / "OpenMaterialsDimensions.lean").write_text(dim_src)
    stats["dim7_nodes"] = dim_stats["nodes"]
    stats["dim7_lemmas"] = dim_stats["lemmas"]
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
