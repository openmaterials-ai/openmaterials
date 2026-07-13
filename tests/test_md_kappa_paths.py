"""Smoke tests for phase-2 P3 MD-based κ paths.

P3 adds three Pattern-A `transport_model` variants of
ThermalConductivity — `green_kubo`, `nemd`, `hnemd` — and three
contraction edges that close the cross-paradigm κ map.

Adapter coverage extends `lammps` (green_kubo + nemd; HNEMD declared
not-exposed) and `gpumd` (green_kubo + hnemd; NEMD declared
not-exposed). The not-exposed entries are *also* OperatorRepresentationSpec
instances — they're documented as routing through the other adapter,
but they still appear in the audit.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import THERMAL_CONDUCTIVITY
from omai.operator.space import ObservableSpace
from omai.operator.validate import validate_dag
from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator import EDGES, NODES
from omai.thermal_transport.operator.edges import (
    contract_kappa_green_kubo,
    contract_kappa_hnemd,
    contract_kappa_nemd,
)
from omai.thermal_transport.operator.nodes import (
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_GREEN_KUBO,
    THERMAL_CONDUCTIVITY_HNEMD,
    THERMAL_CONDUCTIVITY_NEMD,
)


# ---------------------------------------------------------------------------
# State identity
# ---------------------------------------------------------------------------


def test_three_new_kappa_variants_are_observables():
    for kappa in (
        THERMAL_CONDUCTIVITY_GREEN_KUBO,
        THERMAL_CONDUCTIVITY_NEMD,
        THERMAL_CONDUCTIVITY_HNEMD,
    ):
        assert isinstance(kappa, ObservableSpace)
        (field,) = kappa.fields
        assert field.name == "kappa"
        assert field.dimension is THERMAL_CONDUCTIVITY
        assert field.indices == ("alpha", "beta")


def test_kappa_variants_carry_transport_model_parameter():
    assert THERMAL_CONDUCTIVITY_GREEN_KUBO.labels == {
        "transport_model": "green_kubo"
    }
    assert THERMAL_CONDUCTIVITY_NEMD.labels == {"transport_model": "nemd"}
    assert THERMAL_CONDUCTIVITY_HNEMD.labels == {"transport_model": "hnemd"}


# ---------------------------------------------------------------------------
# Edge identity, inputs/outputs, sympy
# ---------------------------------------------------------------------------


def test_contract_kappa_green_kubo_wires_from_acf():
    assert set(contract_kappa_green_kubo.inputs) == {HEAT_CURRENT_ACF, TEMPERATURE_STATE}
    assert contract_kappa_green_kubo.outputs == (THERMAL_CONDUCTIVITY_GREEN_KUBO,)
    assert isinstance(contract_kappa_green_kubo.formula, sp.Eq)
    # LHS is κ[α, β] — 2 indices.
    assert len(contract_kappa_green_kubo.formula.lhs.indices) == 2
    param_names = {p.name for p in contract_kappa_green_kubo.parameters}
    assert {"tau_max", "tau_min"} <= param_names


def test_contract_kappa_nemd_wires_from_heat_current():
    assert set(contract_kappa_nemd.inputs) == {HEAT_CURRENT, TEMPERATURE_STATE}
    assert contract_kappa_nemd.outputs == (THERMAL_CONDUCTIVITY_NEMD,)
    assert isinstance(contract_kappa_nemd.formula, sp.Eq)
    assert "nemd_method" in contract_kappa_nemd.schemes
    param_names = {p.name for p in contract_kappa_nemd.parameters}
    assert {"imposed_gradient", "imposed_flux"} <= param_names


def test_contract_kappa_hnemd_wires_from_heat_current():
    assert set(contract_kappa_hnemd.inputs) == {HEAT_CURRENT, TEMPERATURE_STATE}
    assert contract_kappa_hnemd.outputs == (THERMAL_CONDUCTIVITY_HNEMD,)
    assert isinstance(contract_kappa_hnemd.formula, sp.Eq)
    param_names = {p.name for p in contract_kappa_hnemd.parameters}
    assert {"driving_force_magnitude", "driving_direction"} <= param_names


# ---------------------------------------------------------------------------
# DAG-level
# ---------------------------------------------------------------------------


def test_dag_validates_clean_with_md_kappa_paths():
    errors = validate_dag(NODES, EDGES)
    assert errors == [], "\n".join(errors)


def test_all_six_transport_models_present_in_nodes():
    """All six transport_model variants of κ are nodes in the DAG: lbte
    (split into rta + direct_inverse along the orthogonal bte_solver
    axis), wigner (split into populations + coherences + total), qhgk,
    green_kubo, nemd, hnemd."""
    from omai.thermal_transport.operator.nodes import (
        THERMAL_CONDUCTIVITY_DIRECT,
        THERMAL_CONDUCTIVITY_QHGK,
        THERMAL_CONDUCTIVITY_RTA,
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    )

    all_kappas = [
        THERMAL_CONDUCTIVITY_RTA,
        THERMAL_CONDUCTIVITY_DIRECT,
        THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
        THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
        THERMAL_CONDUCTIVITY_WIGNER,
        THERMAL_CONDUCTIVITY_QHGK,
        THERMAL_CONDUCTIVITY_GREEN_KUBO,
        THERMAL_CONDUCTIVITY_NEMD,
        THERMAL_CONDUCTIVITY_HNEMD,
    ]
    for kappa in all_kappas:
        assert kappa in NODES, f"{kappa.name} missing from NODES"


# ---------------------------------------------------------------------------
# LAMMPS coverage (green_kubo + nemd; HNEMD not-exposed)
# ---------------------------------------------------------------------------


def test_lammps_covers_green_kubo_and_nemd_states():
    from omai.thermal_transport.representation.lammps import (
        LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO,
        LAMMPS_THERMAL_CONDUCTIVITY_NEMD,
    )

    pairs = [
        (LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO, THERMAL_CONDUCTIVITY_GREEN_KUBO),
        (LAMMPS_THERMAL_CONDUCTIVITY_NEMD, THERMAL_CONDUCTIVITY_NEMD),
    ]
    for spec, state in pairs:
        assert isinstance(spec, SpaceRepresentationSpec)
        assert spec.representation_name == "lammps"
        assert spec.space is state
        assert spec.code_api, f"{state.name}: empty code_api"


def test_lammps_covers_green_kubo_and_nemd_edges():
    from omai.thermal_transport.representation.lammps import (
        LAMMPS_CONTRACT_KAPPA_GREEN_KUBO,
        LAMMPS_CONTRACT_KAPPA_NEMD,
    )

    assert isinstance(LAMMPS_CONTRACT_KAPPA_GREEN_KUBO, OperatorRepresentationSpec)
    assert LAMMPS_CONTRACT_KAPPA_GREEN_KUBO.operator is contract_kappa_green_kubo
    assert isinstance(LAMMPS_CONTRACT_KAPPA_NEMD, OperatorRepresentationSpec)
    assert LAMMPS_CONTRACT_KAPPA_NEMD.operator is contract_kappa_nemd


def test_lammps_hnemd_is_documented_as_not_exposed():
    from omai.thermal_transport.representation.lammps import LAMMPS_CONTRACT_KAPPA_HNEMD

    assert isinstance(LAMMPS_CONTRACT_KAPPA_HNEMD, OperatorRepresentationSpec)
    assert LAMMPS_CONTRACT_KAPPA_HNEMD.operator is contract_kappa_hnemd
    # Notes mention that HNEMD is not exposed in LAMMPS — content check is light.
    notes = LAMMPS_CONTRACT_KAPPA_HNEMD.notes.lower()
    assert "not exposed" in notes or "gpumd" in notes


# ---------------------------------------------------------------------------
# GPUMD coverage (green_kubo + hnemd; NEMD not-exposed)
# ---------------------------------------------------------------------------


def test_gpumd_covers_green_kubo_and_hnemd_states():
    from omai.thermal_transport.representation.gpumd import (
        GPUMD_THERMAL_CONDUCTIVITY_GREEN_KUBO,
        GPUMD_THERMAL_CONDUCTIVITY_HNEMD,
    )

    pairs = [
        (GPUMD_THERMAL_CONDUCTIVITY_GREEN_KUBO, THERMAL_CONDUCTIVITY_GREEN_KUBO),
        (GPUMD_THERMAL_CONDUCTIVITY_HNEMD, THERMAL_CONDUCTIVITY_HNEMD),
    ]
    for spec, state in pairs:
        assert isinstance(spec, SpaceRepresentationSpec)
        assert spec.representation_name == "gpumd"
        assert spec.space is state
        assert spec.code_api, f"{state.name}: empty code_api"


def test_gpumd_covers_green_kubo_and_hnemd_edges():
    from omai.thermal_transport.representation.gpumd import (
        GPUMD_CONTRACT_KAPPA_GREEN_KUBO,
        GPUMD_CONTRACT_KAPPA_HNEMD,
    )

    assert isinstance(GPUMD_CONTRACT_KAPPA_GREEN_KUBO, OperatorRepresentationSpec)
    assert GPUMD_CONTRACT_KAPPA_GREEN_KUBO.operator is contract_kappa_green_kubo
    assert isinstance(GPUMD_CONTRACT_KAPPA_HNEMD, OperatorRepresentationSpec)
    assert GPUMD_CONTRACT_KAPPA_HNEMD.operator is contract_kappa_hnemd


def test_gpumd_nemd_is_documented_as_not_exposed():
    from omai.thermal_transport.representation.gpumd import GPUMD_CONTRACT_KAPPA_NEMD

    assert isinstance(GPUMD_CONTRACT_KAPPA_NEMD, OperatorRepresentationSpec)
    assert GPUMD_CONTRACT_KAPPA_NEMD.operator is contract_kappa_nemd
    notes = GPUMD_CONTRACT_KAPPA_NEMD.notes.lower()
    assert "not exposed" in notes or "lammps" in notes


# ---------------------------------------------------------------------------
# MESCAL coherent-transport rail (Landauer). MESCAL joins for coherent transport
# the way kaldo enters for QHGK: it serves PhononTransmission and the Landauer
# ThermalConductance.
# ---------------------------------------------------------------------------


def test_mescal_appears_in_build_codes_with_phonon_transmission_mapped():
    from omai.map_data import build_codes, build_graph_dict
    from omai.thermal_transport.domain import THERMAL_TRANSPORT

    codes = build_codes((THERMAL_TRANSPORT,))
    assert "mescal" in codes, "mescal rail missing from build_codes"
    mescal = codes["mescal"]
    # PhononTransmission is mapped (the observable every coherent method shares).
    assert "PhononTransmission" in mescal
    assert mescal["PhononTransmission"]["unit"] == "dimensionless"
    # The Landauer conductance is served in nW/K and credited (MIT license).
    landauer = "ThermalConductance[transport_model=landauer]"
    assert landauer in mescal
    assert mescal[landauer]["unit"] == "nW_per_K"
    assert mescal[landauer]["license"] == "MIT"
    # The mapped variables are real nodes on the map.
    ids = {n["id"] for n in build_graph_dict((THERMAL_TRANSPORT,))["nodes"]}
    assert "PhononTransmission" in ids and landauer in ids
