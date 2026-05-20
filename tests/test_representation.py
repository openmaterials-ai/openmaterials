"""Tests for the thermal-transport adapter conformance specs."""

from __future__ import annotations

import math

import pytest

from omai.representation import (
    conversion_factor,
    operator_to_representation,
    representation_algorithmic_match,
    representation_discretization_match,
    representation_convention_match,
    inter_representation_factor,
    inter_representation_unit_factor,
    representation_to_operator,
)
from omai.thermal_transport.representation import (
    KALDO_COMPUTE_HEAT_CAPACITY,
    KALDO_COMPUTE_LINEWIDTH,
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    PHONO3PY_COMPUTE_HEAT_CAPACITY,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
)


# --- units ---


def test_linear_thz_to_angular_thz_round_trip():
    f = conversion_factor("linear_THz", "angular_THz")
    assert math.isclose(f, 2 * math.pi)
    assert math.isclose(conversion_factor("angular_THz", "linear_THz"), 1.0 / (2 * math.pi))


def test_eV_per_K_to_J_per_K_is_boltzmann_factor():
    f = conversion_factor("eV_per_K", "J_per_K")
    assert math.isclose(f, 1.602176634e-19)


def test_dimension_mismatch_raises():
    with pytest.raises(ValueError, match="different dimensions"):
        conversion_factor("linear_THz", "J_per_K")


# --- state adapters: linewidth ---


def test_kaldo_linewidth_unit_is_angular_thz():
    assert KALDO_LINEWIDTH.declared_unit("Gamma") == "angular_THz"


def test_phono3py_linewidth_unit_is_linear_thz():
    assert PHONO3PY_LINEWIDTH.declared_unit("Gamma") == "linear_THz"


def test_kaldo_to_phono3py_unit_factor_is_one_over_two_pi():
    f = inter_representation_unit_factor(KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma")
    assert math.isclose(f, 1.0 / (2 * math.pi))


def test_kaldo_linewidth_convention_factor_is_2():
    """kaldo declares Gamma = 2 Im Sigma; canonical is Im Sigma."""
    assert math.isclose(KALDO_LINEWIDTH.observable_convention_factor("Gamma"), 2.0)


def test_phono3py_linewidth_convention_factor_is_canonical():
    assert math.isclose(PHONO3PY_LINEWIDTH.observable_convention_factor("Gamma"), 1.0)


def test_kaldo_to_phono3py_total_factor_closes_4pi_gap():
    """Combined unit + convention factor matches the empirical 4π."""
    f = inter_representation_factor(KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma")
    assert math.isclose(f, 1.0 / (4 * math.pi))


def test_gamma_definition_convention_mismatch_is_surfaced():
    matched, msg = representation_convention_match(
        KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "gamma_definition"
    )
    assert matched is False
    assert "linewidth_2x_imag_self_energy" in msg
    assert "imag_self_energy" in msg


# --- state adapters: heat capacity ---


def test_heat_capacity_unit_factor_is_e():
    f = inter_representation_unit_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    assert math.isclose(f, 1.0 / 1.602176634e-19)


def test_heat_capacity_total_equals_unit_when_no_conventions():
    """No state-level conventions on HeatCapacity, so total = unit."""
    unit = inter_representation_unit_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    total = inter_representation_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    assert math.isclose(unit, total)


# --- operation adapters: algorithmic conventions ---


def test_broadening_param_convention_mismatch_surfaced():
    matched, msg = representation_algorithmic_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is False
    assert "adaptive_velocity_projection" in msg
    assert "stdev" in msg


# --- operation adapters: discretization choices ---


def test_bz_summation_discretization_mismatch_surfaced():
    matched, msg = representation_discretization_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "bz_summation"
    )
    assert matched is False
    assert "full_grid" in msg
    assert "symmetry_reduced" in msg


def test_delta_cutoff_discretization_mismatch_surfaced():
    matched, msg = representation_discretization_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "delta_cutoff_sigmas"
    )
    assert matched is False


# --- error paths ---


def test_cross_state_for_different_states_raises():
    with pytest.raises(ValueError, match="different states"):
        inter_representation_unit_factor(KALDO_LINEWIDTH, PHONO3PY_HEAT_CAPACITY, "Gamma")


def test_cross_operation_for_different_operations_raises():
    with pytest.raises(ValueError, match="different operations"):
        representation_algorithmic_match(
            KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_HEAT_CAPACITY, "broadening_param"
        )


def test_unknown_observable_raises():
    with pytest.raises(KeyError):
        KALDO_LINEWIDTH.declared_unit("not_a_quantity")


def test_unknown_convention_raises():
    with pytest.raises(KeyError):
        KALDO_LINEWIDTH.declared_convention("not_a_convention")


# --- operation adapter factories: kaldo broadening mode parameterization ---


def test_kaldo_compute_linewidth_default_factory_matches_module_constant():
    """Calling the factory with no args yields the same configuration as the
    module-level constant (kaldo default: adaptive velocity-projection)."""
    from omai.thermal_transport.representation import (
        KALDO_COMPUTE_LINEWIDTH,
        kaldo_compute_linewidth_spec,
    )
    default = kaldo_compute_linewidth_spec()
    assert default.declared_algorithmic_convention("broadening_param") == \
        KALDO_COMPUTE_LINEWIDTH.declared_algorithmic_convention("broadening_param")
    assert default.declared_algorithmic_convention("broadening_param") == \
        "adaptive_velocity_projection"


def test_inter_representation_factor_equals_composition_through_operator():
    """The star-topology architectural commitment: cross-adapter factors
    must factor through the operator/canonical form. Verify mechanically
    that
        inter_representation_factor(A, B, obs)
          == operator_to_representation(B, obs)
             * representation_to_operator(A, obs)

    This is a load-bearing invariant: no direct A→B mapping should ever
    diverge from the composition; if it does, the framework has snuck a
    second source of truth.
    """
    for a, b, obs in [
        (KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma"),
        (PHONO3PY_LINEWIDTH, KALDO_LINEWIDTH, "Gamma"),
        (KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c"),
        (PHONO3PY_HEAT_CAPACITY, KALDO_HEAT_CAPACITY, "c"),
    ]:
        direct = inter_representation_factor(a, b, obs)
        composed = operator_to_representation(b, obs) * representation_to_operator(a, obs)
        assert math.isclose(direct, composed, rel_tol=1e-12), (
            f"star-topology composition broke for {a.representation_name}→"
            f"{b.representation_name} on {obs}: direct={direct}, composed={composed}"
        )


def test_representation_to_operator_and_back_are_inverses():
    """representation_to_operator(A) * operator_to_representation(A) ≈ 1
    for every (spec, observable). Round-trip identity."""
    for spec, obs in [
        (KALDO_LINEWIDTH, "Gamma"),
        (PHONO3PY_LINEWIDTH, "Gamma"),
        (KALDO_HEAT_CAPACITY, "c"),
        (PHONO3PY_HEAT_CAPACITY, "c"),
    ]:
        forward = representation_to_operator(spec, obs)
        reverse = operator_to_representation(spec, obs)
        assert math.isclose(forward * reverse, 1.0, rel_tol=1e-12), (
            f"representation_to_operator and operator_to_representation "
            f"not inverse for {spec.representation_name} on {obs}: "
            f"forward={forward}, reverse={reverse}"
        )


def test_kaldo_compute_linewidth_factory_halfwidth_mode():
    """Asking for halfwidth mode produces a spec whose declared convention
    reflects the fixed-σ kaldo configuration (third_bandwidth=σ set)."""
    from omai.thermal_transport.representation import kaldo_compute_linewidth_spec
    spec = kaldo_compute_linewidth_spec(broadening_param="halfwidth")
    assert spec.declared_algorithmic_convention("broadening_param") == "halfwidth"
    # Halfwidth mode should disagree with shengbte's adaptive default; the
    # cross-operation match must surface that.
    from omai.representation.adapter import representation_algorithmic_match
    from omai.thermal_transport.representation import SHENGBTE_COMPUTE_LINEWIDTH
    matched, msg = representation_algorithmic_match(
        spec, SHENGBTE_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is False
    assert "halfwidth" in msg
    assert "adaptive_velocity_projection" in msg
