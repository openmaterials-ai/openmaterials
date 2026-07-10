"""REVIEW (API pass 3): an adversarial pass over the claims that survived
deterministic validation.

For each surviving claim, given the quote in its page context (a window of the
extracted text), try to refute it: wrong quantity, wrong material, unit misread,
a value cited from another work rather than the paper's own, or a table header
mistaken for a value. Verdict per claim: confirmed / corrected(field) / killed.

Structured outputs (no citations here), so the catalog can again ride cached in
the system prompt for consistency with MAP.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .detect import MODEL, MAX_TOKENS, Usage
from .validate import normalize_quote


@dataclass
class Verdict:
    """The adversarial verdict for one surviving claim."""
    index: int
    verdict: str            # confirmed | corrected | killed
    corrected_field: str | None
    corrected_value: str | None
    reason: str
    raw: dict = field(default_factory=dict)


def _review_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdicts"],
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", "verdict", "corrected_field",
                                 "corrected_value", "reason"],
                    "properties": {
                        "index": {"type": "integer"},
                        "verdict": {
                            "type": "string",
                            "enum": ["confirmed", "corrected", "killed"],
                        },
                        "corrected_field": {"type": "string"},
                        "corrected_value": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }


REVIEW_SYSTEM = (
    "You are an adversarial reviewer of extracted physical-value claims from a "
    "scientific paper. For each claim you are given the quote it was extracted "
    "from, in its surrounding page context. Try to REFUTE the claim. Look for: "
    "wrong quantity (the quote is about a different property), wrong material, a "
    "misread unit, a value that is CITED FROM ANOTHER WORK rather than the "
    "paper's own result, or a table-header/label mistaken for a value. Only "
    "confirm a claim you cannot refute.\n\n"
    "Verdict per claim: 'confirmed' (the claim is correct), 'corrected' (a "
    "single field is wrong; give corrected_field and corrected_value), or "
    "'killed' (the claim should not exist; give the reason)."
)


def _context_window(cited_text: str, corpus: str, radius: int = 400) -> str:
    """Return a normalized window of the corpus around the cited_text.

    Locates the (normalized) quote in the (normalized) corpus and returns a
    +/-radius-character window so the reviewer sees surrounding sentences. If the
    quote is not found (it should be, since only verified claims reach REVIEW),
    returns the cited_text alone.
    """
    ncorpus = normalize_quote(corpus)
    nquote = normalize_quote(cited_text)
    i = ncorpus.find(nquote) if nquote else -1
    if i < 0:
        return cited_text
    lo = max(0, i - radius)
    hi = min(len(ncorpus), i + len(nquote) + radius)
    return ncorpus[lo:hi]


def _payload(surviving, corpus: str) -> str:
    """Render surviving claims + their page-context windows for the reviewer.

    `surviving` is a list of (index, mapped_claim, validation) tuples.
    """
    rows = []
    for index, mapped, _val in surviving:
        d = mapped.detected
        rows.append({
            "index": index,
            "node_id": mapped.node_id,
            "quantity": d.quantity,
            "value": d.value_text,
            "unit": d.unit,
            "material": mapped.material,
            "provenance": d.provenance,
            "pages": d.pages,
            "quote": d.cited_text,
            "page_context": _context_window(d.cited_text, corpus),
        })
    return json.dumps(rows, ensure_ascii=False)


def review(client, surviving, catalog_text: str, corpus: str,
           usage: Usage) -> tuple[list[Verdict], str]:
    """Run pass 3. Returns (verdicts, stop_reason).

    `surviving` is a list of (index, mapped_claim, validation). A refusal returns
    empty verdicts with the stop_reason. Claims with no returned verdict default
    to 'confirmed' (the deterministic gates already cleared them).
    """
    if not surviving:
        return [], "end_turn"

    system = [
        {"type": "text", "text": REVIEW_SYSTEM},
        {"type": "text", "text": catalog_text,
         "cache_control": {"type": "ephemeral"}},
    ]
    user = ("Review these claims. Return a 'verdicts' array, one per claim, in "
            "any order but keyed by index.\n\nCLAIMS:\n" + _payload(surviving, corpus))

    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _review_schema()}},
    )
    usage.add(resp.usage)
    stop = resp.stop_reason
    if stop == "refusal":
        return [], stop
    if stop == "max_tokens":
        raise RuntimeError("REVIEW truncated (max_tokens); raise cap or split")

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"verdicts": []}
    by_index = {v.get("index"): v for v in data.get("verdicts", []) if isinstance(v, dict)}

    verdicts: list[Verdict] = []
    for index, _mapped, _val in surviving:
        v = by_index.get(index)
        if v is None:
            verdicts.append(Verdict(index=index, verdict="confirmed",
                                    corrected_field=None, corrected_value=None,
                                    reason="no reviewer verdict; deterministic gates passed"))
            continue
        verdicts.append(Verdict(
            index=index,
            verdict=v.get("verdict", "confirmed"),
            corrected_field=v.get("corrected_field") or None,
            corrected_value=v.get("corrected_value") or None,
            reason=v.get("reason", ""),
            raw=v,
        ))
    return verdicts, stop
