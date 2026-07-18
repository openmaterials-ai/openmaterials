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
    assert len(rows) == 114
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


def test_unit_check_molar_heat_capacity_spellings():
    # J_per_K_per_mol has been registered from the start, but no printed
    # spelling resolved to it, so C_p claims went "unresolved". Every common
    # spelling must now dimension-check as a hard match.
    for spelling in ("J/(K mol)", "J/(mol K)", "J/(K\u00b7mol)", "J/mol/K",
                     "J mol^-1 K^-1", "J K^-1 mol^-1"):
        res = validate.unit_check(spelling, "MolarHeatCapacity", _catalog_by_id())
        assert res["ok"] and res["kind"] == "match", (spelling, res)


def test_unit_check_interface_conductance_spellings():
    # W_per_m2_k / MW_per_m2_k registered with the composites domain; the
    # printed spellings must dimension-check as hard matches against the
    # InterfaceConductance node, so a Kapitza-conductance claim is checked
    # instead of passing "unresolved" (MW/(m^2 K) is the practitioner scale).
    for spelling in ("W/(m^2 K)", "W/(m2 K)", "W m^-2 K^-1",
                     "MW/(m^2 K)", "MW/(m2 K)", "MW m^-2 K^-1"):
        res = validate.unit_check(spelling, "InterfaceConductance", _catalog_by_id())
        assert res["ok"] and res["kind"] == "match", (spelling, res)


def test_unit_check_molar_energy_spellings():
    for spelling, node in (("kJ/mol", "MolarEnthalpy"), ("J/mol", "MolarEnthalpy")):
        res = validate.unit_check(spelling, node, _catalog_by_id())
        assert res["ok"] and res["kind"] == "match", (spelling, res)


def test_unit_check_molar_energy_against_plain_energy_is_fatal():
    # With kJ/mol resolvable, a molar energy printed against a plain-energy
    # node (ReactionEnergy is per event/atom, not per mole) must now be a hard
    # mismatch instead of slipping through unresolved.
    res = validate.unit_check("kJ/mol", "ReactionEnergy", _catalog_by_id())
    assert not res["ok"] and res["kind"] == "mismatch"


def test_unit_check_thermal_conductance_spellings():
    # W_per_K and nW_per_K entered the registry with the MESCAL onboarding,
    # but no printed spelling resolved to them, so a Landauer G(T) claim
    # passed the unit gate "unresolved". W/K and nW/K (the spelling MESCAL's
    # native serving unit prints) must dimension-check as hard matches
    # against the conductance node.
    node = "ThermalConductance[transport_model=landauer]"
    for spelling in ("W/K", "nW/K", "w/k", "nw/k"):
        res = validate.unit_check(spelling, node, _catalog_by_id())
        assert res["ok"] and res["kind"] == "match", (spelling, res)


def test_unit_check_conductance_against_conductivity_is_fatal():
    # The conductance/conductivity distinction the MESCAL onboarding drew:
    # a W/K (power per temperature) value printed against the per-length
    # kappa node must die as a dimensional mismatch, not slip through.
    res = validate.unit_check(
        "nW/K", "ThermalConductivity[bte_solver=rta]", _catalog_by_id())
    assert not res["ok"] and res["kind"] == "mismatch"


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
    from omai.lineages import lineage_id

    d = tmp_path / "instances"
    d.mkdir()
    lin1 = {"node": "ThermalConductivity[bte_solver=rta]", "material": "Si",
            "conditions": {}, "values": {"value": 16.735, "units": "W/(m K)"}}
    (d / "si-kappa.json").write_text(json.dumps({
        "id": lineage_id(lin1), "kind": "simulation", "lineage": lin1,
        "source": {"kind": "simulation", "ref": "x"},
    }))
    lin2 = {"node": "ElectricalConductivity[carrier=ionic]",
            "material": "LGPS", "conditions": {},
            "values": {"value": 91.44, "units": "mS/cm"}}
    (d / "lgps-sigma.json").write_text(json.dumps({
        "id": lineage_id(lin2), "kind": "simulation", "lineage": lin2,
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
# Deterministic semantic gates: a delta posing as a value, and a descriptive
# spectral marker. These are the code-level kills for the two families the LLM
# reviewer failed to catch on the amorphous-alloys (Lundgren) live parse: it
# confirmed "a 0.6 W/mK drop of kappa" (a delta) and "below 4 THz" (a prose
# band edge) as absolute values. A soft prompt rule is not reliable; these
# gates make the kill off the LLM, and are deliberately conservative.
# --------------------------------------------------------------------------
def _validate(node_id, printed_unit, value, quote):
    """validate_claim with the quote as its own corpus (so the hallucination
    gate passes and only the semantic gates are exercised)."""
    return validate.validate_claim(
        node_id=node_id, printed_unit=printed_unit, value=value,
        cited_text=quote, material="a-Si", corpus_text=quote,
        name_to_uid=validate.build_name_to_uid(), catalog_by_id=_catalog_by_id(),
        instance_index=[])


def test_validate_claim_kills_delta_drop_of_kappa():
    # Lundgren idx 40: "0.6 W/mK drop of kappa" is a delta, not a kappa value.
    v = _validate("ThermalConductivity[transport_model=qhgk]", "W/(m K)", 0.6,
                  "the substitution of 5% Ge results in a 0.6 W m-1 K-1 drop of kappa")
    assert not v.survives
    assert "delta_posing_as_value" in v.kills


def test_validate_claim_kills_delta_reduction_of_kappa():
    # Lundgren idx 41: "0.55 W/mK reduction of kappa" is a delta (the PDF glues
    # the unit to "reduction", which the gate tolerates).
    v = _validate("ThermalConductivity[transport_model=qhgk]", "W/(m K)", 0.55,
                  "A further 0.55 W m-1 K-1reduction of kappa is obtained")
    assert not v.survives
    assert "delta_posing_as_value" in v.kills


def test_validate_claim_kills_descriptive_spectral_marker_below_4thz():
    # Lundgren idx 36: "below 4 THz" is a prose band edge on the Frequency node.
    v = _validate("Frequency", "THz", 4,
                  "mostly build in the low-frequency part of the spectrum, below 4 THz")
    assert not v.survives
    assert "descriptive_spectral_marker" in v.kills


def test_validate_claim_survives_absolute_kappa_value():
    # An absolute first-principles kappa is a real value; no delta cue binds.
    v = _validate("ThermalConductivity[bte_solver=rta]", "W/(m K)", 39.0,
                  "our first-principles BTE calculations give kr = 39.0 Wm-1K-1")
    assert v.survives
    assert "delta_posing_as_value" not in v.kills


def test_validate_claim_survives_real_spectral_peak():
    # A genuine measured/computed peak or mode value must survive the spectral
    # gate: the "peak"/"mode at" cue short-circuits the kill.
    for quote, value in (("a Raman peak at 520 cm-1", 520),
                         ("the LA mode at 12.3 THz", 12.3)):
        v = _validate("Frequency", "THz", value, quote)
        assert v.survives, (quote, v.kills)
        assert "descriptive_spectral_marker" not in v.kills


def test_validate_claim_survives_absolute_value_with_distant_change_word():
    # A distant "increase" (a different clause, after a sentence break) must NOT
    # kill a real absolute value: the change is not bound to 145.
    v = _validate("ThermalConductivity[transport_model=qhgk]", "W/(m K)", 145,
                  "the thermal conductivity is 145 W/mK; an increase in "
                  "temperature was applied later")
    assert v.survives
    assert "delta_posing_as_value" not in v.kills


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
    assert rec["lineage"]["node"] == "ThermalConductivity[bte_solver=rta]"


def test_default_map_version_is_the_live_published_pin():
    """A proposal must never ship with map_version None while its catalog
    fingerprint is set (found live 2026-07-12: the CLI's --map-version
    defaulted to None and nothing fell back to the published head)."""
    from omai.paper_parser import default_map_version
    v = default_map_version()
    assert isinstance(v, str) and len(v) == 64
    repo = Path(__file__).resolve().parent.parent
    assert v == json.load(open(repo / "docs" / "data" / "version.json"))["version"]


def test_review_prompt_kills_descriptive_spectral_markers():
    """Prose band edges / crossovers ('below 4 THz') are narrative structure,
    not results; the pattern showed up in Esfarjani (3 hand-cut) and the
    amorphous-alloys parse (9 more) before the prompt learned it."""
    from omai.paper_parser.review import REVIEW_SYSTEM
    assert "DESCRIPTIVE SPECTRAL MARKERS" in REVIEW_SYSTEM
    assert "Raman" in REVIEW_SYSTEM  # the counter-example stays protected


def test_collapse_same_finding_within_proposal():
    """The same finding stated twice in a paper (abstract + body) must
    collapse to one surviving claim (max support, merged_from recorded);
    distinct values on the same node/material are never touched. Found live
    in the kALDo 2.0 parse (the CsPbBr3 340 K transition, twice)."""
    from omai.paper_parser.propose import _collapse_same_finding

    def claim(i, val, support, mat="CsPbBr3", node="TransitionTemperature"):
        return {"index": i, "node_id": node, "material": mat, "value_text": val,
                "kind": "value", "support": support,
                "validation": {"survives": True},
                "review": {"verdict": "confirmed"}}

    out = _collapse_same_finding([
        claim(0, "340", 2), claim(1, "340", 1),          # same finding: collapse
        claim(2, "118", 3, node="X"), claim(3, "123", 3, node="X"),  # distinct: keep
    ])
    by = {c["index"]: c for c in out}
    assert 1 not in by and by[0]["support"] == 2 and by[0]["merged_from"] == [1]
    assert 2 in by and 3 in by
    # non-surviving claims never participate
    dead = claim(4, "340", 3)
    dead["validation"] = {"survives": False}
    out2 = _collapse_same_finding([claim(0, "340", 2), dead])
    assert len(out2) == 2


def test_ingest_survives_broken_pages(monkeypatch, tmp_path):
    """One malformed compressed stream (pypdf LimitReachedError, live on a
    55-page arXiv PDF) must not take down the whole corpus: the broken page
    contributes empty text and is recorded; a mostly-broken PDF is refused."""
    import pypdf
    from omai.paper_parser.ingest import read_pdf

    class FakePage:
        def __init__(self, ok):
            self.ok = ok
        def extract_text(self):
            if not self.ok:
                raise RuntimeError("Limit reached while decompressing")
            return "good text"

    class OneBad:
        def __init__(self, path):
            self.pages = [FakePage(True), FakePage(False), FakePage(True)]

    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(pypdf, "PdfReader", OneBad)
    ing = read_pdf(f)
    assert ing.broken_pages == (2,)
    assert len(ing.pages) == 3 and ing.pages[1] == ""

    class MostlyBad:
        def __init__(self, path):
            self.pages = [FakePage(False), FakePage(False), FakePage(True)]

    monkeypatch.setattr(pypdf, "PdfReader", MostlyBad)
    with pytest.raises(ValueError):
        read_pdf(f)


def test_review_prompt_kills_differences_posing_as_values():
    """'a 0.6 W/mK drop of kappa' is a delta, not a kappa value; two such
    claims survived review in the amorphous-alloys parse (caught only by the
    human adversarial pass, 2026-07-12) before the prompt learned it."""
    from omai.paper_parser.review import REVIEW_SYSTEM
    assert "DIFFERENCES POSING AS VALUES" in REVIEW_SYSTEM


def test_map_claims_batches_and_reassembles(monkeypatch):
    """121 claims must arrive as ceil(121/40)=4 MAP calls whose batch-local
    indices reassemble in order (live: 100+-claim papers overflowed a single
    16k mapping call)."""
    from omai.paper_parser import map_nodes

    calls = []

    class FakeMessages:
        def create(self, **kw):
            user = kw["messages"][0]["content"]
            rows = json.loads(user.split("CLAIMS:\n", 1)[1])
            calls.append(len(rows))

            class R:
                stop_reason = "end_turn"
                usage = _FakeUsage()
                content = [type("B", (), {
                    "type": "text",
                    "text": json.dumps({"mappings": [
                        {"index": r["index"], "node_id": "UNMAPPABLE",
                         "unmappable_reason": "x", "proposed_quantity": None,
                         "unit_declaration": "", "material": r["material"],
                         "conditions_json": "{}"} for r in rows]})})()]
            return R()

    class FakeClient:
        messages = FakeMessages()

    claims = [_claim(str(i), quantity=f"q{i}", material=f"m{i}") for i in range(121)]
    mapped, stop, info = map_nodes.map_claims(FakeClient(), claims, "CATALOG", Usage())
    assert calls == [40, 40, 40, 1]
    assert stop == "end_turn" and len(mapped) == 121
    # order preserved across batches: the reassembled mapping carries each
    # claim's own material back
    assert [m.material for m in mapped] == [f"m{i}" for i in range(121)]


def test_split_for_api_partitions_oversized_documents(monkeypatch, tmp_path):
    """Documents above the API request cap detect on page-range parts: real
    sub-PDFs with their own text, page offsets converting back to whole-doc
    numbering; small documents stay single-part (live: a 26MB figure-heavy
    paper 413'd, 2026-07-12)."""
    from omai.paper_parser.ingest import Ingested, split_for_api

    small = Ingested(pdf_b64="A" * 100, pages=("p1", "p2"), full_text="p1\np2")
    assert split_for_api("unused.pdf", small) == [(small, 0)]

    # an oversized doc splits via real sub-PDF construction; fake the
    # PdfReader/Writer machinery to keep the test hermetic
    import pypdf

    class FakePage:
        pass

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage() for _ in range(4)]

    class FakeWriter:
        def __init__(self):
            self.n = 0
        def add_page(self, p):
            self.n += 1
        def write(self, buf):
            buf.write(b"x" * (self.n * 30))  # 30 raw bytes/page -> 40 b64 chars

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    monkeypatch.setattr(pypdf, "PdfWriter", FakeWriter)
    big = Ingested(pdf_b64="A" * 1000, pages=("a", "b", "c", "d"),
                   full_text="a\nb\nc\nd", broken_pages=(3,))
    parts = split_for_api("fake.pdf", big, max_b64=90)
    assert len(parts) == 2
    (p1, off1), (p2, off2) = parts
    assert (off1, off2) == (0, 2)
    assert p1.pages == ("a", "b") and p2.pages == ("c", "d")
    # the broken page (3, whole-doc) lands in part 2 as its local page 1
    assert p2.broken_pages == (1,) and p1.broken_pages == ()


def test_map_payload_carries_deterministic_resolver_hint():
    """The MAP stage grounds each claim's fuzzy quantity string in the map's
    own vocabulary via the semantic resolver, passed as a hint the model may
    confirm or override. A known family hints, a genuine gap hints nothing."""
    from omai.paper_parser.map_nodes import _resolve_hint

    assert "PhononDOS" in _resolve_hint("phonon density of states")
    qha = _resolve_hint("quasi-harmonic approximation")
    assert "QHAGibbsEnergy" in qha and "ThermalExpansion" in qha
    assert _resolve_hint("atomic multipole partitioning") == []  # honest gap
    assert _resolve_hint("") == []

    # the hint rides in the rendered claims payload
    from omai.paper_parser.map_nodes import _claims_payload
    d = _claim("2.2", quote="q", pages=[1])
    d.quantity = "phonon density of states"
    row = json.loads(_claims_payload([d]))[0]
    assert "PhononDOS" in row["resolver_hint"]


def test_split_for_api_max_pages_force(monkeypatch):
    """A dense paper can overflow the detect OUTPUT budget while fitting the
    request cap; max_pages forces page-chunking regardless of byte size (live:
    a 55-page paper defeated the 32k budget, 2026-07-13)."""
    import pypdf
    from omai.paper_parser.ingest import Ingested, split_for_api

    class FakePage:
        pass

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage() for _ in range(30)]

    class FakeWriter:
        def __init__(self):
            self.n = 0
        def add_page(self, p):
            self.n += 1
        def write(self, buf):
            buf.write(b"x" * self.n)

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    monkeypatch.setattr(pypdf, "PdfWriter", FakeWriter)
    doc = Ingested(pdf_b64="A" * 100, pages=tuple(f"p{i}" for i in range(30)),
                   full_text="x")
    # fits the size cap: without the force it stays whole
    assert len(split_for_api("f.pdf", doc)) == 1
    # with the force every part is <= 12 pages and offsets tile the document
    parts = split_for_api("f.pdf", doc, max_pages=12)
    assert all(len(p.pages) <= 12 for p, _ in parts)
    assert [off for _, off in parts] == sorted(off for _, off in parts)
    assert sum(len(p.pages) for p, _ in parts) == 30


def test_adaptive_chunking_halves_until_detect_fits(monkeypatch, tmp_path):
    """A table-dense part can overflow the detect budget even at 12 pages
    (live, 2026-07-13): the pipeline halves any truncating range down to
    single pages, never re-runs parts that succeeded, and unions the claims
    with whole-document page numbers."""
    import pypdf

    from omai.paper_parser import run_pipeline
    from omai.paper_parser import detect as detect_mod

    class FakePage:
        def extract_text(self):
            return "page text 1.23 W/(m K)"

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage() for _ in range(8)]

    class FakeWriter:
        def __init__(self):
            self.n = 0
        def add_page(self, p):
            self.n += 1
        def write(self, buf):
            buf.write(b"x" * self.n)

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    monkeypatch.setattr(pypdf, "PdfWriter", FakeWriter)

    calls = []

    def fake_ensemble(client, ingested, usage, passes=3):
        n = len(ingested.pages)
        calls.append(n)
        if n > 3:
            raise RuntimeError("DETECT truncated (max_tokens); raise cap or split the PDF")
        c = _claim("1.23", quote="1.23 W/(m K)", pages=[1])
        return [c], "end_turn", {"passes": passes, "per_pass_claim_counts": [1],
                                 "stop_reasons": ["end_turn"],
                                 "cache_read_input_tokens": 0}

    monkeypatch.setattr(detect_mod, "detect_ensemble", fake_ensemble)

    pdf = tmp_path / "dense.pdf"
    pdf.write_bytes(b"%PDF-fake")
    # exercise the worklist through run_pipeline with MAP/REVIEW as no-ops
    from omai import paper_parser as pp
    monkeypatch.setattr(pp._map, "map_claims", lambda client, claims, cat, usage: ([], "end_turn", {"cache_read_input_tokens": 0}))
    monkeypatch.setattr(pp._review, "review", lambda *a, **k: ({}, "end_turn"))
    res = pp.run_pipeline(pdf, client=object(), write=False, proposals_dir=tmp_path)
    # 8 pages: the whole doc (8) truncates, the 12-page tile (still 8)
    # truncates, both 4-page halves truncate, all four 2-page quarters fit:
    # 2 eights, 2 fours, 4 twos regardless of pop order.
    assert calls.count(8) == 2 and calls.count(4) == 2 and calls.count(2) == 4
    assert res.proposal["ensemble"]["document_parts"] == 4


def test_review_batches_and_concatenates_verdicts():
    """A dense paper's surviving claims overflow a single 16k review output
    (live: kappa-limit, 2026-07-13): review now runs in REVIEW_BATCH_SIZE
    batches with global indices, and a refusal aborts the remaining batches
    honestly (their claims carry no verdict)."""
    from omai.paper_parser import review as review_mod

    surviving = []
    for i in range(95):
        m, v = _mapped_and_validation("Temperature", str(200 + i))
        surviving.append((i, m, v))

    class FakeUsageBlock:
        input_tokens = output_tokens = 0
        cache_read_input_tokens = cache_creation_input_tokens = 0

    class FakeResp:
        def __init__(self, indices):
            self.usage = FakeUsageBlock()
            self.stop_reason = "end_turn"
            body = json.dumps({"verdicts": [
                {"index": i, "verdict": "confirmed", "corrected_field": "",
                 "corrected_value": "", "reason": "holds"} for i in indices]})
            self.content = [type("B", (), {"type": "text", "text": body})()]

    class FakeClient:
        def __init__(self):
            self.batch_sizes = []
            self.messages = self

        def create(self, **kw):
            rows = json.loads(kw["messages"][0]["content"].split("CLAIMS:\n", 1)[1])
            self.batch_sizes.append(len(rows))
            return FakeResp([r["index"] for r in rows])

    fc = FakeClient()
    verdicts, stop = review_mod.review(fc, surviving, "catalog", "corpus", Usage())
    assert fc.batch_sizes == [40, 40, 15]
    assert stop == "end_turn" and len(verdicts) == 95
    assert sorted(v.index for v in verdicts) == list(range(95))

    class RefusingClient(FakeClient):
        def create(self, **kw):
            resp = super().create(**kw)
            if len(self.batch_sizes) == 2:
                resp.stop_reason = "refusal"
                resp.content = []
            return resp

    rc = RefusingClient()
    verdicts, stop = review_mod.review(rc, surviving, "catalog", "corpus", Usage())
    # batch 2 refuses: batch 3 never runs, batch 1's verdicts survive
    assert rc.batch_sizes == [40, 40] and stop == "refusal"
    assert len(verdicts) == 40


# --------------------------------------------------------------------------
# Numeral normalization before the value gate (the CNT lesson: "9, 960",
# "13,000", and "2408 ± 83" are real claims wearing printed formatting)
# --------------------------------------------------------------------------
def test_to_float_normalizes_printed_numerals():
    from omai.paper_parser import _to_float

    assert _to_float("13,000") == 13000.0
    assert _to_float("9, 960") == 9960.0
    assert _to_float("1,234,567") == 1234567.0
    assert _to_float("2408 ± 83") == 2408.0
    assert _to_float("2408 +/- 83") == 2408.0
    assert _to_float("−5.2") == -5.2
    assert _to_float("3.14") == 3.14
    assert _to_float("42") == 42.0


def test_to_float_still_refuses_non_numerals():
    from omai.paper_parser import _to_float

    assert _to_float("about 3190") is None
    assert _to_float("") is None
    assert _to_float(None) is None
    assert _to_float("6 mm (QM)") is None
