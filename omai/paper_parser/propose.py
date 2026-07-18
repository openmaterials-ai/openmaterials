"""PROPOSE / APPLY.

Default: assemble a proposal dict (all claims + every stage's record) and write
proposals/<paper-slug>.json. NO key material appears anywhere in the output.

--apply (only after human review, guarded by --yes at the CLI): write instances
via the existing record_instance bridge and an index/papers entry. P1's golden
eval NEVER applies; the apply path is here for P2 completeness but is not
exercised by the offline tests or the golden run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def slugify(text: str) -> str:
    """Lowercase, non-alphanumerics to single hyphens, trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _collapse_same_finding(claims_out: list[dict]) -> list[dict]:
    """Collapse SURVIVING duplicate findings within one proposal.

    The detect-stage union merges only same-page / overlapping-quote pairs,
    so the same finding stated twice in a paper (abstract and body, e.g. the
    CsPbBr3 340 K transition in the kALDo 2.0 parse) survives as two claims.
    Same (node_id, material, normalized value, kind) among surviving,
    review-confirmed claims is one finding: keep the higher-support claim,
    record merged_from with the other's index, take the max support. Distinct
    values on the same node/material (118 vs 123 W/mK) are never touched.
    """
    def _norm_val(t):
        try:
            return float(str(t).replace(",", ""))
        except (TypeError, ValueError):
            return str(t)

    def _surviving(c):
        return (c.get("node_id")
                and (c.get("validation") or {}).get("survives")
                and (c.get("review") or {}).get("verdict") in ("confirmed", "corrected"))

    best: dict = {}
    drop = set()
    for c in claims_out:
        if not _surviving(c):
            continue
        key = (c["node_id"], str(c.get("material") or "").strip().lower(),
               _norm_val(c.get("value_text")), c.get("kind"))
        prev = best.get(key)
        if prev is None:
            best[key] = c
            continue
        keep, lose = (prev, c) if (prev.get("support") or 0) >= (c.get("support") or 0) else (c, prev)
        keep["support"] = max(prev.get("support") or 0, c.get("support") or 0)
        keep.setdefault("merged_from", []).append(lose["index"])
        drop.add(lose["index"])
        best[key] = keep
    return [c for c in claims_out if c["index"] not in drop]


def build_proposal(*, paper_slug: str, map_version: str | None, mapped, validations,
                   verdicts_by_index: dict, usage, catalog_fingerprint: str,
                   detect_stop: str, map_stop: str, review_stop: str,
                   detect_info: dict | None = None,
                   catalog_by_id: dict | None = None) -> dict:
    """Assemble the full proposal record.

    `mapped` and `validations` are index-aligned lists. Each claim's entry carries
    the detected fields, the node decision, the deterministic verdict (with the
    surviving flag, duplicate flag, and any kills), the adversarial verdict, and
    a `support` count (how many ensemble passes found the finding). The
    unmappable/new-node feed is collected separately for the P-next node work.
    `detect_info` (from detect.detect_ensemble) records the ensemble pass count
    and per-pass claim counts in the run metadata; None defaults to a single pass.
    """
    from .map_nodes import node_kind

    catalog_by_id = catalog_by_id or {}
    claims_out = []
    new_node_feed = []
    for i, (m, v) in enumerate(zip(mapped, validations)):
        d = m.detected
        verdict = verdicts_by_index.get(i)
        # P2.1: a claim on a source / parameter node is CONTEXT (a run condition),
        # not evidence. It survives into the proposal but is excluded from
        # instance minting at apply time (see apply_proposal).
        kind = node_kind(m.node_id, catalog_by_id)
        entry = {
            "index": i,
            "quantity": d.quantity,
            "symbol": d.symbol,
            "value_text": d.value_text,
            "unit": d.unit,
            "material": m.material,
            "conditions": m.conditions,
            "provenance": d.provenance,
            "support": d.support,
            "quote": d.cited_text,
            "pages": d.pages,
            "node_id": m.node_id,
            "node_uid": v.node_uid,
            "kind": kind,
            "unit_declaration": m.unit_declaration,
            "unmappable_reason": m.unmappable_reason,
            "validation": {
                "node_ok": v.node_ok,
                "quote_ok": v.quote_ok,
                "value_ok": v.value_ok,
                "unit": v.unit,
                "survives": v.survives,
                "kills": v.kills,
                "duplicate": v.duplicate,
            },
            "review": None if verdict is None else {
                "verdict": verdict.verdict,
                "corrected_field": verdict.corrected_field,
                "corrected_value": verdict.corrected_value,
                "reason": verdict.reason,
            },
        }
        claims_out.append(entry)
        if m.node_id is None and m.proposed_quantity:
            new_node_feed.append({
                "quantity": d.quantity,
                "proposed_quantity": m.proposed_quantity,
                "reason": m.unmappable_reason,
                "value_text": d.value_text,
                "unit": d.unit,
                "material": m.material,
            })

    claims_out = _collapse_same_finding(claims_out)

    # Separated counts (spec section 6): value targets vs. input conditions.
    # A surviving, non-duplicate, non-killed VALUE claim is what apply would
    # mint; conditions are context and never minted.
    value_claims = sum(1 for c in claims_out if c["kind"] == "value")
    condition_claims = sum(1 for c in claims_out if c["kind"] == "condition")

    info = detect_info or {}
    return {
        "paper_slug": paper_slug,
        "map_version": map_version,
        "catalog_fingerprint": catalog_fingerprint,
        "counts": {
            "claims_total": len(claims_out),
            "value_claims": value_claims,
            "condition_claims": condition_claims,
        },
        "stages": {
            "detect_stop_reason": detect_stop,
            "map_stop_reason": map_stop,
            "review_stop_reason": review_stop,
        },
        "ensemble": {
            "detect_passes": info.get("passes", 1),
            "per_pass_claim_counts": info.get("per_pass_claim_counts", []),
            "detect_stop_reasons": info.get("stop_reasons", []),
            # oversized/dense documents detect on page-range parts; the part
            # count and the adaptive-chunking flag are provenance worth keeping
            "document_parts": info.get("document_parts", 1),
            "chunked_after_truncation": info.get("chunked_after_truncation", False),
        },
        "usage": usage.as_dict(),
        "cost_estimate_usd": usage.cost_estimate_usd(),
        "claims": claims_out,
        "new_node_feed": new_node_feed,
    }


def write_proposal(proposal: dict, proposals_dir: Path | None = None) -> Path:
    """Write the proposal to proposals/<slug>.json (dir is gitignored)."""
    proposals_dir = proposals_dir or (_REPO_ROOT / "proposals")
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"{proposal['paper_slug']}.json"
    path.write_text(json.dumps(proposal, indent=2))
    return path


def _claim_lineage(claim: dict, slug: str) -> dict | None:
    """The minimal LINEAGE one surviving value claim mints, or None.

    Exactly the shape record_instance writes inside ``lineage`` (node, material,
    conditions, values{value, units}, plus the identity-bearing scheme:ref
    source), so an envelope member's id equals the id the instance minted at
    apply time would carry: sharing before applying and applying then sharing
    agree on identity. Returns None for a claim the apply bar excludes (a
    condition claim, a killed or duplicate one, an unmappable node, a
    non-numeric value): the envelope carries what apply would mint, no more.
    """
    v = claim.get("validation") or {}
    review = claim.get("review") or {}
    if claim.get("kind") == "condition":
        return None
    if not v.get("survives") or v.get("duplicate") is not None:
        return None
    if review.get("verdict") == "killed":
        return None
    if claim.get("node_id") is None:
        return None
    try:
        value = float(claim["value_text"])
    except (TypeError, ValueError):
        return None
    return {"node": claim["node_id"], "material": claim.get("material"),
            "conditions": claim.get("conditions") or {},
            "values": {"value": value, "units": claim.get("unit") or ""},
            "source": f"paper:{slug}"}


def build_envelope_from_proposal(proposal: dict, *, doc_meta: dict | None = None):
    """The proposal as a SHARE ENVELOPE: one link for the whole paper.

    ``doc`` is the shared document context: the paper's source ref
    (``paper:<slug>``, the same ref apply writes on every instance) plus any
    bibliographic metadata the caller supplies (``doc_meta``: title, authors,
    year, journal; the proposal itself carries only the slug). ``lineages`` is
    one minimal record per claim clearing the apply bar, each identified by its
    own lineage hash exactly as record_instance would mint it. Returns None
    when no claim clears the bar (an envelope needs at least one lineage).
    Read-only over the proposal: the parser's gates are untouched.
    """
    from omai.lineages import envelope, lineage_id

    slug = proposal["paper_slug"]
    members = []
    for c in proposal.get("claims") or []:
        lineage = _claim_lineage(c, slug)
        if lineage is None:
            continue
        members.append({"id": lineage_id(lineage), "lineage": lineage})
    if not members:
        return None
    doc = {"source": f"paper:{slug}"}
    for key in ("title", "authors", "year", "journal"):
        if doc_meta and doc_meta.get(key) is not None:
            doc[key] = doc_meta[key]
    return envelope(members, doc=doc)


def proposal_envelope_fragment(proposal: dict, *,
                               doc_meta: dict | None = None) -> str | None:
    """The shareable ``#x=`` fragment of the proposal's envelope, or None when
    no claim clears the apply bar. The CLI prints this; opening
    ``play/#/play?tab=lineage&x=<fragment>`` renders the paper view."""
    from omai.lineages import envelope_to_fragment

    env = build_envelope_from_proposal(proposal, doc_meta=doc_meta)
    return None if env is None else envelope_to_fragment(env)


def apply_proposal(proposal: dict, *, source_kind: str = "measurement",
                   instances_dir: Path | None = None) -> list[Path]:
    """Write instances for every surviving, non-duplicate, review-confirmed claim.

    Uses the existing record_instance bridge. source.ref is 'paper:<slug>' and
    the quote + page go in source.detail. NOT called by P1's golden eval; guarded
    at the CLI behind --apply --yes.
    """
    from omai.map_data import _domains, record_instance

    domains = _domains()
    written: list[Path] = []
    slug = proposal["paper_slug"]
    for c in proposal["claims"]:
        v = c["validation"]
        review = c.get("review") or {}
        # P2.1: a condition claim (a source / parameter node) is context, never
        # a minted instance. Excluded here regardless of survival.
        if c.get("kind") == "condition":
            continue
        if not v["survives"] or v["duplicate"] is not None:
            continue
        if review.get("verdict") == "killed":
            continue
        node_id = c["node_id"]
        if node_id is None:
            continue
        try:
            value = float(c["value_text"])
        except (TypeError, ValueError):
            continue
        detail = (f"quote: {c['quote']!r}; pages: {c['pages']}; "
                  f"unit_declaration: {c['unit_declaration']}")
        path = record_instance(
            domains=domains,
            variable=node_id,
            material=c["material"],
            value=value,
            units=c["unit"] or "",
            source_kind=source_kind,
            source_ref=f"paper:{slug}",
            conditions=c["conditions"],
            detail=detail,
            instances_dir=instances_dir,
        )
        written.append(path)
    return written
