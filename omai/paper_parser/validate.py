"""Deterministic, kernel-powered validation (no LLM).

Every surviving MAP claim must clear these gates:

  - node resolves: the mapped variable is a live node in docs/data/graph.json
    (uid-pinned via the same name->uid bridge the instance bundler uses);
  - unit sane: the printed unit maps to a registered unit whose dimension
    matches the node's field dimension, OR is a soft note when the printed unit
    cannot be resolved (many real printed spellings are not in the 47-token
    registry); a dimensional MISMATCH is a hard kill;
  - value finite: the numeric value is a real, finite number;
  - quote VERIFIED: the cited_text appears, after normalization, as a substring
    of the extracted PDF text. A claim whose quote is not present DIES here.
    This is the hallucination gate.
  - duplicate: (node uid + material + approx value) already present in
    docs/data/instances/ -> flagged duplicate (already on the map).

The quote gate is the one that proves the pipeline is honest: no claim survives
without a verbatim, page-located quote from the document.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[2] / "docs"


# --------------------------------------------------------------------------
# Quote normalization and verification (the hallucination gate)
# --------------------------------------------------------------------------
# Ligatures and hyphenation break naive substring matching against PDF text.
# Normalization: NFKC (splits ligatures like fi -> f i), strip soft hyphens and
# line-break hyphenation, collapse all whitespace to single spaces, lowercase.
_LIGATURE_MAP = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "­": "",  # soft hyphen
}


def normalize_quote(text: str) -> str:
    """Normalize a string for whitespace/ligature/hyphenation-insensitive
    matching.

    Applies: explicit ligature expansion, NFKC compatibility decomposition,
    removal of hyphen-newline hyphenation (a word split across a line break),
    whitespace collapse, and lowercasing. Deterministic and idempotent.
    """
    for src, dst in _LIGATURE_MAP.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    # Join words hyphenated across a line break: "conduc-\ntivity" -> "conductivity".
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def quote_verified(cited_text: str, corpus_text: str) -> bool:
    """True iff the normalized cited_text is a substring of the normalized
    corpus.

    Empty cited_text never verifies (a claim must carry a real quote). The
    corpus is the extracted PDF full text; both sides are normalized the same
    way so ligature and hyphenation artifacts do not cause false negatives. A
    second, stricter pass compares both sides with ALL whitespace removed: PDF
    extraction inconsistently inserts or drops the space between a number and its
    unit (e.g. "156 W/(m K)" vs a quote's "156W/(m K)"), and that single space is
    not a semantic difference. The space-free pass never lets a genuinely absent
    quote through: it can only merge tokens that were already adjacent, so a
    fabricated number still fails both passes.
    """
    needle = normalize_quote(cited_text)
    if not needle:
        return False
    corpus = normalize_quote(corpus_text)
    if needle in corpus:
        return True
    ns = needle.replace(" ", "")
    return bool(ns) and ns in corpus.replace(" ", "")


# --------------------------------------------------------------------------
# Node resolution
# --------------------------------------------------------------------------
def build_name_to_uid(domains=None) -> dict[str, str]:
    """Return the {node id -> content-addressed uid} map over the unified map.

    This is exactly the bridge build_instances uses to pin a value to a node,
    so a validated claim's node_uid matches what an applied instance would get.
    """
    from omai.map_data import _domains, build_graph_dict

    g = build_graph_dict(domains or _domains())
    return {n["id"]: n["uid"] for n in g["nodes"]}


# --------------------------------------------------------------------------
# Unit sanity
# --------------------------------------------------------------------------
# Printed-unit spellings the map's 47-token registry does not carry verbatim.
# Mapping a printed unit to its registered token lets us check the dimension
# against the node; an unmapped printed unit is a soft note, not a kill.
_PRINTED_UNIT_ALIASES = {
    "w/(m k)": "W_per_m_per_K",
    "w/(m·k)": "W_per_m_per_K",
    "w/m k": "W_per_m_per_K",
    "w/m/k": "W_per_m_per_K",
    "mс/cm": "ms_per_cm",
    "ms/cm": "ms_per_cm",
    "ev": "ev",
    "ev/atom": "ev_per_atom",
    "gpa": "GPa",
    "1/k": "per_kelvin",
    "k^-1": "per_kelvin",
    "v": "volt",
    "volt": "volt",
    "j/m^2": "J_per_m2",
    "j/m2": "J_per_m2",
    "mu_b": "mu_B",
    "ry": "ry",
    # Molar heat capacity and molar energy: the registry has carried
    # J_per_K_per_mol / J_per_mol / kJ_per_mol from the start (units.py calls
    # J/(K·mol) the canonical molar heat capacity), but no printed spelling
    # resolved to them, so every C_p / reaction-enthalpy claim passed the
    # unit gate "unresolved" instead of dimension-checked. These are the
    # spellings thermochemistry papers actually print.
    "j/(k mol)": "J_per_K_per_mol",
    "j/(mol k)": "J_per_K_per_mol",
    "j/(k·mol)": "J_per_K_per_mol",
    "j/(mol·k)": "J_per_K_per_mol",
    "j/mol/k": "J_per_K_per_mol",
    "j/mol k": "J_per_K_per_mol",
    "j mol^-1 k^-1": "J_per_K_per_mol",
    "j mol-1 k-1": "J_per_K_per_mol",
    # the IUPAC/NIST order (K before mol) is at least as common in journals
    "j k^-1 mol^-1": "J_per_K_per_mol",
    "j k-1 mol-1": "J_per_K_per_mol",
    "j/mol": "J_per_mol",
    "j mol^-1": "J_per_mol",
    "kj/mol": "kJ_per_mol",
    "kj mol^-1": "kJ_per_mol",
    "kj mol-1": "kJ_per_mol",
    # Thermal conductance (the Landauer G(T) of the MESCAL onboarding): the
    # registry carries W_per_K (canonical) and nW_per_K (MESCAL's native
    # serving unit, 1e-9). These printed spellings let a coherent-transport
    # claim dimension-check against ThermalConductance instead of passing
    # unresolved, and a W/K value pasted onto the per-length
    # ThermalConductivity node dies as a hard mismatch.
    "w/k": "W_per_K",
    "nw/k": "nW_per_K",
}


def unit_check(printed_unit: str, node_id: str, catalog_by_id: dict) -> dict:
    """Check the printed unit against the mapped node's dimension.

    Returns {ok, kind, note} where kind is one of:
      - "match": printed unit maps to a registered token whose dimension equals
        the node's field dimension (best case);
      - "mismatch": printed unit maps to a registered token of a DIFFERENT
        dimension -> ok=False (a hard kill signal);
      - "unresolved": printed unit could not be mapped to any registered token
        -> ok=True with a note (soft: many valid printed spellings, e.g. the
        node has no single canonical unit exposed in the catalog).
    """
    from omai.representation.units import UNITS

    node = catalog_by_id.get(node_id)
    node_dim = (node or {}).get("dimension")
    key = (printed_unit or "").strip().lower()
    token = _PRINTED_UNIT_ALIASES.get(key)
    if token is None:
        return {"ok": True, "kind": "unresolved",
                "note": f"printed unit {printed_unit!r} not in registry; unchecked"}
    unit = UNITS.get(token)
    if unit is None:
        return {"ok": True, "kind": "unresolved",
                "note": f"alias {token!r} not registered; unchecked"}
    unit_dim = unit.dimension.name
    # The node's catalog dimension is the field-dimension string; a node may
    # report several comma-joined dims, so accept a membership match.
    node_dims = {d.strip() for d in (node_dim or "").split(",") if d.strip()}
    if node_dim and node_dims and unit_dim not in node_dims:
        return {"ok": False, "kind": "mismatch",
                "note": f"unit {printed_unit!r} is {unit_dim}; node is {node_dim}"}
    return {"ok": True, "kind": "match", "note": f"{printed_unit!r} -> {token} ({unit_dim})"}


# --------------------------------------------------------------------------
# Value sanity
# --------------------------------------------------------------------------
def value_finite(value) -> bool:
    """True iff value is a real finite number (bool rejected, as elsewhere)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


# --------------------------------------------------------------------------
# Duplicate detection against the committed instance corpus
# --------------------------------------------------------------------------
# Full element / compound names a paper may spell out, mapped to the symbol the
# committed instances use. Applied before the alphanumeric collapse so
# 'silicon' and 'Si', 'germanium' and 'Ge' dedup to the same key.
_MATERIAL_NAME_ALIASES = {
    "silicon": "si",
    "germanium": "ge",
    "copper": "cu",
    "iron": "fe",
    "lithium": "li",
}


def _norm_material(material: str) -> str:
    """Loose material key: element-name aliasing then lowercase alphanumerics.

    'Cu Sigma5 [001] tilt' and 'cu sigma5 001 tilt' collapse to the same key, and
    a spelled-out 'silicon' collapses to the committed 'si', so a paper's phrasing
    still matches the committed instance's material.
    """
    m = (material or "").lower()
    for name, sym in _MATERIAL_NAME_ALIASES.items():
        m = re.sub(rf"\b{name}\b", sym, m)
    return re.sub(r"[^a-z0-9]+", "", m)


def load_instance_index(instances_dir: Path | None = None, domains=None) -> list[dict]:
    """Load the committed instances as dedup records: node_uid, material key,
    value.

    Uses the same node_uid pinning as the bundler so dedup compares by node
    identity, not by the (mutable) node name string.
    """
    instances_dir = instances_dir or (_DOCS / "data" / "instances")
    name_to_uid = build_name_to_uid(domains)
    out: list[dict] = []
    if not instances_dir.exists():
        return out
    for f in sorted(instances_dir.glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        var = rec.get("variable")
        uid = name_to_uid.get(var)
        if uid is None:
            continue
        out.append({
            "node_uid": uid,
            "variable": var,
            "material_key": _norm_material(rec.get("material", "")),
            "value": rec.get("value"),
            "units": rec.get("units"),
            "file": f.name,
        })
    return out


def is_duplicate(node_uid: str, material: str, value, index: list[dict],
                 rel_tol: float = 1e-3, abs_tol: float = 1e-6) -> dict | None:
    """Return the matching instance record if (uid + material + approx value)
    is already committed, else None.

    Approximate value match tolerates rounded renderings in the paper (e.g. a
    phono3py 16.74 quote against a committed 16.735) via math.isclose with a
    relative tolerance. Material compares on the loose alphanumeric key.
    """
    mat_key = _norm_material(material)
    if not value_finite(value):
        return None
    for rec in index:
        if rec["node_uid"] != node_uid:
            continue
        if rec["material_key"] != mat_key:
            continue
        rv = rec["value"]
        if not value_finite(rv):
            continue
        if math.isclose(value, rv, rel_tol=rel_tol, abs_tol=abs_tol):
            return rec
    return None


# --------------------------------------------------------------------------
# The per-claim validation record
# --------------------------------------------------------------------------
@dataclass
class Validation:
    """The deterministic verdict for one mapped claim."""
    node_ok: bool
    unit: dict
    value_ok: bool
    quote_ok: bool
    duplicate: dict | None
    node_uid: str | None
    kills: list[str] = field(default_factory=list)

    @property
    def survives(self) -> bool:
        """A claim survives VALIDATE iff it has no fatal kill.

        Fatal kills: unmapped/unknown node, unit dimensional mismatch, non-finite
        value, unverified quote. A duplicate flag is NOT fatal (the whole point of
        the P1 golden gate is that recovered knowns survive and are flagged).
        """
        return not self.kills


def validate_claim(*, node_id: str | None, printed_unit: str, value,
                   cited_text: str, material: str, corpus_text: str,
                   name_to_uid: dict, catalog_by_id: dict,
                   instance_index: list[dict]) -> Validation:
    """Run all deterministic gates on one mapped claim and return the verdict.

    node_id may be None (an UNMAPPABLE claim from MAP): that is a node kill.
    Order of kills recorded: node, quote, unit, value. The quote gate is the
    hallucination gate; a claim whose quote is absent is killed here regardless
    of how well-formed the rest is.
    """
    kills: list[str] = []

    node_uid = name_to_uid.get(node_id) if node_id else None
    node_ok = node_uid is not None
    if not node_ok:
        kills.append(f"unmapped_node:{node_id!r}")

    quote_ok = quote_verified(cited_text, corpus_text)
    if not quote_ok:
        kills.append("unverified_quote")

    unit = unit_check(printed_unit, node_id, catalog_by_id) if node_ok else {
        "ok": True, "kind": "skipped", "note": "no node"}
    if not unit["ok"]:
        kills.append("unit_dimension_mismatch")

    value_ok = value_finite(value)
    if not value_ok:
        kills.append("nonfinite_value")

    duplicate = None
    if node_ok and value_ok:
        duplicate = is_duplicate(node_uid, material, value, instance_index)

    return Validation(node_ok=node_ok, unit=unit, value_ok=value_ok,
                      quote_ok=quote_ok, duplicate=duplicate,
                      node_uid=node_uid, kills=kills)
