"""Cross-code agreement: what the map already knows about codes agreeing.

The map's thesis is that one observable is produced by many estimators and
codes that MUST agree, and the map makes that agreement checkable (KPI #6,
performance vs other code). This module surfaces the agreement the committed
instances already contain: it finds sets of values that are the SAME observable,
SAME material, and SAME physical conditions, differing only in the METHOD or
CODE that produced them, and reports their spread.

THE HONESTY CONTRACT (the equivalence rule):
Two instances are COMPARABLE iff they share the same BASE variable (the variable
with its ``[label]`` suffix stripped: ThermalConductivity[bte_solver=rta] and
ThermalConductivity[bte_solver=direct_inverse] share base ThermalConductivity),
the same material string, and the same PHYSICAL conditions. The physical
conditions are the ``conditions`` dict MINUS the estimator-identifying keys. The
estimator is identified by the variable's ``[label]`` (bte_solver=..., etc.) and
the conditions keys ``method`` and ``scattering``. EVERYTHING else in conditions
(T, direction, component, mesh, potential, supercell, q-grid, statistics, size,
Ge fraction, ...) is a PHYSICAL condition and must match. So a reported spread is
a REAL method or code disagreement, never an apples-to-oranges artifact: two
values only ever appear side by side when they answer the identical physical
question, and the source paper or code is not itself a physical condition (two
values from one paper with different solvers still compare; two values from
different codes with the same method and inputs are the strongest comparison).

A comparison GROUP is a set of >= 2 comparable instances that span >= 2 distinct
estimators (a distinct ``[label]`` or a distinct ``method``/``scattering``),
sharing identical physical conditions.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parent.parent / "docs"

# The [label] suffix a variable may carry (e.g. "[bte_solver=rta]"): stripping it
# yields the BASE observable two estimators of the same quantity share.
_LABEL_RE = re.compile(r"\[[^\]]*\]$")

# Conditions keys that IDENTIFY the estimator, not the physical question. These
# are removed to form the physical conditions, and (together with the variable's
# [label]) they are what makes two instances "different estimators".
_ESTIMATOR_COND_KEYS = ("method", "scattering")


def _base_var(variable: str) -> str:
    """The observable with its estimator [label] stripped."""
    return _LABEL_RE.sub("", variable)


def _label(variable: str) -> str:
    """The estimator [label] of a variable, without brackets, or ""."""
    m = _LABEL_RE.search(variable)
    return m.group(0)[1:-1] if m else ""


def _physical_conditions(conditions: dict) -> dict:
    """The conditions dict minus the estimator-identifying keys: the physical
    question two comparable instances must answer identically."""
    return {k: v for k, v in conditions.items() if k not in _ESTIMATOR_COND_KEYS}


def _estimator_key(rec: dict) -> tuple:
    """A hashable identity of the estimator that produced a value: its variable
    [label] together with the estimator-identifying conditions. Two records with
    the same key are the SAME estimator (so they may still be a cross-CODE pair
    if their source.ref differs); two records with different keys span the method
    axis the group reports on."""
    cond = rec.get("conditions") or {}
    return (_label(rec["variable"]),) + tuple(
        (k, cond[k]) for k in _ESTIMATOR_COND_KEYS if k in cond)


def _estimator_str(rec: dict) -> str:
    """A human label for the estimator: the variable [label] when present, else
    the method string (the neutral-node case, e.g. PtSe2's first-principles BTE
    vs FDTR, carries no [label] so the method is the only distinguishing text)."""
    lab = _label(rec["variable"])
    cond = rec.get("conditions") or {}
    parts = []
    if lab:
        parts.append(lab)
    for k in _ESTIMATOR_COND_KEYS:
        if k in cond:
            parts.append(f"{k}={cond[k]}")
    return " | ".join(parts) if parts else "(unlabeled)"


def agreement_groups(instances=None) -> list[dict]:
    """Same-observable, same-material, same-conditions comparison groups.

    Loads docs/data/instances.json when ``instances`` is None. Applies the
    equivalence rule in the module docstring: bucket by (base variable, material,
    physical conditions), keep only buckets with >= 2 members that span >= 2
    distinct estimators. Returns one dict per group, sorted by estimator count
    desc then spread desc.
    """
    if instances is None:
        instances = json.loads((_DOCS / "data" / "instances.json").read_text())

    buckets: dict[tuple, list[dict]] = {}
    for rec in instances:
        cond = rec.get("conditions") or {}
        key = (
            _base_var(rec["variable"]),
            rec["material"],
            json.dumps(_physical_conditions(cond), sort_keys=True),
        )
        buckets.setdefault(key, []).append(rec)

    groups = []
    for (base, material, cond_json), members in buckets.items():
        if len(members) < 2:
            continue
        # Span the method axis: at least two distinct estimators. A group of four
        # values on two solvers from two codes (the Si-Tersoff case) spans two
        # estimators (direct_inverse, rta) and is cross-CODE within each.
        est_keys = {_estimator_key(r) for r in members}
        if len(est_keys) < 2:
            continue

        values = [r["value"] for r in members]
        vmin, vmax = min(values), max(values)
        # math.fsum, not the builtin sum, so the mean (and the spread derived
        # from it) is byte-identical on every supported Python. Python 3.12
        # switched sum() to Neumaier compensated summation for floats
        # (python/cpython#100425); 3.11's plain left fold accumulates a
        # different last-ULP rounding, so sum([26.908, 24.301, 19.46, 16.735])
        # is 87.404 on 3.12 but 87.40400000000001 on 3.11. Since the committed
        # bundle is derived and pinned by test, that ULP would make the same
        # code emit two different agreement.json files. math.fsum returns the
        # exactly-rounded sum on both, matching the committed value, so the
        # bundle reproduces regardless of interpreter version.
        mean = math.fsum(values) / len(values)
        # Spread as a fraction of the mean: a dimensionless "how much do these
        # methods/codes disagree". Guard the degenerate mean == 0 (no thermal
        # group hits it, but a formation energy or a signed quantity could).
        spread = (vmax - vmin) / mean if mean else 0.0

        # Cross-CODE: the same estimator computed by two different sources. Within
        # any one estimator key, more than one distinct source.ref means two codes
        # (or two papers) ran the identical method and inputs and can be compared
        # directly.
        refs_by_est: dict[tuple, set] = {}
        for r in members:
            ref = (r.get("source") or {}).get("ref")
            refs_by_est.setdefault(_estimator_key(r), set()).add(ref)
        has_cross_code = any(len(refs) >= 2 for refs in refs_by_est.values())

        has_measurement = any(
            (r.get("source") or {}).get("kind") == "measurement" for r in members)

        # Members sorted by value desc so the table reads high-to-low.
        member_dicts = [{
            "value": r["value"],
            "units": r.get("units"),
            "estimator": _estimator_str(r),
            "ref": (r.get("source") or {}).get("ref"),
            "kind": (r.get("source") or {}).get("kind"),
        } for r in sorted(members, key=lambda x: x["value"], reverse=True)]

        groups.append({
            "observable": base,
            "material": material,
            "conditions": json.loads(cond_json),
            "members": member_dicts,
            "spread": spread,
            "min": vmin,
            "max": vmax,
            "mean": mean,
            "n_estimators": len(est_keys),
            "has_measurement": has_measurement,
            "has_cross_code": has_cross_code,
        })

    groups.sort(key=lambda g: (-g["n_estimators"], -g["spread"]))
    return groups


def build_agreement(out=None) -> Path:
    """Write docs/data/agreement.json: the groups plus a summary header.

    The summary counts the groups, how many are cross-code, how many put theory
    against experiment (a measurement member), and stamps the map version read
    from docs/data/version.json so a shared agreement view cites the map state it
    was built from, exactly like the other derived bundles.
    """
    out = Path(out) if out else (_DOCS / "data" / "agreement.json")
    groups = agreement_groups()
    version = {}
    version_path = _DOCS / "data" / "version.json"
    if version_path.exists():
        version = json.loads(version_path.read_text())
    payload = {
        "summary": {
            "groups": len(groups),
            "cross_code": sum(1 for g in groups if g["has_cross_code"]),
            "theory_vs_experiment": sum(1 for g in groups if g["has_measurement"]),
            "version": version.get("version"),
        },
        "groups": groups,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload))
    return out


if __name__ == "__main__":  # pragma: no cover - CLI: rebuild + summary
    path = build_agreement()
    data = json.loads(path.read_text())
    s = data["summary"]
    print(f"wrote {path}: {s['groups']} groups "
          f"({s['cross_code']} cross-code, "
          f"{s['theory_vs_experiment']} theory-vs-experiment)")
    for g in data["groups"]:
        tags = []
        if g["has_cross_code"]:
            tags.append("cross-code")
        if g["has_measurement"]:
            tags.append("theory-vs-experiment")
        tag = (" [" + ", ".join(tags) + "]") if tags else ""
        print(f"  {g['observable']} / {g['material']}: "
              f"{g['n_estimators']} estimators, spread {g['spread'] * 100:.1f}%{tag}")
        for m in g["members"]:
            print(f"    {m['value']} {m['units']}  {m['estimator']}  "
                  f"({m['ref']}, {m['kind']})")
