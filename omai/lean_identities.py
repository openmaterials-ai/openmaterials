"""Lean export Tier 2: the executable identities as real-valued theorems.

Tier 1 (omai.physlean_export) proves the map's DIMENSIONAL layer: each edge's
output dimension is the product of its inputs. Tier 2 proves the ALGEBRAIC
layer, in two shapes:

  * A `composition` theorem covers a place where the map chains one identity
    edge into another: substituting the upstream formula into the downstream one
    yields the fully-expanded law, and the chained (grouped) form equals the flat
    form. These are non-trivial: the two sides differ before ring-normalization.
    Example: ZT = PF*T/kappa_tot, with PF = S^2*sigma and kappa_tot = kappa +
    kappa_e, expands to S^2*sigma*T/(kappa + kappa_e). The theorem states the
    grouped form equals the flat form; `field_simp` certifies it. Compositions
    are drawn only from the thermodynamic-identities domain, whose six edges form
    a closed, collision-free algebraic component (every output symbol is defined
    exactly once), so chained substitution is unambiguous.

  * A `law` theorem covers a STANDALONE rational operator Y = f(x1..xn) drawn
    from ANY domain: its formula is a rational function of its inputs with a real
    denominator to clear. Writing that formula as a single fraction N/D (N and D
    fraction-free polynomials), introducing the output Y by hypothesis, and
    clearing the one denominator certifies the operator's defining relation in
    cleared form: given `h : Y = N/D` and `D ≠ 0`, the theorem states
    `Y * D = N`. After `subst h` the goal is exactly `N/D * D = N`, closed by
    `div_mul_cancel₀`. The two sides genuinely differ before the denominator
    clears, so these are not reflexive. Combining to one fraction is what keeps
    the proof uniform and robust across operators (a single denominator, no
    nested inverses, no `ring`, no deep recursion on the big composite formulas),
    so no proof ever carries a never-executed tactic.

An operator is in scope for a `law` theorem when, after treating each indexed
slot (e.g. k_f[3,3], kappa[alpha,beta]) as an opaque real scalar, its formula is
`output_symbol = rational(other scalars)` with a real denominator and contains no
Integral, Sum, Product, Derivative, Piecewise, transcendental function (log, exp,
sin, cos, sinh, ..., sqrt / fractional powers) or opaque applied function. Pure
polynomial definitions (no denominator to clear) carry no algebraic content
beyond their definition, exactly like a single-edge composition would, so they
are recorded as skipped rather than emitted as a near-reflexive law. Everything
that needs analysis (an integral, a sum, a special function) or is an opaque
solver call is recorded in the skip list with an honest reason, so coverage is an
honest, displayable number.

CLI:  python -m omai.lean_identities  ->  writes lean/OpenMaterialsIdentities.lean
"""
from __future__ import annotations

import re
from pathlib import Path

import sympy as sp
from sympy.core.function import AppliedUndef

_REPO = Path(__file__).resolve().parent.parent


def _identity_edges():
    from omai.thermodynamic_identities.operator import edges as tid
    return list(tid.EDGES)


def _all_edges():
    """Every operator (edge) across every domain, in a stable order. The `law`
    pass ranges over all of them; the `composition` pass stays scoped to the
    thermodynamic-identities domain (see module docstring)."""
    from omai.map_data import DOMAINS
    edges = []
    for dom in DOMAINS:
        edges.extend(getattr(dom, "edges", []) or [])
    return edges


def _lean_var(latex_sym: str) -> str:
    s = latex_sym
    for a, b in ((r"\gamma", "gamma"), (r"\alpha", "alpha"), (r"\sigma", "sigma"),
                 (r"\kappa", "kappa"), (r"\beta", "beta"), (r"\nu", "nu"),
                 (r"\mu", "mu"), (r"\rho", "rho"), (r"\Gamma", "Gamma"),
                 (r"\Delta", "Delta"), (r"\nabla", "nabla"),
                 (r"\varepsilon", "varepsilon"), (r"\mathbf", ""),
                 (r"\mathrm", "")):
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


def _flatten_indexed(expr):
    """Replace every Indexed atom (k_f[3,3], kappa[alpha,beta], ...) with a plain
    real Symbol named by the indexed atom's rendered form, so a formula written
    over tensor components becomes a scalar real expression. The index variables
    and the tensor base symbol then drop out (they only ever appeared inside the
    Indexed), leaving exactly the genuine scalar leaves."""
    idx = sorted(expr.atoms(sp.Indexed), key=str)
    return expr.xreplace({ix: sp.Symbol(str(ix)) for ix in idx})


# ---------------------------------------------------------------------------
# Composition theorems (thermodynamic-identities domain only).
# ---------------------------------------------------------------------------

def _theorem_list():
    """One composition theorem per identity edge that CHAINS on upstream
    identities. Given the upstream formulas as hypotheses, the direct form (in
    the intermediate symbols) equals the flat form (fully substituted), proved
    by `subst` then `ring`/`field_simp`. The two sides are genuinely different
    expressions; the hypotheses are what make them equal. A single-edge identity
    carries no algebraic content beyond its definition (proving it would be a
    reflexive X = X), so it is recorded as skipped, not emitted.

    Scoped to the thermodynamic-identities domain: there every output symbol is
    defined by exactly one edge, so the upstream-formula map is unambiguous.
    Across the whole map the same symbol (K, kappa_c, ...) is produced by several
    operators, so a global chain would substitute an arbitrary definition."""
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
        # Collect denominators in the form the goal takes AFTER the upstream
        # substitutions are applied (so `kappa_tot` becomes `kappa + kappa_e`
        # before we read its denominators). Substituting first means two
        # denominators that coincide post-substitution render identically and
        # deduplicate, instead of emitting a redundant `≠ 0` hypothesis.
        subst_map = {s: form for s, form in inters}
        raw_dens = (_denominators(rhs.subs(subst_map))
                    + _denominators(sp.together(flat)))
        dens, seen = [], set()
        for d in raw_dens:
            key = _lean_expr(d, symmap)
            if key not in seen:
                seen.add(key)
                dens.append(d)
        binders = " ".join(f"({symmap[str(x)]} : ℝ)" for x in all_syms)
        hyp_binders = "".join(f" (h_{hn} : {hn} = {he})" for hn, he in hyps)
        den_binders = "".join(f" (hd{i} : {_lean_expr(d, symmap)} ≠ 0)"
                              for i, d in enumerate(dens))
        subst_names = " ".join(f"h_{hn}" for hn, _ in hyps)
        # `field_simp` clears the (nonzero) denominators and closes these
        # algebraic identities on its own; a chained `ring` would be a
        # never-executed tactic and trips the unreachable-tactic linter.
        tail = "field_simp" if dens else "ring"
        proof = f"by subst {subst_names}; {tail}"
        name = "identity_" + _lean_var(op.name)
        lean = (f"theorem {name} {binders}{hyp_binders}{den_binders} :\n"
                f"    {direct_lean} = {flat_lean} := {proof}")
        theorems.append({"op": op.name, "name": name, "kind": "composition",
                         "chained": [str(s) for s, _ in inters], "lean": lean})
    return theorems, skipped


# ---------------------------------------------------------------------------
# Law theorems (standalone rational operators, any domain).
# ---------------------------------------------------------------------------

_TRANSC_NAMES = ("log", "exp", "sin", "cos", "tan", "cot", "sinh", "cosh",
                 "tanh", "coth", "asin", "acos", "atan", "atan2", "asinh",
                 "acosh", "atanh", "erf", "gamma", "Abs", "sign", "Min", "Max",
                 "floor", "ceiling", "conjugate")
_TRANSCENDENTAL = tuple(getattr(sp, n) for n in _TRANSC_NAMES if hasattr(sp, n))


def _law_out_reason(lhs, rhs):
    """Why an operator is out of scope for a `law` theorem, or None if in scope
    (a rational operator with a real denominator to clear). `lhs`/`rhs` are the
    formula's two sides with indexed slots already flattened to scalars."""
    for side in (lhs, rhs):
        for node in sp.preorder_traversal(side):
            if isinstance(node, sp.Integral):
                return "needs-analysis: integral"
            if isinstance(node, sp.Sum):
                return "needs-analysis: sum"
            if isinstance(node, sp.Product):
                return "needs-analysis: product"
            if isinstance(node, sp.Derivative):
                return "needs-analysis: derivative"
            if isinstance(node, sp.Piecewise):
                return "needs-analysis: piecewise"
    for node in sp.preorder_traversal(rhs):
        if isinstance(node, AppliedUndef):
            return f"opaque-function: {type(node).__name__}"
        if isinstance(node, sp.Function) and isinstance(node, _TRANSCENDENTAL):
            return f"special-function: {type(node).__name__}"
        if isinstance(node, sp.Pow):
            if node.exp.is_Rational and not node.exp.is_Integer:
                return "special-function: fractional-power"
            if node.exp.has(sp.Symbol):
                return "special-function: symbolic-exponent"
    if not lhs.is_Symbol:
        return f"non-scalar-lhs: {type(lhs).__name__}"
    try:
        if rhs.is_rational_function(*rhs.free_symbols) is False:
            return "non-rational"
    except Exception:  # pragma: no cover - defensive
        return "non-rational"
    if lhs in rhs.free_symbols:
        return "self-referential-lhs"
    if rhs.is_Symbol:
        return "trivial-alias: single-symbol definition"
    _, den = sp.fraction(sp.together(rhs))
    if den == 1 or den.is_number:
        return "trivial-law: polynomial definition (no denominator to clear)"
    return None


def _law_lean(op):
    """Render the `law` theorem for a standalone rational operator, or return a
    (None, reason) skip. Writing the formula's RHS as a single fraction N/D
    (N, D fraction-free polynomials, via together), the theorem introduces the
    output Y by hypothesis `h : Y = N / D`, requires the single denominator
    `D ≠ 0`, and asserts the cleared form `Y * D = N`. After `subst h` the goal
    is exactly `N / D * D = N`, closed by `div_mul_cancel₀`. Combining to one
    fraction first is what makes the proof uniform and robust: there is a single
    denominator to clear (no nested inverses `field_simp` stumbles on, no deep
    recursion on the composite formulas), and no `ring` is ever needed, so no
    tactic is ever a dead never-executed step."""
    f = getattr(op, "formula", None)
    if f is None or not isinstance(f, sp.Equality):
        return None, "no-formula"
    lhs = _flatten_indexed(f.lhs)
    rhs = _flatten_indexed(f.rhs)
    reason = _law_out_reason(lhs, rhs)
    if reason is not None:
        return None, reason

    num, den = sp.fraction(sp.together(rhs))
    all_syms = sorted({lhs} | rhs.free_symbols, key=str)
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
        num_lean = _lean_expr(num, symmap)
        den_lean = _lean_expr(den, symmap)
    except (ValueError, KeyError):
        return None, "unrenderable"

    yv = symmap[str(lhs)]
    binders = " ".join(f"({symmap[str(x)]} : ℝ)" for x in all_syms)
    hyp_binder = f" (h_{yv} : {yv} = ({num_lean}) / ({den_lean}))"
    den_binder = f" (hd0 : ({den_lean}) ≠ 0)"
    # After `subst`, the goal is `N / D * D = N`; `div_mul_cancel₀` closes it
    # exactly from `hd0`. No field_simp, no ring: nothing to leave unexecuted.
    proof = f"by subst h_{yv}; exact div_mul_cancel₀ _ hd0"
    name = "law_" + _lean_var(op.name)
    goal = f"{yv} * ({den_lean}) = ({num_lean})"
    lean = (f"theorem {name} {binders}{hyp_binder}{den_binder} :\n"
            f"    {goal} := {proof}")
    return {"op": op.name, "name": name, "kind": "law", "lean": lean}, None


def _law_list():
    """A `law` theorem for every standalone rational operator across all domains
    that is NOT already emitted as a composition, plus the skip list with honest
    per-operator reasons for the rest."""
    composition_ops = {t["op"] for t in _theorem_list()[0]}
    theorems, skipped = [], []
    for op in _all_edges():
        if op.name in composition_ops:
            continue  # already carried by a (richer) composition theorem
        thm, reason = _law_lean(op)
        if thm is not None:
            theorems.append(thm)
        else:
            skipped.append((op.name, reason))
    return theorems, skipped


def _combined():
    """Compositions then laws, and the merged skip list. An operator emitted as a
    composition never also appears as a skipped law (it is filtered in
    `_law_list`), and an operator emitted as a law is removed from the
    composition skip list so the skip reasons do not double-count."""
    comp_thms, comp_skips = _theorem_list()
    law_thms, law_skips = _law_list()
    theorems = comp_thms + law_thms
    emitted = {t["op"] for t in theorems}
    # The composition pass records every non-chaining edge of the
    # thermodynamic-identities domain as "no-upstream-chain"; if such an edge is
    # now emitted as a law, drop that stale skip entry. The law pass's own skip
    # list is the authoritative reason for every operator it did not emit.
    law_skip_ops = {op for op, _ in law_skips}
    skipped = [(op, r) for (op, r) in comp_skips
               if op not in emitted and op not in law_skip_ops]
    skipped += [(op, r) for (op, r) in law_skips if op not in emitted]
    # Stable order, unique by op.
    seen, uniq = set(), []
    for op, r in skipped:
        if op not in seen:
            seen.add(op)
            uniq.append((op, r))
    return theorems, uniq


def build_identities():
    theorems, skipped = _combined()
    stats = {"theorems": len(theorems),
             "compositions": sum(1 for t in theorems if t["kind"] == "composition"),
             "laws": sum(1 for t in theorems if t["kind"] == "law"),
             "skipped_noncomposition": len(skipped),
             "skipped": skipped, "map_version": _version()[:12]}
    return _render(theorems), stats


def build_index():
    """op -> {lean, kind} for the frontend."""
    theorems, _ = _combined()
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
        "  A `law` theorem introduces a standalone rational operator's output by",
        "  hypothesis (Y = N / D) and certifies its defining relation in cleared",
        "  form Y * D = N (subst then div_mul_cancel₀).",
        "  Dimensional consistency is Tier 1 (OpenMaterials.lean).",
        "  Compiles against Mathlib (Lean 4.31.0).",
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
        if k == "skipped":
            print(f"  {k}: {len(v)} entries")
        else:
            print(f"  {k}: {v}")
