"""Tests for the index registry generator and instance uid pinning (kernel P3).

The `index/codes/` entries pin each representation's coverage to the store
HEAD at generation time: one file per representation, each covered node
carrying its live node uid, the whole file stamped with the map version read
from the committed store's head (decision: head-at-generation; the map_version
field is the version the coverage was computed against, which advances past
the frozen genesis as contributions land). Instances gain a `node_uid` at
bundle time, resolved from the live identity of the variable they name
(additive; existing keys untouched).
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.index_data import write_index
from omai.map_data import DOMAINS, build_codes, build_graph_dict, build_instances

_HEX = set("0123456789abcdef")


def _is_hex64(s) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in _HEX for c in s)


def _name_to_uid() -> dict[str, str]:
    return {n["id"]: n["uid"] for n in build_graph_dict(DOMAINS)["nodes"]}


def _store_head() -> str:
    from omai.store import Store
    return Store(Path(__file__).resolve().parents[1] / "map").head


# --------------------------------------------------------------------------
# Instance uid pinning.
# --------------------------------------------------------------------------

def test_every_instance_carries_a_node_uid_matching_its_variable():
    name_to_uid = _name_to_uid()
    insts = build_instances()
    assert insts, "expected instances on disk"
    for it in insts:
        assert _is_hex64(it.get("node_uid")), \
            f"instance for {it['variable']} lacks a 64-hex node_uid"
        assert it["node_uid"] == name_to_uid[it["variable"]], \
            f"instance node_uid does not match live identity of {it['variable']}"


def test_instance_node_uid_is_additive_existing_keys_survive():
    insts = build_instances()
    for it in insts:
        for key in ("variable", "material", "conditions", "value", "units",
                    "source"):
            assert key in it, f"instance lost key {key}"


# --------------------------------------------------------------------------
# write_index: nine files, uid + map_version correct, qe and lammps cover 9.
# --------------------------------------------------------------------------

def test_write_index_emits_one_file_per_representation(tmp_path):
    write_index(tmp_path)
    codes_dir = tmp_path / "codes"
    files = sorted(p.name for p in codes_dir.glob("*.json"))
    reps = sorted(build_codes(DOMAINS).keys())
    # One file per representation, named <rep>.json. Compared as sets: a plain
    # sorted-list compare is fragile when one rep name is a prefix of another
    # (pymatgen vs pymatgen-analysis-diffusion sort differently before and after
    # suffixing, because '-' < '.').
    assert set(files) == {f"{r}.json" for r in reps}
    # One file per representation; the count grows as domains add codes /
    # skills (the mechanics domain added the mat-elasticity skill, 10th rep;
    # the pymatgen scan added the pymatgen rail, 11th; the MLIP-family scan
    # added the mace / matgl / fairchem rails, 12th-14th; the atomate2/VASP scan
    # added the vasp rail, 15th; the mp-api scan added the mp-api DATABASE rail,
    # 16th; the pycalphad scan added the pycalphad rail, 17th; the matcalc/ASE
    # scan added the ase Structure/Trajectory coverage and the two skill rails
    # mat-equation-of-state and mat-surface-adsorption, 18th-19th (matcalc
    # itself is NOT a rail, the atomate2 ruling); the config-thermo scan added
    # smol, rxn-network, and pymatgen-analysis-diffusion, 20th-22nd.
    assert len(files) == len(reps)
    assert len(files) == 22


def test_each_index_entry_uid_matches_live_node_id(tmp_path):
    write_index(tmp_path)
    name_to_uid = _name_to_uid()
    for path in (tmp_path / "codes").glob("*.json"):
        doc = json.loads(path.read_text())
        for entry in doc["covers"]:
            assert entry["uid"] == name_to_uid[entry["node"]], \
                f"{path.name}: {entry['node']} uid mismatch"
            assert _is_hex64(entry["uid"])


def test_index_map_version_equals_the_store_head(tmp_path):
    # Head-at-generation, not the frozen GENESIS: the index pins the version
    # its coverage was computed against, which advances as contributions land.
    write_index(tmp_path)
    head = _store_head()
    for path in (tmp_path / "codes").glob("*.json"):
        doc = json.loads(path.read_text())
        assert doc["map_version"] == head, f"{path.name}: wrong map_version"


def test_qe_and_lammps_coverage_counts(tmp_path):
    # Counts derive from the live domain set, so the next domain does not
    # re-break this test: each representation's covers must equal its live
    # build_codes entry (qe grew from 9 to 13 when the DFT ground-state domain
    # added Structure / TotalEnergy / Forces / Stress; lammps grew from 9 to 11
    # when the mechanics domain added the ELASTIC and pressure specs).
    write_index(tmp_path)
    codes = build_codes(DOMAINS)
    for rep in ("qe", "lammps"):
        doc = json.loads((tmp_path / "codes" / f"{rep}.json").read_text())
        assert doc["representation"] == rep
        assert len(doc["covers"]) == len(codes[rep]), \
            f"{rep} covers {len(doc['covers'])}, live build_codes says {len(codes[rep])}"
    assert len(codes["qe"]) == 13
    assert len(codes["lammps"]) == 11


def test_index_covers_sorted_by_node(tmp_path):
    write_index(tmp_path)
    for path in (tmp_path / "codes").glob("*.json"):
        doc = json.loads(path.read_text())
        nodes = [e["node"] for e in doc["covers"]]
        assert nodes == sorted(nodes), f"{path.name}: covers not sorted by node"


def test_index_entries_carry_api_and_unit(tmp_path):
    write_index(tmp_path)
    for path in (tmp_path / "codes").glob("*.json"):
        doc = json.loads(path.read_text())
        for entry in doc["covers"]:
            assert "api" in entry and "unit" in entry


def test_write_index_writes_readme(tmp_path):
    write_index(tmp_path)
    assert (tmp_path / "README.md").exists()
