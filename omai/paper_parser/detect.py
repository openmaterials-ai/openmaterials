"""DETECT (API passes): enumerate every reported physical value with a verbatim,
page-located citation.

Uses claude-opus-4-8 with the PDF as a document content block (citations
enabled) placed FIRST in the user turn (so its tokens cache across passes),
before the text prompt. Citations split the response into multiple text blocks;
cited blocks carry a citations array whose entries have cited_text and a
page_location (1-indexed). One claim per sentence so citations attach cleanly.

Citations are INCOMPATIBLE with structured outputs (the API returns 400), so
this pass returns free-form JSON-in-text that we parse leniently, and the MAP
pass (map_nodes.py) applies the schema.

P2 ENSEMBLE: a single detect pass is unreliable (P1's golden eval saw recall
swing 0.375-0.875 across runs because one pass can miss values). detect_ensemble
runs N independent passes (default 3) with diverse prompts (the shipped sweep,
a table/figure-caption sweep, a running-text/prose sweep), then UNIONS their
claims. Two claims are the same finding if they share a normalized value AND a
compatible quantity name AND (an overlapping quote OR the same page +/-1); the
richer of a merged pair (more conditions, longer quote) is kept, and a `support`
count records how many passes found it. Support is evidence for the reviewer,
never a filter. The document block is identical and FIRST in every pass with
cache_control on it, so passes 2+ read the cached PDF tokens
(usage.cache_read_input_tokens > 0) instead of re-billing them.
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
    """One reported value with its verbatim citation and page(s).

    `support` is the number of independent ensemble passes that found this
    finding (1 for a single-pass run). It is carried through mapping into the
    proposal as evidence for the reviewer; it is NEVER used to filter a claim.
    """
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
    support: int = 1


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


# --------------------------------------------------------------------------
# Ensemble prompt variants (deterministic, no RNG)
# --------------------------------------------------------------------------
# Diversity across passes is what makes the union recover values a single pass
# misses: the three prompts steer attention to different regions of the paper.
# Each variant prepends a short focus directive to the shared DETECT_PROMPT so
# the extraction contract (fields, "quote" gate, no-invention rule) is byte-for-
# byte identical across passes; only the emphasis changes. Written as named
# constants so a test can assert the variants exist and differ.

# Pass 1: the shipped prompt, unchanged. A broad sweep of the whole document.
DETECT_PROMPT_BROAD = DETECT_PROMPT

# Pass 2: tables and figure captions. Papers pack most of their numbers into
# table cells and caption text, which a prose-oriented reader skims past.
_FOCUS_TABLES = (
    "FOCUS FOR THIS PASS: sweep every TABLE and every FIGURE CAPTION in the "
    "document. Go table by table and read each row and column header and each "
    "cell; go caption by caption and read each figure and table caption in "
    "full. Extract every reported physical value that appears in a table cell "
    "or a caption. Still report values you notice elsewhere, but tables and "
    "captions are the priority for this pass.\n\n"
)
DETECT_PROMPT_TABLES = _FOCUS_TABLES + DETECT_PROMPT

# Pass 3: running prose and the abstract. Numbers stated in sentences and in the
# abstract summary are easy to miss when attention is on tabular data.
_FOCUS_PROSE = (
    "FOCUS FOR THIS PASS: sweep the RUNNING TEXT and the ABSTRACT of the "
    "document, sentence by sentence. Extract every reported physical value "
    "stated in prose, including summary numbers in the abstract and values "
    "embedded in data or JSON snippets in the text. Do not spend this pass on "
    "tables; read the paragraphs.\n\n"
)
DETECT_PROMPT_PROSE = _FOCUS_PROSE + DETECT_PROMPT

# The default ensemble prompt sequence, index 0 first. detect_ensemble uses the
# first N of these; a request for more passes than variants cycles the list.
DETECT_PROMPT_VARIANTS = [DETECT_PROMPT_BROAD, DETECT_PROMPT_TABLES, DETECT_PROMPT_PROSE]


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


def _document_block(ingested) -> dict:
    """The PDF document content block, with cache_control so its (large) token
    footprint is written once and read by later passes in the same run.

    Identical bytes across every pass of a run: same base64 data, citations on,
    same cache_control marker. Placed FIRST in the user turn so the cached prefix
    covers the dominant input cost.
    """
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf",
                   "data": ingested.pdf_b64},
        "citations": {"enabled": True},
        "cache_control": {"type": "ephemeral"},
    }


def detect(client, ingested, usage: Usage, *, prompt: str = DETECT_PROMPT,
           ) -> tuple[list[DetectedClaim], str, int]:
    """Run one detect pass. Returns (claims, stop_reason, cache_read_input_tokens).

    Raises on truncation (stop_reason 'max_tokens') so the caller can retry with
    a higher cap or split; reports a refusal as an empty result with the
    stop_reason rather than crashing. `prompt` selects the pass variant; the
    document block is identical and first in every pass so its tokens cache.
    """
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": [
            _document_block(ingested),
            {"type": "text", "text": prompt},
        ]}],
    )
    usage.add(resp.usage)
    cache_read = getattr(resp.usage, "cache_read_input_tokens", 0) or 0
    stop = resp.stop_reason
    if stop == "refusal":
        return [], stop, cache_read
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
            support=1,
        ))
    return claims, stop, cache_read


# --------------------------------------------------------------------------
# Union / merge semantics for the ensemble
# --------------------------------------------------------------------------
def _norm_value(value_text: str) -> str | None:
    """Normalized numeric key for a printed value string, or None if not numeric.

    Two claims share a value if their printed strings parse to the same float
    (so '16.74' and '16.740' unify; '16.74' and '16.735' do not). Non-numeric
    value strings return None and never unify by value.
    """
    try:
        return repr(float(str(value_text).strip()))
    except (TypeError, ValueError):
        return None


def _norm_quantity(quantity: str) -> str:
    """Loose quantity key: lowercase alphanumerics only.

    'Thermal conductivity' and 'thermal_conductivity' collapse to the same key
    so the same finding reported with slightly different quantity wording unifies.
    """
    return re.sub(r"[^a-z0-9]+", "", (quantity or "").lower())


def _quantity_compatible(a: str, b: str) -> bool:
    """True iff two quantity names are compatible (equal, or one contains the
    other after normalization). Empty on either side is treated as compatible so
    a value-and-page match is not blocked by a missing quantity label."""
    na, nb = _norm_quantity(a), _norm_quantity(b)
    if not na or not nb:
        return True
    return na == nb or na in nb or nb in na


def _quotes_overlap(a: str, b: str) -> bool:
    """True iff two quotes overlap: equal, or one normalized quote contains the
    other. Empty quotes never overlap."""
    from .validate import normalize_quote

    na, nb = normalize_quote(a), normalize_quote(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _pages_near(a: list[int], b: list[int]) -> bool:
    """True iff any page in a is within +/-1 of any page in b (same page or
    adjacent). Empty page lists never match."""
    if not a or not b:
        return False
    return any(abs(pa - pb) <= 1 for pa in a for pb in b)


def _same_finding(a: DetectedClaim, b: DetectedClaim) -> bool:
    """Two claims are the same finding iff they share a normalized value AND a
    compatible quantity name AND (an overlapping quote OR a same/adjacent page).

    A shared numeric value is required (None values never unify), so distinct
    numbers are never merged. Quantity compatibility guards against merging two
    different quantities that happen to print the same number. The quote-or-page
    clause ties the two reports to the same location in the document.
    """
    va, vb = _norm_value(a.value_text), _norm_value(b.value_text)
    if va is None or vb is None or va != vb:
        return False
    if not _quantity_compatible(a.quantity, b.quantity):
        return False
    return _quotes_overlap(a.cited_text, b.cited_text) or _pages_near(a.pages, b.pages)


def _richer(a: DetectedClaim, b: DetectedClaim) -> DetectedClaim:
    """Pick the richer of two merged claims: more stated conditions wins; on a
    tie, the longer quote wins; on a further tie, keep the first (a)."""
    na, nb = len(a.conditions or {}), len(b.conditions or {})
    if na != nb:
        return a if na > nb else b
    la, lb = len(a.cited_text or ""), len(b.cited_text or "")
    if la != lb:
        return a if la >= lb else b
    return a


def union_claims(passes: list[list[DetectedClaim]]) -> list[DetectedClaim]:
    """Union the per-pass claim lists into one deduplicated list with support
    counts.

    Iterates passes in order. Each claim is merged into an existing finding when
    _same_finding holds; on merge the richer claim is kept and its support count
    is incremented. Two claims from the SAME pass are never counted twice toward
    support for one finding (a pass contributes at most one to each finding's
    support), so support is a genuine count of independent passes that found it.
    Order is stable: findings appear in first-seen order.
    """
    merged: list[DetectedClaim] = []
    # Track which pass indices already contributed to each merged finding, so a
    # duplicate within one pass does not double-count support.
    contributors: list[set[int]] = []
    for pass_idx, claims in enumerate(passes):
        for c in claims:
            hit = None
            for j, existing in enumerate(merged):
                if _same_finding(existing, c):
                    hit = j
                    break
            if hit is None:
                keep = DetectedClaim(**{**c.__dict__})
                keep.support = 1
                merged.append(keep)
                contributors.append({pass_idx})
                continue
            existing = merged[hit]
            winner = _richer(existing, c)
            new_support = existing.support
            if pass_idx not in contributors[hit]:
                new_support += 1
                contributors[hit].add(pass_idx)
            winner = DetectedClaim(**{**winner.__dict__})
            winner.support = new_support
            merged[hit] = winner
    return merged


def detect_ensemble(client, ingested, usage: Usage, *, passes: int = 3,
                    ) -> tuple[list[DetectedClaim], str, dict]:
    """Run N independent detect passes and union their claims. Returns
    (claims, stop_reason, info).

    Passes run sequentially (the SDK is sync) but are independent API calls, each
    with a diverse prompt from DETECT_PROMPT_VARIANTS (cycled if passes exceeds
    the variant count). The document block is identical and first in every pass,
    so passes after the first read the cached PDF tokens. `info` reports:
      - passes: the number of passes run,
      - per_pass_claim_counts: raw claim count from each pass, in order,
      - cache_read_input_tokens: total cache reads across passes (nonzero proves
        the document block cached on passes 2+),
      - stop_reasons: the per-pass stop reasons.
    The returned stop_reason is 'refusal' only if EVERY pass refused; otherwise
    the first non-refusal stop is reported.
    """
    n = max(1, int(passes))
    per_pass: list[list[DetectedClaim]] = []
    per_pass_counts: list[int] = []
    stop_reasons: list[str] = []
    total_cache_read = 0
    for i in range(n):
        prompt = DETECT_PROMPT_VARIANTS[i % len(DETECT_PROMPT_VARIANTS)]
        claims, stop, cache_read = detect(client, ingested, usage, prompt=prompt)
        per_pass.append(claims)
        per_pass_counts.append(len(claims))
        stop_reasons.append(stop)
        total_cache_read += cache_read

    unioned = union_claims(per_pass)
    non_refusal = next((s for s in stop_reasons if s != "refusal"), None)
    stop = non_refusal if non_refusal is not None else "refusal"
    info = {
        "passes": n,
        "per_pass_claim_counts": per_pass_counts,
        "cache_read_input_tokens": total_cache_read,
        "stop_reasons": stop_reasons,
    }
    return unioned, stop, info
