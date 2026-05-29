"""Tests for the lazy DAG resolver `compute`."""
from __future__ import annotations

import numpy as np
import pytest

from omai.representation.executor import (
    ComputeResult,
    ExternalSolveRequired,
    NoSourceError,
    Source,
    TraceStep,
    compute,
    operator_form_spec,
)
from omai.representation.instance import Representation
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    HEAT_CAPACITY,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
)

_H_PLANCK = 6.62607015e-34
_HBAR_EFF = _H_PLANCK * 1.0e12
_KB = 1.380649e-23
_N_A = 6.02214076e23


def _op_rep(space, name, data) -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name,
        data=np.asarray(data),
        is_operator=True,
    )


def test_compute_derives_molar_heat_capacity_edge_by_edge():
    """Frequency + Temperature -> (derive HeatCapacity) -> (contract) MolarHeatCapacity."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])  # (N_q=2, N_modes=2)
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    result = compute(MOLAR_HEAT_CAPACITY, sources)
    assert isinstance(result, ComputeResult)
    # Reference: per-mode sinh heat capacity, summed, × N_A / N_q.
    x = _HBAR_EFF * omega / (2 * _KB * 300.0)
    c = (_HBAR_EFF * omega) ** 2 / (4 * _KB * 300.0 ** 2 * np.sinh(x) ** 2)
    expected = _N_A * np.sum(c) / omega.shape[0]
    np.testing.assert_allclose(float(result.representation.data), expected, rtol=1e-10)
    assert result.representation.is_operator is True
    # Trace lists the two leaves (LOAD) and the two derivations (EXEC).
    kinds = [(s.kind, s.space) for s in result.trace]
    assert ("EXEC", "HeatCapacity") in kinds
    assert ("EXEC", "MolarHeatCapacity") in kinds
    assert ("LOAD", "Frequency") in kinds


def test_compute_accepts_callable_source_thunk():
    """A Source may be a thunk returning a Representation."""
    omega = np.array([[5.0, 10.0]])
    calls = {"n": 0}

    def load_freq() -> Representation:
        calls["n"] += 1
        return _op_rep(FREQUENCY_STATE, "omega", omega)

    sources = {
        "Frequency": load_freq,
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    compute(HEAT_CAPACITY, sources)
    assert calls["n"] == 1  # thunk materialized exactly once


def test_compute_missing_source_raises_no_source_error():
    """A leaf with no producer and no source raises NoSourceError naming it."""
    with pytest.raises(NoSourceError) as exc:
        compute(HEAT_CAPACITY, {"Frequency": _op_rep(FREQUENCY_STATE, "omega", np.array([[5.0]]))})
    assert "Temperature" in str(exc.value)


def test_compute_records_lift_for_non_operator_source():
    """A source given in a code's representation (not operator form) records
    a LIFT step when canonicalized."""
    from omai.thermal_transport.representation import KALDO_FREQUENCY
    from omai.representation.instance import represent
    omega = np.array([[5.0, 10.0]])
    rep = represent(KALDO_FREQUENCY, "omega", omega)  # is_operator defaults False
    sources = {
        "Frequency": rep,
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    result = compute(HEAT_CAPACITY, sources)
    kinds = [(s.kind, s.space) for s in result.trace]
    assert ("LOAD", "Frequency") in kinds
    assert ("LIFT", "Frequency") in kinds


def test_compute_implicit_edge_without_source_raises_external_solve_required():
    """ThermalConductivity[direct] is produced by an implicit (BTE-solve)
    chain; without a source for the implicit intermediate, compute raises
    ExternalSolveRequired."""
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", np.array([[5.0, 10.0]])),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
        "GroupVelocity": _op_rep(
            __import__("omai.thermal_transport.operator", fromlist=["GROUP_VELOCITY"]).GROUP_VELOCITY,
            "v", np.ones((3, 1, 2)),
        ),
    }
    with pytest.raises(ExternalSolveRequired):
        compute(THERMAL_CONDUCTIVITY_DIRECT, sources)
