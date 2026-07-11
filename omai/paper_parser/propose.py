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


def build_proposal(*, paper_slug: str, map_version: str | None, mapped, validations,
                   verdicts_by_index: dict, usage, catalog_fingerprint: str,
                   detect_stop: str, map_stop: str, review_stop: str,
                   detect_info: dict | None = None) -> dict:
    """Assemble the full proposal record.

    `mapped` and `validations` are index-aligned lists. Each claim's entry carries
    the detected fields, the node decision, the deterministic verdict (with the
    surviving flag, duplicate flag, and any kills), the adversarial verdict, and
    a `support` count (how many ensemble passes found the finding). The
    unmappable/new-node feed is collected separately for the P-next node work.
    `detect_info` (from detect.detect_ensemble) records the ensemble pass count
    and per-pass claim counts in the run metadata; None defaults to a single pass.
    """
    claims_out = []
    new_node_feed = []
    for i, (m, v) in enumerate(zip(mapped, validations)):
        d = m.detected
        verdict = verdicts_by_index.get(i)
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

    info = detect_info or {}
    return {
        "paper_slug": paper_slug,
        "map_version": map_version,
        "catalog_fingerprint": catalog_fingerprint,
        "stages": {
            "detect_stop_reason": detect_stop,
            "map_stop_reason": map_stop,
            "review_stop_reason": review_stop,
        },
        "ensemble": {
            "detect_passes": info.get("passes", 1),
            "per_pass_claim_counts": info.get("per_pass_claim_counts", []),
            "detect_stop_reasons": info.get("stop_reasons", []),
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
