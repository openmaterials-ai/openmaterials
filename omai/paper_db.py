"""The local paper database: Giuseppe's advanced bibliography.

The split (2026-07-11, Giuseppe): the map + curated instances + index/papers/
are the versioned PUBLIC record; the PDFs (papers_local/), the full parser
proposals (proposals/), and this database are the LOCAL bibliography, richer
than what is published and re-derivable at any time. This module is the
committed code that maintains the gitignored data.

One entry per paper slug, merged from three sources:

  * papers_local/<slug>.pdf        the document (sha256, pages)
  * papers_local/meta.json         bibliographic sidecar written at download
                                   time: slug -> {title, authors, arxiv,
                                   category}, category one of
                                   barbalinardo / donadio / experimental /
                                   reference
  * proposals/<slug>.json          the parser output (counts, cost,
                                   map_version parsed against, ensemble)
  * index/papers/<slug>.json       COMMITTED apply record, if any values
                                   entered the public map

Status ladder: pdf-only -> parsed -> applied. "candidates" counts the claims
that clear the strict apply bar (own_result, survives validation, review
confirmed/corrected, kind=value); the reviewer decides what actually lands.

CLI:  python -m omai.paper_db            print the table, rebuild db.json
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = _REPO / "papers_local"
PROPOSALS_DIR = _REPO / "proposals"
APPLIED_DIR = _REPO / "index" / "papers"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pdf_pages(path: Path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def strict_candidates(proposal: dict) -> int:
    """Claims clearing the strict apply bar. The bar (2026-07-12): the
    parser's own result (not a citation), survives kernel validation, review
    verdict confirmed/corrected, and classified a value (not a run
    condition). Support is reviewer evidence, never a filter here."""
    n = 0
    for c in proposal.get("claims") or []:
        if (
            c.get("node_id")
            and c.get("provenance") == "own_result"
            and (c.get("validation") or {}).get("survives")
            and (c.get("review") or {}).get("verdict") in ("confirmed", "corrected")
            and c.get("kind", "value") == "value"
        ):
            n += 1
    return n


def build_db(papers_dir: Path | None = None, proposals_dir: Path | None = None,
             applied_dir: Path | None = None) -> list[dict]:
    papers_dir = Path(papers_dir) if papers_dir else PAPERS_DIR
    proposals_dir = Path(proposals_dir) if proposals_dir else PROPOSALS_DIR
    applied_dir = Path(applied_dir) if applied_dir else APPLIED_DIR

    meta_path = papers_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    slugs: set[str] = set()
    slugs.update(p.stem for p in papers_dir.glob("*.pdf"))
    slugs.update(p.stem for p in proposals_dir.glob("*.json")) if proposals_dir.exists() else None
    slugs.update(p.stem for p in applied_dir.glob("*.json")) if applied_dir.exists() else None

    entries = []
    for slug in sorted(slugs):
        entry: dict = {"slug": slug, "status": "pdf-only"}
        entry.update(meta.get(slug, {}))

        pdf = papers_dir / f"{slug}.pdf"
        if pdf.exists():
            entry["pdf"] = {"sha256": _sha256(pdf), "pages": _pdf_pages(pdf)}

        prop = proposals_dir / f"{slug}.json"
        if prop.exists():
            p = json.loads(prop.read_text())
            claims = p.get("claims") or []
            conditions = sum(1 for c in claims if c.get("kind") == "condition")
            entry["parsed"] = {
                "detected": len(claims),
                "mapped": sum(1 for c in claims if c.get("node_id")),
                "conditions": conditions,
                "candidates": strict_candidates(p),
                "map_version": (p.get("map_version") or "")[:12],
                "cost_usd": p.get("cost_estimate_usd"),
            }
            entry["status"] = "parsed"

        applied = applied_dir / f"{slug}.json"
        if applied.exists():
            a = json.loads(applied.read_text())
            entry["applied"] = {
                "values": len(a.get("values") or []),
                "map_version": (a.get("map_version") or "")[:12],
                "date": (a.get("parsed") or {}).get("date"),
            }
            entry["status"] = "applied"

        entries.append(entry)
    return entries


def write_db(entries: list[dict], papers_dir: Path | None = None) -> Path:
    papers_dir = Path(papers_dir) if papers_dir else PAPERS_DIR
    papers_dir.mkdir(parents=True, exist_ok=True)
    out = papers_dir / "db.json"
    out.write_text(json.dumps(entries, indent=1, sort_keys=True))
    return out


def render_table(entries: list[dict]) -> str:
    rows = [f"{'slug':38} {'cat':13} {'status':8} {'det':>4} {'cand':>4} {'appl':>4}  title"]
    for e in entries:
        p, a = e.get("parsed") or {}, e.get("applied") or {}
        rows.append(
            f"{e['slug'][:38]:38} {str(e.get('category', '?'))[:13]:13} "
            f"{e['status']:8} {str(p.get('detected', '')):>4} "
            f"{str(p.get('candidates', '')):>4} {str(a.get('values', '')):>4}  "
            f"{str(e.get('title', ''))[:48]}"
        )
    return "\n".join(rows)

if __name__ == "__main__":  # pragma: no cover - the CLI shell
    entries = build_db()
    path = write_db(entries)
    print(render_table(entries))
    print(f"\n{len(entries)} papers -> {path}")
