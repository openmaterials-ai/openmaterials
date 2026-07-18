"""The formalization roadmap: every operator rated by what proving it needs.

Companion to the lean exports. Each operator's formula is classified by the
mathematics a Lean proof of it would take:

- ``easy``: a genuinely rational identity (a nontrivial denominator to clear);
  the generator proves these outright, so they appear in
  ``OpenMaterialsIdentities.lean`` and carry ``proven: true``.
- ``trivial``: a polynomial definition; after substitution the statement is
  reflexive, so a theorem would certify nothing. Deliberately not emitted.
- ``hard``: the formula needs analysis (a sum over modes, an integral, a
  derivative, or a special function); provable in principle, but by hand,
  not by a generator tactic.
- ``na``: the right-hand side names an external code's output (an opaque
  function symbol) or the edge carries no formula; there is nothing
  algebraic to prove, only the dimension and the lineage.

The website renders ``docs/data/lean_roadmap.json``. The counts are an honest
statement of the frontier, not a coverage claim: ``hard`` and ``na`` rows say
plainly what a proof would take and why none is shipped.
"""
from __future__ import annotations

import json
from pathlib import Path

import sympy as sp
from sympy.core.function import AppliedUndef

_REPO = Path(__file__).resolve().parent.parent
_DOCS = _REPO / "docs"

_ANALYTIC = (sp.log, sp.exp, sp.sin, sp.cos, sp.tan,
             sp.sinh, sp.cosh, sp.tanh, sp.coth)


def _classify(op):
    """(class, difficulty, reason) for one operator's formula."""
    f = getattr(op, "formula", None)
    if not isinstance(f, sp.Equality):
        return ("no formula", "na",
                "the edge carries no formula; only dimension and lineage apply")
    rhs = f.rhs
    if any(rhs.has(x) for x in (sp.Integral, sp.Sum, sp.Product, sp.Derivative)):
        return ("integral / sum / derivative", "hard",
                "needs analysis: an aggregation over modes or a derivative, "
                "with convergence and measurability to establish")
    if any(rhs.has(x) for x in _ANALYTIC):
        return ("special function", "hard",
                "needs analysis: transcendental factors (occupation numbers, "
                "logarithms) with their analytic properties")
    if rhs.atoms(AppliedUndef):
        return ("opaque code output", "na",
                "names an external code's output; nothing algebraic to prove")
    den = sp.denom(sp.together(rhs))
    if den == 1 or den.is_number:
        return ("polynomial", "trivial",
                "polynomial definition, reflexive after substitution; a "
                "theorem would certify nothing")
    return ("rational", "easy",
            "rational identity; proven outright by the generator")


def build_roadmap():
    from omai.lean_identities import _version, build_index
    from omai.map_data import DOMAINS

    proven = set(build_index())
    rows, counts = [], {"easy": 0, "trivial": 0, "hard": 0, "na": 0}
    for d in DOMAINS:
        dom = getattr(d, "name", "?")
        for op in getattr(d, "operators", getattr(d, "edges", [])):
            cls, diff, reason = _classify(op)
            counts[diff] += 1
            rows.append({
                "domain": dom,
                "op": op.name,
                "class": cls,
                "difficulty": diff,
                "proven": op.name in proven,
                "reason": reason,
            })
    rows.sort(key=lambda r: (r["domain"], r["op"]))
    return {
        "version": _version()[:12],
        "counts": counts,
        "proven": sum(1 for r in rows if r["proven"]),
        "rows": rows,
    }


def write_roadmap(out: Path | None = None):
    out = out or _DOCS / "data" / "lean_roadmap.json"
    roadmap = build_roadmap()
    out.write_text(json.dumps(roadmap))
    stats = dict(roadmap["counts"], proven=roadmap["proven"],
                 rows=len(roadmap["rows"]))
    return out, stats
