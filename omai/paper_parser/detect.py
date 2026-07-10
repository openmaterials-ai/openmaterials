"""DETECT (API pass 1): enumerate every reported physical value with a verbatim,
page-located citation.

Uses claude-opus-4-8 with the PDF as a document content block (citations
enabled) placed BEFORE the text prompt. Citations split the response into
multiple text blocks; cited blocks carry a citations array whose entries have
cited_text and a page_location (1-indexed). One claim per sentence so citations
attach cleanly.

Citations are INCOMPATIBLE with structured outputs (the API returns 400), so
this pass returns free-form JSON-in-text that we parse leniently, and the MAP
pass (map_nodes.py) applies the schema.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Requires anthropic >= 0.116.0 (messages structured outputs via output_config,
# PDF document blocks with citations, prompt caching). Pinned here as the tested
# floor; install into the miniconda base env if absent.
MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000


# --------------------------------------------------------------------------
# Usage tracking (key-free)
# --------------------------------------------------------------------------
@dataclass
class Usage:
    """Cumulative token usage across a run. No key material ever stored."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    calls: int = 0

    def add(self, usage) -> None:
        """Accumulate one response.usage (SDK object or dict)."""
        def g(name):
            if isinstance(usage, dict):
                return usage.get(name) or 0
            return getattr(usage, name, 0) or 0
        self.input_tokens += g("input_tokens")
        self.output_tokens += g("output_tokens")
        self.cache_creation_input_tokens += g("cache_creation_input_tokens")
        self.cache_read_input_tokens += g("cache_read_input_tokens")
        self.calls += 1

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "calls": self.calls,
        }

    def cost_estimate_usd(self) -> float:
        """Rough claude-opus-4-8 spend: $5/1M input, $25/1M output.

        Cache reads bill ~0.1x and writes ~1.25x; approximated here for a
        ballpark run-cost figure only.
        """
        inp = self.input_tokens * 5.0 / 1e6
        out = self.output_tokens * 25.0 / 1e6
        cw = self.cache_creation_input_tokens * 5.0 * 1.25 / 1e6
        cr = self.cache_read_input_tokens * 5.0 * 0.1 / 1e6
        return round(inp + out + cw + cr, 4)


@dataclass
class DetectedClaim:
    """One reported value with its verbatim citation and page(s)."""
    quantity: str
    symbol: str | None
    value_text: str
    unit: str | None
    material: str | None
    conditions: dict
    provenance: str  # own_result | cited_from_reference | definition_or_example
    cited_text: str
    pages: list[int]
    raw: dict = field(default_factory=dict)


DETECT_PROMPT = """You are extracting reported physical property values from a scientific paper (attached PDF).

Enumerate EVERY reported physical value in the document: quantities with a numeric value and (usually) a unit. Include values in prose, tables, figure captions, and embedded data/JSON snippets.

For EACH value, emit ONE JSON object. Write your answer as a single JSON array of these objects, and nothing else outside the array. Each object has:
- "quantity": the quantity name exactly as the paper states it (e.g. "thermal conductivity", "activation energy").
- "symbol": the symbol if one is printed (e.g. "kappa", "E_a"), else null.
- "value": the numeric value as a STRING, exactly as printed (keep the paper's digits, sign, and exponent form, e.g. "19.46", "-1.06e-05").
- "unit": the unit as printed (e.g. "W/(m K)", "mS/cm", "eV"), else null.
- "material": the material or system the value is for (e.g. "Si", "LGPS", "Cu Sigma5 [001] tilt"), else null.
- "conditions": an object of stated conditions (temperature, method, mesh, potential, ...), or {} if none.
- "provenance": one of "own_result" (a result the paper itself computed/measured), "cited_from_reference" (a value quoted from another work), "definition_or_example" (a value used only to define or illustrate, not a reported measurement).
- "quote": a SHORT verbatim snippet copied EXACTLY from the document text that contains this value (10-25 words, including the number and unit exactly as printed). Copy the characters as they appear; do not paraphrase, reformat, or correct them. This snippet must be findable by exact search in the document.
- "page": the 1-indexed page number where the value appears (an integer), or null if unknown.

Do not invent values: only report numbers that literally appear in the document. If a number is a coordinate, an equation index, a reference number, an author count, a year, or a page number, do NOT report it as a physical value. The "quote" must be a real substring of the document; if you cannot copy an exact snippet, do not report the claim.

Return only the JSON array."""


def _extract_text_and_citations(content_blocks) -> tuple[str, list[dict]]:
    """Concatenate the text of all text blocks and collect their citations.

    Each citation entry becomes {cited_text, pages:[...]} using page_location
    (start/end page numbers, 1-indexed). Non-page locations are kept with an
    empty page list.
    """
    text_parts: list[str] = []
    citations: list[dict] = []
    for block in content_blocks:
        btype = block.type if hasattr(block, "type") else block.get("type")
        if btype != "text":
            continue
        text = block.text if hasattr(block, "text") else block.get("text", "")
        text_parts.append(text or "")
        cites = getattr(block, "citations", None)
        if cites is None and isinstance(block, dict):
            cites = block.get("citations")
        for c in cites or []:
            cited_text = getattr(c, "cited_text", None)
            if cited_text is None and isinstance(c, dict):
                cited_text = c.get("cited_text")
            pages: list[int] = []
            loc_type = getattr(c, "type", None) or (c.get("type") if isinstance(c, dict) else None)
            start = getattr(c, "start_page_number", None)
            end = getattr(c, "end_page_number", None)
            if isinstance(c, dict):
                start = c.get("start_page_number", start)
                end = c.get("end_page_number", end)
            if start is not None:
                lo = int(start)
                hi = int(end) if end is not None else lo
                pages = list(range(lo, hi + 1))
            if cited_text:
                citations.append({"cited_text": cited_text, "pages": pages,
                                  "loc_type": loc_type})
    return "".join(text_parts), citations


def _parse_json_array(text: str) -> list[dict]:
    """Leniently parse the first JSON array from a (possibly fenced) response.

    Strips markdown code fences and grabs the outermost [...] span. Returns [] if
    no array parses (a malformed pass is reported upstream, not crashed on).
    """
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start = t.find("[")
    end = t.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(t[start:end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _best_citation_for(value_text: str, quantity: str, citations: list[dict]) -> dict:
    """Pick the citation most likely to contain this claim's value.

    Prefers a citation whose cited_text contains the printed value string; falls
    back to one containing the quantity name; else the first citation; else an
    empty quote (which the deterministic quote gate will kill).
    """
    v = (value_text or "").strip()
    if v:
        for c in citations:
            if v in c["cited_text"]:
                return c
    q = (quantity or "").strip().lower()
    if q:
        for c in citations:
            if q in c["cited_text"].lower():
                return c
    return citations[0] if citations else {"cited_text": "", "pages": []}


def detect(client, ingested, usage: Usage) -> tuple[list[DetectedClaim], str]:
    """Run pass 1. Returns (claims, stop_reason).

    Raises on truncation (stop_reason 'max_tokens') so the caller can retry with
    a higher cap or split; reports a refusal as an empty result with the
    stop_reason rather than crashing.
    """
    document_block = {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf",
                   "data": ingested.pdf_b64},
        "citations": {"enabled": True},
    }
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": [
            document_block,
            {"type": "text", "text": DETECT_PROMPT},
        ]}],
    )
    usage.add(resp.usage)
    stop = resp.stop_reason
    if stop == "refusal":
        return [], stop
    if stop == "max_tokens":
        raise RuntimeError("DETECT truncated (max_tokens); raise cap or split the PDF")

    text, citations = _extract_text_and_citations(resp.content)
    rows = _parse_json_array(text)
    claims: list[DetectedClaim] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        value_text = str(r.get("value", "")).strip()
        # Primary quote: the model's own verbatim "quote" field. Citation blocks
        # (when the model emits prose) are a secondary source and confirm the
        # page. The deterministic quote gate verifies whichever quote we carry
        # against the extracted corpus, so a paraphrased/invented quote dies.
        model_quote = str(r.get("quote", "") or "").strip()
        cite = _best_citation_for(value_text, str(r.get("quantity", "")), citations)
        cited_text = model_quote or cite.get("cited_text", "")
        pages = cite.get("pages", [])
        page = r.get("page")
        if not pages and isinstance(page, int):
            pages = [page]
        claims.append(DetectedClaim(
            quantity=str(r.get("quantity", "")),
            symbol=r.get("symbol"),
            value_text=value_text,
            unit=r.get("unit"),
            material=r.get("material"),
            conditions=r.get("conditions") or {},
            provenance=str(r.get("provenance", "own_result")),
            cited_text=cited_text,
            pages=pages,
            raw=r,
        ))
    return claims, stop
