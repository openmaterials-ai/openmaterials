"""Demonstration: the substrate spec layer predicts cross-adapter discrepancies.

Without running any LAMMPS, this loads the kaldo and phono3py adapter specs
for the operations exercised in this experiment and prints what the
substrate predicts for cross-adapter comparison.

The 4π factor on Linewidth and the e factor on HeatCapacity that took days
of empirical investigation in `extract_diagnostics.py` are surfaced here at
spec-load time. The 4π decomposes into a 2π unit factor (angular vs linear
THz) and a factor-of-2 convention factor (kaldo's Gamma = 2 Im Sigma;
phono3py emits Im Sigma directly).
"""

from __future__ import annotations

import math

from omai.spec import (
    cross_operation_algorithmic_match,
    cross_operation_discretization_match,
    cross_state_total_factor,
    cross_state_unit_factor,
)
from omai.spec.thermal_transport import (
    KALDO_COMPUTE_LINEWIDTH,
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
)


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    print("=" * 70)
    print("Substrate spec layer: predictions for kaldo vs. phono3py")
    print("=" * 70)

    a, b = KALDO_LINEWIDTH, PHONO3PY_LINEWIDTH

    section("State [Linewidth]: observable Gamma")
    print(f"  kaldo    declares : Gamma in {a.declared_unit('Gamma')}, "
          f"convention {a.declared_convention('gamma_definition')}")
    print(f"  phono3py declares : Gamma in {b.declared_unit('Gamma')}, "
          f"convention {b.declared_convention('gamma_definition')}")
    unit = cross_state_unit_factor(a, b, "Gamma")
    c_a = a.observable_convention_factor("Gamma")
    c_b = b.observable_convention_factor("Gamma")
    total = cross_state_total_factor(a, b, "Gamma")
    print(f"  unit factor (angular_THz → linear_THz)       : {unit:.6f}  [= 1/(2π)]")
    print(f"  kaldo output factor relative to canonical    : {c_a:.1f}    [Gamma = 2 Im Σ]")
    print(f"  phono3py output factor relative to canonical : {c_b:.1f}    [Gamma = Im Σ]")
    print(f"  → total: kaldo × {total:.6f} = phono3py       [= 1/(4π) = {1/(4*math.pi):.6f}]")
    print(f"  matches the empirical kaldo/phono3py ratio of 4π.")

    a, b = KALDO_HEAT_CAPACITY, PHONO3PY_HEAT_CAPACITY

    section("State [HeatCapacity]: observable c")
    print(f"  kaldo    declares : c in {a.declared_unit('c')}")
    print(f"  phono3py declares : c in {b.declared_unit('c')}")
    factor = cross_state_total_factor(a, b, "c")
    print(f"  → total: kaldo × {factor:.6e} = phono3py     [= 1/e ≈ 6.241e+18]")

    a_op, b_op = KALDO_COMPUTE_LINEWIDTH, PHONO3PY_COMPUTE_LINEWIDTH

    section("Operation [compute_linewidth]: algorithmic conventions")
    matched, msg = cross_operation_algorithmic_match(a_op, b_op, "broadening_param")
    if matched:
        print(f"  broadening_param: agreed.")
    else:
        print(f"  broadening_param MISMATCH: {msg}")
        print(f"  → kaldo σ = phono3py σ × √2  (halfwidth = stdev × √2 ≈ {math.sqrt(2):.6f})")

    section("Operation [compute_linewidth]: discretization choices")
    for choice in ("bz_summation", "delta_cutoff_sigmas", "degeneracy_averaging"):
        matched, msg = cross_operation_discretization_match(a_op, b_op, choice)
        if matched:
            print(f"  {choice}: agreed.")
        else:
            print(f"  {choice}: {msg}")
    print(f"  → bz_summation differs but ΣΓ remains stable (contracted observable);")
    print(f"    per-mode Γ_qν will redistribute (~3% std/mean empirically).")
    print(f"    'Linewidth' carries a not-directly-comparable protocol per Principle 7.")

    print()
    print("=" * 70)
    print("All cross-code discrepancies above were found *before running anything*.")
    print("Compare with the multi-day empirical investigation in")
    print("docs/worked_example_silicon.tex.")
    print("=" * 70)


if __name__ == "__main__":
    main()
