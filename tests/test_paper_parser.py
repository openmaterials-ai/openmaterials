"""Offline tests for the paper parser: env loader, catalog builder, and all
deterministic validators (quote normalization, unit check, dedup).

None of these call the API; the suite stays green with and without a key.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai.paper_parser import catalog, detect, env, propose, validate
from omai.paper_parser.detect import DetectedClaim, Usage


# --------------------------------------------------------------------------
# env loader + key redaction
# --------------------------------------------------------------------------
def test_load_env_sets_unset_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('ANTHROPIC_API_KEY=sk-test-123\nOTHER=x\n')
    env.load_env(dotenv)
    assert env.get_key() == "sk-test-123"


def test_load_env_does_not_override_existing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=sk-file\n")
    env.load_env(dotenv)
    assert env.get_key() == "sk-real"


def test_load_env_strips_quotes_and_export(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('export ANTHROPIC_API_KEY="sk-quoted"\n# a comment\n\n')
    env.load_env(dotenv)
    assert env.get_key() == "sk-quoted"


def test_load_env_missing_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env.load_env(tmp_path / "nope.env")
    assert env.get_key() is None


def test_redact_key_masks_secret(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-xyz")
    msg = "boom: authentication failed with key sk-secret-xyz in header"
    out = env.redact_key(msg)
    assert "sk-secret-xyz" not in out
    assert "<redacted-api-key>" in out


def test_redact_key_noop_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert env.redact_key("plain text") == "plain text"


# --------------------------------------------------------------------------
# catalog builder
# --------------------------------------------------------------------------
def test_catalog_is_sorted_and_stable():
    rows = catalog.build_node_catalog()
    assert len(rows) == 104
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids)
    # byte-stability: two builds render identically
    assert catalog.render_catalog(rows) == catalog.render_catalog(catalog.build_node_catalog())


def test_catalog_contains_known_nodes():
    ids = catalog.catalog_ids(catalog.build_node_catalog())
    assert "ThermalConductivity[bte_solver=rta]" in ids
    assert "ElectricalConductivity[carrier=ionic]" in ids
    assert "ActivationEnergy" in ids


def test_catalog_render_has_dimensions():
    rendered = catalog.render_catalog(catalog.build_node_catalog())
    assert "thermal_conductivity" in rendered
    assert "electrical_conductivity" in rendered


def test_catalog_fingerprint_deterministic():
    rendered = catalog.render_catalog(catalog.build_node_catalog())
    assert catalog.catalog_fingerprint(rendered) == catalog.catalog_fingerprint(rendered)
    assert len(catalog.catalog_fingerprint(rendered)) == 12


# --------------------------------------------------------------------------
# quote normalization + verification (the hallucination gate)
# --------------------------------------------------------------------------
def test_normalize_collapses_whitespace():
    assert validate.normalize_quote("a  b\n c\t d") == "a b c d"


def test_normalize_joins_hyphenated_linebreak():
    assert "conductivity" in validate.normalize_quote("conduc-\ntivity")


def test_normalize_expands_ligatures():
    assert validate.normalize_quote("eﬃcient") == "efficient"


def test_quote_verified_matches_across_whitespace():
    corpus = "the value 19.46\nW/(m K)  was reported"
    assert validate.quote_verified("value 19.46 W/(m K) was", corpus)


def test_quote_verified_rejects_absent_quote():
    corpus = "the paper reports 19.46 W/(m K)"
    assert not validate.quote_verified("the fabricated value 42.0 eV", corpus)


def test_quote_verified_rejects_empty():
    assert not validate.quote_verified("", "anything at all")


# --------------------------------------------------------------------------
# unit check
# --------------------------------------------------------------------------
def _catalog_by_id():
    return {r["id"]: r for r in catalog.build_node_catalog()}


def test_unit_check_match():
    res = validate.unit_check("W/(m K)", "ThermalConductivity[bte_solver=rta]", _catalog_by_id())
    assert res["ok"] and res["kind"] == "match"


def test_unit_check_mismatch_is_fatal():
    # eV against a thermal-conductivity node -> dimensional mismatch
    res = validate.unit_check("eV", "ThermalConductivity[bte_solver=rta]", _catalog_by_id())
    assert not res["ok"] and res["kind"] == "mismatch"


def test_unit_check_unresolved_is_soft():
    res = validate.unit_check("furlongs/fortnight", "ActivationEnergy", _catalog_by_id())
    assert res["ok"] and res["kind"] == "unresolved"


def test_unit_check_activation_energy_ev():
    res = validate.unit_check("eV", "ActivationEnergy", _catalog_by_id())
    assert res["ok"] and res["kind"] == "match"


# --------------------------------------------------------------------------
# value sanity
# --------------------------------------------------------------------------
def test_value_finite():
    assert validate.value_finite(19.46)
    assert validate.value_finite(0)
    assert not validate.value_finite(float("inf"))
    assert not validate.value_finite(float("nan"))
    assert not validate.value_finite(True)  # bool rejected
    assert not validate.value_finite("19.46")


# --------------------------------------------------------------------------
# dedup against a fixture instance corpus
# --------------------------------------------------------------------------
def _fixture_instances(tmp_path: Path) -> Path:
    d = tmp_path / "instances"
    d.mkdir()
    (d / "si-kappa.json").write_text(json.dumps({
        "variable": "ThermalConductivity[bte_solver=rta]", "material": "Si",
        "conditions": {}, "value": 16.735, "units": "W/(m K)",
        "source": {"kind": "simulation", "ref": "x"},
    }))
    (d / "lgps-sigma.json").write_text(json.dumps({
        "variable": "ElectricalConductivity[carrier=ionic]", "material": "LGPS",
        "conditions": {}, "value": 91.44, "units": "mS/cm",
        "source": {"kind": "simulation", "ref": "y"},
    }))
    return d


def test_dedup_exact_match(tmp_path):
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    uid = name_to_uid["ElectricalConductivity[carrier=ionic]"]
    hit = validate.is_duplicate(uid, "LGPS", 91.44, idx)
    assert hit is not None and hit["file"] == "lgps-sigma.json"


def test_dedup_rounded_value_within_tolerance(tmp_path):
    # a paper's 16.74 quote against a committed 16.735 -> duplicate
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    uid = name_to_uid["ThermalConductivity[bte_solver=rta]"]
    hit = validate.is_duplicate(uid, "Si", 16.74, idx)
    assert hit is not None


def test_dedup_material_key_loose(tmp_path):
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    uid = name_to_uid["ElectricalConductivity[carrier=ionic]"]
    assert validate.is_duplicate(uid, "lgps", 91.44, idx) is not None


def test_dedup_no_match_different_node(tmp_path):
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    uid = name_to_uid["ActivationEnergy"]
    assert validate.is_duplicate(uid, "LGPS", 91.44, idx) is None


def test_dedup_no_match_far_value(tmp_path):
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    uid = name_to_uid["ThermalConductivity[bte_solver=rta]"]
    assert validate.is_duplicate(uid, "Si", 999.0, idx) is None


# --------------------------------------------------------------------------
# validate_claim end-to-end (deterministic, no API)
# --------------------------------------------------------------------------
def test_validate_claim_survives_and_flags_duplicate(tmp_path):
    idx = validate.load_instance_index(_fixture_instances(tmp_path))
    name_to_uid = validate.build_name_to_uid()
    cat = _catalog_by_id()
    corpus = 'The RTA thermal conductivity was "value": 19.46, W/(m K).'
    v = validate.validate_claim(
        node_id="ThermalConductivity[bte_solver=rta]", printed_unit="W/(m K)",
        value=16.735, cited_text='"value": 19.46', material="Si",
        corpus_text=corpus, name_to_uid=name_to_uid, catalog_by_id=cat,
        instance_index=idx)
    assert v.survives
    assert v.duplicate is not None  # matches the fixture 16.735


def test_validate_claim_kills_unverified_quote(tmp_path):
    name_to_uid = validate.build_name_to_uid()
    cat = _catalog_by_id()
    v = validate.validate_claim(
        node_id="ActivationEnergy", printed_unit="eV", value=0.152,
        cited_text="a quote that is nowhere in the document",
        material="LGPS", corpus_text="the document says nothing of the sort",
        name_to_uid=name_to_uid, catalog_by_id=cat, instance_index=[])
    assert not v.survives
    assert "unverified_quote" in v.kills


def test_validate_claim_kills_unknown_node():
    name_to_uid = validate.build_name_to_uid()
    cat = _catalog_by_id()
    v = validate.validate_claim(
        node_id="NotARealNode", printed_unit="eV", value=1.0,
        cited_text="present", material="X", corpus_text="present here",
        name_to_uid=name_to_uid, catalog_by_id=cat, instance_index=[])
    assert not v.survives
    assert any(k.startswith("unmapped_node") for k in v.kills)


def test_validate_claim_kills_unit_mismatch():
    name_to_uid = validate.build_name_to_uid()
    cat = _catalog_by_id()
    v = validate.validate_claim(
        node_id="ThermalConductivity[bte_solver=rta]", printed_unit="eV",
        value=1.0, cited_text="present", material="Si",
        corpus_text="present here", name_to_uid=name_to_uid,
        catalog_by_id=cat, instance_index=[])
    assert not v.survives
    assert "unit_dimension_mismatch" in v.kills


def test_validate_claim_kills_nonfinite_value():
    name_to_uid = validate.build_name_to_uid()
    cat = _catalog_by_id()
    v = validate.validate_claim(
        node_id="ActivationEnergy", printed_unit="eV", value=None,
        cited_text="present", material="LGPS", corpus_text="present here",
        name_to_uid=name_to_uid, catalog_by_id=cat, instance_index=[])
    assert not v.survives
    assert "nonfinite_value" in v.kills


# --------------------------------------------------------------------------
# usage tracker + slug
# --------------------------------------------------------------------------
def test_usage_accumulates():
    u = Usage()
    u.add({"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50})
    u.add({"input_tokens": 10, "output_tokens": 5})
    assert u.input_tokens == 110
    assert u.output_tokens == 25
    assert u.cache_read_input_tokens == 50
    assert u.calls == 2
    assert u.cost_estimate_usd() > 0


def test_slugify():
    assert propose.slugify("OpenMaterials AI") == "openmaterials-ai"
    assert propose.slugify("Cu Sigma5 [001]") == "cu-sigma5-001"


# --------------------------------------------------------------------------
# Ensemble: variant prompts exist and differ
# --------------------------------------------------------------------------
def test_detect_prompt_variants_exist_and_differ():
    variants = detect.DETECT_PROMPT_VARIANTS
    assert len(variants) == 3
    # All three are distinct texts.
    assert len(set(variants)) == 3
    # Pass 1 is the shipped prompt verbatim.
    assert variants[0] == detect.DETECT_PROMPT
    # Passes 2 and 3 carry their focus directive and steer differently.
    assert "TABLE" in variants[1] and "FIGURE CAPTION" in variants[1]
    assert "RUNNING TEXT" in variants[2] and "ABSTRACT" in variants[2]
    # Every variant still contains the shared extraction contract (the quote gate).
    for v in variants:
        assert '"quote"' in v
        assert "Return only the JSON array." in v


def _claim(value, quantity="thermal conductivity", quote="", pages=None,
           conditions=None, material="Si"):
    return DetectedClaim(
        quantity=quantity, symbol=None, value_text=str(value), unit="W/(m K)",
        material=material, conditions=conditions or {}, provenance="own_result",
        cited_text=quote, pages=pages or [], raw={})


# --------------------------------------------------------------------------
# Ensemble: union / merge semantics
# --------------------------------------------------------------------------
def test_union_merges_same_finding_across_passes_and_counts_support():
    # Same value, compatible quantity, overlapping quote -> one finding, support 2.
    a = _claim("19.46", quote="kappa was 19.46 W/(m K) for Si", pages=[3])
    b = _claim("19.46", quantity="thermal_conductivity",
               quote="19.46 W/(m K)", pages=[3])
    out = detect.union_claims([[a], [b]])
    assert len(out) == 1
    assert out[0].support == 2


def test_union_same_value_same_page_no_quote_overlap_still_merges():
    # Overlapping quote OR same/adjacent page: page +/-1 is enough.
    a = _claim("60.2", quote="", pages=[2])
    b = _claim("60.2", quote="", pages=[3])  # adjacent page
    out = detect.union_claims([[a], [b]])
    assert len(out) == 1 and out[0].support == 2


def test_union_distinct_values_never_merge():
    a = _claim("16.74", quote="16.74 W/(m K)", pages=[3])
    b = _claim("24.30", quote="24.30 W/(m K)", pages=[3])
    out = detect.union_claims([[a], [b]])
    assert len(out) == 2
    assert all(c.support == 1 for c in out)


def test_union_same_value_different_quantity_not_merged():
    # Same number, incompatible quantity names, no quote/page tie -> distinct.
    a = _claim("0.152", quantity="activation energy", quote="E_a 0.152 eV", pages=[5])
    b = _claim("0.152", quantity="formation energy", quote="0.152 eV form", pages=[9])
    out = detect.union_claims([[a], [b]])
    assert len(out) == 2


def test_union_keeps_richer_claim_on_merge():
    # The claim with more conditions (and, tie-broken, longer quote) is kept.
    lean = _claim("91.44", quote="91.44 mS/cm", pages=[4], material="LGPS")
    rich = _claim("91.44", quote="the ionic conductivity of LGPS was 91.44 mS/cm",
                  pages=[4], conditions={"temperature": "300 K"}, material="LGPS")
    out = detect.union_claims([[lean], [rich]])
    assert len(out) == 1
    assert out[0].conditions == {"temperature": "300 K"}
    assert out[0].cited_text == "the ionic conductivity of LGPS was 91.44 mS/cm"
    assert out[0].support == 2


def test_union_duplicate_within_one_pass_does_not_double_count_support():
    # Two same-finding claims in ONE pass contribute support 1, not 2.
    a = _claim("19.46", quote="19.46 W/(m K)", pages=[3])
    a2 = _claim("19.46", quote="19.46 W/(m K) again", pages=[3])
    out = detect.union_claims([[a, a2]])
    assert len(out) == 1
    assert out[0].support == 1


def test_union_single_pass_leaves_support_one():
    out = detect.union_claims([[_claim("156", quote="156 W/(m K)", pages=[1])]])
    assert len(out) == 1 and out[0].support == 1


def test_norm_value_non_numeric_never_unifies():
    a = _claim("n/a", quote="same quote here", pages=[3])
    b = _claim("n/a", quote="same quote here", pages=[3])
    out = detect.union_claims([[a], [b]])
    # Non-numeric values return None and never unify -> two separate findings.
    assert len(out) == 2


# --------------------------------------------------------------------------
# Ensemble: fake-client end-to-end (no real API), support flows to proposal,
# and no key material appears in the artifact
# --------------------------------------------------------------------------
class _FakeUsage:
    input_tokens = 100
    output_tokens = 20
    cache_creation_input_tokens = 10
    cache_read_input_tokens = 0


class _FakeResp:
    def __init__(self, content_json, cache_read=0):
        import json as _json
        self.stop_reason = "end_turn"
        u = _FakeUsage()
        u.cache_read_input_tokens = cache_read
        self.usage = u
        self.content = [type("B", (), {"type": "text", "text": _json.dumps(content_json),
                                        "citations": None})()]


class _FakeClient:
    """A client whose DETECT calls return canned JSON arrays, one per pass, and
    whose later structured-output calls (map/review) return empty. Tracks the
    per-call cache_read to simulate the document block caching on passes 2+."""

    def __init__(self, per_pass_rows):
        self._per_pass = per_pass_rows
        self._detect_i = 0
        self.messages = self

    def create(self, **kw):
        # DETECT passes send a list content with a document block first.
        content = kw.get("messages", [{}])[0].get("content")
        is_detect = isinstance(content, list)
        if is_detect:
            rows = self._per_pass[self._detect_i % len(self._per_pass)]
            cache_read = 0 if self._detect_i == 0 else 500
            self._detect_i += 1
            return _FakeResp(rows, cache_read=cache_read)
        # map/review: empty structured output (both keys present is harmless)
        return _FakeResp({"mappings": [], "verdicts": []})


def test_detect_ensemble_unions_and_reports_cache(tmp_path):
    from omai.paper_parser.ingest import Ingested
    ing = Ingested(pdf_b64="AAAA", pages=("x",), full_text="x")
    rows_p1 = [{"quantity": "thermal conductivity", "value": "19.46",
                "unit": "W/(m K)", "material": "Si", "quote": "19.46 W/(m K)",
                "page": 3, "provenance": "own_result", "conditions": {}}]
    rows_p2 = [{"quantity": "thermal_conductivity", "value": "19.46",
                "unit": "W/(m K)", "material": "Si", "quote": "kappa 19.46 W/(m K)",
                "page": 3, "provenance": "own_result", "conditions": {}}]
    rows_p3 = [{"quantity": "activation energy", "value": "0.152", "unit": "eV",
                "material": "LGPS", "quote": "0.152 eV", "page": 5,
                "provenance": "own_result", "conditions": {}}]
    client = _FakeClient([rows_p1, rows_p2, rows_p3])
    u = Usage()
    claims, stop, info = detect.detect_ensemble(client, ing, u, passes=3)
    assert stop == "end_turn"
    assert info["passes"] == 3
    assert info["per_pass_claim_counts"] == [1, 1, 1]
    # passes 2 and 3 read the cached document block
    assert info["cache_read_input_tokens"] == 1000
    # the two 19.46 findings union (support 2); the 0.152 stays support 1
    by_val = {c.value_text: c for c in claims}
    assert by_val["19.46"].support == 2
    assert by_val["0.152"].support == 1


def test_proposal_carries_support_and_ensemble_metadata_and_no_key(monkeypatch):
    # A run through build_proposal with a support-bearing mapped claim: the
    # per-claim support, the ensemble block, and no leaked key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-should-not-appear")
    from omai.paper_parser.map_nodes import MappedClaim
    d = _claim("19.46", quote="19.46 W/(m K)", pages=[3])
    d.support = 3
    m = MappedClaim(detected=d, node_id="ThermalConductivity[bte_solver=rta]",
                    unmappable_reason=None, proposed_quantity=None,
                    unit_declaration="W/(m K)", material="Si", conditions={})
    v = validate.Validation(node_ok=True, unit={"ok": True, "kind": "match"},
                            value_ok=True, quote_ok=True, duplicate=None,
                            node_uid="uid-1", kills=[])
    u = Usage()
    u.add(_FakeUsage())
    proposal = propose.build_proposal(
        paper_slug="p", map_version=None, mapped=[m], validations=[v],
        verdicts_by_index={}, usage=u, catalog_fingerprint="abc",
        detect_stop="end_turn", map_stop="end_turn", review_stop="end_turn",
        detect_info={"passes": 3, "per_pass_claim_counts": [5, 4, 6],
                     "stop_reasons": ["end_turn", "end_turn", "end_turn"]})
    assert proposal["claims"][0]["support"] == 3
    assert proposal["ensemble"]["detect_passes"] == 3
    assert proposal["ensemble"]["per_pass_claim_counts"] == [5, 4, 6]
    # The serialized artifact never contains the key.
    assert "sk-secret-should-not-appear" not in json.dumps(proposal)


# --------------------------------------------------------------------------
# P2.1: the condition rule (source / parameter nodes are context, not evidence)
# --------------------------------------------------------------------------

def _catalog_by_id():
    return {r["id"]: r for r in catalog.build_node_catalog()}


def test_node_kind_classifies_condition_vs_value():
    from omai.paper_parser.map_nodes import node_kind

    cat = _catalog_by_id()
    # A kappa claim is a value target; a Temperature / AtomCount claim is a
    # condition (evidence_target: false).
    assert node_kind("ThermalConductivity[bte_solver=rta]", cat) == "value"
    assert node_kind("Temperature", cat) == "condition"
    assert node_kind("AtomCount", cat) == "condition"
    assert node_kind("Structure", cat) == "condition"
    # An unmappable claim (no node) defaults to value; an unknown id too.
    assert node_kind(None, cat) == "value"
    assert node_kind("NotANode", cat) == "value"


def _mapped_and_validation(node_id, value="300", material="Si"):
    from omai.paper_parser.map_nodes import MappedClaim

    d = _claim(value, quote=f"{value} at conditions", pages=[1], material=material)
    m = MappedClaim(detected=d, node_id=node_id, unmappable_reason=None,
                    proposed_quantity=None, unit_declaration="", material=material,
                    conditions={})
    v = validate.Validation(node_ok=True, unit={"ok": True, "kind": "match"},
                            value_ok=True, quote_ok=True, duplicate=None,
                            node_uid=f"uid-{node_id}", kills=[])
    return m, v


def test_build_proposal_tags_kind_and_separates_counts():
    cat = _catalog_by_id()
    m1, v1 = _mapped_and_validation("ThermalConductivity[bte_solver=rta]", "19.46")
    m2, v2 = _mapped_and_validation("Temperature", "300")
    m3, v3 = _mapped_and_validation("AtomCount", "2")
    proposal = propose.build_proposal(
        paper_slug="p", map_version=None, mapped=[m1, m2, m3],
        validations=[v1, v2, v3], verdicts_by_index={}, usage=Usage(),
        catalog_fingerprint="abc", detect_stop="end_turn", map_stop="end_turn",
        review_stop="end_turn", catalog_by_id=cat)
    kinds = [c["kind"] for c in proposal["claims"]]
    assert kinds == ["value", "condition", "condition"]
    assert proposal["counts"] == {"claims_total": 3, "value_claims": 1,
                                  "condition_claims": 2}


def test_apply_proposal_excludes_condition_claims(tmp_path):
    cat = _catalog_by_id()
    m1, v1 = _mapped_and_validation("ThermalConductivity[bte_solver=rta]", "19.46")
    m2, v2 = _mapped_and_validation("Temperature", "300")
    proposal = propose.build_proposal(
        paper_slug="p", map_version=None, mapped=[m1, m2],
        validations=[v1, v2], verdicts_by_index={}, usage=Usage(),
        catalog_fingerprint="abc", detect_stop="end_turn", map_stop="end_turn",
        review_stop="end_turn", catalog_by_id=cat)
    written = propose.apply_proposal(proposal, source_kind="simulation",
                                     instances_dir=tmp_path)
    # Only the kappa value instance is minted; the Temperature condition is not.
    assert len(written) == 1
    rec = json.loads(written[0].read_text())
    assert rec["variable"] == "ThermalConductivity[bte_solver=rta]"


def test_default_map_version_is_the_live_published_pin():
    """A proposal must never ship with map_version None while its catalog
    fingerprint is set (found live 2026-07-12: the CLI's --map-version
    defaulted to None and nothing fell back to the published head)."""
    from omai.paper_parser import default_map_version
    v = default_map_version()
    assert isinstance(v, str) and len(v) == 64
    repo = Path(__file__).resolve().parent.parent
    assert v == json.load(open(repo / "docs" / "data" / "version.json"))["version"]
