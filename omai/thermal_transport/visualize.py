"""Generate an interactive HTML visualization of the thermal-transport DAG.

Walks the abstract layer (omai.thermal_transport.symbolic) and the materialized
adapter specs (omai.thermal_transport.materialized.{kaldo,phono3py}) and emits
a single self-contained HTML file:

  * Mermaid-rendered DAG with Observables in blue and HiddenStates in gray
  * adapter-coverage badges (K, P) on nodes that have a StateAdapterSpec
  * click on a node → details panel (fields, indices, conventions, adapter
    specs, cross-code factor)
  * click on an edge → details panel (sympy formula via MathJax, inputs,
    outputs, parameters, algorithmic conventions, adapter discretization
    choices where present)

Run:
    python -m omai.thermal_transport.visualize
to write docs/dag.html. The output is a single HTML file (no build step
needed at use time; loads Mermaid and MathJax from public CDNs).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import sympy as sp

from omai.abstract.state import HiddenState, Observable, State
from omai.materialization.adapter import (
    OperationAdapterSpec,
    StateAdapterSpec,
    cross_state_total_factor,
)
from omai.materialization.units import UNITS
from omai.thermal_transport.materialized import kaldo as kaldo_specs
from omai.thermal_transport.materialized import phono3py as phono3py_specs
from omai.thermal_transport.symbolic import EDGES, NODES


# ---------------------------------------------------------------------------
# Mermaid: short ids and DAG body
# ---------------------------------------------------------------------------

# Mermaid identifiers must be alphanumeric / underscore. Map state names to ids.
def _mermaid_id(state: State) -> str:
    return (
        state.name
        .replace("[", "_")
        .replace("]", "")
        .replace("=", "_")
        .replace(" ", "")
    )


def _short_label(state: State) -> str:
    # Compact display label that fits inside a node box
    name = state.name
    if "[" in name:
        head, params = name.split("[", 1)
        return f"{head}<br/>[{params.rstrip(']')}]"
    return name


def _gauge_class(state: State) -> str:
    return "observable" if isinstance(state, Observable) else "hidden"


def _collect_specs() -> tuple[
    dict[str, StateAdapterSpec],
    dict[str, StateAdapterSpec],
    dict[str, OperationAdapterSpec],
    dict[str, OperationAdapterSpec],
]:
    """Index adapter specs by state/operation name."""
    kaldo_state_specs: dict[str, StateAdapterSpec] = {}
    phono3py_state_specs: dict[str, StateAdapterSpec] = {}
    kaldo_op_specs: dict[str, OperationAdapterSpec] = {}
    phono3py_op_specs: dict[str, OperationAdapterSpec] = {}

    for attr_name in dir(kaldo_specs):
        if attr_name.startswith("_"):
            continue
        obj = getattr(kaldo_specs, attr_name)
        if isinstance(obj, StateAdapterSpec):
            kaldo_state_specs[obj.state.name] = obj
        elif isinstance(obj, OperationAdapterSpec):
            kaldo_op_specs[obj.operation.name] = obj

    for attr_name in dir(phono3py_specs):
        if attr_name.startswith("_"):
            continue
        obj = getattr(phono3py_specs, attr_name)
        if isinstance(obj, StateAdapterSpec):
            phono3py_state_specs[obj.state.name] = obj
        elif isinstance(obj, OperationAdapterSpec):
            phono3py_op_specs[obj.operation.name] = obj

    return kaldo_state_specs, phono3py_state_specs, kaldo_op_specs, phono3py_op_specs


def _mermaid_diagram(
    kaldo_states: dict[str, StateAdapterSpec],
    phono3py_states: dict[str, StateAdapterSpec],
) -> str:
    lines = ["flowchart TD"]
    for state in NODES:
        nid = _mermaid_id(state)
        label = _short_label(state)
        badges = []
        if state.name in kaldo_states:
            badges.append("K")
        if state.name in phono3py_states:
            badges.append("P")
        badge = f" [{'/'.join(badges)}]" if badges else ""
        cls = _gauge_class(state)
        lines.append(f'  {nid}["{label}{badge}"]:::{cls}')

    for op in EDGES:
        for inp in op.inputs:
            for out in op.outputs:
                from_id = _mermaid_id(inp)
                to_id = _mermaid_id(out)
                op_label = op.name.split("[")[0]  # short verb-headed name
                lines.append(f"  {from_id} -->|{op_label}| {to_id}")

    # Edges for nullary (source) operations: synthetic origin node "_src" not needed;
    # sources appear as nodes with no upstream — Mermaid handles that fine.

    lines.append("")
    lines.append("  classDef observable fill:#3f7fc1,stroke:#2c5d8f,color:#fff,stroke-width:1px")
    lines.append("  classDef hidden fill:#888,stroke:#666,color:#fff,stroke-width:1px")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON data: node and edge details
# ---------------------------------------------------------------------------


def _state_to_json(
    state: State,
    kaldo_states: dict[str, StateAdapterSpec],
    phono3py_states: dict[str, StateAdapterSpec],
) -> dict:
    fields = [
        {
            "name": f.name,
            "dimension": f.dimension.name,
            "indices": list(f.indices),
        }
        for f in state.fields
    ]
    convention_factors = [
        {"convention": c[0], "value": c[1], "field": c[2], "factor": c[3]}
        for c in state.convention_factors
    ]

    def _spec_to_dict(spec: StateAdapterSpec | None) -> dict | None:
        if spec is None:
            return None
        return {
            "adapter": spec.adapter_name,
            "observable_units": dict(spec.observable_units),
            "observable_convention_overrides": dict(spec.observable_convention_overrides),
            "notes": spec.notes,
        }

    k = kaldo_states.get(state.name)
    p = phono3py_states.get(state.name)

    cross_factors: dict[str, float] = {}
    if k is not None and p is not None:
        for f in state.fields:
            try:
                cross_factors[f.name] = cross_state_total_factor(k, p, f.name)
            except Exception:
                pass

    return {
        "name": state.name,
        "physics_type": state.physics_type.value,
        "kind": "Observable" if isinstance(state, Observable) else "HiddenState",
        "fields": fields,
        "canonical_conventions": dict(state.canonical_conventions),
        "convention_factors": convention_factors,
        "type_parameters": {k_: str(v_) for k_, v_ in state.type_parameters.items()},
        "description": state.description,
        "kaldo_spec": _spec_to_dict(k),
        "phono3py_spec": _spec_to_dict(p),
        "cross_state_total_factors": cross_factors,
    }


def _operation_to_json(
    op,
    kaldo_ops: dict[str, OperationAdapterSpec],
    phono3py_ops: dict[str, OperationAdapterSpec],
) -> dict:
    formula_latex = sp.latex(op.formula) if op.formula is not None else None

    def _op_spec(spec: OperationAdapterSpec | None) -> dict | None:
        if spec is None:
            return None
        return {
            "adapter": spec.adapter_name,
            "parameter_units": dict(spec.parameter_units),
            "algorithmic_convention_overrides": dict(spec.algorithmic_convention_overrides),
            "discretization_choices": dict(spec.discretization_choices),
            "notes": spec.notes,
        }

    return {
        "name": op.name,
        "inputs": [s.name for s in op.inputs],
        "outputs": [s.name for s in op.outputs],
        "parameters": [
            {"name": p.name, "dimension": p.dimension.name}
            for p in op.parameters
        ],
        "algorithmic_conventions": dict(op.algorithmic_conventions),
        "formula_latex": formula_latex,
        "description": op.description,
        "kaldo_spec": _op_spec(kaldo_ops.get(op.name)),
        "phono3py_spec": _op_spec(phono3py_ops.get(op.name)),
    }


# ---------------------------------------------------------------------------
# HTML emission
# ---------------------------------------------------------------------------


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>omai — lattice thermal-transport DAG</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
         margin: 0; padding: 0; color: #222; background: #fafafa; }}
  header {{ padding: 1rem 1.5rem; background: #fff; border-bottom: 1px solid #e0e0e0; }}
  h1 {{ margin: 0; font-size: 1.15rem; }}
  .subtitle {{ color: #666; font-size: 0.85rem; margin-top: 0.25rem; }}
  .badges {{ display: inline-block; margin-left: 0.5rem; font-size: 0.7rem; color: #666; }}
  main {{ display: grid; grid-template-columns: 1fr 480px; gap: 1.5rem;
          padding: 1.5rem; min-height: calc(100vh - 80px); }}
  #diagram {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 4px;
              padding: 1rem; overflow: auto; }}
  #details {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 4px;
              padding: 1rem; overflow-y: auto; max-height: calc(100vh - 130px); }}
  #details h2 {{ margin-top: 0; font-size: 1rem; }}
  #details .kind {{ display: inline-block; font-size: 0.7rem; padding: 0.1rem 0.5rem;
                    border-radius: 3px; color: #fff; margin-left: 0.5rem;
                    vertical-align: middle; }}
  #details .kind.Observable {{ background: #3f7fc1; }}
  #details .kind.HiddenState {{ background: #888; }}
  #details table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem;
                   margin: 0.5rem 0; }}
  #details th, #details td {{ padding: 0.3rem 0.5rem; border-bottom: 1px solid #eee;
                              text-align: left; vertical-align: top; }}
  #details th {{ background: #f5f5f5; font-weight: 600; }}
  #details code {{ background: #f0f0f0; padding: 0 0.25rem; border-radius: 3px;
                   font-size: 0.85em; }}
  #details .section {{ margin-top: 1rem; }}
  #details .section h3 {{ font-size: 0.85rem; text-transform: uppercase;
                          letter-spacing: 0.05em; color: #888; margin: 0 0 0.4rem 0; }}
  .formula {{ background: #fafafa; border: 1px solid #eee; padding: 0.75rem;
              border-radius: 3px; margin: 0.5rem 0; overflow-x: auto; }}
  .empty {{ color: #999; font-style: italic; font-size: 0.85rem; }}
  .legend {{ display: flex; gap: 1rem; font-size: 0.8rem; color: #555;
             margin-top: 0.5rem; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 0.4rem; }}
  .swatch {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
  .placeholder {{ color: #aaa; padding: 2rem; text-align: center; font-size: 0.9rem; }}
  /* Mermaid clickable nodes */
  .node {{ cursor: pointer; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  window.MathJax = {{
    tex: {{ inlineMath: [['$', '$']], displayMath: [['$$', '$$']] }},
    svg: {{ fontCache: 'global' }}
  }};
</script>
<script id="MathJax-script" async
        src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
</head>
<body>
<header>
  <h1>omai &mdash; lattice thermal-transport DAG
    <span class="badges">{n_observables} Observables &middot; {n_hidden} HiddenStates &middot;
                          {n_edges} edges</span></h1>
  <div class="subtitle">click a node or edge for details &middot;
    <span class="legend">
      <span class="legend-item"><span class="swatch" style="background:#3f7fc1"></span>Observable (gauge-invariant)</span>
      <span class="legend-item"><span class="swatch" style="background:#888"></span>HiddenState (adapter-internal)</span>
      <span class="legend-item">[K] kaldo spec &middot; [P] phono3py spec</span>
    </span>
  </div>
</header>
<main>
  <div id="diagram">
    <pre class="mermaid">
{mermaid_source}
    </pre>
  </div>
  <div id="details">
    <div class="placeholder">click any node or edge</div>
  </div>
</main>

<script>
const NODE_DATA = {node_data_json};
const EDGE_DATA = {edge_data_json};
const NODE_ID_TO_NAME = {node_id_to_name_json};
const EDGE_BY_PAIR = {edge_by_pair_json};

function escapeHtml(s) {{
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

function renderNode(name) {{
  const d = NODE_DATA[name];
  if (!d) return `<div class="empty">no data for ${{escapeHtml(name)}}</div>`;
  let html = `<h2>${{escapeHtml(d.name)}} <span class="kind ${{d.kind}}">${{d.kind}}</span></h2>`;
  if (d.description) html += `<p>${{escapeHtml(d.description)}}</p>`;
  html += `<div class="section"><h3>Physics type</h3><code>${{escapeHtml(d.physics_type)}}</code></div>`;

  if (d.fields.length) {{
    html += '<div class="section"><h3>Fields</h3><table><tr><th>name</th><th>dimension</th><th>indices</th></tr>';
    for (const f of d.fields) {{
      html += `<tr><td><code>${{escapeHtml(f.name)}}</code></td>` +
              `<td>${{escapeHtml(f.dimension)}}</td>` +
              `<td>${{f.indices.length ? f.indices.map(escapeHtml).join(', ') : '<span class="empty">(scalar)</span>'}}</td></tr>`;
    }}
    html += '</table></div>';
  }}

  if (Object.keys(d.canonical_conventions).length) {{
    html += '<div class="section"><h3>Canonical conventions</h3><table>';
    for (const [k, v] of Object.entries(d.canonical_conventions)) {{
      html += `<tr><td><code>${{escapeHtml(k)}}</code></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
    }}
    html += '</table></div>';
  }}

  if (d.convention_factors.length) {{
    html += '<div class="section"><h3>Convention factors</h3><table>' +
            '<tr><th>convention</th><th>value</th><th>field</th><th>factor</th></tr>';
    for (const c of d.convention_factors) {{
      html += `<tr><td><code>${{escapeHtml(c.convention)}}</code></td>` +
              `<td><code>${{escapeHtml(c.value)}}</code></td>` +
              `<td><code>${{escapeHtml(c.field)}}</code></td>` +
              `<td>${{c.factor}}</td></tr>`;
    }}
    html += '</table></div>';
  }}

  for (const [adapter, spec] of [['kaldo', d.kaldo_spec], ['phono3py', d.phono3py_spec]]) {{
    html += `<div class="section"><h3>${{adapter}}</h3>`;
    if (!spec) {{
      html += '<div class="empty">no adapter spec yet</div>';
    }} else {{
      if (Object.keys(spec.observable_units).length) {{
        html += '<table>';
        for (const [k, v] of Object.entries(spec.observable_units)) {{
          html += `<tr><td>unit (<code>${{escapeHtml(k)}}</code>)</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
        }}
        for (const [k, v] of Object.entries(spec.observable_convention_overrides)) {{
          html += `<tr><td>${{escapeHtml(k)}}</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
        }}
        html += '</table>';
      }}
      if (spec.notes) html += `<p style="font-size:0.85rem; color:#555">${{escapeHtml(spec.notes)}}</p>`;
    }}
    html += '</div>';
  }}

  if (Object.keys(d.cross_state_total_factors).length) {{
    html += '<div class="section"><h3>Cross-code factor (kaldo → phono3py)</h3><table>';
    for (const [k, v] of Object.entries(d.cross_state_total_factors)) {{
      html += `<tr><td><code>${{escapeHtml(k)}}</code></td><td>${{v.toExponential(4)}}</td></tr>`;
    }}
    html += '</table></div>';
  }}

  return html;
}}

function renderEdge(name) {{
  const d = EDGE_DATA[name];
  if (!d) return `<div class="empty">no data for ${{escapeHtml(name)}}</div>`;
  let html = `<h2>${{escapeHtml(d.name)}}</h2>`;
  if (d.description) html += `<p>${{escapeHtml(d.description)}}</p>`;

  html += `<div class="section"><h3>Inputs</h3>${{d.inputs.length ?
            '<ul>' + d.inputs.map(s => `<li><code>${{escapeHtml(s)}}</code></li>`).join('') + '</ul>' :
            '<div class="empty">(no inputs &mdash; nullary source)</div>'}}</div>`;
  html += `<div class="section"><h3>Outputs</h3><ul>` +
          d.outputs.map(s => `<li><code>${{escapeHtml(s)}}</code></li>`).join('') + `</ul></div>`;

  if (d.parameters.length) {{
    html += '<div class="section"><h3>Parameters</h3><table>' +
            '<tr><th>name</th><th>dimension</th></tr>';
    for (const p of d.parameters) {{
      html += `<tr><td><code>${{escapeHtml(p.name)}}</code></td><td>${{escapeHtml(p.dimension)}}</td></tr>`;
    }}
    html += '</table></div>';
  }}

  if (Object.keys(d.algorithmic_conventions).length) {{
    html += '<div class="section"><h3>Algorithmic conventions</h3><table>';
    for (const [k, v] of Object.entries(d.algorithmic_conventions)) {{
      html += `<tr><td><code>${{escapeHtml(k)}}</code></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
    }}
    html += '</table></div>';
  }}

  if (d.formula_latex) {{
    html += `<div class="section"><h3>Formula</h3><div class="formula">$$${{d.formula_latex}}$$</div></div>`;
  }}

  for (const [adapter, spec] of [['kaldo', d.kaldo_spec], ['phono3py', d.phono3py_spec]]) {{
    html += `<div class="section"><h3>${{adapter}}</h3>`;
    if (!spec) {{
      html += '<div class="empty">no operation-adapter spec yet</div>';
    }} else {{
      let any = false;
      let tbl = '<table>';
      for (const [k, v] of Object.entries(spec.parameter_units)) {{
        tbl += `<tr><td>unit (<code>${{escapeHtml(k)}}</code>)</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
        any = true;
      }}
      for (const [k, v] of Object.entries(spec.algorithmic_convention_overrides)) {{
        tbl += `<tr><td>${{escapeHtml(k)}}</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
        any = true;
      }}
      for (const [k, v] of Object.entries(spec.discretization_choices)) {{
        tbl += `<tr><td>${{escapeHtml(k)}}</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
        any = true;
      }}
      tbl += '</table>';
      if (any) html += tbl;
      if (spec.notes) html += `<p style="font-size:0.85rem; color:#555">${{escapeHtml(spec.notes)}}</p>`;
      if (!any && !spec.notes) html += '<div class="empty">(no parameters or conventions)</div>';
    }}
    html += '</div>';
  }}

  return html;
}}

function showDetails(html) {{
  const panel = document.getElementById('details');
  panel.innerHTML = html;
  if (window.MathJax && MathJax.typesetPromise) {{
    MathJax.typesetPromise([panel]);
  }}
}}

document.addEventListener('DOMContentLoaded', async () => {{
  mermaid.initialize({{ startOnLoad: false, securityLevel: 'loose', flowchart: {{ curve: 'basis' }} }});
  await mermaid.run({{ querySelector: '.mermaid' }});

  // Wire click handlers on rendered nodes and edges
  document.querySelectorAll('#diagram .node').forEach(el => {{
    el.addEventListener('click', () => {{
      const id = el.id.replace(/^flowchart-/, '').replace(/-\\d+$/, '');
      const name = NODE_ID_TO_NAME[id];
      if (name) showDetails(renderNode(name));
    }});
  }});

  document.querySelectorAll('#diagram .edgePaths .edgePath, #diagram .edgeLabels .edgeLabel').forEach(el => {{
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => {{
      // Mermaid annotates edge label text with the operation name
      const lbl = el.querySelector('.edgeLabel, foreignObject span');
      const text = (lbl ? lbl.textContent : el.textContent).trim();
      // text is the short name, e.g. "compute_linewidth"; find a matching EDGE_DATA entry
      let candidate = null;
      for (const fullName of Object.keys(EDGE_DATA)) {{
        if (fullName === text || fullName.startsWith(text + '[')) {{
          if (!candidate || fullName.length > candidate.length) candidate = fullName;
        }}
      }}
      if (candidate) showDetails(renderEdge(candidate));
    }});
  }});
}});
</script>
</body>
</html>
"""


def render_html(output_path: Path | str) -> Path:
    kaldo_states, phono3py_states, kaldo_ops, phono3py_ops = _collect_specs()
    mermaid_source = _mermaid_diagram(kaldo_states, phono3py_states)

    node_data = {
        state.name: _state_to_json(state, kaldo_states, phono3py_states)
        for state in NODES
    }
    edge_data = {
        op.name: _operation_to_json(op, kaldo_ops, phono3py_ops)
        for op in EDGES
    }

    n_observables = sum(1 for s in NODES if isinstance(s, Observable))
    n_hidden = sum(1 for s in NODES if isinstance(s, HiddenState))

    node_id_to_name = {_mermaid_id(state): state.name for state in NODES}
    # Index edge by (from, to) — useful for click resolution
    edge_by_pair: dict[str, str] = {}
    for op in EDGES:
        for inp in op.inputs:
            for out in op.outputs:
                edge_by_pair[f"{_mermaid_id(inp)}->{_mermaid_id(out)}"] = op.name

    html = _HTML_TEMPLATE.format(
        n_observables=n_observables,
        n_hidden=n_hidden,
        n_edges=len(EDGES),
        mermaid_source=mermaid_source,
        node_data_json=json.dumps(node_data, indent=2),
        edge_data_json=json.dumps(edge_data, indent=2),
        node_id_to_name_json=json.dumps(node_id_to_name),
        edge_by_pair_json=json.dumps(edge_by_pair),
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


def main() -> None:
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    out = render_html(repo_root / "docs" / "dag.html")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
