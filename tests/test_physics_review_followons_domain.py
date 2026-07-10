r"""Tests for the physics-review follow-on contributions (records 195-203).

The whole-map physics review (scans/map-physics-review-2026-07-10.md) named three
next recommendations, landed here as three small gated contributions:

  * Contribution 1 (records 195-197, thermochemistry): CalphadMolarEntropy S_m
    (the constant-P assessed molar entropy per mole of atoms) plus the implicit
    compute_calphad_entropy and the EXECUTABLE contract_gibbs_hts (G_m = H_m -
    T S_m), the SECOND producer of MolarGibbsEnergy (Pattern C).
  * Contribution 2 (records 198-201, materials): CarrierDensity n_c (NEW
    dimension NUMBER_DENSITY) plus compute_carrier_density and the SECOND
    SUPERSEDE: the opaque v1 compute_ionic_conductivity replaced by the
    executable Nernst-Einstein sigma = n_c z^2 e^2 D / (k_B T).
  * Contribution 3 (records 202-203, molecular): MolecularFrequency (FREQUENCY,
    the molecular normal-mode axis indexed by the registered mode kind m) plus
    the implicit compute_molecular_frequencies.

The suite pins the records, proves the new dimension, asserts the second producer
of MolarGibbsEnergy and the supersede succession.
"""
from __future__ import annotations

import json
from pathlib import Path

from omai.operator.identity import edge_id, node_id, node_identity


_LOG = Path(__file__).resolve().parents[1] / "map" / "log.jsonl"


def _lines():
    return _LOG.read_text().splitlines()


# ==========================================================================
# Contribution 1: CalphadMolarEntropy and the executable Gibbs identity.
# ==========================================================================

def test_calphad_molar_entropy_reuses_the_phonon_entropy_dimension():
    """CalphadMolarEntropy carries ENERGY_PER_TEMPERATURE_PER_MOLE, exactly the
    same exponent vector as the phonon-side MolarEntropy, but is a DISTINCT node
    kept apart by the calphad_molar_entropy quantity tag (the Molar* false-merge
    guardrail: constant-P per-atom vs constant-V per-cell)."""
    from omai.operator.dimensions import ENERGY_PER_TEMPERATURE_PER_MOLE
    from omai.thermochemistry.operator.nodes import CALPHAD_MOLAR_ENTROPY
    from omai.thermal_transport.operator.nodes import MOLAR_ENTROPY

    assert (CALPHAD_MOLAR_ENTROPY.field("S_m").dimension
            == ENERGY_PER_TEMPERATURE_PER_MOLE)
    # Same field dimension as the phonon MolarEntropy...
    assert (CALPHAD_MOLAR_ENTROPY.field("S_m").dimension
            == MOLAR_ENTROPY.fields[0].dimension)
    # ...but a distinct node identity (the tag does the work).
    assert node_id(CALPHAD_MOLAR_ENTROPY) != node_id(MOLAR_ENTROPY)
    assert (node_identity(CALPHAD_MOLAR_ENTROPY)["quantity"]
            == "calphad_molar_entropy")
    assert node_identity(MOLAR_ENTROPY)["quantity"] == "molar_entropy"


def test_contract_gibbs_hts_is_the_second_producer_of_molar_gibbs_energy():
    """Pattern C: MolarGibbsEnergy has TWO producing edges, the direct
    solve_equilibrium (Gibbs minimization) and contract_gibbs_hts (the H - T S
    identity). Both land on the SAME MolarGibbsEnergy node uid, with distinct
    edge uids; they must agree numerically."""
    from omai.thermochemistry.operator.edges import (
        contract_gibbs_hts,
        solve_equilibrium,
    )
    from omai.thermochemistry.operator.nodes import MOLAR_GIBBS_ENERGY

    gibbs_uid = node_id(MOLAR_GIBBS_ENERGY)
    producers = [solve_equilibrium, contract_gibbs_hts]
    for op in producers:
        assert [o.name for o in op.outputs] == ["MolarGibbsEnergy"], op.name
        assert node_id(op.outputs[0]) == gibbs_uid, op.name
    edge_uids = {edge_id(op, node_id) for op in producers}
    assert len(edge_uids) == 2, "the two producers must be distinct edges"


def test_contract_gibbs_hts_dimension_is_proven():
    """The dimensional gate PROVES G_m = H_m - T S_m: T S_m = TEMPERATURE .
    ENERGY_PER_TEMPERATURE_PER_MOLE = ENERGY_PER_MOLE, an Add of two equal
    ENERGY_PER_MOLE dimensions matching G_m."""
    from omai.map_data import DOMAINS
    from omai.operator.dimcheck import dimensional_report

    nodes, edges = [], []
    sn, se = set(), set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in sn:
                sn.add(s.name); nodes.append(s)
        for op in d.edges:
            if op.name not in se:
                se.add(op.name); edges.append(op)
    report = dimensional_report(nodes, edges)
    assert "contract_gibbs_hts" in report["ok"], report
    assert "compute_calphad_entropy" in report["skipped"], report


def test_contribution_1_is_records_195_to_197():
    """Records 195-197: one node (CalphadMolarEntropy) then two edges
    (compute_calphad_entropy, contract_gibbs_hts)."""
    from omai.thermochemistry.operator.edges import (
        compute_calphad_entropy,
        contract_gibbs_hts,
    )
    from omai.thermochemistry.operator.nodes import CALPHAD_MOLAR_ENTROPY

    lines = _lines()
    assert len(lines) >= 197, "contribution 1 has not landed"
    uids = [
        node_id(CALPHAD_MOLAR_ENTROPY),
        edge_id(compute_calphad_entropy, node_id),
        edge_id(contract_gibbs_hts, node_id),
    ]
    recs = [json.loads(line) for line in lines[194:197]]
    assert [r["payload"]["uid"] for r in recs] == uids
    assert [r["op"] for r in recs] == ["add_node", "add_edge", "add_edge"]
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "assessed entropy" in r["reason"]


# ==========================================================================
# Contribution 2: CarrierDensity and the executable Nernst-Einstein supersede.
# ==========================================================================

def test_number_density_is_the_new_inverse_volume_dimension():
    """NUMBER_DENSITY is a genuinely new dimension: 1/m^3 = L^-3
    (0,-3,0,0,0,0,0), a pure inverse-volume; CarrierDensity carries it."""
    from omai.operator.dimensions import NUMBER_DENSITY
    from omai.materials.operator.nodes import CARRIER_DENSITY

    assert NUMBER_DENSITY.exponents == (0, -3, 0, 0, 0, 0, 0)
    assert CARRIER_DENSITY.field("n_c").dimension == NUMBER_DENSITY
    assert node_identity(CARRIER_DENSITY)["quantity"] == "carrier_density"


def test_number_density_units_per_m3_canonical_per_cm3_factor():
    from omai.operator.dimensions import NUMBER_DENSITY
    from omai.representation.units import UNITS, conversion_factor

    assert UNITS["per_m3"].dimension == NUMBER_DENSITY
    assert UNITS["per_m3"].to_operator == 1.0
    # 1 cm^-3 = 1e6 m^-3, so per_cm3 carries to_operator 1e6.
    assert UNITS["per_cm3"].to_operator == 1e6
    assert abs(conversion_factor("per_cm3", "per_m3") - 1e6) < 1e-3


def test_nernst_einstein_dimension_chain_proves_s_per_m():
    """The executable Nernst-Einstein sigma = n_c z^2 e^2 D / (k_B T) is PROVEN
    to land on ELECTRICAL_CONDUCTIVITY (S/m). The chain:
    n_c (0,-3,0,0,0,0,0) . z^2 (dimensionless) . e^2 (0,0,2,0,0,2,0)
    . D (0,2,-1,0,0,0,0) / (k_B T) (energy 1,2,-2,0,0,0,0)
    = (-1,-3,3,0,0,2,0) = ELECTRICAL_CONDUCTIVITY."""
    from omai.map_data import DOMAINS
    from omai.operator.dimcheck import dimensional_report
    from omai.operator.dimensions import (
        DIFFUSIVITY,
        ELECTRICAL_CONDUCTIVITY,
        ENERGY,
        NUMBER_DENSITY,
        VOLTAGE,
    )

    # By-hand chain (the gate proves the same).
    charge = ENERGY / VOLTAGE  # (0,0,1,0,0,1,0)
    chain = NUMBER_DENSITY * (charge ** 2) * DIFFUSIVITY / ENERGY
    assert chain.exponents == ELECTRICAL_CONDUCTIVITY.exponents == (
        -1, -3, 3, 0, 0, 2, 0)

    nodes, edges = [], []
    sn, se = set(), set()
    for d in DOMAINS:
        for s in d.nodes:
            if s.name not in sn:
                sn.add(s.name); nodes.append(s)
        for op in d.edges:
            if op.name not in se:
                se.add(op.name); edges.append(op)
    report = dimensional_report(nodes, edges)
    assert "compute_ionic_conductivity" in report["ok"], report


def test_ionic_conductivity_v2_is_executable_and_v1_is_not():
    """The executable v2 supersedes the opaque v1: the live edge is now
    sympy-executable, its inputs are (CarrierDensity, Diffusivity, Temperature),
    and its edge id differs from the frozen v1 uid."""
    from omai.materials.operator.edges import compute_ionic_conductivity

    assert compute_ionic_conductivity.is_executable_in_sympy_override is None
    assert compute_ionic_conductivity.is_executable_in_sympy
    assert [s.name for s in compute_ionic_conductivity.inputs] == [
        "CarrierDensity", "Diffusivity", "Temperature"]
    OLD_V1 = ("504b2deeec3553dc90f91bdc0b4136feaf52abcbc585edd6"
              "5500d5cab9f27cb2")
    assert edge_id(compute_ionic_conductivity, node_id) != OLD_V1


def test_ionic_conductivity_supersede_succession_in_the_store():
    """The store records the succession: the v1 edge (record 150) carries
    superseded_by pointing at the executable v2 (the live edge id), and the v2
    edge is present."""
    from omai.materials.operator.edges import compute_ionic_conductivity
    from omai.store import Store

    OLD_V1 = ("504b2deeec3553dc90f91bdc0b4136feaf52abcbc585edd6"
              "5500d5cab9f27cb2")
    m = Store(_LOG.parent).read()
    v2_uid = edge_id(compute_ionic_conductivity, node_id)
    assert OLD_V1 in m["edges"], "the v1 edge must remain in the store log"
    assert m["edges"][OLD_V1].get("superseded_by") == [v2_uid]
    assert v2_uid in m["edges"], "the executable v2 edge must be live"


def test_contribution_2_is_records_198_to_201():
    """Records 198-201: node CarrierDensity, edge compute_carrier_density, the
    executable v2 compute_ionic_conductivity add_edge, then the supersede tying
    v1 -> v2."""
    from omai.materials.operator.edges import (
        compute_carrier_density,
        compute_ionic_conductivity,
    )
    from omai.materials.operator.nodes import CARRIER_DENSITY

    lines = _lines()
    assert len(lines) >= 201, "contribution 2 has not landed"
    recs = [json.loads(line) for line in lines[197:201]]
    assert [r["op"] for r in recs] == [
        "add_node", "add_edge", "add_edge", "supersede"]
    assert recs[0]["payload"]["uid"] == node_id(CARRIER_DENSITY)
    assert recs[1]["payload"]["uid"] == edge_id(compute_carrier_density, node_id)
    v2_uid = edge_id(compute_ionic_conductivity, node_id)
    assert recs[2]["payload"]["uid"] == v2_uid
    OLD_V1 = ("504b2deeec3553dc90f91bdc0b4136feaf52abcbc585edd6"
              "5500d5cab9f27cb2")
    assert recs[3]["payload"]["old_uids"] == [OLD_V1]
    assert recs[3]["payload"]["new_uids"] == [v2_uid]
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "carrier density" in r["reason"]


# ==========================================================================
# Contribution 3: MolecularFrequency.
# ==========================================================================

def test_molecular_frequency_is_frequency_indexed_by_mode_not_phonon():
    """MolecularFrequency carries FREQUENCY indexed by the registered mode kind
    (m), NOT the periodic phonon (q, nu) = (qpoint, branch) signature, so it is
    a distinct node from the phonon Frequency."""
    from omai.operator.dimensions import FREQUENCY
    from omai.operator.registry import INDEX_KINDS
    from omai.molecular.operator.nodes import MOLECULAR_FREQUENCY
    from omai.thermal_transport.operator.nodes import FREQUENCY_STATE

    assert MOLECULAR_FREQUENCY.field("nu_mol").dimension == FREQUENCY
    assert MOLECULAR_FREQUENCY.field("nu_mol").indices == ("m",)
    assert INDEX_KINDS["m"] == "mode"
    assert (node_identity(MOLECULAR_FREQUENCY)["fields"][0]["indices"]
            == ["mode"])
    # Same FREQUENCY dimension as the phonon Frequency, but a distinct node
    # (different index signature and quantity tag).
    assert MOLECULAR_FREQUENCY.field("nu_mol").dimension \
        == FREQUENCY_STATE.fields[0].dimension
    assert node_id(MOLECULAR_FREQUENCY) != node_id(FREQUENCY_STATE)
    assert (node_identity(MOLECULAR_FREQUENCY)["quantity"]
            == "molecular_frequency")


def test_molecular_frequency_served_in_wavenumbers():
    from omai.map_data import build_codes
    from omai.map_data import DOMAINS

    orca = build_codes(DOMAINS)["orca"]
    assert orca["MolecularFrequency"]["unit"] == "inverse_cm"


def test_contribution_3_is_records_202_to_203():
    """Records 202-203: node MolecularFrequency then edge
    compute_molecular_frequencies."""
    from omai.molecular.operator.edges import compute_molecular_frequencies
    from omai.molecular.operator.nodes import MOLECULAR_FREQUENCY

    lines = _lines()
    assert len(lines) >= 203, "contribution 3 has not landed"
    recs = [json.loads(line) for line in lines[201:203]]
    assert [r["op"] for r in recs] == ["add_node", "add_edge"]
    assert recs[0]["payload"]["uid"] == node_id(MOLECULAR_FREQUENCY)
    assert recs[1]["payload"]["uid"] == edge_id(
        compute_molecular_frequencies, node_id)
    for r in recs:
        assert r["author"] == "gbarbalinardo"
        assert r["date"] == "2026-07-10"
        assert "molecular normal modes" in r["reason"]


# ==========================================================================
# Cross-cutting: the store stays clean and in sync after all three.
# ==========================================================================

def test_store_head_at_203_records_and_clean():
    from omai.store import Store

    lines = _lines()
    assert len(lines) >= 203
    assert Store(_LOG.parent).verify() == []
    # Genesis stays the frozen prefix.
    assert (_LOG.parent / "GENESIS").read_text().strip() == \
        "e6e8044e92039696417b53b220b0f3f10559a286b0eaabbe7ea4167ff510f6cd"
