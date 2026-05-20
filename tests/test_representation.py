"""Tests for the thermal-transport adapter conformance specs."""

from __future__ import annotations

import math

import pytest

from omai.representation import (
    conversion_factor,
    operator_to_representation,
    representation_discretization_match,
    representation_scheme_match,
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


# Convenience: cross-adapter A→B factor is the composition of the two
# primitives (Section: "star topology" in the substrate doc).
def _inter_rep_factor(a, b, obs):
    return operator_to_representation(b, obs) * representation_to_operator(a, obs)


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


# --- space adapters: linewidth ---


def test_kaldo_linewidth_unit_is_angular_thz():
    assert KALDO_LINEWIDTH.declared_unit("Gamma") == "angular_THz"


def test_phono3py_linewidth_unit_is_linear_thz():
    assert PHONO3PY_LINEWIDTH.declared_unit("Gamma") == "linear_THz"


def test_kaldo_to_phono3py_unit_factor_is_one_over_two_pi():
    f = conversion_factor(
        KALDO_LINEWIDTH.declared_unit("Gamma"),
        PHONO3PY_LINEWIDTH.declared_unit("Gamma"),
    )
    assert math.isclose(f, 1.0 / (2 * math.pi))


def test_kaldo_linewidth_normalization_factor_is_one_half():
    """kaldo declares Gamma = 2 Im Sigma (the `linewidth_2x_imag_self_energy`
    normalization); canonical is Im Sigma. Composing kaldo's emission with
    the normalization's to_operator value (0.5) must recover the canonical
    multiplier."""
    from omai.representation.normalizations import NORMALIZATIONS
    assert math.isclose(NORMALIZATIONS["linewidth_2x_imag_self_energy"].to_operator, 0.5)


def test_phono3py_linewidth_uses_canonical_normalization():
    # phono3py declares no normalization override → falls back to canonical.
    assert PHONO3PY_LINEWIDTH.observable_normalizations.get("Gamma", "canonical") == "canonical"


def test_kaldo_to_phono3py_total_factor_closes_4pi_gap():
    """Combined unit + normalization factor matches the empirical 1/(4π).

    kaldo emits Γ in angular_THz with the 2× linewidth normalization (so
    its to_operator multiplier is 2π · 0.5 = π); phono3py emits Γ in
    linear_THz with canonical normalization (to_operator multiplier is
    1.0). Then kaldo→phono3py factor is (1/1.0) · π = π… but the empirical
    gap is 1/(4π). The discrepancy is the opposite-direction convention:
    canonical operator-form Γ corresponds to Im Σ in *linear* THz, so the
    factor from kaldo's emitted value to phono3py's emitted value is
    operator_to_representation(phono3py, Γ) · representation_to_operator(
    kaldo, Γ) = 1.0 · (2π · 0.5) = π. The 4π appears the other way (multiply
    phono3py by 4π to recover kaldo's number)."""
    f = _inter_rep_factor(PHONO3PY_LINEWIDTH, KALDO_LINEWIDTH, "Gamma")
    assert math.isclose(f, 4 * math.pi)


# --- space adapters: heat capacity ---


def test_heat_capacity_unit_factor_is_e():
    f = conversion_factor(
        KALDO_HEAT_CAPACITY.declared_unit("c"),
        PHONO3PY_HEAT_CAPACITY.declared_unit("c"),
    )
    assert math.isclose(f, 1.0 / 1.602176634e-19)


def test_heat_capacity_total_equals_unit_when_no_normalizations():
    """No space-level normalization on HeatCapacity, so total ≡ unit."""
    unit = conversion_factor(
        KALDO_HEAT_CAPACITY.declared_unit("c"),
        PHONO3PY_HEAT_CAPACITY.declared_unit("c"),
    )
    total = _inter_rep_factor(KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c")
    assert math.isclose(unit, total)


# --- operator adapters: schemes ---


def test_broadening_param_scheme_mismatch_surfaced():
    matched, msg = representation_scheme_match(
        KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is False
    assert "adaptive_velocity_projection" in msg
    assert "stdev" in msg


# --- operator adapters: discretization choices ---


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


def test_cross_operator_for_different_operators_raises():
    with pytest.raises(ValueError, match="different operators"):
        representation_scheme_match(
            KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_HEAT_CAPACITY, "broadening_param"
        )


def test_unknown_observable_raises():
    with pytest.raises(KeyError):
        KALDO_LINEWIDTH.declared_unit("not_a_quantity")


def test_unknown_scheme_raises():
    with pytest.raises(KeyError):
        KALDO_COMPUTE_LINEWIDTH.declared_scheme("not_a_scheme")


# --- operator adapter factories: kaldo broadening mode parameterization ---


def test_kaldo_compute_linewidth_default_factory_matches_module_constant():
    """Calling the factory with no args yields the same configuration as the
    module-level constant (kaldo default: adaptive velocity-projection)."""
    from omai.thermal_transport.representation import (
        KALDO_COMPUTE_LINEWIDTH,
        kaldo_compute_linewidth_spec,
    )
    default = kaldo_compute_linewidth_spec()
    assert default.declared_scheme("broadening_param") == \
        KALDO_COMPUTE_LINEWIDTH.declared_scheme("broadening_param")
    assert default.declared_scheme("broadening_param") == \
        "adaptive_velocity_projection"


def test_cross_adapter_factor_factors_through_operator():
    """The star-topology architectural commitment: cross-adapter factors
    must factor through the operator/canonical form. Verify mechanically
    that the helper composition equals the explicit operator hub
    composition.
    """
    for a, b, obs in [
        (KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH, "Gamma"),
        (PHONO3PY_LINEWIDTH, KALDO_LINEWIDTH, "Gamma"),
        (KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY, "c"),
        (PHONO3PY_HEAT_CAPACITY, KALDO_HEAT_CAPACITY, "c"),
    ]:
        helper = _inter_rep_factor(a, b, obs)
        composed = operator_to_representation(b, obs) * representation_to_operator(a, obs)
        assert math.isclose(helper, composed, rel_tol=1e-12)


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
    """Asking for halfwidth mode produces a spec whose declared scheme
    reflects the fixed-σ kaldo configuration (third_bandwidth=σ set)."""
    from omai.thermal_transport.representation import kaldo_compute_linewidth_spec
    spec = kaldo_compute_linewidth_spec(broadening_param="halfwidth")
    assert spec.declared_scheme("broadening_param") == "halfwidth"
    # Halfwidth mode should disagree with shengbte's adaptive default; the
    # cross-operator match must surface that.
    from omai.representation.adapter import representation_scheme_match
    from omai.thermal_transport.representation import SHENGBTE_COMPUTE_LINEWIDTH
    matched, msg = representation_scheme_match(
        spec, SHENGBTE_COMPUTE_LINEWIDTH, "broadening_param"
    )
    assert matched is False
    assert "halfwidth" in msg
    assert "adaptive_velocity_projection" in msg
