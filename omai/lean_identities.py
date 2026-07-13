"""PhysLean export Tier 2: the executable identities as real-valued theorems.

Tier 1 (omai.physlean_export) proves the map's DIMENSIONAL layer: each edge's
output dimension is the product of its inputs. Tier 2 proves the ALGEBRAIC
layer: where the map chains one identity edge into another, substituting the
upstream formula into the downstream one yields the fully-expanded law, and the
chained (grouped) form equals the flat form. These are non-trivial: the two
sides differ before ring-normalization.

Example: ZT = PF*T/kappa_tot, with PF = S^2*sigma and kappa_tot = kappa +
kappa_e, expands to S^2*sigma*T/(kappa + kappa_e). The theorem states the
grouped form equals the flat form; `ring` / `field_simp` certifies it.

An identity that chains on nothing upstream is emitted as a plain
well-formedness law (its formula is a well-typed real expression), marked
`kind: law`. Divisions get `field_simp` with denominators assumed nonzero.

CLI:  python -m omai.lean_identities  ->  writes lean/OpenMaterialsIdentities.lean
"""
from __future__ import annotations

import re
from pathlib import Path

import sympy as sp

_REPO = Path(__file__).resolve().parent.parent


def _identity_edges():
    from omai.thermodynamic_identities.operator import edges as tid
    return list(tid.EDGES)


def _lean_var(latex_sym: str) -> str:
    s = latex_sym
    for a, b in ((r"\gamma", "gamma"), (r"\alpha", "alpha"), (r"\sigma", "sigma"),
                 (r"\kappa", "kappa"), (r"\beta", "beta")):
        s = s.replace(a, b)
    s = re.sub(r"[{}\\]", "", s)
    s = s.replace("^", "_").replace(",", "_")
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "v_" + s
    return s or "x"


def _lean_expr(expr, symmap: dict) -> str:
    if expr.is_Symbol:
        return symmap[str(expr)]
    if expr.is_Integer:
        return str(int(expr))
    if expr.is_Rational:
        return f"({int(expr.p)} / {int(expr.q)} : ℝ)"
    if expr.is_Add:
        return "(" + " + ".join(_lean_expr(a, symmap) for a in expr.args) + ")"
    if expr.is_Mul:
        num, den = [], []
        for a in expr.args:
            if a.is_Pow and a.exp.is_number and a.exp < 0:
                den.append(a.base if a.exp == -1 else sp.Pow(a.base, -a.exp))
            else:
                num.append(a)
        num_s = " * ".join(_lean_expr(a, symmap) for a in num) if num else "1"
        if den:
            den_s = " * ".join(_lean_expr(a, symmap) for a in den)
            return f"({num_s}) / ({den_s})"
        return "(" + num_s + ")"
    if expr.is_Pow:
        base = _lean_expr(expr.base, symmap)
        if expr.exp.is_Integer and expr.exp >= 0:
            return f"{base} ^ {int(expr.exp)}"
        if expr.exp.is_Integer and expr.exp < 0:
            return f"1 / ({base} ^ {int(-expr.exp)})"
    raise ValueError(f"cannot render {expr!r}")


def _denominators(expr) -> list:
    dens = []
    for a in sp.preorder_traversal(expr):
        if a.is_Pow and a.exp.is_number and a.exp < 0:
            dens.append(a.base)
    return dens


def _theorem_list():
    """One composition theorem per identity edge that CHAINS on upstream
    identities. Given the upstream formulas as hypotheses, the direct form (in
    the intermediate symbols) equals the flat form (fully substituted), proved
    by `subst` then `ring`/`field_simp`. The two sides are genuinely different
    expressions; the hypotheses are what make them equal. A single-edge identity
    carries no algebraic content beyond its definition (proving it would be a
    reflexive X = X), so it is recorded as skipped, not emitted."""
    edges = _identity_edges()
    sym_to_form = {}
    for op in edges:
        f = getattr(op, "formula", None)
        if f is not None and isinstance(f, sp.Equality):
            sym_to_form[f.lhs] = f.rhs

    theorems, skipped = [], []
    for op in edges:
        f = getattr(op, "formula", None)
        if f is None or not isinstance(f, sp.Equality):
            skipped.append((op.name, "no-formula"))
            continue
        rhs = f.rhs
        inters = [(s, sym_to_form[s]) for s in sorted(rhs.free_symbols, key=str)
                  if s in sym_to_form and s != f.lhs]
        if not inters:
            skipped.append((op.name, "no-upstream-chain"))
            continue
        flat = rhs
        for s, form in inters:
            flat = flat.subs(s, form)
        all_syms = sorted(rhs.free_symbols | flat.free_symbols, key=str)
        symmap = {str(x): _lean_var(str(x)) for x in all_syms}
        used = {}
        for k in list(symmap):
            v = symmap[k]
            if v in used.values():
                n = 2
                while f"{v}_{n}" in used.values():
                    n += 1
                symmap[k] = f"{v}_{n}"
            used[k] = symmap[k]
        try:
            direct_lean = _lean_expr(rhs, symmap)
            flat_lean = _lean_expr(sp.together(flat), symmap)
            hyps = [(symmap[str(s)], _lean_expr(form, symmap)) for s, form in inters]
        except (ValueError, KeyError):
            skipped.append((op.name, "unrenderable"))
            continue
        dens = _denominators(rhs) + _denominators(sp.together(flat))
        binders = " ".join(f"({symmap[str(x)]} : ℝ)" for x in all_syms)
        hyp_binders = "".join(f" (h_{hn} : {hn} = {he})" for hn, he in hyps)
        den_binders = "".join(f" (hd{i} : {_lean_expr(d, symmap)} ≠ 0)"
                              for i, d in enumerate(dens))
        subst_names = " ".join(f"h_{hn}" for hn, _ in hyps)
        tail = "field_simp <;> ring" if dens else "ring"
        proof = f"by subst {subst_names}; {tail}"
        name = "identity_" + _lean_var(op.name)
        lean = (f"theorem {name} {binders}{hyp_binders}{den_binders} :\n"
                f"    {direct_lean} = {flat_lean} := {proof}")
        theorems.append({"op": op.name, "name": name, "kind": "composition",
                         "chained": [str(s) for s, _ in inters], "lean": lean})
    return theorems, skipped


def build_identities():
    theorems, skipped = _theorem_list()
    stats = {"theorems": len(theorems),
             "compositions": sum(1 for t in theorems if t["kind"] == "composition"),
             "skipped_noncomposition": len(skipped),
             "skipped": skipped, "map_version": _version()[:12]}
    return _render(theorems), stats


def build_index():
    """op -> {lean, kind} for the frontend."""
    theorems, _ = _theorem_list()
    return {t["op"]: {"lean": t["lean"], "kind": t["kind"]} for t in theorems}


def _version():
    import json
    p = _REPO / "docs" / "data" / "version.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("version") or ""
        except Exception:
            return ""
    return ""


def _render(theorems):
    ver = _version()[:12] or "unknown"
    lines = [
        "/-",
        "  OpenMaterials Tier 2: the executable identities as real-valued theorems.",
        "",
        "  Generated by omai.lean_identities from map version " + ver + ".",
        "  A `composition` theorem substitutes an upstream identity into a downstream",
        "  one and proves the chained form equals the flat form (ring / field_simp).",
        "  A `law` theorem states a single identity's formula as a well-typed real",
        "  equation. Dimensional consistency is Tier 1 (OpenMaterials.lean).",
        "  Compiles against Mathlib (Lean 4.29.1).",
        "-/",
        "import Mathlib.Tactic",
        "",
        "namespace OpenMaterials.Identities",
        "",
    ]
    for t in theorems:
        lines.append(f"-- {t['op']} ({t['kind']})")
        lines.append(t["lean"])
        lines.append("")
    lines.append("end OpenMaterials.Identities")
    lines.append("")
    return "\n".join(lines)


def write_identities(out: Path | None = None):
    out = out or (_REPO / "lean" / "OpenMaterialsIdentities.lean")
    out.parent.mkdir(parents=True, exist_ok=True)
    src, stats = build_identities()
    out.write_text(src)
    return out, stats


if __name__ == "__main__":  # pragma: no cover
    path, stats = write_identities()
    print(f"wrote {path}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
