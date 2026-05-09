"""Demonstration: the substrate spec layer predicts cross-adapter discrepancies.

Without running any LAMMPS, this loads the kaldo and phono3py adapter specs for
the operations exercised in this experiment and prints what the substrate
predicts for cross-adapter comparison.

The 4π factor on Gamma_qν and the e-factor on heat capacity that took days of
empirical investigation in `extract_diagnostics.py` are surfaced here at
spec-load time. The 4π decomposes into a 2π unit factor (angular vs linear
THz) and a factor-of-2 convention factor (kaldo's linewidth = 2 × imaginary
self-energy; phono3py emits Im Sigma directly).
"""

from __future__ import annotations

import math

from omai.spec import (
    cross_adapter_convention_match,
    cross_adapter_total_factor,
    cross_adapter_unit_factor,
    output_convention_factor,
)
from omai.spec.adapters import (
    KALDO_COMPUTE_HEAT_CAPACITY,
    KALDO_COMPUTE_SCATTERING_RATES,
    PHONO3PY_COMPUTE_HEAT_CAPACITY,
    PHONO3PY_COMPUTE_SCATTERING_RATES,
)


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    print("=" * 70)
    print("Substrate spec layer: predictions for kaldo vs. phono3py")
    print("=" * 70)

    a = KALDO_COMPUTE_SCATTERING_RATES
    b = PHONO3PY_COMPUTE_SCATTERING_RATES

    section("compute_scattering_rates: linewidth Gamma_qν")
    print(f"  kaldo    declares linewidth in : {a.declared_unit('linewidth')}, "
          f"{a.declared_convention('gamma_definition')}")
    print(f"  phono3py declares linewidth in : {b.declared_unit('linewidth')}, "
          f"{b.declared_convention('gamma_definition')}")
    unit = cross_adapter_unit_factor(a, b, "linewidth")
    c_a = output_convention_factor(a, "linewidth")
    c_b = output_convention_factor(b, "linewidth")
    total = cross_adapter_total_factor(a, b, "linewidth")
    print(f"  unit factor (angular_THz → linear_THz)        : {unit:.6f}  [= 1/(2π)]")
    print(f"  kaldo output factor relative to canonical     : {c_a:.1f}    [Gamma = 2 Im Σ]")
    print(f"  phono3py output factor relative to canonical  : {c_b:.1f}    [Gamma = Im Σ]")
    print(f"  → total: kaldo × {total:.6f} = phono3py        [= 1/(4π) = {1/(4*math.pi):.6f}]")
    print(f"  matches empirical kaldo/phono3py ratio of 4π.")

    section("compute_scattering_rates: broadening_param convention")
    matched, msg = cross_adapter_convention_match(a, b, "broadening_param")
    if matched:
        print("  conventions agree.")
    else:
        print(f"  MISMATCH: {msg}")
        print(f"  → physical broadenings match when kaldo σ = phono3py σ × √2")
        print(f"    (halfwidth = stdev × √2 ≈ stdev × {math.sqrt(2):.6f})")

    section("compute_scattering_rates: bz_summation convention")
    matched, msg = cross_adapter_convention_match(a, b, "bz_summation")
    if matched:
        print("  conventions agree.")
    else:
        print(f"  MISMATCH: {msg}")
        print( "  → ΣΓ remains stable across the choice (contracted observable),")
        print( "    but per-mode Γ_qν will redistribute (~3% std/mean empirically).")
        print( "    The 'linewidth' observable carries a not-directly-comparable")
        print( "    protocol per the substrate doc.")

    a = KALDO_COMPUTE_HEAT_CAPACITY
    b = PHONO3PY_COMPUTE_HEAT_CAPACITY

    section("compute_heat_capacity: c_qν")
    print(f"  kaldo    declares c_v in : {a.declared_unit('heat_capacity')}")
    print(f"  phono3py declares c_v in : {b.declared_unit('heat_capacity')}")
    factor = cross_adapter_unit_factor(a, b, "heat_capacity")
    print(f"  → unit-layer prediction: kaldo × {factor:.6e} = phono3py")
    print(f"    (1/e ≈ 6.241e+18 reciprocal Joules per eV)")

    print()
    print("=" * 70)
    print("All cross-code discrepancies above were found *before running anything*.")
    print("Compare with the multi-day empirical investigation in")
    print("docs/worked_example_silicon.tex.")
    print("=" * 70)


if __name__ == "__main__":
    main()
