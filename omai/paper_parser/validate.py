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
  - not a delta: the quote does not frame the value as a difference/change of
    the mapped quantity ("a 0.6 W/mK drop of kappa" is a delta, not a value);
  - not a descriptive spectral marker: a Frequency-family quote does not frame
    the value as a prose band edge / threshold ("below 4 THz") rather than a
    measured peak. These two are code-level kills for cases the LLM reviewer
    does not reliably catch; both are deliberately conservative.
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
    # Interface (Kapitza) thermal boundary conductance: W_per_m2_k and
    # MW_per_m2_k entered the registry with the composites domain, but no
    # printed spelling resolved to them, so a G claim would pass the unit
    # gate "unresolved" instead of dimension-checked. These are the spellings
    # composite / thermal-boundary-conductance papers actually print (the
    # practitioner scale is MW/(m^2 K)).
    "w/(m^2 k)": "W_per_m2_k",
    "w/(m^2·k)": "W_per_m2_k",
    "w/(m2 k)": "W_per_m2_k",
    "w/m^2/k": "W_per_m2_k",
    "w/m^2 k": "W_per_m2_k",
    "w m^-2 k^-1": "W_per_m2_k",
    "w m-2 k-1": "W_per_m2_k",
    "mw/(m^2 k)": "MW_per_m2_k",
    "mw/(m^2·k)": "MW_per_m2_k",
    "mw/(m2 k)": "MW_per_m2_k",
    "mw/m^2/k": "MW_per_m2_k",
    "mw/m^2 k": "MW_per_m2_k",
    "mw m^-2 k^-1": "MW_per_m2_k",
    "mw m-2 k-1": "MW_per_m2_k",
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
# Semantic quote gates (deterministic; the LLM reviewer is not reliable here)
# --------------------------------------------------------------------------
# The adversarial REVIEW prompt asks the model to kill two families of claim
# that corrupt the map if applied: a DIFFERENCE quoted as if it were an
# absolute value (a "0.6 W/mK drop of kappa" is a delta, not a value of the
# absolute-value node), and a DESCRIPTIVE SPECTRAL MARKER (a frequency quoted
# as a band edge / threshold in running prose, "below 4 THz", is narrative
# structure, not a measured mode). The model does not obey that instruction
# reliably (live: it confirmed the Lundgren 0.6/0.55 drops and the "below 4
# THz" markers, reason text and all), so these two gates make the kill in
# code, off the LLM. Both are deliberately CONSERVATIVE: a false kill discards
# a real value, so when the signal is not tightly bound to the value we do NOT
# kill and leave the ambiguous case to the LLM reviewer backstop.

# Delta cues. A NOUN ("drop", "reduction", ...) marks the value as a change
# only when it binds to the value via "of" (drop of / reduction of), and a
# VERB ("reduced", "decreased", ...) only when it binds via "by" (reduced by
# <number>). The binding word is what proves the CHANGE is the quantity
# itself, not a change mentioned elsewhere in the sentence.
_DELTA_NOUNS = ("drop", "reduction", "decrease", "increase", "rise",
                "change", "delta", "difference")
_DELTA_VERBS = ("reduced", "decreased", "increased", "rose", "lowered",
                "raised", "dropped")
# The delta cue must sit within this many characters of the value token; a
# sentence break (. ; :) between the value and the cue defeats the binding.
_DELTA_WINDOW = 24


def _value_token(value) -> str:
    """The bare numeric token as printed, to locate the value in a normalized
    quote. Integral floats render without the trailing ".0" so a quote's "4"
    matches value 4.0. Non-numeric -> "" (never locates, so never kills)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(f)) if f == int(f) else repr(f)


def is_delta_posing_as_value(cited_text: str, value) -> bool:
    """True iff the quote frames `value` as a difference/change of the mapped
    quantity rather than an absolute value.

    Deliberately conservative: fires only on a delta cue TIGHTLY bound to the
    value token ("<noun> of <value>", "<value> <unit> <noun> of <quantity>",
    "<verb> by <value>"), with no sentence break between them. A sentence that
    merely mentions a change far from the value (e.g. "the conductivity is 145
    W/mK; an increase in temperature was applied later") is NOT killed: the
    "increase" neither binds to 145 by "of"/"by" nor sits before a sentence
    break-free window, so a real absolute value survives to the LLM backstop.
    """
    q = normalize_quote(cited_text)
    tok = _value_token(value)
    if not q or not tok:
        return False
    m = re.search(r"(?<![\d.])" + re.escape(tok) + r"(?![\d.])", q)
    if not m:
        return False
    lo, hi = m.start(), m.end()
    left = q[max(0, lo - _DELTA_WINDOW):lo]
    # a touch beyond the window so a cue starting at the edge still completes
    right = q[hi:hi + _DELTA_WINDOW + 16]

    def _blocked(s: str) -> bool:
        return bool(re.search(r"[.;:]", s))

    # PATTERN A: delta-noun BEFORE the value, bound by "of": "reduction of 0.55".
    for noun in _DELTA_NOUNS:
        if re.search(rf"\b{noun}\s+of\s*$", left) and not _blocked(left):
            return True
    # PATTERN B: delta-noun AFTER value(+unit), bound to the quantity by a
    # trailing "of": "0.6 W/mK drop of kappa". No LEADING word boundary is
    # required because PDF extraction glues the unit to the noun ("K-1reduction"),
    # where the character before the noun is a digit, not a boundary; a lowercase
    # letter before the noun WOULD make it a different word, so only that is
    # excluded.
    for noun in _DELTA_NOUNS:
        mb = re.search(rf"(?<![a-z]){noun}\s+of\b", right)
        if mb and mb.start() <= _DELTA_WINDOW and not _blocked(right[:mb.start()]):
            return True
    # PATTERN C: delta-verb BEFORE the value, bound by "by": "decreased by 0.6".
    for verb in _DELTA_VERBS:
        if re.search(rf"\b{verb}\s+by\s*$", left) and not _blocked(left):
            return True
    return False


# The Frequency-family nodes: frequency-dimensioned observables that name a
# POSITION on a spectral axis (a frequency/wavenumber value a paper describes
# with band edges). Deliberately excludes Linewidth, GroupVelocity, and the
# dynamical matrices: a "below X" on a linewidth or velocity is not the
# band-edge narrative this gate targets, so keeping the set small avoids
# killing legitimate values on those nodes.
_SPECTRAL_NODE_IDS = frozenset({"Frequency", "MolecularFrequency", "PhononDOS"})
# Band-edge / threshold / range-bound / crossover cues in prose.
_SPECTRAL_MARKERS = ("below", "above", "larger than", "smaller than",
                     "less than", "greater than", "lower than", "higher than",
                     "up to", "crossover", "threshold", "range", "edge",
                     "upper bound", "lower bound", "cutoff", "cut-off")
# Cues that a number is a REAL measured/computed spectral feature (a peak, a
# mode, a Raman shift, a table entry), which must survive even if a bound word
# is also present in the sentence.
_SPECTRAL_PEAK_CUES = ("peak", "mode at", "modes at", "shift", "centered at",
                       "centred at", "located at", "resonance", "line at")


def _is_spectral_node(node_id: str | None, catalog_by_id: dict) -> bool:
    """True iff node_id is one of the Frequency-family nodes AND still carries
    the frequency dimension in the catalog (so a rename that changed the
    physics would drop out of the gate rather than silently mis-fire)."""
    if node_id not in _SPECTRAL_NODE_IDS:
        return False
    dim = (catalog_by_id.get(node_id) or {}).get("dimension", "")
    return "frequency" in {d.strip() for d in dim.split(",") if d.strip()}


def is_descriptive_spectral_marker(cited_text: str, node_id: str | None,
                                   catalog_by_id: dict) -> bool:
    """True iff the node is a Frequency-family node AND the quote frames the
    value as a band edge / threshold / range bound / crossover in prose rather
    than a measured or computed peak/mode value.

    Deliberately conservative: a genuine peak/mode/shift value survives (the
    "peak"/"mode at"/"shift"/"centered at" cues short-circuit the kill), and a
    bare number sequence with no marker word (a table row) survives too. Only
    an explicit prose bound ("below/above/larger than ... THz", "between X and
    Y") on a spectral node is killed; anything else is left to the LLM backstop.
    """
    if not _is_spectral_node(node_id, catalog_by_id):
        return False
    q = normalize_quote(cited_text)
    if not q:
        return False
    # a real spectral feature survives even if a bound word appears nearby
    for cue in _SPECTRAL_PEAK_CUES:
        if cue in q:
            return False
    # "between X and Y" is a range bound
    if re.search(r"\bbetween\b.*\band\b", q):
        return True
    for marker in _SPECTRAL_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", q):
            return True
    return False


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
        # Evidence files are lineage instances ({id, kind, lineage, source});
        # the claim lives in the lineage object.
        lineage = rec.get("lineage") or {}
        var = lineage.get("node")
        uid = name_to_uid.get(var)
        if uid is None:
            continue
        values = lineage.get("values") or {}
        out.append({
            "node_uid": uid,
            "variable": var,
            "material_key": _norm_material(lineage.get("material") or ""),
            "value": values.get("value"),
            "units": values.get("units"),
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
        value, unverified quote, a delta posing as a value, a descriptive
        spectral marker. A duplicate flag is NOT fatal (the whole point of the
        P1 golden gate is that recovered knowns survive and are flagged).
        """
        return not self.kills


def validate_claim(*, node_id: str | None, printed_unit: str, value,
                   cited_text: str, material: str, corpus_text: str,
                   name_to_uid: dict, catalog_by_id: dict,
                   instance_index: list[dict]) -> Validation:
    """Run all deterministic gates on one mapped claim and return the verdict.

    node_id may be None (an UNMAPPABLE claim from MAP): that is a node kill.
    Order of kills recorded: node, quote, unit, value, then the two semantic
    quote gates (delta-posing-as-value, descriptive-spectral-marker). The quote
    gate is the hallucination gate; a claim whose quote is absent is killed here
    regardless of how well-formed the rest is.
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

    # Semantic quote gates (deterministic, off the unreliable LLM reviewer): a
    # difference posing as an absolute value, and a descriptive spectral marker
    # on a Frequency-family node. Both are conservative (see the functions);
    # they run only for a live node so the node kill is not double-counted.
    if node_ok and is_delta_posing_as_value(cited_text, value):
        kills.append("delta_posing_as_value")
    if node_ok and is_descriptive_spectral_marker(cited_text, node_id, catalog_by_id):
        kills.append("descriptive_spectral_marker")

    duplicate = None
    if node_ok and value_ok:
        duplicate = is_duplicate(node_uid, material, value, instance_index)

    return Validation(node_ok=node_ok, unit=unit, value_ok=value_ok,
                      quote_ok=quote_ok, duplicate=duplicate,
                      node_uid=node_uid, kills=kills)
