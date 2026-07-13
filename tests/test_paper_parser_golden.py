"""Golden eval: run the REAL pipeline live against the FROZEN golden copy of
the openmaterials paper (tests/golden/openmaterials-golden.pdf) and
score it against the honestly-built expected set.

Skipped without an API key so the suite is green with and without a key. When a
key is present, this makes a handful of claude-opus-4-8 calls (that is what the
key is for). Acceptance (from the spec):
  - recall >= 0.8 on the expected set (expected values detected AND mapped to the
    right node),
  - zero hallucinated quotes surviving validation,
  - every recovered known value flagged DUPLICATE by the deterministic stage 4.

The scoring helpers are pure and importable; the live test that drives the API
is guarded by the skip.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from omai.paper_parser import run_pipeline
from omai.paper_parser.env import has_key, load_env

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PDF = _REPO_ROOT / "tests" / "golden" / "openmaterials-golden.pdf"
# Frozen 2026-07-12 (104-node era; all 8 expected values verified present).
# The living docs/openmaterials.pdf keeps evolving with the map counts, so
# pinning the eval to it made the golden silently drift; the frozen copy
# makes the eval reproducible forever.
# 2026-07-13: the two measurement entries (Si 156, Ge 60.2) re-pointed to the
# method-neutral ThermalConductivity node, following the 2026-07-12 instance
# migration (a measurement reports the observable, not a solver route); the
# instances they must duplicate now live on that node.
_EXPECTED = _REPO_ROOT / "tests" / "golden" / "openmaterials-expected.json"


def load_expected() -> dict:
    return json.loads(_EXPECTED.read_text())


def _material_key(m: str) -> str:
    # Reuse the pipeline's material normalization so scoring aliases element
    # names (silicon->si) exactly as the dedup gate does.
    from omai.paper_parser.validate import _norm_material
    return _norm_material(m)


def score_run(result, expected: dict) -> dict:
    """Score a PipelineResult against the expected set. Pure function.

    An expected value is 'recovered' when some surviving claim maps to the same
    node id, the same (loose) material key, and an approximately equal value.
    Precision is over surviving, non-unmappable claims: a claim is 'correct' if
    it matches some expected entry OR its quote is verified and its node
    resolves (a real, gated claim even if not in the small expected set).
    """
    surviving = [(m, v) for m, v in zip(result.mapped, result.validations) if v.survives]

    recovered = []
    for exp in expected["expected"]:
        found = None
        for m, v in surviving:
            if m.node_id != exp["node_id"]:
                continue
            if _material_key(m.material) != _material_key(exp["material"]):
                continue
            fv = _to_float(m.detected.value_text)
            if fv is None:
                continue
            if math.isclose(fv, exp["value"], rel_tol=1e-2, abs_tol=1e-6):
                found = (m, v)
                break
        recovered.append({"expected": exp, "recovered": found is not None,
                          "duplicate": bool(found and found[1].duplicate)})

    n_expected = len(expected["expected"])
    n_recovered = sum(1 for r in recovered if r["recovered"])
    recall = n_recovered / n_expected if n_expected else 0.0

    # Every recovered known must be flagged DUPLICATE (already on the map).
    all_recovered_dup = all(r["duplicate"] for r in recovered if r["recovered"])

    # Zero hallucinated quotes surviving: by construction, VALIDATE kills any
    # claim whose quote is not verbatim in the corpus, so no surviving claim can
    # carry an unverified quote. Assert it directly as a proof.
    hallucinated_surviving = sum(1 for _m, v in surviving if not v.quote_ok)

    return {
        "recall": recall,
        "n_expected": n_expected,
        "n_recovered": n_recovered,
        "all_recovered_flagged_duplicate": all_recovered_dup,
        "hallucinated_quotes_surviving": hallucinated_surviving,
        "surviving_total": len(surviving),
        "recovered_detail": recovered,
        "stage_kills": result.stage_kills,
    }


def _to_float(value_text):
    try:
        return float(str(value_text).strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Offline sanity: the expected set is well-formed and only lists present values
# --------------------------------------------------------------------------
def test_expected_set_is_wellformed():
    exp = load_expected()
    assert exp["acceptance"]["recall_min"] == 0.8
    assert len(exp["expected"]) >= 6
    from omai.paper_parser import validate
    name_to_uid = validate.build_name_to_uid()
    for e in exp["expected"]:
        assert e["node_id"] in name_to_uid, e["node_id"]
        assert "value" in e and "value_text" in e


def test_expected_values_are_committed_duplicates():
    """Every expected value must already exist as a committed instance (so the
    DUPLICATE gate can trip). Offline: no API needed."""
    from omai.paper_parser import validate
    exp = load_expected()
    idx = validate.load_instance_index()
    name_to_uid = validate.build_name_to_uid()
    for e in exp["expected"]:
        uid = name_to_uid[e["node_id"]]
        hit = validate.is_duplicate(uid, e["material"], e["value"], idx)
        assert hit is not None, f"{e['node_id']} {e['material']} {e['value']} not committed"


# --------------------------------------------------------------------------
# Live golden run (skipped without a key)
# --------------------------------------------------------------------------
def _key_available() -> bool:
    load_env()
    return has_key()


def _golden_runs() -> int:
    """How many full-pipeline runs the acceptance test performs.

    Defaults to 1 to keep CI cost sane. Set GOLDEN_RUNS=3 (or any N>=1) to enable
    STABILITY mode: the pipeline runs N times and the test requires the MINIMUM
    recall across all runs to clear the bar (proving the ensemble killed the
    run-to-run recall variance, not just that one lucky run passed).
    """
    try:
        n = int(os.environ.get("GOLDEN_RUNS", "1"))
    except ValueError:
        n = 1
    return max(1, n)


@pytest.mark.skipif(not _key_available(), reason="no ANTHROPIC_API_KEY; live golden run skipped")
def test_golden_acceptance(tmp_path):
    expected = load_expected()
    recall_min = expected["acceptance"]["recall_min"]
    runs = _golden_runs()

    recalls: list[float] = []
    for run_i in range(runs):
        result = run_pipeline(_PDF, proposals_dir=tmp_path, write=True)
        scores = score_run(result, expected)

        # Report (visible with -s)
        ensemble = result.proposal.get("ensemble", {})
        print(f"\nGOLDEN SCORES (run {run_i + 1}/{runs}):", json.dumps({
            **{k: scores[k] for k in (
                "recall", "n_expected", "n_recovered",
                "all_recovered_flagged_duplicate",
                "hallucinated_quotes_surviving", "surviving_total", "stage_kills")},
            "ensemble": ensemble,
            "cache_read_input_tokens": result.cache_read_input_tokens,
        }, indent=2))

        # These invariants must hold on EVERY run.
        assert scores["hallucinated_quotes_surviving"] == 0, (
            f"run {run_i + 1}: a hallucinated quote survived validation")
        assert scores["all_recovered_flagged_duplicate"], (
            f"run {run_i + 1}: a recovered known was not flagged DUPLICATE by stage 4")
        recalls.append(scores["recall"])

    # STABILITY: the worst run must still clear the bar.
    min_recall = min(recalls)
    print(f"\nGOLDEN STABILITY: recalls={recalls} min={min_recall:.3f} "
          f"threshold={recall_min}")
    assert min_recall >= recall_min, (
        f"min recall {min_recall:.2f} across {runs} run(s) below {recall_min} "
        f"(recalls={recalls})")
