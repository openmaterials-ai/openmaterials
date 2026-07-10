"""Offline tests for the paper parser: env loader, catalog builder, and all
deterministic validators (quote normalization, unit check, dedup).

None of these call the API; the suite stays green with and without a key.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai.paper_parser import catalog, env, propose, validate
from omai.paper_parser.detect import Usage


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
    assert len(rows) == 98
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
