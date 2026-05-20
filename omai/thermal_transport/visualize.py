"""Generate an interactive HTML visualization of the thermal-transport DAG.

Layout: four side-by-side per-pipeline DAGs (Operator | kaldo |
phonopy/phono3py | shengbte), each rendered as circles + arrows in one
unified SVG. Row alignment is preserved across pipelines (a given
operator state sits at the same y in every column); horizontal x-spread
inside each column is determined by the DAG layer index, so converging
arrows are visually distinguishable.

Adapter discovery is automatic: any top-level submodule of
`omai.thermal_transport.representation` that exposes module-level
`SpaceRepresentationSpec` / `OperatorRepresentationSpec` instances is picked up.

Run:
    python -m omai.thermal_transport.visualize
to write docs/dag.html (single self-contained file; no build step).
"""

from __future__ import annotations

import html as _html
import importlib
import itertools
import json
import pkgutil
from pathlib import Path

import sympy as sp

from omai.operator.space import HiddenSpace, ObservableSpace, Space
from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
    operator_to_representation,
    representation_to_operator,
)
from omai.thermal_transport import representation as representation_pkg
from omai.thermal_transport.operator import EDGES, NODES


_PIPELINES = [
    {
        "id": "operator",
        "label": "Operator",
        "color": "#1F2937",
        "adapters": [],
        "is_operator": True,
    },
    # BTE-tier codes (phase 1)
    {
        "id": "kaldo",
        "label": "kaldo",
        "color": "#DC2626",
        "adapters": ["kaldo"],
        "is_operator": False,
    },
    {
        "id": "phono3py",
        "label": "phono3py",
        "color": "#059669",            # emerald
        "adapters": ["phono3py"],
        "is_operator": False,
    },
    {
        "id": "phonopy",
        "label": "phonopy",
        "color": "#0891B2",            # cyan-teal — adjacent to phono3py
        "adapters": ["phonopy"],
        "is_operator": False,
    },
    {
        "id": "shengbte",
        "label": "shengbte",
        "color": "#7C3AED",
        "adapters": ["shengbte"],
        "is_operator": False,
    },
    # MD-tier codes and the ASE Potential anchor (phase 2)
    {
        "id": "ase",
        "label": "ase",
        "color": "#F59E0B",            # amber — protocol-level Potential anchor
        "adapters": ["ase"],
        "is_operator": False,
    },
    {
        "id": "lammps",
        "label": "lammps",
        "color": "#EA580C",            # orange — adjacent to ase (LAMMPS-via-ASE shares the row)
        "adapters": ["lammps"],
        "is_operator": False,
    },
    {
        "id": "gpumd",
        "label": "gpumd",
        "color": "#DB2777",            # pink/magenta — standalone CUDA-MD code
        "adapters": ["gpumd"],
        "is_operator": False,
    },
]


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------


SYMBOLIC_COL_WIDTH = 620              # primary lane — extra-wide
MAT_COL_WIDTH = 720                   # plenty of room for long API names + arrow spread
COLUMN_GAP = 44
LEFT_PAD = 36
RIGHT_PAD = 28
TOP_PAD = 64
STAGE_HEADER_H = 38
ROW_HEIGHT = 82                       # more vertical room for arrow curves

# Represented circle (smaller, secondary)
MAT_NODE_RADIUS = 8
MAT_CIRCLE_BAND_LEFT = 26
MAT_CIRCLE_BAND_WIDTH = 150           # much wider band → arrows fan out clearly
MAT_LABEL_START = MAT_CIRCLE_BAND_LEFT + MAT_CIRCLE_BAND_WIDTH + 32

# Operator circle (larger, primary)
SYM_NODE_RADIUS = 12
SYM_CIRCLE_BAND_LEFT = 30
SYM_CIRCLE_BAND_WIDTH = 180           # generous spread for the primary DAG
SYM_LABEL_START = SYM_CIRCLE_BAND_LEFT + SYM_CIRCLE_BAND_WIDTH + 36


# ---------------------------------------------------------------------------
# Adapter discovery
# ---------------------------------------------------------------------------


def _discover_adapter_modules() -> list[str]:
    return sorted(
        info.name
        for info in pkgutil.iter_modules(representation_pkg.__path__)
        if not info.name.startswith("_")
    )


def _collect_specs() -> tuple[
    dict[str, dict[str, SpaceRepresentationSpec]],
    dict[str, dict[str, OperatorRepresentationSpec]],
]:
    state_specs: dict[str, dict[str, SpaceRepresentationSpec]] = {}
    op_specs: dict[str, dict[str, OperatorRepresentationSpec]] = {}

    for mod_name in _discover_adapter_modules():
        mod = importlib.import_module(
            f"omai.thermal_transport.representation.{mod_name}"
        )
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if isinstance(obj, SpaceRepresentationSpec):
                state_specs.setdefault(obj.representation_name, {})[obj.space.name] = obj
            elif isinstance(obj, OperatorRepresentationSpec):
                op_specs.setdefault(obj.representation_name, {})[obj.operator.name] = obj

    return state_specs, op_specs


# ---------------------------------------------------------------------------
# Layout: compute (x_within_column, y) per (state, column) and layer info
# ---------------------------------------------------------------------------


_LAYER_LABELS = {
    0: "Sources",
    1: "Force constants",
    2: "Harmonic",
    3: "Dispersion",
    4: "Mode-resolved",
    5: "BTE solution",
    6: "κ (observable)",
}


def _compute_layers() -> dict[str, int]:
    producer: dict[str, object] = {}
    for op in EDGES:
        for out in op.outputs:
            producer[out.name] = op

    cache: dict[str, int] = {}

    def layer_of(state_name: str) -> int:
        if state_name in cache:
            return cache[state_name]
        op = producer.get(state_name)
        if op is None or not op.inputs:
            cache[state_name] = 0
            return 0
        L = 1 + max(layer_of(inp.name) for inp in op.inputs)
        cache[state_name] = L
        return L

    for state in NODES:
        layer_of(state.name)
    return cache


def _split_symbolic_name(name: str) -> tuple[str, str | None]:
    """Split 'ForceConstants[order=2]' into ('ForceConstants', '[order=2]').
    Non-parameterized names return (name, None)."""
    if "[" in name:
        head, rest = name.split("[", 1)
        return head, "[" + rest
    return name, None


def _band_x(band_left: float, band_width: float,
            i: int, N: int) -> float:
    """Place state index i out of N in a horizontal band."""
    if N == 1:
        return band_left + band_width / 2
    return band_left + band_width * i / (N - 1)


def _compute_layout(layers: dict[str, int]) -> dict:
    by_layer: dict[int, list[Space]] = {}
    for s in NODES:
        by_layer.setdefault(layers[s.name], []).append(s)

    # Y per state
    state_y: dict[str, float] = {}
    cursor = TOP_PAD
    for L in sorted(by_layer):
        cursor += STAGE_HEADER_H
        for s in by_layer[L]:
            state_y[s.name] = cursor + ROW_HEIGHT / 2
            cursor += ROW_HEIGHT
        cursor += 6
    total_height = cursor + 24

    # Stage header y
    stage_header_y: dict[int, float] = {}
    cursor = TOP_PAD
    for L in sorted(by_layer):
        stage_header_y[L] = cursor + STAGE_HEADER_H / 2
        cursor += STAGE_HEADER_H + len(by_layer[L]) * ROW_HEIGHT + 6

    # Per-column geometry (variable widths)
    column_left: dict[int, float] = {}
    column_width: dict[int, float] = {}
    cursor_x = LEFT_PAD
    for c, p in enumerate(_PIPELINES):
        w = SYMBOLIC_COL_WIDTH if p["is_operator"] else MAT_COL_WIDTH
        column_left[c] = cursor_x
        column_width[c] = w
        cursor_x += w + COLUMN_GAP
    total_width = cursor_x - COLUMN_GAP + RIGHT_PAD

    # Represented circles: layer-spread within band
    circle_x_within_mat: dict[str, float] = {}
    for L, states in by_layer.items():
        for i, s in enumerate(states):
            circle_x_within_mat[s.name] = _band_x(
                MAT_CIRCLE_BAND_LEFT, MAT_CIRCLE_BAND_WIDTH, i, len(states)
            )

    # Operator circles: same pattern (larger band)
    circle_x_within_sym: dict[str, float] = {}
    for L, states in by_layer.items():
        for i, s in enumerate(states):
            circle_x_within_sym[s.name] = _band_x(
                SYM_CIRCLE_BAND_LEFT, SYM_CIRCLE_BAND_WIDTH, i, len(states)
            )

    # Leaves: states that no operation consumes as input (i.e. final
    # outputs of the workflow). For these, we hide the node entirely in
    # any column that has no adapter spec — the code genuinely doesn't
    # produce this output. Intermediate states stay dashed when unspecced.
    used_as_input: set[str] = set()
    for op in EDGES:
        for inp in op.inputs:
            used_as_input.add(inp.name)
    leaf_states = {s.name for s in NODES} - used_as_input

    return {
        "state_y": state_y,
        "stage_header_y": stage_header_y,
        "column_left": column_left,
        "column_width": column_width,
        "circle_x_within_mat": circle_x_within_mat,
        "circle_x_within_sym": circle_x_within_sym,
        "total_width": total_width,
        "total_height": total_height,
        "by_layer": by_layer,
        "layers": layers,
        "leaf_states": leaf_states,
    }


# ---------------------------------------------------------------------------
# Per-pipeline node label + coverage
# ---------------------------------------------------------------------------


def _pipeline_covers(pipeline: dict, state_name: str,
                     state_specs: dict[str, dict[str, SpaceRepresentationSpec]]) -> bool:
    if pipeline["is_operator"]:
        return True
    return any(state_name in state_specs.get(a, {}) for a in pipeline["adapters"])


def _pipeline_label(pipeline: dict, state: Space,
                    state_specs: dict[str, dict[str, SpaceRepresentationSpec]]) -> str:
    """Return the label text to render at this cell."""
    if pipeline["is_operator"]:
        return state.name
    # Pick the first matching adapter's code_api (or representation_name as fallback)
    for adapter in pipeline["adapters"]:
        spec = state_specs.get(adapter, {}).get(state.name)
        if spec is None:
            continue
        if spec.code_api:
            return next(iter(spec.code_api.values()))
        return adapter
    return ""   # not represented — empty


def _pipeline_secondary_label(pipeline: dict, state: Space,
                              state_specs: dict[str, dict[str, SpaceRepresentationSpec]]) -> str:
    """If multiple adapters in the pipeline cover this state, return the
    second one's label as a small secondary line."""
    if pipeline["is_operator"] or len(pipeline["adapters"]) <= 1:
        return ""
    matched = []
    for adapter in pipeline["adapters"]:
        spec = state_specs.get(adapter, {}).get(state.name)
        if spec is None:
            continue
        if spec.code_api:
            matched.append((adapter, next(iter(spec.code_api.values()))))
        else:
            matched.append((adapter, adapter))
    if len(matched) < 2:
        return ""
    return f"{matched[1][0]} · {matched[1][1]}"


def _pipeline_primary_adapter_tag(pipeline: dict, state: Space,
                                  state_specs: dict[str, dict[str, SpaceRepresentationSpec]]) -> str:
    """For multi-adapter columns, indicate which adapter the primary
    label belongs to (so the reader can disambiguate)."""
    if pipeline["is_operator"] or len(pipeline["adapters"]) <= 1:
        return ""
    for adapter in pipeline["adapters"]:
        if state.name in state_specs.get(adapter, {}):
            return adapter
    return ""


# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------


def _node_id(state: Space) -> str:
    return (
        state.name
        .replace("[", "_").replace("]", "")
        .replace("=", "_").replace(" ", "")
        .replace("/", "_")
    )


def _is_input_state(state: Space, layers: dict[str, int]) -> bool:
    """An 'input' state is a layer-0 source (Potential, Temperature) —
    the DAG's external inputs."""
    return layers.get(state.name, 0) == 0


def _node_attach_points(state: Space, c: int, layout: dict) -> tuple[float, float, float, float]:
    """Return (top_x, top_y, bot_x, bot_y) for arrows attaching to the
    state's node in column c. Same vertical span for circles and
    squares — they share the same radius/half-side."""
    cl = layout["column_left"][c]
    y = layout["state_y"][state.name]
    p = _PIPELINES[c]
    if p["is_operator"]:
        cx = cl + layout["circle_x_within_sym"][state.name]
        r = SYM_NODE_RADIUS
    else:
        cx = cl + layout["circle_x_within_mat"][state.name]
        r = MAT_NODE_RADIUS
    return cx, y - r, cx, y + r


def _pipeline_op_covered(pipeline: dict, op_name: str,
                         op_specs: dict[str, dict[str, OperatorRepresentationSpec]]) -> bool:
    """Whether any adapter in this pipeline declares an OperatorRepresentationSpec
    for `op_name`. The operator (no-adapter) column always counts as covered
    — the operator layer is the source of the operation declaration."""
    if not pipeline["adapters"]:
        return True
    return any(op_name in op_specs.get(a, {}) for a in pipeline["adapters"])


def _build_svg(
    layout: dict,
    state_specs: dict[str, dict[str, SpaceRepresentationSpec]],
    op_specs: dict[str, dict[str, OperatorRepresentationSpec]],
) -> str:
    width = layout["total_width"]
    height = layout["total_height"]
    column_left = layout["column_left"]
    column_width = layout["column_width"]
    state_y = layout["state_y"]
    by_layer = layout["by_layer"]
    stage_header_y = layout["stage_header_y"]
    circle_x_within_mat = layout["circle_x_within_mat"]

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="-apple-system, BlinkMacSystemFont, Inter, \'Segoe UI\', system-ui, sans-serif">'
    )

    # ---------- defs: per-pipeline arrowheads ----------
    parts.append('<defs>')
    for p in _PIPELINES:
        parts.append(
            f'<marker id="arrow-{p["id"]}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,1 L9,5 L0,9 z" fill="{p["color"]}" />'
            f'</marker>'
        )
        parts.append(
            f'<marker id="arrow-{p["id"]}-dim" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0,1 L9,5 L0,9 z" fill="{p["color"]}" opacity="0.18" />'
            f'</marker>'
        )
    parts.append('</defs>')

    # ---------- background bands for alternating stages ----------
    bg_band_color = "#F3F4F6"
    for L_idx, L in enumerate(sorted(by_layer)):
        if L_idx % 2 == 0:
            continue
        band_y_top = stage_header_y[L] - STAGE_HEADER_H / 2
        band_height = STAGE_HEADER_H + len(by_layer[L]) * ROW_HEIGHT + 4
        parts.append(
            f'<rect x="0" y="{band_y_top}" width="{width}" height="{band_height}" '
            f'fill="{bg_band_color}" opacity="0.55" />'
        )

    # ---------- subtle column-separator backgrounds for operator column ----------
    # Give the operator column a faint tinted background to mark it as
    # primary, since it's structurally different from the represented
    # columns.
    sym_cl = column_left[0]
    sym_cw = column_width[0]
    parts.append(
        f'<rect x="{sym_cl - 4}" y="{TOP_PAD - 36}" width="{sym_cw + 8}" '
        f'height="{height - TOP_PAD + 30}" fill="#EFF6FF" opacity="0.45" rx="6" />'
    )

    # ---------- column header dots + labels ----------
    for c, p in enumerate(_PIPELINES):
        cl = column_left[c]
        cw = column_width[c]
        parts.append(
            f'<rect x="{cl}" y="{TOP_PAD - 10}" width="{cw}" height="2.5" '
            f'fill="{p["color"]}" />'
        )
        parts.append(
            f'<circle cx="{cl + 10}" cy="{TOP_PAD - 26}" r="5.5" fill="{p["color"]}" />'
        )
        label_weight = "700" if p["is_operator"] else "600"
        label_size = 14.5 if p["is_operator"] else 13.5
        parts.append(
            f'<text x="{cl + 23}" y="{TOP_PAD - 20}" font-size="{label_size}" '
            f'font-weight="{label_weight}" fill="#111827">'
            f'{_html.escape(p["label"])}</text>'
        )

    # ---------- stage-header labels (full-width text) ----------
    for L in sorted(by_layer):
        y = stage_header_y[L]
        parts.append(
            f'<line x1="0" y1="{y - 12}" x2="{width}" y2="{y - 12}" '
            f'stroke="#D1D5DB" stroke-width="1" stroke-dasharray="3 4" />'
        )
        parts.append(
            f'<text x="{LEFT_PAD}" y="{y + 4}" font-size="11" font-weight="600" '
            f'fill="#9CA3AF" letter-spacing="0.08em">'
            f'<tspan fill="#9CA3AF">STAGE {L}</tspan>  '
            f'<tspan fill="#374151">{_html.escape(_LAYER_LABELS.get(L, ""))}</tspan>'
            f'</text>'
        )

    # ---------- edges ----------
    # Two visual classes:
    #   * Active edge — both endpoints represented via an adapter spec
    #     in this pipeline. Solid, full opacity.
    #   * Implicit edge — at least one endpoint lives inside the code but
    #     is not exposed as an adapter spec (e.g., Temperature parameter
    #     in kaldo, kaldo's internal DynamicalMatrix). The dependency
    #     is real; the SpaceRepresentationSpec just hasn't been written yet.
    #     Dashed, dimmed-but-readable.
    leaf_states = layout["leaf_states"]
    for c, p in enumerate(_PIPELINES):
        for op in EDGES:
            if not op.inputs:
                continue
            for inp in op.inputs:
                for out in op.outputs:
                    # Skip the edge if either endpoint is a DAG leaf
                    # that this pipeline does not cover — the leaf node
                    # itself is hidden in that column, so an arrow into
                    # nothing makes no sense.
                    if (out.name in leaf_states
                            and not _pipeline_covers(p, out.name, state_specs)):
                        continue
                    if (inp.name in leaf_states
                            and not _pipeline_covers(p, inp.name, state_specs)):
                        continue
                    sx, _, _, sy = _node_attach_points(inp, c, layout)
                    tx, ty, _, _ = _node_attach_points(out, c, layout)
                    if ty <= sy:
                        continue
                    src_cov = _pipeline_covers(p, inp.name, state_specs)
                    tgt_cov = _pipeline_covers(p, out.name, state_specs)
                    states_active = src_cov and tgt_cov
                    op_covered = _pipeline_op_covered(p, op.name, op_specs)
                    op_dy = max((ty - sy) * 0.45, 26)
                    sy_p = sy + 2
                    ty_p = ty - 4
                    d = (
                        f"M {sx} {sy_p} "
                        f"C {sx} {sy + op_dy}, {tx} {ty - op_dy}, {tx} {ty_p}"
                    )
                    if states_active and op_covered:
                        parts.append(
                            f'<path d="{d}" stroke="{p["color"]}" stroke-width="1.7" '
                            f'fill="none" opacity="0.68" '
                            f'marker-end="url(#arrow-{p["id"]})" '
                            f'class="edge edge-{p["id"]}" data-op="{op.name}" />'
                        )
                    elif states_active and not op_covered:
                        # Data flow is declared (both states covered) but
                        # the operation lacks an adapter spec — algorithmic
                        # conventions on this edge aren't recorded yet.
                        parts.append(
                            f'<path d="{d}" stroke="{p["color"]}" stroke-width="1.5" '
                            f'fill="none" opacity="0.55" stroke-dasharray="2 3" '
                            f'marker-end="url(#arrow-{p["id"]}-dim)" '
                            f'class="edge edge-{p["id"]} edge-no-op-spec" data-op="{op.name}" />'
                        )
                    else:
                        parts.append(
                            f'<path d="{d}" stroke="{p["color"]}" stroke-width="1.3" '
                            f'fill="none" opacity="0.42" stroke-dasharray="6 4" '
                            f'marker-end="url(#arrow-{p["id"]})" '
                            f'class="edge edge-{p["id"]} edge-implicit" data-op="{op.name}" />'
                        )

    # ---------- nodes per state per column ----------
    layers_map = layout["layers"]
    for c, p in enumerate(_PIPELINES):
        cl = column_left[c]
        cw = column_width[c]
        is_sym = p["is_operator"]

        for state in NODES:
            covered = _pipeline_covers(p, state.name, state_specs)
            # Leaf-hiding rule: if this state is a final output (DAG leaf)
            # and the pipeline has no adapter spec for it, the code
            # genuinely doesn't produce it — skip the node entirely.
            # Intermediate states (non-leaves) still render as dashed
            # when unspecced, since the code uses them internally.
            if state.name in leaf_states and not covered:
                continue
            y = state_y[state.name]
            is_input = _is_input_state(state, layers_map)

            parts.append(
                f'<g class="node-row" '
                f'data-state="{_html.escape(state.name)}" '
                f'data-pipeline="{p["id"]}" '
                f'style="cursor: pointer;">'
            )
            parts.append(
                f'<rect x="{cl}" y="{y - ROW_HEIGHT / 2}" width="{cw}" '
                f'height="{ROW_HEIGHT}" fill="transparent" />'
            )

            # ---- DAG node shape (square for inputs, circle otherwise) ----
            if is_sym:
                cx = cl + layout["circle_x_within_sym"][state.name]
                r = SYM_NODE_RADIUS
                is_obs = isinstance(state, ObservableSpace)
                if is_obs:
                    c_fill = "#3B82F6"
                    c_stroke = "#1D4ED8"
                    c_sw = 2
                    c_dash = ""
                else:
                    c_fill = "#FFFFFF"
                    c_stroke = "#64748B"
                    c_sw = 2
                    c_dash = ' stroke-dasharray="4 3"'
                if is_input:
                    side = r * 1.9
                    parts.append(
                        f'<rect x="{cx - side / 2}" y="{y - side / 2}" '
                        f'width="{side}" height="{side}" rx="3" ry="3" '
                        f'fill="{c_fill}" stroke="{c_stroke}" stroke-width="{c_sw}"{c_dash} '
                        f'class="node-shape node-input node-shape-sym" />'
                    )
                else:
                    parts.append(
                        f'<circle cx="{cx}" cy="{y}" r="{r}" '
                        f'fill="{c_fill}" stroke="{c_stroke}" stroke-width="{c_sw}"{c_dash} '
                        f'class="node-shape node-circle node-circle-sym" />'
                    )
            else:
                cx = cl + circle_x_within_mat[state.name]
                r = MAT_NODE_RADIUS
                if covered:
                    c_fill = p["color"]
                    c_stroke = p["color"]
                    c_sw = 1.5
                    c_dash = ""
                else:
                    c_fill = "#FFFFFF"
                    c_stroke = p["color"]
                    c_sw = 1.0
                    c_dash = ' stroke-dasharray="3 2" opacity="0.55"'
                if is_input:
                    side = r * 2.0
                    parts.append(
                        f'<rect x="{cx - side / 2}" y="{y - side / 2}" '
                        f'width="{side}" height="{side}" rx="2" ry="2" '
                        f'fill="{c_fill}" stroke="{c_stroke}" stroke-width="{c_sw}"{c_dash} '
                        f'class="node-shape node-input" />'
                    )
                else:
                    parts.append(
                        f'<circle cx="{cx}" cy="{y}" r="{r}" '
                        f'fill="{c_fill}" stroke="{c_stroke}" stroke-width="{c_sw}"{c_dash} '
                        f'class="node-shape node-circle" />'
                    )

            # ---- label (to the right of the circle) ----
            if is_sym:
                # Split parameterised names into two lines: head + bracketed-tail.
                head, params = _split_symbolic_name(state.name)
                label_x = cl + SYM_LABEL_START
                is_obs = isinstance(state, ObservableSpace)
                # Bigger, bolder font; sans-serif (this is the canonical state name).
                if params is None:
                    parts.append(
                        f'<text x="{label_x}" y="{y + 6}" '
                        f'font-size="17" font-weight="700" '
                        f'fill="#0F172A">'
                        f'{_html.escape(head)}</text>'
                    )
                else:
                    parts.append(
                        f'<text x="{label_x}" y="{y - 3}" '
                        f'font-size="17" font-weight="700" '
                        f'fill="#0F172A">'
                        f'{_html.escape(head)}</text>'
                    )
                    parts.append(
                        f'<text x="{label_x}" y="{y + 16}" '
                        f'font-size="12.5" font-weight="500" '
                        f'font-family="ui-monospace, \'SF Mono\', Monaco, monospace" '
                        f'fill="#475569">'
                        f'{_html.escape(params)}</text>'
                    )
                # Small "hidden" pill annotation for HiddenSpaces
                if not isinstance(state, ObservableSpace):
                    badge_text = "hidden"
                    badge_x = label_x + max(len(head), len(params or "")) * 8.5 + 12
                    bw = 6 + len(badge_text) * 6.3
                    parts.append(
                        f'<rect x="{badge_x}" y="{y - 8}" width="{bw}" height="13" '
                        f'rx="3" ry="3" fill="#F1F5F9" stroke="#CBD5E1" />'
                    )
                    parts.append(
                        f'<text x="{badge_x + bw / 2}" y="{y + 2}" '
                        f'font-size="9" font-weight="600" fill="#64748B" '
                        f'text-anchor="middle" letter-spacing="0.05em">'
                        f'{_html.escape(badge_text.upper())}</text>'
                    )
            else:
                label_x = cl + MAT_LABEL_START
                primary = _pipeline_label(p, state, state_specs)
                secondary = _pipeline_secondary_label(p, state, state_specs)
                adapter_tag = _pipeline_primary_adapter_tag(p, state, state_specs)
                text_color = "#111827" if covered else "#9CA3AF"

                label_text_x = label_x
                if adapter_tag:
                    tag_w = 6 + len(adapter_tag) * 6.2
                    parts.append(
                        f'<rect x="{label_x}" y="{y - 8}" width="{tag_w}" height="14" '
                        f'rx="3" ry="3" fill="#F3F4F6" stroke="#E5E7EB" />'
                    )
                    parts.append(
                        f'<text x="{label_x + tag_w / 2}" y="{y + 2.5}" '
                        f'font-size="9.5" fill="#6B7280" text-anchor="middle">'
                        f'{_html.escape(adapter_tag)}</text>'
                    )
                    label_text_x = label_x + tag_w + 6

                label_text = primary if primary else "—"
                label_dy = -3 if secondary else 4.5
                font_family = (
                    "ui-monospace, 'SF Mono', Monaco, Consolas, monospace"
                    if primary else
                    "-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
                )
                parts.append(
                    f'<text x="{label_text_x}" y="{y + label_dy}" '
                    f'font-size="13.5" font-family="{font_family}" '
                    f'fill="{text_color}">{_html.escape(label_text)}</text>'
                )
                if secondary:
                    parts.append(
                        f'<text x="{label_text_x}" y="{y + 13}" '
                        f'font-size="11.5" '
                        f'font-family="ui-monospace, \'SF Mono\', Monaco, monospace" '
                        f'fill="#6B7280">{_html.escape(secondary)}</text>'
                    )

            parts.append('</g>')

    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# JSON for the details panel (unchanged)
# ---------------------------------------------------------------------------


def _state_spec_to_dict(spec: SpaceRepresentationSpec) -> dict:
    return {
        "adapter": spec.representation_name,
        "observable_units": dict(spec.observable_units),
        "observable_normalizations": dict(spec.observable_normalizations),
        "code_api": dict(spec.code_api),
        "notes": spec.notes,
    }


def _op_spec_to_dict(spec: OperatorRepresentationSpec) -> dict:
    return {
        "adapter": spec.representation_name,
        "parameter_units": dict(spec.parameter_units),
        "scheme_overrides": dict(spec.scheme_overrides),
        "discretization_choices": dict(spec.discretization_choices),
        "notes": spec.notes,
    }


def _state_to_json(
    state: Space,
    state_specs: dict[str, dict[str, SpaceRepresentationSpec]],
    adapter_order: list[str],
) -> dict:
    fields = [
        {"name": f.name, "dimension": f.dimension.name, "indices": list(f.indices)}
        for f in state.fields
    ]
    specs = {
        adapter: _state_spec_to_dict(state_specs[adapter][state.name])
        for adapter in adapter_order
        if state.name in state_specs.get(adapter, {})
    }
    cross_factors: dict[str, dict[str, float]] = {}
    for a, b in itertools.combinations(list(specs.keys()), 2):
        spec_a = state_specs[a][state.name]
        spec_b = state_specs[b][state.name]
        per_field: dict[str, float] = {}
        for f in state.fields:
            try:
                # Cross-adapter factor A→B is the composition
                # operator_to_representation(b, f) · representation_to_operator(a, f).
                per_field[f.name] = (
                    operator_to_representation(spec_b, f.name)
                    * representation_to_operator(spec_a, f.name)
                )
            except Exception:
                pass
        if per_field:
            cross_factors[f"{a} → {b}"] = per_field
    return {
        "name": state.name,
        "kind": "ObservableSpace" if isinstance(state, ObservableSpace) else "HiddenSpace",
        "fields": fields,
        "labels": {k_: str(v_) for k_, v_ in state.labels.items()},
        "description": state.description,
        "specs": specs,
        "cross_factors": cross_factors,
    }


def _operation_to_json(
    op,
    op_specs: dict[str, dict[str, OperatorRepresentationSpec]],
    adapter_order: list[str],
) -> dict:
    def _to_latex(f):
        if isinstance(f, sp.Basic):
            return sp.latex(f)
        return f if isinstance(f, str) else None

    formula_latex = _to_latex(op.formula) if op.formula is not None else None
    auxiliary_latex = [_to_latex(f) for f in getattr(op, "auxiliary_formulas", ())]

    specs = {
        adapter: _op_spec_to_dict(op_specs[adapter][op.name])
        for adapter in adapter_order
        if op.name in op_specs.get(adapter, {})
    }

    return {
        "name": op.name,
        "inputs": [s.name for s in op.inputs],
        "outputs": [s.name for s in op.outputs],
        "parameters": [
            {"name": p.name, "dimension": p.dimension.name}
            for p in op.parameters
        ],
        "schemes": dict(op.schemes),
        "formula_latex": formula_latex,
        "auxiliary_latex": auxiliary_latex,
        "description": op.description,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# HTML emission
# ---------------------------------------------------------------------------


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>omai · thermal-transport DAG</title>
<style>
  :root {{
    --bg: #F9FAFB;
    --surface: #FFFFFF;
    --border: #E5E7EB;
    --border-strong: #D1D5DB;
    --text: #111827;
    --text-secondary: #4B5563;
    --text-muted: #9CA3AF;
    --observable: #3B82F6;
    --hidden: #94A3B8;
    --code-bg: #F3F4F6;
    --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: var(--text);
    background: var(--bg);
    -webkit-font-smoothing: antialiased;
  }}
  header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1rem 1.5rem 0.75rem;
  }}
  .legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem 1.75rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px dashed var(--border);
    font-size: 0.78rem;
    color: var(--text-secondary);
  }}
  .legend-group {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }}
  .legend-group .label {{
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    font-size: 0.66rem;
    white-space: nowrap;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    white-space: nowrap;
  }}
  .legend-item svg {{ flex-shrink: 0; }}
  .extension-rules {{
    margin-top: 0.85rem;
    padding: 0.55rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.02);
    font-size: 0.78rem;
    color: var(--text-secondary);
  }}
  .extension-rules > summary {{
    cursor: pointer;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.7rem;
    padding: 0.05rem 0;
  }}
  .extension-rules[open] > summary {{
    margin-bottom: 0.5rem;
    border-bottom: 1px dashed var(--border);
    padding-bottom: 0.4rem;
  }}
  .extension-rules-body code {{
    background: rgba(0, 0, 0, 0.05);
    padding: 0.05em 0.3em;
    border-radius: 3px;
    font-size: 0.85em;
  }}
  .title-row {{
    display: flex;
    align-items: baseline;
    gap: 1rem;
    flex-wrap: wrap;
  }}
  h1 {{
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  .stats {{
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }}
  .stats span + span {{ margin-left: 0.75rem; }}
  .stats strong {{ color: var(--text); font-weight: 600; }}

  .layout {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) 420px;
    gap: 1.25rem;
    padding: 1.25rem 1.5rem;
    align-items: start;
  }}
  body.details-collapsed .layout {{ grid-template-columns: minmax(0, 1fr) 40px; }}

  .diagram-wrap {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-sm);
    overflow-x: auto;
    overflow-y: visible;
    min-width: 0;
  }}
  .diagram-wrap svg {{ display: block; }}

  /* node hover */
  .node-row {{ cursor: pointer; }}
  .node-row:hover .node-shape {{
    filter: drop-shadow(0 1px 3px rgba(0,0,0,0.18));
  }}
  .node-row:hover .node-circle {{ r: 9; }}
  .edge {{ transition: opacity 120ms ease; }}
  .edge:hover {{ opacity: 0.95 !important; stroke-width: 2.5 !important; }}

  /* details panel */
  #details-rail {{
    position: sticky;
    top: 1rem;
    align-self: start;
    max-height: calc(100vh - 2rem);
    display: flex;
    flex-direction: column;
  }}
  body.details-collapsed #details-rail {{ width: 40px; }}
  .details-toggle {{
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 4;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    color: var(--text-secondary);
    width: 28px;
    height: 28px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .details-toggle:hover {{ background: var(--code-bg); color: var(--text); }}
  body.details-collapsed .details-toggle {{ right: 4px; top: 50%; transform: translateY(-50%); }}
  #details {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-sm);
    padding: 1.25rem;
    flex: 1;
    overflow-y: auto;
    position: relative;
  }}
  body.details-collapsed #details {{ display: none; }}
  #details .placeholder {{
    color: var(--text-muted);
    padding: 1.5rem 1rem;
    text-align: center;
    font-size: 0.9rem;
  }}
  #details h2 {{
    margin: 0 0 0.4rem;
    font-size: 1rem;
    font-weight: 600;
  }}
  #details h2 .kind {{
    display: inline-block;
    font-size: 0.65rem;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    color: #fff;
    margin-left: 0.5rem;
    vertical-align: middle;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }}
  #details h2 .kind.ObservableSpace {{ background: var(--observable); }}
  #details h2 .kind.HiddenSpace {{ background: var(--hidden); }}
  #details > p {{
    margin: 0 0 1rem;
    color: var(--text-secondary);
    font-size: 0.88rem;
  }}
  #details .section {{
    margin-top: 1rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--border);
  }}
  #details .section h3 {{
    margin: 0 0 0.45rem;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-weight: 600;
  }}
  #details .section.adapter-section h3 {{
    color: var(--adapter-color, var(--text-muted));
    display: flex; align-items: center; gap: 0.5rem;
  }}
  #details .section.adapter-section h3::before {{
    content: "";
    width: 8px; height: 8px; border-radius: 2px;
    background: var(--adapter-color, var(--text-muted));
    display: inline-block;
  }}
  #details table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin: 0.35rem 0;
  }}
  #details th, #details td {{
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
  }}
  #details th {{
    background: var(--code-bg);
    font-weight: 600;
    font-size: 0.72rem;
    color: var(--text-secondary);
    text-transform: uppercase;
  }}
  #details code {{
    background: var(--code-bg);
    padding: 0.05rem 0.35rem;
    border-radius: 3px;
    font-size: 0.85em;
    font-family: ui-monospace, "SF Mono", Monaco, Consolas, monospace;
  }}
  #details .empty {{ color: var(--text-muted); font-style: italic; }}
  #details .notes {{
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 0.4rem;
    padding: 0.5rem 0.75rem;
    background: var(--code-bg);
    border-radius: 4px;
    border-left: 3px solid var(--adapter-color, var(--border-strong));
  }}
  .formula {{
    background: var(--code-bg);
    border: 1px solid var(--border);
    padding: 0.75rem;
    border-radius: 4px;
    margin: 0.5rem 0;
    overflow-x: auto;
  }}
  .coverage-row {{ display: flex; gap: 0.35rem; flex-wrap: wrap; margin: 0.4rem 0; }}
  .coverage-chip {{
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 10px;
    background: var(--chip-color, var(--border));
    color: #fff;
    font-weight: 500;
  }}
  footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
    padding: 0.75rem;
    border-top: 1px solid var(--border);
  }}
  @media (max-width: 1100px) {{
    .layout {{ grid-template-columns: 1fr; }}
    body.details-collapsed .layout {{ grid-template-columns: 1fr; }}
    #details-rail {{ position: static; max-height: none; }}
  }}
</style>
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
  <div class="title-row">
    <h1>omai · thermal-transport DAG</h1>
    <span class="stats">
      <span><strong>{n_observables}</strong> ObservableSpaces</span>
      <span><strong>{n_hidden}</strong> HiddenSpaces</span>
      <span><strong>{n_edges}</strong> edges</span>
      <span><strong>{n_adapters}</strong> adapters</span>
    </span>
  </div>
  <div class="legend">
    <div class="legend-group">
      <span class="label">Operator</span>
      <span class="legend-item">
        <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#3B82F6" stroke="#1D4ED8" stroke-width="2"/></svg>
        ObservableSpace
      </span>
      <span class="legend-item">
        <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#FFFFFF" stroke="#64748B" stroke-width="2" stroke-dasharray="3 2"/></svg>
        HiddenSpace
      </span>
      <span class="legend-item">
        <svg width="16" height="16" viewBox="0 0 16 16"><rect x="2" y="2" width="12" height="12" rx="2" fill="#3B82F6" stroke="#1D4ED8" stroke-width="2"/></svg>
        Input (external source)
      </span>
    </div>
    <div class="legend-group">
      <span class="label">Represented</span>
      <span class="legend-item">
        <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5" fill="#DC2626" stroke="#DC2626" stroke-width="1.5"/></svg>
        Adapter spec written
      </span>
      <span class="legend-item">
        <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5" fill="#FFFFFF" stroke="#DC2626" stroke-width="1.2" stroke-dasharray="3 2" opacity="0.7"/></svg>
        Intermediate (no spec — needed by downstream, not exposed)
      </span>
      <span class="legend-item" style="opacity:0.7">
        <svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="3" fill="#9CA3AF" opacity="0.4"/></svg>
        Leaf hidden (DAG output not emitted by this code)
      </span>
    </div>
    <div class="legend-group">
      <span class="label">Edges</span>
      <span class="legend-item">
        <svg width="36" height="14" viewBox="0 0 36 14">
          <defs><marker id="lg-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="#374151"/></marker></defs>
          <path d="M2 7 L 28 7" stroke="#374151" stroke-width="1.6" fill="none" marker-end="url(#lg-a)"/>
        </svg>
        States + op spec (full coverage)
      </span>
      <span class="legend-item">
        <svg width="36" height="14" viewBox="0 0 36 14">
          <defs><marker id="lg-c" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="#374151" opacity="0.55"/></marker></defs>
          <path d="M2 7 L 28 7" stroke="#374151" stroke-width="1.5" stroke-dasharray="2 3" opacity="0.55" fill="none" marker-end="url(#lg-c)"/>
        </svg>
        States covered, op spec missing
      </span>
      <span class="legend-item">
        <svg width="36" height="14" viewBox="0 0 36 14">
          <defs><marker id="lg-b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="#374151" opacity="0.55"/></marker></defs>
          <path d="M2 7 L 28 7" stroke="#374151" stroke-width="1.3" stroke-dasharray="6 4" opacity="0.55" fill="none" marker-end="url(#lg-b)"/>
        </svg>
        Implicit (state endpoint lacks spec)
      </span>
    </div>
    <div class="legend-group">
      <span class="label">Lanes</span>
      <span class="legend-item"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#1F2937"></span> Operator</span>
      <span class="legend-item"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#DC2626"></span> kaldo</span>
      <span class="legend-item"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#059669"></span> phono3py</span>
      <span class="legend-item"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0891B2"></span> phonopy</span>
      <span class="legend-item"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#7C3AED"></span> shengbte</span>
    </div>
  </div>
  <details class="extension-rules">
    <summary>DAG extension rules — when to add a node vs. a parameter</summary>
    <div class="extension-rules-body">
      <p style="margin:0 0 0.6em 0">
        Edges carry the sympy formula; states are typed places. Different
        production formulas force different <em>edges</em>, not necessarily
        different states. When adding a new variant, pick exactly one pattern:
      </p>
      <ol style="margin:0 0 0.6em 1.2em; padding:0;">
        <li><strong>Pattern A — label on the space.</strong> Only
            when the variant changes the gauge type (ObservableSpace vs
            HiddenSpace) AND the labelled space is terminal-ish.
            Example: <code>ThermalConductivity[bte_solver=rta|direct_inverse]</code>,
            <code>[transport_model=lbte|wigner|qhgk]</code>.</li>
        <li><strong>Pattern B — sibling states, converging edge.</strong>
            Variants with different input chains that combine before a
            downstream consumer uses them. Example:
            <code>AnharmonicLinewidth</code> /
            <code>IsotopicLinewidth</code> /
            <code>BoundaryLinewidth</code> →
            <code>sum_linewidths</code> → <code>TotalLinewidth</code>.</li>
        <li><strong>Pattern C — shared output, alternative producing
            edges.</strong> Same output type and gauge classification,
            different production formulas. A small upstream intermediate
            keeps it acyclic. Example:
            <code>BareDynamicalMatrix</code> →
            (<code>apply_nac_correction</code> OR <code>identity_dm</code>) →
            <code>DynamicalMatrix</code>.</li>
      </ol>
      <p style="margin:0">
        Anti-pattern: type parameter on an intermediate state. Forces every
        downstream consumer to be parameterised too. See
        <code>docs/skills/extend_dag.md</code> for the full skill and
        <code>docs/operator_representation_substrate.tex</code> § "DAG
        extension rules" for the canonical statement.
      </p>
    </div>
  </details>
</header>

<div class="layout">
  <div class="diagram-wrap">
{svg_markup}
  </div>

  <div id="details-rail">
    <button class="details-toggle" id="details-toggle" title="Hide details panel">›</button>
    <div id="details">
      <div class="placeholder">Click a circle (node) or an arrow (edge) for details.</div>
    </div>
  </div>
</div>

<footer>
  Generated by <code>python -m omai.thermal_transport.visualize</code>
</footer>

<script>
const NODE_DATA = {node_data_json};
const EDGE_DATA = {edge_data_json};
const ADAPTER_COLORS = {adapter_colors_json};

function escapeHtml(s) {{
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}
function adapterChip(adapter) {{
  const c = ADAPTER_COLORS[adapter] || '#9CA3AF';
  return `<span class="coverage-chip" style="--chip-color: ${{c}}; background: ${{c}}">${{escapeHtml(adapter)}}</span>`;
}}

// Pipeline → adapter list mapping. Mirrors _PIPELINES in Python.
const PIPELINE_ADAPTERS = {{
  operator: null,
  kaldo: ['kaldo'],
  phono3py: ['phono3py'],
  phonopy: ['phonopy'],
  shengbte: ['shengbte'],
}};

function renderNode(name, pipelineId) {{
  const d = NODE_DATA[name];
  if (!d) return `<div class="empty">no data for ${{escapeHtml(name)}}</div>`;
  let html = `<h2>${{escapeHtml(d.name)}} <span class="kind ${{d.kind}}">${{d.kind}}</span></h2>`;
  // Pipeline context note: when the click came from a per-code column,
  // we filter the specs shown to just that code's adapters.
  const allowedAdapters = PIPELINE_ADAPTERS[pipelineId];
  const filteredSpecs = (allowedAdapters === null || allowedAdapters === undefined)
    ? d.specs
    : Object.fromEntries(Object.entries(d.specs).filter(([a, _]) => allowedAdapters.includes(a)));

  if (pipelineId && pipelineId !== 'operator') {{
    html += `<div style="font-size:0.78rem; color: var(--text-secondary); margin-bottom: 0.5rem">`
          + `Filtered to <strong>${{escapeHtml(pipelineId)}}</strong>. `
          + `<a href="#" id="show-all-link" style="color: var(--accent-active); text-decoration: underline; cursor: pointer">Show all adapters</a>`
          + `</div>`;
  }}
  if (d.description) html += `<p>${{escapeHtml(d.description)}}</p>`;
  const adapters = Object.keys(filteredSpecs);
  if (adapters.length) html += `<div class="coverage-row">${{adapters.map(adapterChip).join('')}}</div>`;
  if (d.fields.length) {{
    html += '<div class="section"><h3>Fields</h3><table><tr><th>name</th><th>dimension</th><th>indices</th></tr>';
    for (const f of d.fields) {{
      html += `<tr><td><code>${{escapeHtml(f.name)}}</code></td>` +
              `<td>${{escapeHtml(f.dimension)}}</td>` +
              `<td>${{f.indices.length ? f.indices.map(escapeHtml).join(', ') : '<span class="empty">(scalar)</span>'}}</td></tr>`;
    }}
    html += '</table></div>';
  }}
  if (Object.keys(d.labels).length) {{
    html += '<div class="section"><h3>Labels</h3><table>';
    for (const [k, v] of Object.entries(d.labels)) {{
      html += `<tr><td><code>${{escapeHtml(k)}}</code></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
    }}
    html += '</table></div>';
  }}
  for (const adapter of adapters) {{
    const spec = filteredSpecs[adapter];
    const color = ADAPTER_COLORS[adapter] || '#9CA3AF';
    html += `<div class="section adapter-section" style="--adapter-color: ${{color}}"><h3>${{escapeHtml(adapter)}}</h3>`;
    if (Object.keys(spec.code_api || {{}}).length) {{
      html += '<table>';
      for (const [k, v] of Object.entries(spec.code_api)) {{
        html += `<tr><td>API for <code>${{escapeHtml(k)}}</code></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      }}
      html += '</table>';
    }}
    if (Object.keys(spec.observable_units).length || Object.keys(spec.observable_normalizations).length) {{
      html += '<table>';
      for (const [k, v] of Object.entries(spec.observable_units)) {{
        html += `<tr><td>unit (<code>${{escapeHtml(k)}}</code>)</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      }}
      for (const [k, v] of Object.entries(spec.observable_normalizations)) {{
        html += `<tr><td>normalization (<code>${{escapeHtml(k)}}</code>)</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      }}
      html += '</table>';
    }}
    if (spec.notes) html += `<div class="notes">${{escapeHtml(spec.notes)}}</div>`;
    html += '</div>';
  }}
  if (Object.keys(d.cross_factors).length) {{
    html += '<div class="section"><h3>Cross-code factors</h3>';
    for (const [pair, perField] of Object.entries(d.cross_factors)) {{
      html += `<div style="margin-top:0.5rem"><strong style="font-size:0.78rem; color: var(--text-secondary)">${{escapeHtml(pair)}}</strong>`;
      html += '<table>';
      for (const [field, factor] of Object.entries(perField)) {{
        html += `<tr><td><code>${{escapeHtml(field)}}</code></td><td>${{factor.toExponential(4)}}</td></tr>`;
      }}
      html += '</table></div>';
    }}
    html += '</div>';
  }}
  return html;
}}

function renderEdge(name) {{
  const d = EDGE_DATA[name];
  if (!d) return `<div class="empty">no data for ${{escapeHtml(name)}}</div>`;
  let html = `<h2>${{escapeHtml(d.name)}}</h2>`;
  if (d.description) html += `<p>${{escapeHtml(d.description)}}</p>`;
  const adapters = Object.keys(d.specs);
  if (adapters.length) html += `<div class="coverage-row">${{adapters.map(adapterChip).join('')}}</div>`;
  html += `<div class="section"><h3>Inputs</h3>${{d.inputs.length ?
            '<ul>' + d.inputs.map(s => `<li><code>${{escapeHtml(s)}}</code></li>`).join('') + '</ul>' :
            '<div class="empty">(no inputs — nullary source)</div>'}}</div>`;
  html += `<div class="section"><h3>Outputs</h3><ul>` +
          d.outputs.map(s => `<li><code>${{escapeHtml(s)}}</code></li>`).join('') + `</ul></div>`;
  if (d.parameters.length) {{
    html += '<div class="section"><h3>Parameters</h3><table><tr><th>name</th><th>dimension</th></tr>';
    for (const p of d.parameters) {{
      html += `<tr><td><code>${{escapeHtml(p.name)}}</code></td><td>${{escapeHtml(p.dimension)}}</td></tr>`;
    }}
    html += '</table></div>';
  }}
  if (Object.keys(d.schemes).length) {{
    html += '<div class="section"><h3>Schemes</h3><table>';
    for (const [k, v] of Object.entries(d.schemes)) {{
      html += `<tr><td><code>${{escapeHtml(k)}}</code></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
    }}
    html += '</table></div>';
  }}
  if (d.formula_latex) {{
    html += `<div class="section"><h3>Formula</h3><div class="formula">$$${{d.formula_latex}}$$</div></div>`;
  }}
  if (d.auxiliary_latex && d.auxiliary_latex.length) {{
    html += `<div class="section"><h3>Auxiliary definitions</h3>`;
    for (const aux of d.auxiliary_latex) {{
      if (aux) html += `<div class="formula">$$${{aux}}$$</div>`;
    }}
    html += `</div>`;
  }}
  for (const adapter of adapters) {{
    const spec = d.specs[adapter];
    const color = ADAPTER_COLORS[adapter] || '#9CA3AF';
    html += `<div class="section adapter-section" style="--adapter-color: ${{color}}"><h3>${{escapeHtml(adapter)}}</h3>`;
    let any = false;
    let tbl = '<table>';
    for (const [k, v] of Object.entries(spec.parameter_units)) {{
      tbl += `<tr><td>unit (<code>${{escapeHtml(k)}}</code>)</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      any = true;
    }}
    for (const [k, v] of Object.entries(spec.scheme_overrides)) {{
      tbl += `<tr><td>${{escapeHtml(k)}}</td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      any = true;
    }}
    for (const [k, v] of Object.entries(spec.discretization_choices)) {{
      tbl += `<tr><td>${{escapeHtml(k)}} <span style="color:var(--text-muted); font-size:0.7rem">(disc.)</span></td><td><code>${{escapeHtml(v)}}</code></td></tr>`;
      any = true;
    }}
    tbl += '</table>';
    if (any) html += tbl;
    if (spec.notes) html += `<div class="notes">${{escapeHtml(spec.notes)}}</div>`;
    if (!any && !spec.notes) html += '<div class="empty">(no parameters or schemes)</div>';
    html += '</div>';
  }}
  return html;
}}

function showDetails(html) {{
  if (document.body.classList.contains('details-collapsed')) {{
    document.body.classList.remove('details-collapsed');
    const t = document.getElementById('details-toggle');
    if (t) {{ t.textContent = '›'; t.title = 'Hide details panel'; }}
  }}
  const panel = document.getElementById('details');
  panel.innerHTML = html;
  panel.scrollTop = 0;
  // Wire up the "show all adapters" link if present (when filtered view).
  const showAll = panel.querySelector('#show-all-link');
  if (showAll && panel.dataset.state) {{
    showAll.addEventListener('click', (e) => {{
      e.preventDefault();
      panel.dataset.pipeline = 'operator';
      showDetails(renderNode(panel.dataset.state, 'operator'));
    }});
  }}
  if (window.MathJax && MathJax.typesetPromise) {{
    MathJax.typesetPromise([panel]);
  }}
}}

document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('.node-row').forEach(g => {{
    g.addEventListener('click', () => {{
      const name = g.dataset.state;
      const pipeline = g.dataset.pipeline || 'operator';
      if (name) {{
        const panel = document.getElementById('details');
        panel.dataset.state = name;
        panel.dataset.pipeline = pipeline;
        showDetails(renderNode(name, pipeline));
      }}
    }});
  }});
  document.querySelectorAll('.edge').forEach(p => {{
    p.style.cursor = 'pointer';
    p.addEventListener('click', () => {{
      const op = p.dataset.op;
      if (op) showDetails(renderEdge(op));
    }});
  }});

  const toggle = document.getElementById('details-toggle');
  if (toggle) {{
    toggle.addEventListener('click', () => {{
      document.body.classList.toggle('details-collapsed');
      const collapsed = document.body.classList.contains('details-collapsed');
      toggle.textContent = collapsed ? '‹' : '›';
      toggle.title = collapsed ? 'Show details panel' : 'Hide details panel';
    }});
  }}
}});
</script>
</body>
</html>
"""


def render_html(output_path: Path | str) -> Path:
    state_specs, op_specs = _collect_specs()
    adapter_order = sorted(set(state_specs.keys()) | set(op_specs.keys()))
    # Adapter colors mirror the per-pipeline palette where possible.
    colors: dict[str, str] = {}
    for a in adapter_order:
        for p in _PIPELINES:
            if a in p["adapters"]:
                colors[a] = p["color"]
                break
        else:
            colors[a] = "#9CA3AF"

    layers = _compute_layers()
    layout = _compute_layout(layers)
    svg_markup = _build_svg(layout, state_specs, op_specs)

    node_data = {
        state.name: _state_to_json(state, state_specs, adapter_order)
        for state in NODES
    }
    edge_data = {
        op.name: _operation_to_json(op, op_specs, adapter_order)
        for op in EDGES
    }

    n_observables = sum(1 for s in NODES if isinstance(s, ObservableSpace))
    n_hidden = sum(1 for s in NODES if isinstance(s, HiddenSpace))

    html = _HTML_TEMPLATE.format(
        n_observables=n_observables,
        n_hidden=n_hidden,
        n_edges=len(EDGES),
        n_adapters=len(adapter_order),
        svg_markup=svg_markup,
        node_data_json=json.dumps(node_data, indent=2),
        edge_data_json=json.dumps(edge_data, indent=2),
        adapter_colors_json=json.dumps(colors),
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
