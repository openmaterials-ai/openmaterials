"""MAP (API pass 2): map each detected claim onto a map node, deterministically
shaped by structured outputs.

Citations are incompatible with structured outputs (400), so this is a separate
call from DETECT. The compact node catalog rides in the system prompt under
cache_control ephemeral, byte-stable across calls and retries so a run's second
call reads the cache (verified via usage.cache_read_input_tokens).

Output per claim: a node id (or "UNMAPPABLE" with a reason and a proposed
quantity sketch for the new-node feed), a unit conversion declaration, a
material string, and a conditions dict.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .detect import MODEL, MAX_TOKENS, Usage, DetectedClaim


@dataclass
class MappedClaim:
    """A detected claim joined to a node decision from MAP."""
    detected: DetectedClaim
    node_id: str | None            # None when UNMAPPABLE
    unmappable_reason: str | None
    proposed_quantity: str | None  # the new-node feed sketch when UNMAPPABLE
    unit_declaration: str          # printed unit -> node canonical unit (factor/named)
    material: str
    conditions: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


# JSON schema for the structured output. No recursion, no min/max, every object
# closed with additionalProperties false and a required list.
def _output_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["mappings"],
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", "node_id", "unmappable_reason",
                                 "proposed_quantity", "unit_declaration",
                                 "material", "conditions_json"],
                    "properties": {
                        "index": {"type": "integer"},
                        "node_id": {
                            "type": "string",
                            "description": "A catalog node id, or 'UNMAPPABLE'.",
                        },
                        "unmappable_reason": {"type": "string"},
                        "proposed_quantity": {"type": "string"},
                        "unit_declaration": {"type": "string"},
                        "material": {"type": "string"},
                        "conditions_json": {
                            "type": "string",
                            "description": "The conditions object as a JSON string.",
                        },
                    },
                },
            }
        },
    }


def node_kind(node_id: str | None, catalog_by_id: dict) -> str:
    """Classify a mapped node as a value target or an input condition (P2.1).

    A claim landing on a source / parameter node (evidence_target: false in the
    catalog: Structure, Temperature, Potential, CellVolume, AtomicMass,
    AtomCount, ...) is CONTEXT, not evidence: it names a condition of a run, not
    a measured result. Such a claim survives into the proposal as context but is
    excluded from instance minting at apply time. Everything else, and an
    unmappable claim (node_id None), is a value. The discriminator is the
    catalog's per-node evidence_target flag, defaulted true, so a node absent
    from the catalog (or a claim with no node) defaults to "value".
    """
    if node_id is None:
        return "value"
    row = catalog_by_id.get(node_id)
    if row is None:
        return "value"
    return "value" if row.get("evidence_target", True) else "condition"


MAP_SYSTEM_INTRO = (
    "You map reported physical values from a paper onto nodes of the "
    "OpenMaterials map. Each node is a specific physical quantity with a fixed "
    "dimension. Map each claim to the SINGLE best node id from the catalog "
    "below, or 'UNMAPPABLE' if no node fits.\n\n"
)


def build_system(catalog_text: str) -> list[dict]:
    """The cached system prompt: instructions + the byte-stable node catalog.

    The catalog block carries cache_control ephemeral so multi-claim runs and
    retries reuse the cached prefix.
    """
    return [
        {"type": "text", "text": MAP_SYSTEM_INTRO},
        {"type": "text", "text": catalog_text,
         "cache_control": {"type": "ephemeral"}},
    ]


def _claims_payload(claims: list[DetectedClaim]) -> str:
    """Render the detected claims as a compact JSON list for the user turn."""
    rows = []
    for i, c in enumerate(claims):
        rows.append({
            "index": i,
            "quantity": c.quantity,
            "symbol": c.symbol,
            "value": c.value_text,
            "unit": c.unit,
            "material": c.material,
            "conditions": c.conditions,
            "provenance": c.provenance,
        })
    return json.dumps(rows, ensure_ascii=False)


MAP_USER_INSTRUCTIONS = (
    "Here are the detected claims as a JSON array. For each, return a mapping "
    "object. Rules:\n"
    "- node_id: the exact id of the best-matching catalog node, or the literal "
    "string 'UNMAPPABLE'. Match on the physical quantity AND its dimension; a "
    "value in W/(m K) can only map to a thermal-conductivity node, etc. When a "
    "node id carries a label like [bte_solver=rta] or [carrier=ionic], choose "
    "the label that matches the claim's stated method/conditions. For a lattice "
    "thermal conductivity, [bte_solver=rta] means the relaxation-time "
    "approximation and [bte_solver=direct_inverse] means the direct/iterative "
    "(full/exact) LBTE solver; a bulk single-crystal steady-state or "
    "experimental-reference thermal conductivity given WITHOUT a stated RTA "
    "method maps to [bte_solver=direct_inverse] (the reference solver), NOT to "
    "[contribution=total] (which is only for an explicit lattice+electronic "
    "sum).\n"
    "- unmappable_reason: a short reason when UNMAPPABLE, else empty string.\n"
    "- proposed_quantity: when UNMAPPABLE, a one-line sketch of the quantity a "
    "new node would represent (this feeds new-node design), else empty string.\n"
    "- unit_declaration: 'printed_unit -> node_canonical_unit' with a factor or "
    "named registered unit, or the printed unit alone if already canonical.\n"
    "- material: the material/system string.\n"
    "- conditions_json: the conditions object serialized as a JSON string.\n"
    "Return an object with a 'mappings' array, one entry per claim, in index "
    "order."
)


MAP_BATCH_SIZE = 40  # claims per MAP call. The ensemble detect on a long
                     # paper can union 100+ claims, whose mappings overflow a
                     # single 16k output (live: quantum-elastic and ptse2,
                     # 2026-07-12). Batches keep each call's output bounded;
                     # the catalog system block is cache_control'd, so extra
                     # calls re-read it from cache instead of paying full price.


def map_claims(client, claims: list[DetectedClaim], catalog_text: str,
               usage: Usage) -> tuple[list[MappedClaim], str, dict]:
    """Run pass 2 with structured outputs, in batches of MAP_BATCH_SIZE claims.

    Returns (mapped, stop_reason, cache_info) where cache_info sums the
    cache reads across batches and stop_reason is the first non-end_turn
    stop encountered (a refusal aborts the remaining batches).
    """
    if not claims:
        return [], "end_turn", {"cache_read_input_tokens": 0}

    mapped_all: list[MappedClaim] = []
    total_cache = 0
    for lo in range(0, len(claims), MAP_BATCH_SIZE):
        batch = claims[lo:lo + MAP_BATCH_SIZE]
        mapped, stop, info = _map_one_batch(client, batch, catalog_text, usage)
        total_cache += info.get("cache_read_input_tokens", 0)
        mapped_all.extend(mapped)
        if stop != "end_turn":
            return mapped_all, stop, {"cache_read_input_tokens": total_cache}
    return mapped_all, "end_turn", {"cache_read_input_tokens": total_cache}


def _map_one_batch(client, claims: list[DetectedClaim], catalog_text: str,
                   usage: Usage) -> tuple[list[MappedClaim], str, dict]:
    """One structured-output MAP call over a bounded batch. Payload indices
    are LOCAL to the batch (0..len-1); the caller reassembles by order."""
    system = build_system(catalog_text)
    user = MAP_USER_INSTRUCTIONS + "\n\nCLAIMS:\n" + _claims_payload(claims)

    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _output_schema()}},
    )
    usage.add(resp.usage)
    stop = resp.stop_reason
    cache_read = getattr(resp.usage, "cache_read_input_tokens", 0) or 0
    cache_info = {"cache_read_input_tokens": cache_read}
    if stop == "refusal":
        return [], stop, cache_info
    if stop == "max_tokens":
        raise RuntimeError("MAP truncated (max_tokens); raise cap or split claims")

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"mappings": []}
    by_index = {m.get("index"): m for m in data.get("mappings", []) if isinstance(m, dict)}

    mapped: list[MappedClaim] = []
    for i, c in enumerate(claims):
        m = by_index.get(i, {})
        node_id = m.get("node_id") or ""
        unmappable = node_id.strip().upper() == "UNMAPPABLE" or node_id == ""
        cond_raw = m.get("conditions_json") or "{}"
        try:
            conditions = json.loads(cond_raw)
            if not isinstance(conditions, dict):
                conditions = {}
        except json.JSONDecodeError:
            conditions = c.conditions or {}
        mapped.append(MappedClaim(
            detected=c,
            node_id=None if unmappable else node_id,
            unmappable_reason=(m.get("unmappable_reason") or None) if unmappable else None,
            proposed_quantity=(m.get("proposed_quantity") or None) if unmappable else None,
            unit_declaration=m.get("unit_declaration") or (c.unit or ""),
            material=m.get("material") or (c.material or ""),
            conditions=conditions,
            raw=m,
        ))
    return mapped, stop, cache_info
