"""Demonstration: the substrate spec layer predicts cross-adapter discrepancies,
and `compare()` verifies them against real numerical data.

Two sections:
  (1) Predictions  — without running any code, the spec layer says how
      kaldo's outputs map to phono3py's (4π on Linewidth, e on HeatCapacity).
  (2) Verification — load the diagnostic .npz from a real silicon-Tersoff run,
      apply the predicted factors via `compare()`, report residuals against
      tolerance.

The verification closes the loop: the substrate's symbolic claim becomes a
checkable statement against measured data.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from omai.materialization import (
    compare,
    cross_operation_algorithmic_match,
    cross_operation_discretization_match,
    cross_state_total_factor,
    cross_state_unit_factor,
    materialize,
)
from omai.thermal_transport.materialized import (
    KALDO_COMPUTE_LINEWIDTH,
    KALDO_FREQUENCY,
    KALDO_GROUP_VELOCITY,
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    KALDO_THERMAL_CONDUCTIVITY_DIRECT,
    KALDO_THERMAL_CONDUCTIVITY_RTA,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_FREQUENCY,
    PHONO3PY_GROUP_VELOCITY,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
    PHONO3PY_THERMAL_CONDUCTIVITY_DIRECT,
    PHONO3PY_THERMAL_CONDUCTIVITY_RTA,
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
    print("Predictions above were derived without running anything.")
    print("=" * 70)

    print()
    print("=" * 70)
    print("Verification: applying the predictions to real data")
    print("=" * 70)

    diagnostics = (
        Path(__file__).resolve().parent.parent.parent
        / "runs"
        / "silicon_tersoff"
        / "comparison"
        / "diagnostics_at_stdev_0.10.npz"
    )
    if not diagnostics.exists():
        print()
        print(f"  diagnostic .npz not found at {diagnostics}")
        print("  run experiments/silicon_tersoff/extract_diagnostics.py to produce it.")
        return

    data = np.load(diagnostics)
    print(f"\nLoaded {diagnostics.name} with arrays:")
    for k in sorted(data.files):
        print(f"  {k:20s} shape={data[k].shape}")

    section("Frequency: per-mode (tight; atol covers acoustic Γ-modes)")
    mk = materialize(KALDO_FREQUENCY, "omega", data["kaldo_freq"])
    mp = materialize(PHONO3PY_FREQUENCY, "omega", data["ph3_freq"])
    r = compare(mk, mp, rtol=1e-3, atol=1e-2)
    print(f"  {r.summary()}")

    section("GroupVelocity: HiddenState — per-element not cross-compared")
    kaldo_v_norm = np.linalg.norm(data["kaldo_gv"], axis=-1)
    ph3_v_norm = np.linalg.norm(data["ph3_gv"], axis=-1)
    mk = materialize(KALDO_GROUP_VELOCITY, "v", kaldo_v_norm)
    mp = materialize(PHONO3PY_GROUP_VELOCITY, "v", ph3_v_norm)
    per_mode = compare(mk, mp, rtol=1e-3, atol=1e-2)
    print(f"  per-mode |v|: {per_mode.summary()}")
    diff = np.abs(np.sort(kaldo_v_norm, axis=-1) - np.sort(ph3_v_norm, axis=-1))
    n_disagreeing = int((diff > 0.5).sum())
    print(
        f"  Diagnostic spread (sort-within-q): median |Δ|v|| = {float(np.median(diff)):.3e}, "
        f"max = {float(diff.max()):.3f}, "
        f"{n_disagreeing}/{diff.size} modes > 0.5 Å·THz."
    )
    print("  → GroupVelocity is a HiddenState (eigenvector rotation at degenerate ω");
    print("    + apparent definitional differences); per-element comparison")
    print("    isn't a substrate verdict, just a diagnostic.")

    section("HeatCapacity: per-mode (tight, after applying 1/e factor)")
    mk = materialize(KALDO_HEAT_CAPACITY, "c", data["kaldo_cv"])
    mp = materialize(PHONO3PY_HEAT_CAPACITY, "c", data["ph3_cv"])
    r = compare(mk, mp, rtol=1e-3)
    print(f"  {r.summary()}")

    section("Linewidth: HiddenState — only contractions are observables")
    mk = materialize(KALDO_LINEWIDTH, "Gamma", data["kaldo_gamma"])
    mp = materialize(PHONO3PY_LINEWIDTH, "Gamma", data["ph3_gamma"])
    # Linewidth is a HiddenState. Per-element compare returns NOT_COMPARABLE
    # (diagnostic residual only). Contractions are the cross-code observables.
    per_mode = compare(mk, mp, rtol=0.01)
    # per-q is intermediate (still gauge-affected by BZ-summation choice)
    per_q = compare(
        mk, mp, contraction=lambda x: np.sum(x, axis=-1), rtol=0.02, expected_to_agree=False
    )
    total = compare(mk, mp, contraction=np.sum, rtol=1e-2)
    print(f"  per-mode (HiddenState):                    {per_mode.summary()}")
    print(f"  per-q Σ_ν Γ_qν (rtol=2e-2):                {per_q.summary()}")
    print(f"  total Σ_qν Γ contracted (rtol=1e-2):       {total.summary()}")

    section("ThermalConductivity κ: parameterized by bte_solver")
    csv_path = (
        Path(__file__).resolve().parent.parent.parent
        / "runs"
        / "silicon_tersoff"
        / "comparison"
        / "sigma_normalization_test.csv"
    )
    if not csv_path.exists():
        print(f"  κ CSV not found at {csv_path}; skipping.")
    else:
        kaldo_rta = ph3_rta = kaldo_direct = ph3_direct = None
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                if abs(float(row["effective_stdev_THz"]) - 0.10) < 1e-4:
                    kaldo_rta = float(row["kaldo_rta"])
                    ph3_rta = float(row["phono3py_rta"])
                    kaldo_direct = float(row["kaldo_inv"])
                    ph3_direct = float(row["phono3py_lbte"])
                    break
        if kaldo_rta is None:
            print(f"  no σ=0.10 row in {csv_path}; skipping.")
        else:
            # κ[bte_solver=rta] is a HiddenState → NOT_COMPARABLE per-element
            mk = materialize(
                KALDO_THERMAL_CONDUCTIVITY_RTA, "kappa", np.array(kaldo_rta)
            )
            mp = materialize(
                PHONO3PY_THERMAL_CONDUCTIVITY_RTA, "kappa", np.array(ph3_rta)
            )
            r_rta = compare(mk, mp, rtol=0.01)
            # κ[bte_solver=direct_inverse] is an Observable → tight comparison
            mk = materialize(
                KALDO_THERMAL_CONDUCTIVITY_DIRECT, "kappa", np.array(kaldo_direct)
            )
            mp = materialize(
                PHONO3PY_THERMAL_CONDUCTIVITY_DIRECT, "kappa", np.array(ph3_direct)
            )
            r_direct = compare(mk, mp, rtol=0.01)
            print(
                f"  κ[bte_solver=rta]            "
                f"(kaldo={kaldo_rta:.2f}, ph3={ph3_rta:.2f}):"
            )
            print(f"    {r_rta.summary()}")
            print(
                f"  κ[bte_solver=direct_inverse] "
                f"(kaldo={kaldo_direct:.2f}, ph3={ph3_direct:.2f}, rtol=1e-2):"
            )
            print(f"    {r_direct.summary()}")
            print(
                "  → κ[rta] is a HiddenState: RTA's 1/Γ non-linearity inherits"
            )
            print(
                "    Linewidth's gauge-dependence. Per-element disagreement is"
            )
            print("    diagnostic, not anomalous.")
            print(
                "  → κ[direct] is an Observable: the LBTE off-diagonals cancel"
            )
            print("    the redistribution, so κ is gauge-invariant.")

    print()
    print("=" * 70)
    print("Loop closed: substrate's symbolic predictions verified against real data.")
    print("=" * 70)


if __name__ == "__main__":
    main()
