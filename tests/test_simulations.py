"""Tests for the simulation layer (omai/simulations.py).

Recipe identity (the light model: same recipe -> same id; a url, an artifact
pointer, or an execution change does NOT change the id; a recipe change,
including a hyperparameter or setup value, DOES), the light record builder
record_light (a record with no artifacts and no node is valid, flagged
node-unresolved not rejected), the URL round-trip (record_to_fragment ->
record_from_fragment is identity-stable and base64url, and a hand-built fragment
decodes), artifact-pointer well-formedness, the optional mirror `provider` key
(who holds the bytes: outside identity, shape-checked as a string, round-tripping
the fragment, echoed onto the verify report), the heavy checksummed writer's
idempotence and overwrite refusal, the OPTIONAL heavy import path (a no-sha256
bundle now yields a pointer record, not an exception; a full checksummed bundle
verifies), the verify report shapes (offline: a fake fetcher, no network), the
build_simulations bundler (including slug resolution), and the instance
simulation-backref gate in both directions. All hermetic: node identity is
supplied as a fixture name_to_uid or resolved against the live map read-only,
and no test touches the network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omai import simulations as sim

# A fixed fixture map: a recipe node and a result variable with pinned uids. The
# ids are arbitrary 64-hex strings; the point is that the pin must MATCH, not
# that it equals any live value.
_NODE = "ThermalConductivity[transport_model=hnemd]"
_NODE_UID = "e7157a52da5eb7d2ae79e57692acc30d7e63a3a0d1c731b14da4d6ab8fd5eb88"
_NAME_TO_UID = {_NODE: _NODE_UID}

_SHA_A = "a" * 64
_SHA_B = "b" * 64


def _recipe(**over):
    r = {
        "node": _NODE,
        "node_uid": _NODE_UID,
        "material": {"name": "Si"},
        "conditions": {"T": "300 K", "potential": "Si-NEP"},
        "params": {},
    }
    r.update(over)
    return r


def _execution(**over):
    e = {
        "code": "gpumd",
        "code_version": "3.9.5",
        "container_digest": "sha256:" + ("c" * 64),
        "runner": "mcg-cloud/pod-abc",
        "wall_time_s": 4210,
        "seeds": [12345],
    }
    e.update(over)
    return e


def _artifacts(**over):
    a = [{"path": "results/thermal_summary.json", "bytes": 2048,
          "sha256": _SHA_A, "role": "result"},
         {"path": "traj/dump.xyz", "bytes": 88123456, "sha256": _SHA_B,
          "role": "trajectory"}]
    if over.get("single"):
        return a[:1]
    return a


# --------------------------------------------------------------------------
# Recipe identity (the light model: the id is the recipe alone).
# --------------------------------------------------------------------------

def test_same_recipe_same_id():
    a = sim.recipe_id(_recipe())
    b = sim.recipe_id(_recipe())
    assert a == b
    assert len(a) == 64


def test_canonical_id_is_recipe_only():
    """The back-compatible canonical_id(recipe, execution, artifacts) hashes the
    RECIPE alone: execution and artifacts are accepted but ignored, so it agrees
    with recipe_id and never folds either into identity."""
    assert (sim.canonical_id(_recipe(), _execution(), _artifacts())
            == sim.recipe_id(_recipe()))
    # A different execution / different artifacts, same recipe -> same id.
    assert (sim.canonical_id(_recipe(), _execution(wall_time_s=9999), [])
            == sim.recipe_id(_recipe()))


def test_url_change_does_not_change_id():
    """Location is out of identity: an artifact url (or any resolver-layer key)
    never perturbs the recipe id."""
    base = sim.recipe_id(_recipe())
    arts = _artifacts()
    arts[0]["url"] = "https://r2.example.com/runs/abc/thermal_summary.json"
    arts[1]["url"] = "https://zenodo.org/record/12345/files/dump.xyz"
    # Artifacts are not part of identity at all; the id is the recipe.
    assert sim.canonical_id(_recipe(), _execution(), arts) == base


def test_recipe_change_changes_id():
    base = sim.recipe_id(_recipe())
    other = sim.recipe_id(_recipe(conditions={"T": "500 K"}))
    assert other != base


def test_artifact_change_does_not_change_id():
    """Artifacts NEVER enter identity: changing a checksum, adding, or removing
    a pointer leaves the recipe id unchanged (the light model's core promise)."""
    base = sim.recipe_id(_recipe())
    arts = _artifacts()
    arts[0]["sha256"] = "f" * 64
    assert sim.canonical_id(_recipe(), _execution(), arts) == base
    assert sim.canonical_id(_recipe(), _execution(), []) == base


def test_execution_change_does_not_change_id():
    """Execution rides outside identity: a different wall time, seed, or code
    version is the same experiment recipe and mints the same id."""
    base = sim.recipe_id(_recipe())
    assert sim.canonical_id(_recipe(), _execution(wall_time_s=4210.5), []) == base
    assert sim.canonical_id(_recipe(), _execution(seeds=[999]), []) == base


def test_float_conditions_round_to_one_identity():
    """Refetch-level float noise in conditions collapses to one id; a
    physically distinct value does not."""
    noisy = _recipe(conditions={"T": 300.0000001, "fmax": 0.05})
    clean = _recipe(conditions={"T": 300.0, "fmax": 0.05})
    assert sim.recipe_id(noisy) == sim.recipe_id(clean)
    distinct = _recipe(conditions={"T": 301.0, "fmax": 0.05})
    assert sim.recipe_id(distinct) != sim.recipe_id(clean)


def test_hyperparameters_and_values_round_and_matter():
    """hyperparameters and setup values are recipe scalars: their floats round
    to one identity, and a distinct value changes the id (they are part of the
    recipe, unlike a url or an execution stamp)."""
    noisy = _recipe(hyperparameters={"cutoff": 8.0000001},
                    values={"pressure_GPa": 1.0000001})
    clean = _recipe(hyperparameters={"cutoff": 8.0},
                    values={"pressure_GPa": 1.0})
    assert sim.recipe_id(noisy) == sim.recipe_id(clean)
    other = _recipe(hyperparameters={"cutoff": 9.0},
                    values={"pressure_GPa": 1.0})
    assert sim.recipe_id(other) != sim.recipe_id(clean)


# --------------------------------------------------------------------------
# Writer: idempotence and overwrite refusal.
# --------------------------------------------------------------------------

def test_record_simulation_writes_and_is_idempotent(tmp_path):
    p1 = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    # A byte-identical re-record returns the SAME path, no second file.
    p2 = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    assert p1 == p2
    assert len(list(tmp_path.glob("*.json"))) == 1
    rec = json.loads(p1.read_text())
    assert rec["id"] == sim.canonical_id(_recipe(), _execution(), _artifacts())
    assert rec["recipe"]["node"] == _NODE


def test_record_simulation_stores_id_and_manifest(tmp_path):
    rec_id = sim.canonical_id(_recipe(), _execution(), _artifacts())
    path = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    rec = json.loads(path.read_text())
    assert rec["id"] == rec_id
    # The manifest keeps exactly the four hashed keys per entry (no url when no
    # mirror was declared).
    for art in rec["artifacts"]:
        assert set(art) == {"path", "bytes", "sha256", "role"}


def test_overwrite_refusal_on_different_content(tmp_path, monkeypatch):
    """Two DIFFERENT records that slug to the same base must not clobber each
    other: the record_instance discipline. Force a slug collision by pinning
    slugify to a constant, so distinct ids land a numeric suffix instead of an
    overwrite."""
    monkeypatch.setattr(sim, "slugify", lambda *_a, **_k: "collide")
    p1 = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    p2 = sim.record_simulation(
        recipe=_recipe(conditions={"T": "500 K"}), execution=_execution(),
        artifacts=_artifacts(), sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    assert p1 != p2
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_mirrors_ride_outside_the_hash_and_mirror_urls(tmp_path):
    mirrors = {"results/thermal_summary.json":
               {"url": "https://r2.example.com/x.json", "store": "r2"}}
    rec_id_no_mirror = sim.canonical_id(_recipe(), _execution(), _artifacts())
    path = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        mirrors=mirrors, sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    rec = json.loads(path.read_text())
    # The id is the same as without any mirror: location is not identity.
    assert rec["id"] == rec_id_no_mirror
    assert rec["mirrors"] == mirrors
    # The mirrored url appears on the matching artifact row as a convenience.
    row = next(a for a in rec["artifacts"]
               if a["path"] == "results/thermal_summary.json")
    assert row["url"] == "https://r2.example.com/x.json"


# --------------------------------------------------------------------------
# Validation failures.
# --------------------------------------------------------------------------

def test_bad_node_uid_pin_rejected(tmp_path):
    with pytest.raises(sim.SimulationError, match="node_uid"):
        sim.record_simulation(
            recipe=_recipe(node_uid="0" * 64), execution=_execution(),
            artifacts=_artifacts(), sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


def test_unknown_node_rejected(tmp_path):
    with pytest.raises(sim.SimulationError, match="live map node"):
        sim.record_simulation(
            recipe=_recipe(node="NotANode", node_uid=None),
            execution=_execution(), artifacts=_artifacts(),
            sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


def test_unknown_configuration_rejected(tmp_path):
    """A recipe naming a configuration uid absent from docs/data/configurations/
    fails, but the check reads the REAL configurations dir; point it at an empty
    one so a missing record is deterministic."""
    empty_cfg = tmp_path / "cfg"
    empty_cfg.mkdir()
    recipe = _recipe(material={"name": "Si", "configuration": "sha256:" + "9" * 64})
    with pytest.raises(sim.SimulationError, match="configuration"):
        sim._validate(
            {"recipe": recipe, "execution": _execution(),
             "artifacts": _artifacts()},
            name_to_uid=_NAME_TO_UID, config_dir=empty_cfg, where="t")


def test_known_configuration_accepted(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    uid = "9" * 64
    (cfg / "si.json").write_text(json.dumps({"canonical": {"uid": uid}}))
    recipe = _recipe(material={"name": "Si", "configuration": uid})
    # Should not raise: the configuration resolves.
    sim._validate(
        {"recipe": recipe, "execution": _execution(), "artifacts": _artifacts()},
        name_to_uid=_NAME_TO_UID, config_dir=cfg, where="t")


@pytest.mark.parametrize("bad", [
    {"path": "", "bytes": 10, "sha256": _SHA_A, "role": "result"},
    {"path": "x", "bytes": 0, "sha256": _SHA_A, "role": "result"},
    {"path": "x", "bytes": -1, "sha256": _SHA_A, "role": "result"},
    {"path": "x", "bytes": 10, "sha256": "tooshort", "role": "result"},
    {"path": "x", "bytes": 10, "sha256": _SHA_A, "role": ""},
    {"path": "x", "bytes": True, "sha256": _SHA_A, "role": "result"},
])
def test_malformed_manifest_rejected(tmp_path, bad):
    with pytest.raises(sim.SimulationError, match="artifact"):
        sim.record_simulation(
            recipe=_recipe(), execution=_execution(), artifacts=[bad],
            sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


def test_result_backref_mismatch_rejected(tmp_path):
    """An inline result stub whose simulation backref is not this record's id is
    rejected: the run owns the values it produced."""
    good_id = sim.canonical_id(_recipe(), _execution(), _artifacts())
    stub = {"variable": _NODE, "material": "Si",
            "conditions": {"T": "300 K"}, "value": 1.37, "units": "W/(m K)",
            "source": {"kind": "simulation", "ref": "gpumd", "detail": "HNEMD"},
            "simulation": "0" * 64}  # wrong backref
    assert stub["simulation"] != good_id
    with pytest.raises(sim.SimulationError, match="backref"):
        sim.record_simulation(
            recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
            results=[stub], sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


def test_result_stub_with_correct_backref_accepted(tmp_path):
    rec_id = sim.canonical_id(_recipe(), _execution(), _artifacts())
    stub = {"variable": _NODE, "material": "Si",
            "conditions": {"T": "300 K"}, "value": 1.37, "units": "W/(m K)",
            "source": {"kind": "simulation", "ref": "gpumd", "detail": "HNEMD"},
            "simulation": rec_id}
    path = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        results=[stub], sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    rec = json.loads(path.read_text())
    assert rec["results"][0]["simulation"] == rec_id


def test_result_stub_missing_conditions_rejected(tmp_path):
    """The instance contract (build_instances) requires conditions; an inline
    stub is held to the same bar, so a stub that would be refused as an
    instance file cannot ride into a simulation record either."""
    rec_id = sim.canonical_id(_recipe(), _execution(), _artifacts())
    stub = {"variable": _NODE, "material": "Si", "value": 1.37,
            "units": "W/(m K)",
            "source": {"kind": "simulation", "ref": "gpumd", "detail": "HNEMD"},
            "simulation": rec_id}  # no conditions
    with pytest.raises(sim.SimulationError, match="conditions"):
        sim.record_simulation(
            recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
            results=[stub], sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


@pytest.mark.parametrize("bad_exec", [
    None,
    "gpumd",
    {},
    {"code": ""},
    {"code": 3},
    {"code_version": "3.9.5"},
])
def test_malformed_execution_rejected(tmp_path, bad_exec):
    """The execution block is the record's "what ran" claim: it must be an
    object naming the code that ran. A null, bare-string, or code-less block is
    degenerate and fails the gate (the manifest well-formedness bar applied to
    execution)."""
    with pytest.raises(sim.SimulationError, match="execution"):
        sim.record_simulation(
            recipe=_recipe(), execution=bad_exec, artifacts=_artifacts(),
            sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)


def test_result_backref_slug_string_accepted(tmp_path):
    """A bare backref slug (a pointer to a committed instance file) is a legal
    result entry; its own backref is checked where that instance is bundled."""
    path = sim.record_simulation(
        recipe=_recipe(), execution=_execution(), artifacts=_artifacts(),
        results=["si-thermalconductivity-gpumd-hnemd"],
        sim_dir=tmp_path, name_to_uid=_NAME_TO_UID)
    rec = json.loads(path.read_text())
    assert rec["results"] == ["si-thermalconductivity-gpumd-hnemd"]


def test_stated_id_mismatch_rejected(tmp_path):
    """A record whose stated id does not recompute from its claim (e.g. someone
    folded a url into the hash) is rejected."""
    with pytest.raises(sim.SimulationError, match="recomputed"):
        sim._validate(
            {"id": "0" * 64, "recipe": _recipe(), "execution": _execution(),
             "artifacts": _artifacts()},
            name_to_uid=_NAME_TO_UID, config_dir=tmp_path, where="t")


# --------------------------------------------------------------------------
# verify_simulation: a dated report, never a gate (offline, fake fetcher).
# --------------------------------------------------------------------------

def _record_for_verify():
    return {
        "id": "deadbeef",
        "artifacts": [
            {"path": "a.json", "bytes": 3, "sha256":
             __import__("hashlib").sha256(b"abc").hexdigest(), "role": "result"},
            {"path": "b.bin", "bytes": 3, "sha256": _SHA_B, "role": "trajectory"},
            {"path": "c.txt", "bytes": 3, "sha256": _SHA_A, "role": "log"},
        ],
        "mirrors": {
            "a.json": {"url": "https://x/a.json"},
            "b.bin": {"url": "https://x/b.bin"},
            # c.txt has NO mirror -> no-url
        },
    }


def test_verify_report_shape_ok_mismatch_and_unreachable():
    import datetime

    rec = _record_for_verify()

    def fetcher(url):
        if url.endswith("a.json"):
            return b"abc"          # sha matches -> ok
        if url.endswith("b.bin"):
            return b"xyz"          # sha differs -> mismatch
        raise RuntimeError("boom")

    report = sim.verify_simulation(rec, fetcher=fetcher,
                                   today=datetime.date(2026, 7, 13))
    assert report["id"] == "deadbeef"
    assert report["date"] == "2026-07-13"
    by_path = {c["path"]: c for c in report["checked"]}
    assert by_path["a.json"]["status"] == "ok"
    assert by_path["b.bin"]["status"] == "mismatch"
    assert by_path["b.bin"]["expected"] == _SHA_B
    assert by_path["c.txt"]["status"] == "no-url"


def test_verify_unreachable_url_no_network():
    """The required case: an unreachable url is reported unreachable, never
    raised, never a gate."""
    import datetime

    rec = _record_for_verify()

    def down(url):
        raise ConnectionError("host unreachable")

    report = sim.verify_simulation(rec, fetcher=down,
                                   today=datetime.date(2026, 7, 13))
    statuses = {c["path"]: c["status"] for c in report["checked"]}
    assert statuses["a.json"] == "unreachable"
    assert statuses["b.bin"] == "unreachable"
    assert statuses["c.txt"] == "no-url"
    # Never raised: verify is a report.
    assert report["date"] == "2026-07-13"


def test_verify_without_fetcher_reports_unreachable():
    rec = _record_for_verify()
    report = sim.verify_simulation(rec)
    urlful = [c for c in report["checked"] if c["url"] is not None]
    assert urlful and all(c["status"] == "unreachable" for c in urlful)
    assert all(c.get("reason") == "no fetcher" for c in urlful)


# --------------------------------------------------------------------------
# build_simulations bundler and the instance backref passthrough.
# --------------------------------------------------------------------------

def test_build_simulations_bundles_and_pins_node_uid(tmp_path):
    """A written record round-trips through build_simulations, is pinned to the
    LIVE recipe-node uid, and carries its file. Uses a real live node so the
    bundler's live-map resolution agrees with the record's pin."""
    from omai.map_data import _domains, build_graph_dict, build_simulations

    live = {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}
    node = "ThermalConductivity[transport_model=hnemd]"
    recipe = _recipe(node=node, node_uid=live[node])
    sim.record_simulation(
        recipe=recipe, execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=live)
    bundle = build_simulations(tmp_path)
    assert len(bundle) == 1
    entry = bundle[0]
    assert entry["node_uid"] == live[node]
    assert entry["file"].endswith(".json")
    assert entry["id"] == sim.canonical_id(recipe, _execution(), _artifacts())


def test_build_simulations_empty_dir_returns_empty(tmp_path):
    from omai.map_data import build_simulations

    assert build_simulations(tmp_path) == []


# --------------------------------------------------------------------------
# The backref loop, record -> instance: a result slug must resolve at bundle
# time to a committed instance that backrefs the record.
# --------------------------------------------------------------------------

def _live_uids():
    from omai.map_data import _domains, build_graph_dict

    return {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}


_LIVE_NODE = "ThermalConductivity[transport_model=hnemd]"


def _record_and_instance(tmp_path, *, backref=None, slug=None):
    """Write one simulation record (results=[slug]) into tmp_path/sims and one
    instance into tmp_path/insts carrying ``backref`` (default: the record's
    id). Returns (sims_dir, insts_dir, record_id, instance_slug)."""
    from omai.map_data import _domains, record_instance

    live = _live_uids()
    recipe = _recipe(node=_LIVE_NODE, node_uid=live[_LIVE_NODE])
    rec_id = sim.canonical_id(recipe, _execution(), _artifacts())
    sims, insts = tmp_path / "sims", tmp_path / "insts"
    inst_path = record_instance(
        domains=_domains(), variable=_LIVE_NODE, material="Si", value=1.37,
        units="W/(m K)", source_kind="simulation", source_ref="gpumd",
        detail="HNEMD bulk Si", simulation=backref or rec_id,
        instances_dir=insts)
    sim.record_simulation(
        recipe=recipe, execution=_execution(), artifacts=_artifacts(),
        results=[slug or inst_path.stem], sim_dir=sims, name_to_uid=live)
    return sims, insts, rec_id, inst_path.stem


def test_bundler_resolves_result_slugs_and_their_backrefs(tmp_path):
    """The good path: a record whose result slug names a committed instance
    that backrefs it bundles cleanly and carries the slug through."""
    from omai.map_data import build_simulations

    sims, insts, rec_id, slug = _record_and_instance(tmp_path)
    bundle = build_simulations(sims, instances_dir=insts)
    assert len(bundle) == 1
    assert bundle[0]["id"] == rec_id
    assert bundle[0]["results"] == [slug]


def test_bundler_refuses_a_dangling_result_slug(tmp_path):
    """A record citing an instance file the commons does not hold must not
    enter simulations.json. The WRITER accepts the bare slug (results sit
    outside the hashed claim and may land after the record); the BUNDLER is the
    gate."""
    from omai.map_data import build_simulations

    sims, insts, _rec_id, _slug = _record_and_instance(
        tmp_path, slug="no-such-instance")
    with pytest.raises(sim.SimulationError, match="no committed instance"):
        build_simulations(sims, instances_dir=insts)


def test_bundler_refuses_a_slug_whose_instance_backrefs_another_run(tmp_path):
    """The cited instance exists but names a different run: the loop must not
    close on someone else's record."""
    from omai.map_data import build_simulations

    sims, insts, _rec_id, _slug = _record_and_instance(
        tmp_path, backref="0" * 64)
    with pytest.raises(sim.SimulationError, match="does not backref"):
        build_simulations(sims, instances_dir=insts)


# --------------------------------------------------------------------------
# The backref loop, instance -> record: shape at record_instance, membership
# against the committed record ids at build_instances.
# --------------------------------------------------------------------------

def test_instance_carries_simulation_backref(tmp_path):
    """record_instance writes the simulation key only when set (the
    configuration-field precedent), and the bundler checks it against the
    committed record ids and carries it through."""
    from omai.map_data import _domains, build_instances, record_instance

    live = _live_uids()
    sims, insts = tmp_path / "sims", tmp_path / "insts"
    recipe = _recipe(node=_LIVE_NODE, node_uid=live[_LIVE_NODE])
    rec_path = sim.record_simulation(
        recipe=recipe, execution=_execution(), artifacts=_artifacts(),
        sim_dir=sims, name_to_uid=live)
    rec_id = json.loads(rec_path.read_text())["id"]
    path = record_instance(
        domains=_domains(), variable=_LIVE_NODE, material="Si",
        value=1.37, units="W/(m K)", source_kind="simulation",
        source_ref="gpumd", detail="HNEMD bulk Si", simulation=rec_id,
        instances_dir=insts)
    rec = json.loads(path.read_text())
    assert rec["simulation"] == rec_id
    bundle = build_instances(insts, simulations_dir=sims)
    assert bundle[0]["simulation"] == rec_id


def test_record_instance_refuses_malformed_backref(tmp_path):
    """A record id is a sha256: anything that is not 64 hex characters can
    never resolve, so the writer refuses it outright."""
    from omai.map_data import _domains, record_instance

    with pytest.raises(ValueError, match="64-hex"):
        record_instance(
            domains=_domains(), variable=_LIVE_NODE, material="Si",
            value=1.37, units="W/(m K)", source_kind="simulation",
            source_ref="gpumd", detail="bad backref", simulation="s" * 64,
            instances_dir=tmp_path)


def _handwritten_instance(insts, backref):
    insts.mkdir(parents=True, exist_ok=True)
    (insts / "si-thermalconductivity-gpumd.json").write_text(json.dumps({
        "variable": _LIVE_NODE, "material": "Si",
        "conditions": {"T": "300 K"}, "value": 1.37, "units": "W/(m K)",
        "uncertainty": None,
        "source": {"kind": "simulation", "ref": "gpumd", "detail": "HNEMD"},
        "simulation": backref}))


def test_build_instances_refuses_backref_to_uncommitted_record(tmp_path):
    """An instance citing a well-formed record id that no committed simulation
    record carries is a dangling citation: the bundler refuses it."""
    from omai.map_data import build_instances

    insts = tmp_path / "insts"
    _handwritten_instance(insts, "a" * 64)
    with pytest.raises(ValueError, match="matches no committed"):
        build_instances(insts, simulations_dir=tmp_path / "sims-empty")


def test_build_instances_refuses_malformed_backref(tmp_path):
    """A hand-written instance file with a non-sha256 backref fails the shape
    check before any membership lookup."""
    from omai.map_data import build_instances

    insts = tmp_path / "insts"
    _handwritten_instance(insts, "s" * 64)
    with pytest.raises(ValueError, match="64-hex"):
        build_instances(insts, simulations_dir=tmp_path / "sims-empty")


def test_committed_ids_reads_the_record_ids(tmp_path):
    assert sim.committed_ids(tmp_path / "nowhere") == set()
    live = _live_uids()
    recipe = _recipe(node=_LIVE_NODE, node_uid=live[_LIVE_NODE])
    rec_path = sim.record_simulation(
        recipe=recipe, execution=_execution(), artifacts=_artifacts(),
        sim_dir=tmp_path, name_to_uid=live)
    rec_id = json.loads(rec_path.read_text())["id"]
    assert sim.committed_ids(tmp_path) == {rec_id}


def test_instance_without_simulation_omits_key(tmp_path):
    from omai.map_data import _domains, record_instance

    doms = _domains()
    node = "ThermalConductivity[transport_model=hnemd]"
    path = record_instance(
        domains=doms, variable=node, material="Si",
        value=1.37, units="W/(m K)", source_kind="simulation",
        source_ref="gpumd", detail="no backref", instances_dir=tmp_path)
    rec = json.loads(path.read_text())
    assert "simulation" not in rec


# --------------------------------------------------------------------------
# Import: a hosted MCG-shape bundle -> a verified record (record_from_bundle).
# The reciprocal of the host's export; refuses an unverifiable bundle rather
# than mint a null-checksum record. All offline (real bytes hashed in-process).
# --------------------------------------------------------------------------

import hashlib  # noqa: E402  (import-half tests hash real bytes offline)

# Two artifact bodies with their real checksums: the well-formed MCG export
# carries a sha256 and a role per file (the companion PR's manifest shape).
_BODY_RESULT = b'{"kappa": 1.37, "units": "W/(m K)"}'
_BODY_TRAJ = b"HNEMD trajectory frames ..."
_SHA_RESULT = hashlib.sha256(_BODY_RESULT).hexdigest()
_SHA_TRAJ = hashlib.sha256(_BODY_TRAJ).hexdigest()


def _bundle(**over):
    """A realistic MCG export manifest: name/kind/template/spec, ISO
    timestamps, a current stage, headline outputs, and artifacts each carrying
    {path, bytes, sha256, role}. The spec names a real live map node so the
    resulting recipe resolves (the enriched-spec case)."""
    m = {
        "name": "Si HNEMD (local)",
        "kind": "composite_kappa",
        "template": "gpumd",
        "spec": {
            "node": _NODE,
            "material": {"name": "Si"},
            "conditions": {"T": "300 K", "potential": "Si-NEP"},
            "params": {},
        },
        "created_at": "2026-07-13T10:00:00+00:00",
        "started_at": "2026-07-13T10:00:00+00:00",
        "finished_at": "2026-07-13T11:10:10+00:00",
        "current_stage": "thermal_summary",
        "outputs": {"thermal_summary": {"kappa": 1.37, "units": "W/(m K)"}},
        "artifacts": [
            {"path": "results/thermal_summary.json", "bytes": len(_BODY_RESULT),
             "sha256": _SHA_RESULT, "role": "result"},
            {"path": "traj/dump.xyz", "bytes": len(_BODY_TRAJ),
             "sha256": _SHA_TRAJ, "role": "trajectory"},
        ],
        "skipped_artifacts": [],
    }
    m.update(over)
    return m


def test_record_from_bundle_builds_stable_record():
    """A well-formed MCG-shape manifest becomes a record whose id is stable
    (same manifest -> same id) and whose id is the recipe alone."""
    r1 = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    r2 = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    assert r1["id"] == r2["id"]
    assert len(r1["id"]) == 64
    # The recipe lifts the spec's node and pins the live uid.
    assert r1["recipe"]["node"] == _NODE
    assert r1["recipe"]["node_uid"] == _NODE_UID
    assert r1["recipe"]["spec"]["material"] == {"name": "Si"}
    # Execution maps template -> code, timestamps, and derives wall time.
    assert r1["execution"]["code"] == "gpumd"
    assert r1["execution"]["current_stage"] == "thermal_summary"
    assert r1["execution"]["wall_time_s"] == 4210.0  # 70 min 10 s
    # Identity is the recipe alone.
    assert r1["id"] == sim.recipe_id(r1["recipe"])


def test_record_from_bundle_artifacts_are_pointers_outside_identity():
    """Bundle artifacts are stored as POINTERS {path, role, sha256?, bytes?,
    url?}, and none of it enters identity: the recipe id is unchanged whether the
    artifacts carry checksums or not."""
    rec = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    for art in rec["artifacts"]:
        assert art["path"] and art["role"]
        assert set(art) <= {"path", "role", "url", "sha256", "bytes"}
    # Identity is the recipe; the checksummed pointers do not enter it.
    assert rec["id"] == sim.recipe_id(rec["recipe"])


def test_record_from_bundle_validates_light_against_live_map():
    """The record record_from_bundle produces passes the LIGHT validator against
    the LIVE map (node resolves by id and uid pin, pointers well-formed): the
    import writer and the light gate agree on the shape."""
    from pathlib import Path

    from omai.map_data import _domains, build_graph_dict

    live = {n["id"]: n["uid"] for n in build_graph_dict(_domains())["nodes"]}
    # Rebuild against the live uid so the pin matches this checkout's node.
    man = _bundle(spec={"node": _NODE, "material": {"name": "Si"},
                        "conditions": {"T": "300 K"}, "params": {}})
    rec = sim.record_from_bundle(man, name_to_uid=live)
    report = sim.validate_light(rec, name_to_uid=live,
                                config_dir=Path("docs/data/configurations"),
                                where="bundle")
    assert report["id"] == rec["id"]
    assert report["node_resolved"] is True


def test_record_from_bundle_no_sha256_yields_pointer_record():
    """The corrected model: an unsummed bundle (artifacts {path, bytes} only, no
    sha256) is NO LONGER refused. It yields a valid record whose artifact is a
    plain pointer (a defaulted role, no sha256, outside identity)."""
    old = _bundle(artifacts=[{"path": "results/thermal_summary.json",
                              "bytes": len(_BODY_RESULT)}])
    rec = sim.record_from_bundle(old, name_to_uid=_NAME_TO_UID)
    assert rec["id"] == sim.recipe_id(rec["recipe"])
    art = rec["artifacts"][0]
    assert art["path"] == "results/thermal_summary.json"
    assert art["role"] == "artifact"          # defaulted, not rejected
    assert "sha256" not in art                # unsummed: a plain pointer
    # It validates as a light record (pointer well-formed, node resolves).
    report = sim.validate_light(rec, name_to_uid=_NAME_TO_UID, where="bundle")
    assert report["id"] == rec["id"]


def test_record_from_bundle_mixed_sha256_keeps_the_summed_pointer():
    """A bundle with one summed and one unsummed artifact keeps the sha256 on the
    summed pointer and drops it from the other; both are pointers, neither is in
    identity."""
    man = _bundle(artifacts=[
        {"path": "results/thermal_summary.json", "bytes": len(_BODY_RESULT),
         "sha256": _SHA_RESULT, "role": "result"},
        {"path": "traj/dump.xyz", "bytes": len(_BODY_TRAJ)},   # no sha256/role
    ])
    rec = sim.record_from_bundle(man, name_to_uid=_NAME_TO_UID)
    by_path = {a["path"]: a for a in rec["artifacts"]}
    assert by_path["results/thermal_summary.json"]["sha256"] == _SHA_RESULT
    assert by_path["results/thermal_summary.json"]["role"] == "result"
    assert "sha256" not in by_path["traj/dump.xyz"]
    assert by_path["traj/dump.xyz"]["role"] == "artifact"
    assert rec["id"] == sim.recipe_id(rec["recipe"])


def test_record_from_bundle_mirror_does_not_change_id():
    """Identity excludes location: adding or changing a mirror url never
    re-mints the record id (the same url-invariance the recipe id holds)."""
    base = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)["id"]
    mirrors = {"results/thermal_summary.json":
               {"url": "https://r2.example.com/x.json", "store": "r2"}}
    with_mirror = sim.record_from_bundle(
        _bundle(), mirrors=mirrors, name_to_uid=_NAME_TO_UID)
    assert with_mirror["id"] == base
    assert with_mirror["mirrors"] == mirrors
    # The mirrored url appears on the matching artifact pointer as a convenience.
    row = next(a for a in with_mirror["artifacts"]
               if a["path"] == "results/thermal_summary.json")
    assert row["url"] == "https://r2.example.com/x.json"
    # A DIFFERENT mirror url still mints the same id.
    other = sim.record_from_bundle(
        _bundle(), mirrors={"results/thermal_summary.json":
                            {"url": "https://zenodo.org/record/9/files/x.json"}},
        name_to_uid=_NAME_TO_UID)
    assert other["id"] == base


def test_record_from_bundle_outputs_ride_outside_the_claim():
    """The bundle's headline outputs are what the run PRODUCED, not the recipe
    it was asked: they ride outside the hashed claim (like mirrors), so they
    neither pollute the recipe identity nor pretend to be validated instance
    stubs under 'results'."""
    rec = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    assert rec["outputs"] == {"thermal_summary": {"kappa": 1.37,
                                                  "units": "W/(m K)"}}
    assert "results" not in rec
    # Changing only the outputs does NOT change the id (identity is the claim).
    changed = _bundle(outputs={"thermal_summary": {"kappa": 9.99}})
    assert sim.record_from_bundle(changed, name_to_uid=_NAME_TO_UID)["id"] \
        == rec["id"]


def test_record_from_bundle_omits_wall_time_when_unparseable():
    """wall_time_s is derived only when both timestamps parse as ISO; a bundle
    whose timestamps do not parse carries no wall time (never guessed)."""
    man = _bundle(started_at="not-a-timestamp", finished_at="also-not")
    rec = sim.record_from_bundle(man, name_to_uid=_NAME_TO_UID)
    assert "wall_time_s" not in rec["execution"]
    # The raw strings are still carried through as the run's stated stamps.
    assert rec["execution"]["started_at"] == "not-a-timestamp"


def test_record_from_bundle_no_node_is_flagged_not_invented():
    """A bundle whose spec names NO map node (the common MCG case: specs carry
    template physics, not a map node id) is still recorded, but the writer does
    NOT invent a node. The light validator FLAGS it node-unresolved (valid, not
    rejected): the honesty rule, whatever we have."""
    # A real MCG-style spec: template physics params, no 'node'.
    man = _bundle(spec={"temperature_K": 300.0, "potential": "Si-NEP"})
    rec = sim.record_from_bundle(man, name_to_uid=_NAME_TO_UID)
    assert "node" not in rec["recipe"]
    assert "node_uid" not in rec["recipe"]
    # The spec is kept verbatim so nothing the host asked is dropped.
    assert rec["recipe"]["spec"] == {"temperature_K": 300.0, "potential": "Si-NEP"}
    # The record is VALID and flagged node-unresolved, not rejected.
    report = sim.validate_light(rec, name_to_uid=_NAME_TO_UID, where="bundle")
    assert report["node_resolved"] is False
    assert report["node"] is None
    assert report["id"] == rec["id"]


# --------------------------------------------------------------------------
# verify_bundle_bytes: a dated byte-vs-checksum report, never a gate. Fully
# offline (real temp files, or an injected fake fetcher; no network).
# --------------------------------------------------------------------------

def test_verify_bundle_bytes_local_ok(tmp_path):
    """Local artifact_dir whose bytes hash to the manifest sha256 reports ok."""
    import datetime

    rec = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "thermal_summary.json").write_bytes(_BODY_RESULT)
    (tmp_path / "traj").mkdir()
    (tmp_path / "traj" / "dump.xyz").write_bytes(_BODY_TRAJ)
    report = sim.verify_bundle_bytes(rec, artifact_dir=tmp_path,
                                     today=datetime.date(2026, 7, 13))
    assert report["id"] == rec["id"]
    assert report["date"] == "2026-07-13"
    by_path = {c["path"]: c for c in report["checked"]}
    assert by_path["results/thermal_summary.json"]["status"] == "ok"
    assert by_path["traj/dump.xyz"]["status"] == "ok"
    assert report["summary"] == {"ok": 2, "mismatch": 0, "unchecked": 0}


def test_verify_bundle_bytes_tampered_reports_mismatch_not_raise(tmp_path):
    """Tampered local bytes are reported mismatch (with expected/actual), never
    raised: verify is a report, never a gate."""
    rec = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "thermal_summary.json").write_bytes(b"TAMPERED")
    # traj file absent -> unchecked; the result file present but wrong -> mismatch
    report = sim.verify_bundle_bytes(rec, artifact_dir=tmp_path)
    by_path = {c["path"]: c for c in report["checked"]}
    bad = by_path["results/thermal_summary.json"]
    assert bad["status"] == "mismatch"
    assert bad["expected"] == _SHA_RESULT
    assert bad["actual"] == hashlib.sha256(b"TAMPERED").hexdigest()
    assert by_path["traj/dump.xyz"]["status"] == "unchecked"
    assert report["summary"] == {"ok": 0, "mismatch": 1, "unchecked": 1}


def test_verify_bundle_bytes_no_dir_no_fetcher_reports_unchecked():
    """No artifact_dir and no fetcher: every artifact is unchecked with reason
    'bytes not reachable'. Never raises."""
    rec = sim.record_from_bundle(_bundle(), name_to_uid=_NAME_TO_UID)
    report = sim.verify_bundle_bytes(rec)
    assert all(c["status"] == "unchecked" for c in report["checked"])
    assert all(c["reason"] == "bytes not reachable" for c in report["checked"])
    assert report["summary"] == {"ok": 0, "mismatch": 0, "unchecked": 2}


def test_verify_bundle_bytes_fetcher_ok_and_mismatch():
    """With no local dir but a fetcher and mirror urls, bytes are fetched and
    compared: ok on match, mismatch on differ, unchecked on a fetch failure.
    Offline: the fetcher is a fake, no network."""
    mirrors = {
        "results/thermal_summary.json": {"url": "https://x/summary.json"},
        "traj/dump.xyz": {"url": "https://x/dump.xyz"},
    }
    rec = sim.record_from_bundle(_bundle(), mirrors=mirrors,
                                 name_to_uid=_NAME_TO_UID)

    def fetcher(url):
        if url.endswith("summary.json"):
            return _BODY_RESULT              # matches -> ok
        if url.endswith("dump.xyz"):
            return b"corrupted-in-transit"   # differs -> mismatch
        raise RuntimeError("boom")

    report = sim.verify_bundle_bytes(rec, fetcher=fetcher)
    by_path = {c["path"]: c for c in report["checked"]}
    assert by_path["results/thermal_summary.json"]["status"] == "ok"
    assert by_path["results/thermal_summary.json"]["source"] == "https://x/summary.json"
    assert by_path["traj/dump.xyz"]["status"] == "mismatch"
    assert report["summary"] == {"ok": 1, "mismatch": 1, "unchecked": 0}


def test_verify_bundle_bytes_fetch_failure_is_unchecked_not_raised():
    """A fetch that raises is reported unchecked (reason carries the error),
    never propagated: the report philosophy of verify_simulation."""
    mirrors = {"results/thermal_summary.json": {"url": "https://x/summary.json"},
               "traj/dump.xyz": {"url": "https://x/dump.xyz"}}
    rec = sim.record_from_bundle(_bundle(), mirrors=mirrors,
                                 name_to_uid=_NAME_TO_UID)

    def down(url):
        raise ConnectionError("host unreachable")

    report = sim.verify_bundle_bytes(rec, fetcher=down)
    assert all(c["status"] == "unchecked" for c in report["checked"])
    assert all("host unreachable" in c["reason"] for c in report["checked"])


def test_verify_bundle_bytes_local_wins_over_fetcher(tmp_path):
    """When both a local file and a fetcher can reach a path, the local copy is
    the authoritative check (the fetcher is not consulted for that path)."""
    mirrors = {"results/thermal_summary.json": {"url": "https://x/summary.json"}}
    rec = sim.record_from_bundle(_bundle(), mirrors=mirrors,
                                 name_to_uid=_NAME_TO_UID)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "thermal_summary.json").write_bytes(_BODY_RESULT)

    def poisoned(url):
        raise AssertionError("fetcher must not be called when local bytes exist")

    report = sim.verify_bundle_bytes(rec, artifact_dir=tmp_path, fetcher=poisoned)
    by_path = {c["path"]: c for c in report["checked"]}
    assert by_path["results/thermal_summary.json"]["status"] == "ok"
    assert by_path["results/thermal_summary.json"]["source"] == "local"
    # The traj file is neither local nor (this test proves) fetched without a
    # crash: its url is absent from mirrors, so it is simply unchecked.
    assert by_path["traj/dump.xyz"]["status"] == "unchecked"


def test_verify_bundle_bytes_pointer_without_sha256_is_unchecked(tmp_path):
    """A pointer carrying NO sha256 (a light or unsummed-bundle artifact) is
    reported unchecked with reason 'no sha256 to verify against', even when its
    bytes are present: there is no byte claim to check, and that is not a
    failure."""
    old = _bundle(artifacts=[{"path": "results/thermal_summary.json",
                              "bytes": len(_BODY_RESULT)}])
    rec = sim.record_from_bundle(old, name_to_uid=_NAME_TO_UID)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "thermal_summary.json").write_bytes(_BODY_RESULT)
    report = sim.verify_bundle_bytes(rec, artifact_dir=tmp_path)
    entry = report["checked"][0]
    assert entry["status"] == "unchecked"
    assert entry["reason"] == "no sha256 to verify against"
    assert report["summary"] == {"ok": 0, "mismatch": 0, "unchecked": 1}


# --------------------------------------------------------------------------
# record_light: the primary builder. Identity is the recipe alone; artifact
# pointers are optional and never enter the id.
# --------------------------------------------------------------------------

def _light_recipe(**over):
    """A full light recipe: a map node plus material, template, hyperparameters,
    and setup values (the recipe-identified experiment)."""
    r = {
        "node": _NODE,
        "node_uid": _NODE_UID,
        "material": {"name": "Si"},
        "template": "gpumd",
        "conditions": {"T": 300.0, "potential": "Si-NEP"},
        "params": {},
        "hyperparameters": {"nep_cutoff": 8.0, "neighbor": 800},
        "values": {"supercell": [4, 4, 4]},
    }
    r.update(over)
    return r


def _pointer(**over):
    p = {"path": "traj/dump.xyz", "role": "trajectory",
         "url": "https://mcg.example/runs/abc/dump.xyz", "sha256": _SHA_B}
    p.update(over)
    return p


def test_record_light_mints_stable_recipe_id():
    """record_light with a full recipe (map node + material + hyperparameters +
    values) mints a stable, recipe-derived id."""
    r1 = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)
    r2 = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)
    assert r1["id"] == r2["id"] == sim.recipe_id(_light_recipe())
    assert len(r1["id"]) == 64
    # A record with NO artifacts is valid and normal: artifacts is an empty list.
    assert r1["artifacts"] == []


def test_record_light_artifact_pointers_do_not_change_id():
    """Adding or removing artifact POINTERS does not change the id (identity is
    the recipe); the pointers are stored as {path, role, url?, sha256?}."""
    base = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)["id"]
    withp = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(), _pointer(path="results/summary.json",
                                        role="result", sha256=_SHA_A)],
        name_to_uid=_NAME_TO_UID)
    assert withp["id"] == base
    assert len(withp["artifacts"]) == 2
    row = next(a for a in withp["artifacts"] if a["path"] == "traj/dump.xyz")
    assert row["url"] == "https://mcg.example/runs/abc/dump.xyz"
    assert row["sha256"] == _SHA_B
    # Removing the pointers again -> still the same id.
    assert sim.record_light(recipe=_light_recipe(),
                            name_to_uid=_NAME_TO_UID)["id"] == base


def test_record_light_hyperparameter_change_changes_id():
    """Changing a hyperparameter DOES change the id: it is part of the recipe."""
    base = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)["id"]
    other = sim.record_light(
        recipe=_light_recipe(hyperparameters={"nep_cutoff": 9.0, "neighbor": 800}),
        name_to_uid=_NAME_TO_UID)
    assert other["id"] != base


def test_record_light_execution_and_mirrors_ride_outside_identity():
    """execution and mirrors are carried but never hashed: the id is the recipe
    with or without them."""
    base = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)["id"]
    rec = sim.record_light(
        recipe=_light_recipe(),
        execution={"code": "gpumd", "code_version": "3.9.5", "seeds": [7]},
        artifacts=[_pointer(url=None, sha256=None)],
        mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz"}},
        name_to_uid=_NAME_TO_UID)
    assert rec["id"] == base
    assert rec["execution"]["code_version"] == "3.9.5"
    assert rec["mirrors"] == {"traj/dump.xyz":
                              {"url": "https://r2.example.com/dump.xyz"}}
    # The mirror url is copied onto the pointer that had none, as a convenience.
    assert rec["artifacts"][0]["url"] == "https://r2.example.com/dump.xyz"


# --------------------------------------------------------------------------
# The optional mirror `provider` key (#23): who holds the bytes, outside
# identity, shape-checked (a string if present), round-tripping the fragment,
# and echoed onto the verify report.
# --------------------------------------------------------------------------

def test_mirror_provider_does_not_change_identity():
    """A `provider` on a mirror entry names who holds the bytes and rides
    OUTSIDE identity (mirrors never reach recipe_id): the record id is the same
    with the provider, without it, and with a different provider."""
    base = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)["id"]
    with_provider = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(url=None, sha256=None)],
        mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz",
                                   "provider": "materialscodegraph"}},
        name_to_uid=_NAME_TO_UID)
    assert with_provider["id"] == base
    assert with_provider["mirrors"]["traj/dump.xyz"]["provider"] == "materialscodegraph"
    # A DIFFERENT provider still mints the same id (free-form, never hashed).
    other = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(url=None, sha256=None)],
        mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz",
                                   "provider": "zenodo"}},
        name_to_uid=_NAME_TO_UID)
    assert other["id"] == base


def test_mirror_provider_round_trips_through_fragment():
    """The provider survives record_to_fragment -> record_from_fragment intact
    (it is part of the mirror layer carried in the #x= fragment)."""
    rec = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(url=None, sha256=None)],
        mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz",
                                   "provider": "materialscodegraph"}},
        name_to_uid=_NAME_TO_UID)
    back = sim.record_from_fragment(sim.record_to_fragment(rec))
    assert back == rec
    assert back["mirrors"]["traj/dump.xyz"]["provider"] == "materialscodegraph"


def test_mirror_provider_echoed_onto_verify_report():
    """verify_simulation echoes the mirror's provider onto that artifact's
    report entry (the provenance loop), whatever the reachability status."""
    rec = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(url=None, sha256=_SHA_B)],
        mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz",
                                   "provider": "materialscodegraph"}},
        name_to_uid=_NAME_TO_UID)
    report = sim.verify_simulation(rec)  # no fetcher: unreachable, still echoes
    entry = next(e for e in report["checked"] if e["path"] == "traj/dump.xyz")
    assert entry["provider"] == "materialscodegraph"


def test_mirror_provider_must_be_a_string_if_present():
    """provider is optional and free-form, but when present it must be a string:
    a non-string provider is a malformed mirror, rejected by validate_light."""
    with pytest.raises(sim.SimulationError, match="provider"):
        sim.record_light(
            recipe=_light_recipe(),
            artifacts=[_pointer(url=None, sha256=None)],
            mirrors={"traj/dump.xyz": {"url": "https://r2.example.com/dump.xyz",
                                       "provider": 123}},
            name_to_uid=_NAME_TO_UID)


def test_mirror_without_provider_is_valid():
    """provider is optional: a mirror entry with only a url, and a bare url
    string mirror, both validate (provider absent is normal)."""
    rec = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer(url=None, sha256=None)],
        mirrors={"traj/dump.xyz": "https://r2.example.com/dump.xyz"},
        name_to_uid=_NAME_TO_UID)
    assert rec["mirrors"]["traj/dump.xyz"] == "https://r2.example.com/dump.xyz"


def test_record_light_no_node_no_artifacts_is_valid_and_flagged():
    """A light record with NO artifacts and NO node is valid (whatever we have):
    validate_light flags node-unresolved but does NOT reject. The recipe carries
    the template + values honestly."""
    rec = sim.record_light(recipe={"template": "gpumd",
                                   "conditions": {"T": 300.0},
                                   "values": {"pressure_GPa": 0.0}})
    assert rec["artifacts"] == []
    assert "node" not in rec["recipe"]
    report = sim.validate_light(rec)
    assert report["node_resolved"] is False
    assert report["node"] is None
    assert report["id"] == sim.recipe_id(rec["recipe"])


def test_record_light_rejects_stale_node_pin():
    """When the recipe names a node, the P3 pin discipline applies: a stale
    node_uid is a mismatch, not a silent pass."""
    with pytest.raises(sim.SimulationError, match="node_uid"):
        sim.record_light(recipe=_light_recipe(node_uid="0" * 64),
                         name_to_uid=_NAME_TO_UID)


def test_record_light_pins_live_node_uid_when_absent():
    """A recipe naming a node but no pin gets the live uid attached (so a later
    validation is a real match), pulled from name_to_uid."""
    recipe = _light_recipe()
    recipe.pop("node_uid")
    rec = sim.record_light(recipe=recipe, name_to_uid=_NAME_TO_UID)
    assert rec["recipe"]["node_uid"] == _NODE_UID


# --------------------------------------------------------------------------
# Artifact-pointer well-formedness (validate_light / _validate_pointers).
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"role": "trajectory"},                                   # missing path
    {"path": "", "role": "trajectory"},                       # empty path
    {"path": "traj/dump.xyz"},                                # missing role
    {"path": "traj/dump.xyz", "role": ""},                    # empty role
    {"path": "x", "role": "r", "url": 5},                     # url not a string
    {"path": "x", "role": "r", "sha256": "tooshort"},         # bad sha256 shape
])
def test_light_pointer_wellformedness_rejected(bad):
    """A pointer missing path or role is rejected; a url present must be a
    string and a sha256 present must be 64-hex (shape-only)."""
    with pytest.raises(sim.SimulationError, match="artifact"):
        sim.record_light(recipe=_light_recipe(), artifacts=[bad],
                         name_to_uid=_NAME_TO_UID)


def test_light_pointer_minimal_path_role_accepted():
    """path + role with no url and no sha256 is a legal pointer (the minimum)."""
    rec = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[{"path": "log/run.log", "role": "log"}],
        name_to_uid=_NAME_TO_UID)
    assert rec["artifacts"] == [{"path": "log/run.log", "role": "log"}]


def test_light_stated_id_mismatch_rejected():
    """A record whose stated id does not recompute from its recipe (someone
    folded an artifact or url into the hash) is rejected."""
    with pytest.raises(sim.SimulationError, match="recipe"):
        sim.validate_light({"id": "0" * 64, "recipe": _light_recipe()},
                           name_to_uid=_NAME_TO_UID)


# --------------------------------------------------------------------------
# The URL round-trip: record_to_fragment <-> record_from_fragment, matching the
# playground's gzip fragment scheme (gzip, base64url, '=' stripped, 'g' prefix).
# --------------------------------------------------------------------------

def test_fragment_round_trip_is_identity_stable():
    """record -> fragment -> record round-trips: the record is identical and the
    recipe id is unchanged."""
    rec = sim.record_light(
        recipe=_light_recipe(),
        artifacts=[_pointer()],
        execution={"code": "gpumd", "seeds": [7]},
        name_to_uid=_NAME_TO_UID)
    frag = sim.record_to_fragment(rec)
    back = sim.record_from_fragment(frag)
    assert back == rec
    assert back["id"] == rec["id"] == sim.recipe_id(rec["recipe"])


def test_fragment_is_base64url_no_plus_slash_or_padding():
    """The fragment is base64url with a mode prefix: no '+', '/', or '=' (so it
    is safe in a URL fragment), and it starts with 'g' (gzip)."""
    frag = sim.record_to_fragment(
        sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID))
    assert frag[0] == "g"
    body = frag[1:]
    assert "+" not in body and "/" not in body and "=" not in body


def test_fragment_from_fragment_strips_x_prefix():
    """record_from_fragment tolerates a leading '#x=' or 'x=' (a pasted fragment
    key), decoding the payload after it."""
    rec = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)
    frag = sim.record_to_fragment(rec)
    assert sim.record_from_fragment("#x=" + frag) == rec
    assert sim.record_from_fragment("x=" + frag) == rec


def test_hand_built_gzip_fragment_decodes():
    """A fragment built by hand with the playground's exact recipe (gzip, then
    urlsafe base64 with '=' stripped, 'g' prefix) decodes to the record: this is
    the interop contract with docs/play/index.html's gzipToB64url."""
    import base64
    import gzip
    import json

    rec = {"id": sim.recipe_id({"template": "gpumd", "conditions": {"T": 300.0}}),
           "recipe": {"template": "gpumd", "conditions": {"T": 300.0}},
           "artifacts": []}
    blob = json.dumps(rec, separators=(",", ":")).encode("utf-8")
    hand = "g" + base64.urlsafe_b64encode(gzip.compress(blob)).decode().rstrip("=")
    assert sim.record_from_fragment(hand) == rec


def test_raw_mode_fragment_decodes():
    """The 'r' (raw, uncompressed) fallback the playground emits when
    CompressionStream is unavailable also decodes."""
    import base64
    import json

    rec = sim.record_light(recipe=_light_recipe(), name_to_uid=_NAME_TO_UID)
    blob = json.dumps(rec, separators=(",", ":")).encode("utf-8")
    raw = "r" + base64.urlsafe_b64encode(blob).decode().rstrip("=")
    assert sim.record_from_fragment(raw) == rec


def test_fragment_unknown_mode_rejected():
    with pytest.raises(sim.SimulationError, match="mode"):
        sim.record_from_fragment("zabcdef")
