"""Cross-adapter comparison of Materializations.

`compare` takes two materializations of the same abstract state and observable
(produced by different adapters), applies the spec-derived conversion factor
(unit + convention) from `cross_state_total_factor`, optionally contracts the
arrays via a user-provided callable, and reports a numerical residual against
a tolerance.

This is the loop closure of the substrate's symbolic claim. The adapter specs
*predict* a conversion factor; `compare` *applies* it to real data and *checks*
that the codes agree to the spec'd tolerance. Disagreement at this layer is a
real adapter conformance failure, not a numerical mystery.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from omai.materialization.adapter import cross_state_total_factor
from omai.materialization.instance import Materialization


@dataclass(frozen=True)
class ComparisonResult:
    passed: bool
    factor: float
    contracted: bool
    max_absolute_residual: float
    max_relative_residual: float
    rtol: float
    atol: float

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        contraction = " (contracted)" if self.contracted else " (per-element)"
        return (
            f"[{verdict}]{contraction} factor={self.factor:.6e}, "
            f"max_abs={self.max_absolute_residual:.3e}, "
            f"max_rel={self.max_relative_residual:.3e}, "
            f"rtol={self.rtol:.0e}, atol={self.atol:.0e}"
        )


def compare(
    m_a: Materialization,
    m_b: Materialization,
    *,
    contraction: Callable[[np.ndarray], Any] | None = None,
    rtol: float = 1e-3,
    atol: float = 0.0,
) -> ComparisonResult:
    """Apply the spec-predicted factor to A's data and compare to B's.

    Both materializations must wrap the same state and observable.

    Args:
        m_a, m_b: materializations from two adapters of the same abstract state.
        contraction: optional callable applied to both arrays before
            comparison (e.g., np.sum to compare contracted scalars). When
            None, comparison is per-element.
        rtol, atol: passed to np.allclose for the pass/fail verdict.

    Returns:
        ComparisonResult with the applied factor and the maximum relative
        residual observed.
    """
    if m_a.state != m_b.state:
        raise ValueError(
            f"materializations wrap different states: "
            f"{m_a.state.name!r} vs {m_b.state.name!r}"
        )
    if m_a.observable_name != m_b.observable_name:
        raise ValueError(
            f"materializations wrap different observables: "
            f"{m_a.observable_name!r} vs {m_b.observable_name!r}"
        )

    factor = cross_state_total_factor(
        m_a.state_adapter_spec, m_b.state_adapter_spec, m_a.observable_name
    )
    a_converted = m_a.data * factor
    b = m_b.data
    if contraction is not None:
        a_converted = contraction(a_converted)
        b = contraction(b)

    a_arr = np.asarray(a_converted, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    abs_diff = np.abs(a_arr - b_arr)
    max_abs = float(np.max(abs_diff)) if abs_diff.size else 0.0

    # Relative residual is only meaningful where |b| is above the noise floor;
    # at acoustic Γ-modes (ω, v ≈ 0) it blows up artificially. Use atol as
    # the floor below which we treat values as "indistinguishable from zero".
    mask = np.abs(b_arr) > atol
    if mask.any():
        rel = abs_diff[mask] / np.abs(b_arr[mask])
        max_rel = float(np.max(rel))
    else:
        max_rel = 0.0

    passed = bool(np.allclose(a_arr, b_arr, rtol=rtol, atol=atol))

    return ComparisonResult(
        passed=passed,
        factor=factor,
        contracted=contraction is not None,
        max_absolute_residual=max_abs,
        max_relative_residual=max_rel,
        rtol=rtol,
        atol=atol,
    )
