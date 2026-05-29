"""cross_check: redundant routes to a target, verdicts governed by the
target's Observable/HiddenSpace typing."""
from __future__ import annotations

import numpy as np

from omai.representation.executor import operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import ValidationReport, cross_check
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    ANHARMONIC_LINEWIDTH,
)


def _op_rep(space, name, data) -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name,
        data=np.asarray(data),
        is_operator=True,
    )


def test_cross_check_observable_routes_agree():
    """Two routes that derive MolarHeatCapacity from the same Frequency must
    agree; the report is ok() and the pair status is EXPECTED_AGREE."""
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])
    src = lambda: {  # noqa: E731
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, {"routeA": src(), "routeB": src()})
    assert isinstance(report, ValidationReport)
    assert report.ok() is True
    statuses = {(p.label_a, p.label_b): p.status for p in report.pairwise}
    assert statuses[("routeA", "routeB")] == "EXPECTED_AGREE"


def test_cross_check_hidden_space_routes_are_not_comparable():
    """For a HiddenSpace target, per-element routes are NOT_COMPARABLE — the
    framework predicts they need not agree (no bug flagged)."""
    g = np.array([[1.0, 2.0], [3.0, 4.0]])
    routes = {
        "r1": {"Linewidth[channel=anharmonic_3ph]": _op_rep(ANHARMONIC_LINEWIDTH, "Gamma", g)},
        "r2": {"Linewidth[channel=anharmonic_3ph]": _op_rep(ANHARMONIC_LINEWIDTH, "Gamma", g * 1.5)},
    }
    report = cross_check(ANHARMONIC_LINEWIDTH, routes)
    statuses = {(p.label_a, p.label_b): p.status for p in report.pairwise}
    assert statuses[("r1", "r2")] == "NOT_COMPARABLE"
    # NOT_COMPARABLE does not break ok() — it carries no normative weight.
    assert report.ok() is True


def test_validation_report_render_is_a_string_table():
    omega = np.array([[5.0, 10.0]])
    src = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", omega),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, {"only": src})
    text = report.render()
    assert "MolarHeatCapacity" in text
    assert isinstance(text, str)
