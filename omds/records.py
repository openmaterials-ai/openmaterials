"""Record normalization: every simulation-like record becomes one flat shape.

Accepted inputs: a lineage record (omai/lineages.py shape, the lineage dict
plus optional execution), an instance row (variable, material, conditions,
value), or an already-flat dict. Nothing is inferred: absent fields stay
None or empty."""
from __future__ import annotations

FIELDS = ("node", "material", "template", "code", "conditions", "params", "hyperparameters")


def normalize_record(rec: dict) -> dict:
    if not isinstance(rec, dict):
        raise TypeError(f"a record is a dict, got {type(rec).__name__}")
    if "lineage" in rec and isinstance(rec["lineage"], dict):
        lin = rec["lineage"]
        execution = rec.get("execution") or {}
        return {
            "node": lin.get("node"),
            "material": lin.get("material"),
            "template": lin.get("template"),
            "code": execution.get("code"),
            "conditions": dict(lin.get("conditions") or {}),
            "params": {**(lin.get("params") or {}), **(lin.get("hyperparameters") or {}), **(lin.get("values") or {})},
            "hyperparameters": dict(lin.get("hyperparameters") or {}),
        }
    if "variable" in rec:
        return {
            "node": rec.get("variable"),
            "material": rec.get("material"),
            "template": None,
            "code": None,
            "conditions": dict(rec.get("conditions") or {}),
            "params": {},
            "hyperparameters": {},
        }
    out = {f: rec.get(f) for f in FIELDS}
    out["conditions"] = dict(out.get("conditions") or {})
    out["params"] = dict(out.get("params") or {})
    out["hyperparameters"] = dict(out.get("hyperparameters") or {})
    return out
