"""OpenMaterials paper parser (P1): PDF -> gated evidence proposal.

Six stages: INGEST -> DETECT (API, citations) -> MAP (API, structured outputs) ->
VALIDATE (deterministic, kernel-powered) -> REVIEW (API, adversarial) -> PROPOSE.
The default emits a proposal file; --apply (with human confirm) writes instances.

The pipeline never prints or logs the API key. run_pipeline is importable for the
golden eval; the CLI lives in __main__.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from . import catalog as _catalog
from . import detect as _detect
from . import ingest as _ingest
from . import map_nodes as _map
from . import propose as _propose
from . import review as _review
from . import validate as _validate

__all__ = ["run_pipeline", "PipelineResult"]


@dataclass
class PipelineResult:
    """The full outcome of a run: the proposal plus per-stage diagnostics."""
    proposal: dict
    proposal_path: Path | None
    usage: _detect.Usage
    detected: list
    mapped: list
    validations: list
    verdicts: list
    stage_kills: dict = field(default_factory=dict)
    cache_read_input_tokens: int = 0


def _make_client():
    """Construct the SDK client after ensuring a key is loaded from .env.

    Raises a clear, key-free error if no key is available.
    """
    from .env import has_key, load_env

    load_env()
    if not has_key():
        raise RuntimeError(
            "No ANTHROPIC_API_KEY: set it in the environment or the repo-root .env")
    import anthropic

    return anthropic.Anthropic()


def default_map_version() -> str | None:
    """The live published map version (docs/data/version.json), the same
    artifact the node catalog is built from. A proposal must never ship with
    map_version None while its catalog fingerprint is set; this is the
    fallback when the caller does not pin one explicitly."""
    vfile = (Path(__file__).resolve().parents[1] / ".." / "docs" / "data" / "version.json").resolve()
    if not vfile.exists():
        return None
    try:
        return json.loads(vfile.read_text()).get("version")
    except Exception:
        return None


def run_pipeline(pdf_path: str | Path, *, client=None, map_version: str | None = None,
                 proposals_dir: Path | None = None, write: bool = True,
                 instances_dir: Path | None = None,
                 detect_passes: int = 3) -> PipelineResult:
    """Run the six-stage pipeline on one PDF and return the proposal + diagnostics.

    `client` may be injected (tests, custom config); otherwise a real client is
    built from the env/.env key. `write` controls whether the proposal file is
    emitted. `detect_passes` sets the ensemble size for DETECT (default 3; the
    passes are unioned before mapping, see detect.detect_ensemble). This function
    NEVER applies (no instance writes); that is the CLI's --apply path.
    """
    import anthropic

    if client is None:
        client = _make_client()

    # The proposal's provenance pin: which published map this parse ran
    # against. Callers may override; the default is the live version.json.
    if map_version is None:
        map_version = default_map_version()

    # INGEST
    ingested = _ingest.read_pdf(pdf_path)

    # Catalog (cached prompt prefix) + deterministic lookups
    rows = _catalog.build_node_catalog()
    catalog_text = _catalog.render_catalog(rows)
    catalog_by_id = {r["id"]: r for r in rows}
    fingerprint = _catalog.catalog_fingerprint(catalog_text)
    name_to_uid = _validate.build_name_to_uid()
    instance_index = _validate.load_instance_index(instances_dir)

    usage = _detect.Usage()
    detect_stop = map_stop = review_stop = "end_turn"
    cache_read = 0

    # DETECT (ensemble: N independent passes, unioned)
    detected, detect_stop, detect_info = _detect.detect_ensemble(
        client, ingested, usage, passes=detect_passes)

    # MAP (pass 2)
    mapped, map_stop, cache_info = _map.map_claims(client, detected, catalog_text, usage)
    # Total cache reads: the ensemble's cached PDF-document reads (passes 2+) plus
    # the map catalog-prefix read.
    cache_read = (detect_info.get("cache_read_input_tokens", 0)
                  + cache_info.get("cache_read_input_tokens", 0))

    # VALIDATE (deterministic)
    validations = []
    for m in mapped:
        d = m.detected
        v = _validate.validate_claim(
            node_id=m.node_id, printed_unit=d.unit, value=_to_float(d.value_text),
            cited_text=d.cited_text, material=m.material, corpus_text=ingested.full_text,
            name_to_uid=name_to_uid, catalog_by_id=catalog_by_id,
            instance_index=instance_index)
        validations.append(v)

    # REVIEW (pass 3): only claims that survived deterministic validation
    surviving = [(i, mapped[i], validations[i]) for i in range(len(mapped))
                 if validations[i].survives]
    verdicts, review_stop = _review.review(client, surviving, catalog_text,
                                           ingested.full_text, usage)
    verdicts_by_index = {v.index: v for v in verdicts}

    # Stage kill accounting
    stage_kills = _stage_kills(mapped, validations, verdicts_by_index)

    proposal = _propose.build_proposal(
        paper_slug=_propose.slugify(Path(pdf_path).stem),
        map_version=map_version, mapped=mapped, validations=validations,
        verdicts_by_index=verdicts_by_index, usage=usage,
        catalog_fingerprint=fingerprint, detect_stop=detect_stop,
        map_stop=map_stop, review_stop=review_stop, detect_info=detect_info,
        catalog_by_id=catalog_by_id)

    proposal_path = _propose.write_proposal(proposal, proposals_dir) if write else None

    return PipelineResult(
        proposal=proposal, proposal_path=proposal_path, usage=usage,
        detected=detected, mapped=mapped, validations=validations,
        verdicts=verdicts, stage_kills=stage_kills, cache_read_input_tokens=cache_read)


def _to_float(value_text: str):
    """Parse a printed value string to float, or None if it is not numeric."""
    try:
        return float(str(value_text).strip())
    except (TypeError, ValueError):
        return None


def _stage_kills(mapped, validations, verdicts_by_index) -> dict:
    """Count kills per pipeline stage for the run report."""
    unmapped = sum(1 for m in mapped if m.node_id is None)
    quote_killed = sum(1 for v in validations if "unverified_quote" in v.kills)
    unit_killed = sum(1 for v in validations if "unit_dimension_mismatch" in v.kills)
    value_killed = sum(1 for v in validations if "nonfinite_value" in v.kills)
    review_killed = sum(1 for v in verdicts_by_index.values() if v.verdict == "killed")
    review_corrected = sum(1 for v in verdicts_by_index.values() if v.verdict == "corrected")
    duplicates = sum(1 for v in validations if v.duplicate is not None)
    return {
        "detected": len(mapped),
        "unmapped": unmapped,
        "quote_killed": quote_killed,
        "unit_killed": unit_killed,
        "value_killed": value_killed,
        "survived_validation": sum(1 for v in validations if v.survives),
        "duplicates_flagged": duplicates,
        "review_killed": review_killed,
        "review_corrected": review_corrected,
    }
