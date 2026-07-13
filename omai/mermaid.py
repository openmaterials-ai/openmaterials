"""Mermaid export: map views renderable anywhere markdown is.

GitHub, GitLab, Obsidian, and most markdown viewers render ```mermaid blocks
natively, so a sub-map exported as Mermaid text is instantly embeddable in a
README, an issue, a PR description, or a paper's supplementary notes: no
webview, no server, no image pipeline.

Three inputs, one output shape (a `flowchart LR`):

  * a node id            -> its upstream lineage (how the map produces it)
  * a map view {v, e}    -> exactly those edges (the playground's share format)
  * a parser proposal    -> the paper's dataflow (the edges producing the
                            quantities the paper reports)

Node ids carry labels like [bte_solver=rta], which Mermaid cannot use as bare
identifiers; every node gets a sanitized id and a quoted label, so the output
renders verbatim. Observable nodes are styled; the map's semantic colors ride
along in a classDef so the diagram reads like the site.

CLI:
  python -m omai.mermaid ThermalConductivity            # lineage of a node
  python -m omai.mermaid --view  shared-map.json        # a {v, e} map view
  python -m omai.mermaid --proposal proposals/x.json    # a paper's dataflow
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# the site's semantic colors (docs/assets: observable indigo, hidden slate)
_CLASSDEFS = (
    "  classDef observable fill:#eef2ff,stroke:#4f46e5,color:#312e81;\n"
    "  classDef hidden fill:#f4f6fa,stroke:#7c89a0,color:#3d4149;\n"
    "  classDef parameter fill:#f6f7f9,stroke:#94a3b8,color:#475569;\n"
)


def _load_graph() -> dict:
    return json.loads((_REPO / "docs" / "data" / "graph.json").read_text())


def _mid(name: str, seen: dict) -> str:
    """A stable Mermaid-safe identifier for a node id."""
    if name in seen:
        return seen[name]
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    s = re.sub(r"_+", "_", s).strip("_") or "n"
    base, n = s, 2
    while s in seen.values():
        s = f"{base}_{n}"
        n += 1
    seen[name] = s
    return s


def _op_label(op: str) -> str:
    return op.replace("[", " ").replace("]", "").replace("=", " ").replace("_", " ").strip()


def mermaid_from_edges(edges, graph: dict | None = None, title: str | None = None) -> str:
    """[[from, op, to], ...] -> a mermaid flowchart. Unknown nodes still render
    (typed styling just needs the graph)."""
    graph = graph or _load_graph()
    types = {n["id"]: n.get("type", "hidden") for n in graph["nodes"]}
    seen: dict = {}
    lines = ["flowchart LR"]
    if title:
        lines.insert(0, f"---\ntitle: {title}\n---")
    nodes_used, edge_lines = [], []
    for tr in edges:
        if not (isinstance(tr, (list, tuple)) and len(tr) == 3):
            continue
        a, op, b = tr
        ia, ib = _mid(a, seen), _mid(b, seen)
        edge_lines.append(f'  {ia} -- "{_op_label(str(op))}" --> {ib}')
    for name, ident in seen.items():
        cls = types.get(name, "hidden")
        nodes_used.append(f'  {ident}["{name}"]:::{cls}')
    return "\n".join(lines + nodes_used + edge_lines + [_CLASSDEFS.rstrip()]) + "\n"


def mermaid_lineage(node_id: str, graph: dict | None = None, max_edges: int = 40) -> str:
    """The upstream lineage of a node: every producing edge reachable walking
    inputs back toward the sources, capped at max_edges (stated in the output
    if hit, never silently)."""
    graph = graph or _load_graph()
    producers: dict = {}
    for l in graph["links"]:
        if l.get("op") and not str(l["op"]).startswith("provide_"):
            producers.setdefault(l["target"], []).append((l["source"], l["op"]))
    if node_id not in {n["id"] for n in graph["nodes"]}:
        raise ValueError(f"unknown node {node_id!r}")
    edges, queue, visited = [], [node_id], set()
    while queue and len(edges) < max_edges:
        cur = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        for src, op in producers.get(cur, []):
            edges.append([src, op, cur])
            if src not in visited:
                queue.append(src)
    out = mermaid_from_edges(edges, graph, title=f"{node_id}: lineage")
    if len(edges) >= max_edges:
        out += f"%% truncated at {max_edges} edges\n"
    return out


def mermaid_from_view(view: dict, graph: dict | None = None) -> str:
    """The playground's share format {v: version, e: [[from, op, to], ...]}."""
    title = f"map view ({str(view.get('v') or 'unversioned')[:12]})"
    return mermaid_from_edges(view.get("e") or [], graph, title=title)


def mermaid_from_proposal(proposal: dict, graph: dict | None = None) -> str:
    """A parsed paper's dataflow: the map's producing edges among the nodes the
    paper's surviving claims touch (the playground parse tab's logic)."""
    graph = graph or _load_graph()
    touched = set()
    for c in proposal.get("claims") or []:
        if c.get("node_id") and (c.get("validation") or {}).get("survives", True):
            touched.add(c["node_id"])
    edges = [[l["source"], l["op"], l["target"]] for l in graph["links"]
             if l.get("op") and not str(l["op"]).startswith("provide_")
             and l["target"] in touched]
    title = str(proposal.get("paper") or proposal.get("paper_slug") or "paper dataflow")[:80]
    return mermaid_from_edges(edges, graph, title=title)


if __name__ == "__main__":  # pragma: no cover - CLI
    import sys
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--view":
        print(mermaid_from_view(json.loads(Path(args[1]).read_text())))
    elif args[0] == "--proposal":
        print(mermaid_from_proposal(json.loads(Path(args[1]).read_text())))
    else:
        print(mermaid_lineage(args[0]))
