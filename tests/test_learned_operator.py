"""Tests for learned shortcut edges (omai.operator.learned).

The fixtures are the real thermal-transport objects, so these tests double
as the worked example: a surrogate of the three-phonon linewidth that
amortizes away ForceConstants[order=3] (the single-edge shortcut), and an
amortized QHGK kappa that shortcuts the three-edge chain linewidth ->
total linewidth -> kappa (the multi-edge shortcut).
"""

from __future__ import annotations

import pytest
import sympy as sp

from omai.operator import LearnedOperator, path_boundary, validate_learned
from omai.thermal_transport.operator.edges import (
    compute_anharmonic_linewidth,
    compute_kappa_qhgk,
    sum_linewidths,
)
from omai.thermal_transport.operator.nodes import (
    ANHARMONIC_LINEWIDTH,
    BOUNDARY_LINEWIDTH,
    EIGENVECTORS,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    ISOTOPIC_LINEWIDTH,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_QHGK,
    TOTAL_LINEWIDTH,
)
from omai.thermal_transport.operator import EDGES, NODES


# --- the worked examples -------------------------------------------------

def _predict_linewidth(**overrides) -> LearnedOperator:
    """Surrogate of the 3ph linewidth with fc3 amortized into weights.

    Same inputs as the exact edge minus ForceConstants[order=3]; same
    output node; scheme entries re-declared verbatim from the exact edge.
    """
    kwargs = dict(
        name="predict_linewidth[channel=anharmonic_3ph][provider=learned]",
        inputs=(FREQUENCY_STATE, EIGENVECTORS, TEMPERATURE_STATE),
        outputs=(ANHARMONIC_LINEWIDTH,),
        schemes=dict(compute_anharmonic_linewidth.schemes),
        shortcuts=(compute_anharmonic_linewidth.name,),
        model_ref="model:example-linewidth@sha256:0000",
        trained_on=("dataset:example-labels@sha256:1111",),
        validity="test fixture",
        description="test fixture: fc3-amortized 3ph linewidth surrogate",
    )
    kwargs.update(overrides)
    return LearnedOperator(**kwargs)


def _predict_kappa_qhgk(**overrides) -> LearnedOperator:
    """Surrogate of QHGK kappa shortcutting the three-edge chain."""
    kwargs = dict(
        name="predict_kappa[transport_model=qhgk][provider=learned]",
        inputs=(
            FREQUENCY_STATE,
            EIGENVECTORS,
            TEMPERATURE_STATE,
            ISOTOPIC_LINEWIDTH,
            BOUNDARY_LINEWIDTH,
            HEAT_CAPACITY,
            GROUP_VELOCITY,
        ),
        outputs=(THERMAL_CONDUCTIVITY_QHGK,),
        schemes=dict(compute_kappa_qhgk.schemes),
        shortcuts=(
            compute_anharmonic_linewidth.name,
            sum_linewidths.name,
            compute_kappa_qhgk.name,
        ),
        model_ref="model:example-kappa@sha256:2222",
        trained_on=("dataset:example-labels@sha256:1111",),
        validity="test fixture",
        description="test fixture: fc3-amortized QHGK kappa surrogate",
    )
    kwargs.update(overrides)
    return LearnedOperator(**kwargs)


# --- path_boundary -------------------------------------------------------

def test_path_boundary_single_edge():
    boundary, terminal = path_boundary((compute_anharmonic_linewidth,))
    assert boundary == frozenset(
        {FREQUENCY_STATE, EIGENVECTORS, FORCE_CONSTANTS_3, TEMPERATURE_STATE}
    )
    assert terminal == frozenset({ANHARMONIC_LINEWIDTH})


def test_path_boundary_chain():
    boundary, terminal = path_boundary(
        (compute_anharmonic_linewidth, sum_linewidths, compute_kappa_qhgk)
    )
    assert terminal == frozenset({THERMAL_CONDUCTIVITY_QHGK})
    # Interior spaces are neither boundary nor terminal.
    assert ANHARMONIC_LINEWIDTH not in boundary
    assert TOTAL_LINEWIDTH not in boundary
    assert FORCE_CONSTANTS_3 in boundary
    assert ISOTOPIC_LINEWIDTH in boundary


# --- construction discipline ---------------------------------------------

def test_requires_shortcuts():
    with pytest.raises(ValueError, match="shortcuts"):
        _predict_linewidth(shortcuts=())


def test_requires_model_ref():
    with pytest.raises(ValueError, match="model_ref"):
        _predict_linewidth(model_ref="")


def test_never_sympy_executable():
    # Even a closed-form-looking ansatz formula must not make the edge
    # executable: a learned edge is a claim about a path, not a formula.
    gamma, a = sp.symbols(r"\Gamma A", positive=True)
    edge = _predict_linewidth(formula=sp.Eq(gamma, a))
    assert edge.is_executable_in_sympy is False


def test_never_authoritative():
    assert _predict_linewidth().is_authoritative is False


# --- validate_learned: the worked examples pass --------------------------

def test_linewidth_shortcut_validates():
    assert validate_learned((_predict_linewidth(),), EDGES, NODES) == []


def test_kappa_chain_shortcut_validates():
    assert validate_learned((_predict_kappa_qhgk(),), EDGES, NODES) == []


def test_amortized_inputs_names_the_fc3_wall():
    assert _predict_linewidth().amortized_inputs(EDGES) == frozenset(
        {FORCE_CONSTANTS_3}
    )
    assert _predict_kappa_qhgk().amortized_inputs(EDGES) == frozenset(
        {FORCE_CONSTANTS_3}
    )


def test_full_boundary_emulator_is_legal():
    # A surrogate that keeps fc3 as an input is a pure-speed emulator:
    # nothing amortized, still a valid shortcut.
    edge = _predict_linewidth(
        inputs=(FREQUENCY_STATE, EIGENVECTORS, FORCE_CONSTANTS_3, TEMPERATURE_STATE)
    )
    assert validate_learned((edge,), EDGES, NODES) == []
    assert edge.amortized_inputs(EDGES) == frozenset()


# --- validate_learned: violations ----------------------------------------

def test_unknown_shortcut_name():
    edge = _predict_linewidth(shortcuts=("compute_linewidth[channel=nope]",))
    violations = validate_learned((edge,), EDGES, NODES)
    assert len(violations) == 1
    assert "unknown shortcut" in violations[0]


def test_output_must_match_path_terminal():
    edge = _predict_kappa_qhgk(outputs=(TOTAL_LINEWIDTH,))
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("terminal outputs" in v for v in violations)


def test_input_produced_by_path_rejected():
    edge = _predict_kappa_qhgk(
        inputs=(FREQUENCY_STATE, TOTAL_LINEWIDTH, TEMPERATURE_STATE)
    )
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("produced by the shortcut path" in v for v in violations)


def test_downstream_input_rejected():
    edge = _predict_linewidth(
        inputs=(FREQUENCY_STATE, THERMAL_CONDUCTIVITY_QHGK, TEMPERATURE_STATE)
    )
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("downstream" in v for v in violations)


def test_scheme_inheritance_enforced():
    edge = _predict_linewidth(schemes={})
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("broadening_param" in v for v in violations)
    assert any("symmetry_group" in v for v in violations)


def test_scheme_value_mismatch_rejected():
    schemes = dict(compute_anharmonic_linewidth.schemes)
    schemes["broadening_param"] = "halfwidth"
    edge = _predict_linewidth(schemes=schemes)
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("broadening_param" in v for v in violations)


def test_name_collision_with_exact_edge_rejected():
    edge = _predict_linewidth(name=compute_anharmonic_linewidth.name)
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("collides" in v for v in violations)


def test_missing_trained_on_rejected():
    """An entirely absent trained_on is a provenance violation, not a pass:
    the per-entry check alone is silent on an empty tuple."""
    learned = _predict_linewidth(trained_on=())
    errors = validate_learned([learned], EDGES, NODES)
    assert any("trained_on is empty" in e for e in errors)


def test_empty_trained_on_entry_rejected():
    edge = _predict_linewidth(trained_on=("",))
    violations = validate_learned((edge,), EDGES, NODES)
    assert any("trained_on" in v for v in violations)
