"""The share ENVELOPE: multi-lineage bundles in one link fragment.

Pins the envelope contract in omai/lineages.py: the round-trip through the
fragment transport, the dual read (a legacy bare-record fragment normalizes to
a one-element envelope, forever), the ambiguous both-keys payload rejected,
the derived bundle_id (deterministic, order-sensitive, doc-sensitive), the
invariance rules (bundling never changes a member's id; doc.source inheritance
is read-time only and never enters a member's hash), and the FORMAT_DESCRIPTOR
envelope section stating all of it.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from omai import lineages as lin


def _member(**over):
    lineage = {"node": "ThermalConductivity", "material": {"name": "Si"},
               "conditions": {"T": 300.0},
               "values": {"value": 148.0, "units": "W/(m K)"}}
    lineage.update(over)
    return {"id": lin.lineage_id(lineage), "lineage": lineage}


def _doc():
    return {"source": "doi:10.1103/PhysRevLett.127.025902",
            "title": "Ultrahigh convergent thermal conductivity",
            "authors": ["G. Barbalinardo", "D. Donadio"],
            "year": 2021, "journal": "Phys. Rev. Lett."}


# ---- build + round-trip ----------------------------------------------------

def test_envelope_round_trips_through_the_fragment():
    env = lin.envelope([_member(), _member(material={"name": "Ge"})], doc=_doc())
    frag = lin.envelope_to_fragment(env)
    assert frag.startswith("g")
    back = lin.envelope_from_fragment(frag)
    assert back == env
    assert len(back["lineages"]) == 2
    assert back["doc"]["source"] == "doi:10.1103/PhysRevLett.127.025902"


def test_single_lineage_share_is_a_one_element_envelope():
    env = lin.envelope([_member()])
    assert env["v"] == lin.ENVELOPE_VERSION
    assert "doc" not in env
    assert len(env["lineages"]) == 1


def test_fragment_accepts_hash_x_prefix():
    env = lin.envelope([_member()])
    frag = lin.envelope_to_fragment(env)
    assert lin.envelope_from_fragment("#x=" + frag) == env


# ---- the dual read (legacy fragments, forever) -----------------------------

def test_bare_record_fragment_normalizes_to_one_element_envelope():
    record = _member()
    frag = lin.record_to_fragment(record)
    env = lin.envelope_from_fragment(frag)
    assert env == {"v": lin.ENVELOPE_VERSION, "lineages": [record]}
    # and the legacy reader itself is untouched
    assert lin.record_from_fragment(frag) == record


def test_legacy_recipe_fragment_normalizes_and_upgrades_the_key():
    # hand-craft the fragment (record_to_fragment would upgrade the key on
    # emit, hiding the read path under test): a wild legacy link may still
    # carry "recipe" in its payload and must normalize on decode
    import base64
    import gzip
    lineage = _member()["lineage"]
    blob = json.dumps({"recipe": lineage}, separators=(",", ":")).encode()
    frag = "g" + base64.urlsafe_b64encode(gzip.compress(blob)).decode().rstrip("=")
    env = lin.envelope_from_fragment(frag)
    assert env["lineages"] == [{"lineage": lineage}]


def test_envelope_member_with_recipe_key_upgrades_on_build():
    lineage = _member()["lineage"]
    env = lin.envelope([{"recipe": lineage}])
    assert env["lineages"][0] == {"lineage": lineage}


# ---- rubbish rejected ------------------------------------------------------

def test_both_keys_payload_rejected():
    env = lin.envelope([_member()])
    env["lineage"] = _member()["lineage"]
    with pytest.raises(lin.LineageError, match="ambiguous"):
        lin.envelope_to_fragment(env)
    with pytest.raises(lin.LineageError, match="ambiguous"):
        lin.bundle_id(env)


@pytest.mark.parametrize("bad", [
    {"v": 2, "lineages": [{"lineage": {"template": "gpumd"}}]},   # unknown v
    {"v": 1, "lineages": []},                                     # empty
    {"v": 1, "lineages": "not a list"},
    {"v": 1},                                                     # missing
    {"lineages": [{"lineage": {"template": "gpumd"}}]},           # no v
])
def test_malformed_envelopes_rejected(bad):
    with pytest.raises(lin.LineageError):
        lin.envelope_to_fragment(bad)


def test_member_with_both_lineage_and_recipe_rejected():
    lineage = _member()["lineage"]
    with pytest.raises(lin.LineageError, match="both"):
        lin.envelope([{"lineage": lineage, "recipe": lineage}])


def test_member_stated_id_mismatch_rejected():
    member = _member()
    member["id"] = "0" * 64
    with pytest.raises(lin.LineageError, match="does not match"):
        lin.envelope([member])


def test_malformed_doc_source_rejected():
    with pytest.raises(lin.LineageError, match="scheme:ref"):
        lin.envelope([_member()], doc={"source": "no-scheme-here"})


def test_malformed_doc_authors_rejected():
    with pytest.raises(lin.LineageError, match="authors"):
        lin.envelope([_member()], doc={"authors": "not a list"})


def test_doc_extra_keys_tolerated():
    env = lin.envelope([_member()], doc={"source": "doi:10.1/x", "note": "extra"})
    assert env["doc"]["note"] == "extra"


# ---- bundle_id -------------------------------------------------------------

def test_bundle_id_is_the_stated_canonical_rule():
    a, b = _member(), _member(material={"name": "Ge"})
    env = lin.envelope([a, b], doc=_doc())
    ids = [lin.lineage_id(a["lineage"]), lin.lineage_id(b["lineage"])]
    payload = json.dumps({"doc": _doc(), "ids": ids},
                         sort_keys=True, separators=(",", ":"))
    assert lin.bundle_id(env) == hashlib.sha256(payload.encode()).hexdigest()


def test_bundle_id_deterministic_and_sensitive():
    a, b = _member(), _member(material={"name": "Ge"})
    env = lin.envelope([a, b], doc=_doc())
    assert lin.bundle_id(env) == lin.bundle_id(lin.envelope([a, b], doc=_doc()))
    # member order matters (ids in order)
    assert lin.bundle_id(env) != lin.bundle_id(lin.envelope([b, a], doc=_doc()))
    # the doc matters (doc-or-null is hashed)
    assert lin.bundle_id(env) != lin.bundle_id(lin.envelope([a, b]))


def test_no_doc_hashes_as_null():
    a = _member()
    env = lin.envelope([a])
    payload = json.dumps({"doc": None, "ids": [lin.lineage_id(a["lineage"])]},
                         sort_keys=True, separators=(",", ":"))
    assert lin.bundle_id(env) == hashlib.sha256(payload.encode()).hexdigest()


# ---- the invariance rules (the load-bearing pins) --------------------------

def test_bundling_never_changes_a_member_id():
    member = _member()
    solo_id = lin.lineage_id(member["lineage"])
    env = lin.envelope([member, _member(material={"name": "Ge"})], doc=_doc())
    back = lin.envelope_from_fragment(lin.envelope_to_fragment(env))
    assert back["lineages"][0]["id"] == solo_id
    assert lin.lineage_id(back["lineages"][0]["lineage"]) == solo_id


def test_doc_source_inheritance_never_enters_a_member_hash():
    # a member with NO source of its own: shared solo vs inside a doc-bearing
    # bundle, the id must be byte-identical (inheritance is read-time only)
    member = _member()
    assert "source" not in member["lineage"]
    solo = lin.envelope_from_fragment(lin.record_to_fragment(member))
    bundled = lin.envelope_from_fragment(
        lin.envelope_to_fragment(lin.envelope([member], doc=_doc())))
    assert solo["lineages"][0]["id"] == bundled["lineages"][0]["id"]
    # and the bundled member's lineage still carries no source key
    assert "source" not in bundled["lineages"][0]["lineage"]


def test_member_own_source_stays_identity_bearing():
    plain = _member()
    sourced = _member(source="paper:si-2021-x")
    assert plain["id"] != sourced["id"]
    env = lin.envelope([sourced], doc=_doc())
    assert env["lineages"][0]["id"] == sourced["id"]


# ---- the proposal emitter (paper parser -> one shareable link) -------------

def _claim(index, node_id="ThermalConductivity", material="Si",
           value_text="148", unit="W/(m K)", kind="value", survives=True,
           duplicate=None, verdict="confirmed", conditions=None):
    return {"index": index, "node_id": node_id, "material": material,
            "value_text": value_text, "unit": unit, "kind": kind,
            "conditions": conditions or {"T": 300},
            "validation": {"survives": survives, "duplicate": duplicate},
            "review": {"verdict": verdict}}


def _proposal(claims):
    return {"paper_slug": "si-2021-demo", "claims": claims}


def test_proposal_envelope_bundles_surviving_value_claims():
    from omai.paper_parser import propose

    prop = _proposal([
        _claim(0),
        _claim(1, material="Ge", value_text="62"),
        _claim(2, kind="condition"),              # context, never minted
        _claim(3, survives=False),                # killed by validation
        _claim(4, duplicate=0),                   # duplicate
        _claim(5, verdict="killed"),              # killed by review
        _claim(6, node_id=None),                  # unmappable
        _claim(7, value_text="not-a-number"),     # non-numeric
    ])
    env = propose.build_envelope_from_proposal(prop)
    assert env["v"] == 1
    assert env["doc"] == {"source": "paper:si-2021-demo"}
    assert len(env["lineages"]) == 2
    # the member lineage is exactly the record_instance shape, so the shared
    # id equals the id apply-time minting would produce
    lineage = env["lineages"][0]["lineage"]
    assert lineage == {"node": "ThermalConductivity", "material": "Si",
                       "conditions": {"T": 300},
                       "values": {"value": 148.0, "units": "W/(m K)"},
                       "source": "paper:si-2021-demo"}
    assert env["lineages"][0]["id"] == lin.lineage_id(lineage)


def test_proposal_envelope_doc_meta_enriches_the_doc():
    from omai.paper_parser import propose

    env = propose.build_envelope_from_proposal(
        _proposal([_claim(0)]),
        doc_meta={"title": "A demo", "year": 2021, "ignored_key": "x"})
    assert env["doc"]["title"] == "A demo"
    assert env["doc"]["year"] == 2021
    assert env["doc"]["source"] == "paper:si-2021-demo"
    assert "ignored_key" not in env["doc"]


def test_proposal_with_nothing_to_bundle_returns_none():
    from omai.paper_parser import propose

    assert propose.build_envelope_from_proposal(
        _proposal([_claim(0, kind="condition")])) is None
    assert propose.proposal_envelope_fragment(
        _proposal([_claim(0, kind="condition")])) is None


def test_proposal_fragment_round_trips_to_the_same_envelope():
    from omai.paper_parser import propose

    prop = _proposal([_claim(0), _claim(1, material="Ge", value_text="62")])
    frag = propose.proposal_envelope_fragment(prop)
    assert lin.envelope_from_fragment(frag) == \
        propose.build_envelope_from_proposal(prop)


# ---- the descriptor states the contract ------------------------------------

def test_format_descriptor_envelope_section_is_consistent():
    d = lin.FORMAT_DESCRIPTOR["envelope"]
    assert d["v"] == lin.ENVELOPE_VERSION == 1
    assert d["keys"] == ["v", "doc", "lineages"]
    assert d["doc"]["keys"] == ["source", "title", "authors", "year", "journal"]
    assert d["bundle_id"]["canonical_json"] == {
        "sort_keys": True, "separators": [",", ":"]}
    assert "doc-or-null" in d["bundle_id"]["rule"]
    assert "ids" in d["bundle_id"]["rule"]
    assert "never" in d["bundle_id"]["member_ids"]
    assert "read/display time only" in d["inheritance"]
    assert "bare record" in d["dual_read"]
