"""Operator and representation comparison for Representations.

We borrow vocabulary from quantum mechanics:

  * A operator State is an **abstract operator** — basis-independent,
    defined by its dimension, fields, gauge group, and canonical
    conventions.
  * A Representation is that operator in a **specific representation**
    — a particular code's units and conventions.
  * `to_operator(m)` strips the representation and returns the
    representation in operator form (canonical reference: canonical
    unit and canonical convention values).
  * `to_representation(m_op, target_spec)` is the inverse: given a
    representation already in operator form, re-express it in some
    target adapter's representation.
  * `compare_operators(spec_a, spec_b)` is a structural / type-level
    check: do the two specs claim the same operator (same operator
    state, compatible units, conventions resolving to the same
    canonical values)? No tolerance — categorical answer.
  * `compare_representations(m_a, m_b, …, rtol, atol, contraction)` is
    the numerical check: are the actual array values equal once
    expressed in a common representation? Returns a RepresentationComparisonResult
    with residuals and the agree/disagree verdict.

The QM analogy isn't decorative — it matches the gauge structure:
Observables behave like the spectrum of an operator (basis-invariant,
cross-code-comparable), HiddenStates behave like matrix elements in a
specific basis (per-element only meaningful after a basis-matching
contraction).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from omai.operator.state import HiddenState
from omai.representation.adapter import StateAdapterSpec
from omai.representation.instance import Representation
from omai.representation.units import conversion_factor


# ---------------------------------------------------------------------------
# Structural ("operator-level") comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatorComparisonResult:
    """Categorical structural verdict from `compare_operators`.

    Two adapter specs describe the same operator iff:
      * they wrap the same operator State,
      * for every declared observable, their declared units have the
        same physical dimension (otherwise canonicalisation is
        impossible — they're not even comparable),
      * for every convention the state declares, both specs resolve to
        the same canonical-value chain (i.e. after applying their
        convention factors, they land on the same canonical operator).
    """

    same_operator: bool
    mismatches: tuple[str, ...]

    def summary(self) -> str:
        if self.same_operator:
            return "OPERATORS_AGREE"
        return "OPERATORS_DIFFER: " + "; ".join(self.mismatches)


def compare_operators(
    spec_a: StateAdapterSpec, spec_b: StateAdapterSpec
) -> OperatorComparisonResult:
    """Structural check: do two adapter specs describe the same operator?

    No tolerance — this is a categorical answer about what is being
    claimed at the operator level, before any numbers are touched.
    Useful for verifying that two codes are talking about the same
    physical quantity before trying to compare their numerical outputs.
    """
    mismatches: list[str] = []

    if spec_a.state != spec_b.state:
        mismatches.append(
            f"different operator states: {spec_a.state.name!r} vs "
            f"{spec_b.state.name!r}"
        )
        return OperatorComparisonResult(False, tuple(mismatches))

    state = spec_a.state
    for field in state.fields:
        # Units must have the same dimension (otherwise no canonicalisation).
        try:
            u_a = spec_a.declared_unit(field.name)
            u_b = spec_b.declared_unit(field.name)
        except KeyError:
            # Scaffolding spec: no unit declared. Can't structurally
            # confirm, but also can't disprove — leave silent rather
            # than flag a false mismatch.
            continue
        try:
            conversion_factor(u_a, u_b)  # raises if different dimensions
        except ValueError as exc:
            mismatches.append(f"field {field.name!r} unit incompatibility: {exc}")

    # Convention canonicalisation: each spec's declared convention values
    # must produce the same canonical operator. Concretely, two specs
    # describe the same operator only if for every convention key the
    # canonical *operator* arrived at is the same. Since the canonical
    # operator is defined by the operator State (single source of
    # truth), what we actually check is that the specs' declared
    # conventions resolve to a known convention value in the state.
    # The state's canonicalisation chain then guarantees both land on
    # the same canonical operator.
    for conv_name, canonical_value in state.canonical_conventions.items():
        try:
            val_a = spec_a.declared_convention(conv_name)
            val_b = spec_b.declared_convention(conv_name)
        except KeyError:
            continue
        # Each must be either canonical or a known non-canonical value
        # with a defined convention_factor. If either spec's value is
        # unknown to the state, we cannot canonicalise it.
        known_values = {canonical_value} | {
            v for _, v, _, _ in state.convention_factors
        }
        if val_a not in known_values:
            mismatches.append(
                f"adapter {spec_a.adapter_name!r}: convention {conv_name}="
                f"{val_a!r} is not a known canonical/non-canonical value"
            )
        if val_b not in known_values:
            mismatches.append(
                f"adapter {spec_b.adapter_name!r}: convention {conv_name}="
                f"{val_b!r} is not a known canonical/non-canonical value"
            )

    return OperatorComparisonResult(not mismatches, tuple(mismatches))


# ---------------------------------------------------------------------------
# Basis transforms: to_operator / to_representation
# ---------------------------------------------------------------------------


def _spec_to_canonical_factor(
    spec: StateAdapterSpec, observable_name: str
) -> float:
    """Factor f such that (spec's emitted value) × f = (canonical value).

    Combines the unit factor (to the canonical unit) and the convention
    factor (to the canonical convention values). Raises a clear
    KeyError if either piece is missing on the spec.
    """
    state = spec.state
    field = state.field(observable_name)
    canonical_unit = _canonical_unit_for(state, field.name)
    try:
        unit = spec.declared_unit(observable_name)
    except KeyError as exc:
        raise KeyError(
            f"adapter {spec.adapter_name!r} declares no unit for field "
            f"{observable_name!r} of state {state.name!r}; cannot place "
            f"this representation into operator form. Add an "
            f"observable_units entry to its StateAdapterSpec, or "
            f"represent the canonical form directly."
        ) from exc
    u_factor = conversion_factor(unit, canonical_unit)
    # observable_convention_factor returns c such that
    # emitted_value = c × canonical_value (in matching units), so to go
    # from emitted to canonical we divide by c.
    c_factor = spec.observable_convention_factor(observable_name)
    return u_factor / c_factor


def _canonical_unit_for(state, observable_name: str) -> str:
    """Look up the canonical unit name for an observable.

    The canonical unit is whichever named unit on the state's field
    dimension carries a to_canonical factor of 1.0.
    """
    from omai.representation.units import UNITS

    field = state.field(observable_name)
    for u in UNITS.values():
        if u.dimension == field.dimension and u.to_canonical == 1.0:
            return u.name
    # Fallback: use any unit on this dimension. (Shouldn't happen if
    # the unit registry is well-formed.)
    for u in UNITS.values():
        if u.dimension == field.dimension:
            return u.name
    raise KeyError(
        f"no unit registered for dimension {field.dimension.name!r} of "
        f"state {state.name!r} field {observable_name!r}"
    )


def to_operator(m: Representation) -> Representation:
    """Reframe a Representation in operator (canonical) form.

    The returned Representation carries data multiplied by the spec's
    `to_canonical_factor`, and `is_operator_form=True`. The
    state_adapter_spec on the returned object is unchanged (it still
    records the *originating* adapter), but downstream consumers should
    treat the data as basis-independent — units are the operator
    layer's canonical unit, conventions are the canonical values.
    """
    if m.is_operator_form:
        return m
    factor = _spec_to_canonical_factor(m.state_adapter_spec, m.observable_name)
    new_data = np.asarray(m.data, dtype=float) * factor
    return replace(m, data=new_data, is_operator_form=True)


def to_representation(
    m_op: Representation, target_spec: StateAdapterSpec
) -> Representation:
    """Reframe an operator-form Representation in a target adapter's
    representation. Multiplicatively inverse of `to_operator`.

    Useful when you have a canonical reference (e.g., an experimental
    value or a published number) and want to know what a specific code
    would have printed if it had agreed.
    """
    if not m_op.is_operator_form:
        m_op = to_operator(m_op)
    if target_spec.state != m_op.state:
        raise ValueError(
            f"target_spec wraps a different state: "
            f"{target_spec.state.name!r} vs {m_op.state.name!r}"
        )
    factor = _spec_to_canonical_factor(target_spec, m_op.observable_name)
    new_data = np.asarray(m_op.data, dtype=float) / factor
    return Representation(
        state_adapter_spec=target_spec,
        observable_name=m_op.observable_name,
        data=new_data,
        is_operator_form=False,
    )


# ---------------------------------------------------------------------------
# Numerical comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepresentationComparisonResult:
    """Numerical verdict from `compare_representations`.

    The status flag mirrors the QM analogy: comparing matrix elements
    (representation-level) is a numerical agree/disagree question. The
    operator layer (operator-level) predicts whether the matrix elements
    *should* agree given the gauge type of the state:

      * Observable per-element  → predicted to agree (basis-independent
                                  in the gauge-invariant sense).
      * HiddenState per-element → NOT_COMPARABLE without a contraction
                                  (matrix elements only meaningful in a
                                  matched basis).
      * Any state, contracted   → predicted to agree (the contraction
                                  is the gauge-invariant content).

    EXPECTED_AGREE      — predicted to agree, observed agreement.
    EXPECTED_DISAGREE   — predicted not to agree, observed disagreement
                          (user override for partial contractions).
    UNEXPECTED_DISAGREE — predicted to agree, observed disagreement
                          (real anomaly: missing convention, real
                          physics disagreement, or rtol too strict).
    UNEXPECTED_AGREE    — predicted not to agree, observed agreement
                          (rare; per-element protocol tighter than
                          declared).
    NOT_COMPARABLE      — HiddenState per-element; residuals reported
                          for diagnostic inspection only.
    """

    agreed: bool
    expected_to_agree: bool
    factor: float
    contracted: bool
    max_absolute_residual: float
    max_relative_residual: float
    rtol: float
    atol: float
    not_comparable: bool = False

    @property
    def status(self) -> str:
        if self.not_comparable:
            return "NOT_COMPARABLE"
        if self.expected_to_agree and self.agreed:
            return "EXPECTED_AGREE"
        if not self.expected_to_agree and not self.agreed:
            return "EXPECTED_DISAGREE"
        if self.expected_to_agree and not self.agreed:
            return "UNEXPECTED_DISAGREE"
        return "UNEXPECTED_AGREE"

    def summary(self) -> str:
        status = self.status
        contraction = " (contracted)" if self.contracted else " (per-element)"
        return (
            f"[{status}]{contraction} factor={self.factor:.6e}, "
            f"max_abs={self.max_absolute_residual:.3e}, "
            f"max_rel={self.max_relative_residual:.3e}, "
            f"rtol={self.rtol:.0e}, atol={self.atol:.0e}"
        )


def compare_representations(
    m_a: Representation,
    m_b: Representation,
    *,
    contraction: Callable[[np.ndarray], Any] | None = None,
    rtol: float = 1e-3,
    atol: float = 0.0,
    expected_to_agree: bool | None = None,
) -> RepresentationComparisonResult:
    """Numerical agreement check between two representations.

    Internally canonicalises both representations into operator form
    via `to_operator`, then numpy-compares. The reported `factor` is
    the inter-representation factor (A's emitted value × factor =
    B's emitted value), recovered post-hoc for diagnostic purposes;
    it isn't used in the comparison itself.

    Args:
        m_a, m_b: representations of the same operator state and
            observable, in any (possibly differing) representations.
        contraction: optional callable applied to both canonical arrays
            before comparison (e.g., np.sum to compare contracted
            scalars). When None, comparison is per-element.
        rtol, atol: passed to np.allclose for the verdict.
        expected_to_agree: override the operator layer's prediction. By
            default inferred from the state's kind (Observable / per
            element-tight; HiddenState per-element / NOT_COMPARABLE;
            contracted forms / agree).

    Returns:
        RepresentationComparisonResult with residuals and a status reflecting how
        the empirical outcome lines up with the operator prediction.
    """
    if m_a.state != m_b.state:
        raise ValueError(
            f"representations wrap different states: "
            f"{m_a.state.name!r} vs {m_b.state.name!r}"
        )
    if m_a.observable_name != m_b.observable_name:
        raise ValueError(
            f"representations wrap different observables: "
            f"{m_a.observable_name!r} vs {m_b.observable_name!r}"
        )

    # Lift both to operator form.
    a_op = to_operator(m_a)
    b_op = to_operator(m_b)

    # Inter-representation factor, reconstructed for diagnostics:
    # factor_A→B = (b_emitted_value) / (a_emitted_value) where both
    # represent the same canonical value.
    if m_a.is_operator_form and m_b.is_operator_form:
        factor_a_to_b = 1.0
    else:
        f_a = _spec_to_canonical_factor(m_a.state_adapter_spec, m_a.observable_name) \
            if not m_a.is_operator_form else 1.0
        f_b = _spec_to_canonical_factor(m_b.state_adapter_spec, m_b.observable_name) \
            if not m_b.is_operator_form else 1.0
        # a_op_value = a_value * f_a; b_op_value = b_value * f_b.
        # In operator form they should match: a_value * f_a ≈ b_value * f_b
        # → a_value = b_value * (f_b / f_a), so factor_a_to_b = f_a / f_b.
        factor_a_to_b = f_a / f_b

    a = a_op.data
    b = b_op.data
    if contraction is not None:
        a = contraction(a)
        b = contraction(b)

    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    abs_diff = np.abs(a_arr - b_arr)
    max_abs = float(np.max(abs_diff)) if abs_diff.size else 0.0

    mask = np.abs(b_arr) > atol
    if mask.any():
        rel = abs_diff[mask] / np.abs(b_arr[mask])
        max_rel = float(np.max(rel))
    else:
        max_rel = 0.0

    agreed = bool(np.allclose(a_arr, b_arr, rtol=rtol, atol=atol))

    is_hidden_per_element = (
        isinstance(m_a.state, HiddenState) and contraction is None
    )

    if expected_to_agree is None:
        expected_to_agree = not is_hidden_per_element

    return RepresentationComparisonResult(
        agreed=agreed,
        expected_to_agree=expected_to_agree,
        factor=factor_a_to_b,
        contracted=contraction is not None,
        max_absolute_residual=max_abs,
        max_relative_residual=max_rel,
        rtol=rtol,
        atol=atol,
        not_comparable=is_hidden_per_element,
    )


# Convenience alias. `compare` reads as "compare these two representations"
# at call sites without forcing every test to type the longer name.
compare = compare_representations
