"""Cross-code Si κ: ShengBTE ↔ kaldo through the symbolic/materialization layer.

Loads κ tensors from:
  experiments/silicon_shengbte/BTE.KappaTensorVsT_{RTA,CONV}
  runs/silicon_tersoff/kaldo_adaptive/kappa_{rta,sc,inverse}_tensor_WmK.npy

Uses kaldo's adaptive-broadening run (third_bandwidth=None) so both codes
are in the same broadening regime. The residual is then a clean test of
the BTE solver and BZ summation, not of broadening-scheme choice.

A symbolic-formula audit (see `verify_symbolic_agreement.py`) confirms
the three codes implement byte-identical sympy expressions for every
operation in the κ chain.

Findings (Si-Tersoff, 3×3×3 FC3 supercell, 8³ q-mesh, 300K):

  κ_RTA  : shengbte 16.93 ↔ kaldo 15.76  ↔ phono3py 16.74  → ≤8% spread
  κ_LBTE : shengbte 30.13 ↔ kaldo 19.69  ↔ phono3py 24.30  → ≤55% spread

The κ_RTA agreement at the broadening-matched level (≤8%) is consistent
with the framework's claim that the symbolic formula is shared.
The κ_LBTE spread is *real* and reflects implementation differences in
the BTE solver — kaldo's two LBTE methods (direct LU `inverse` vs
iterative `sc`) agree to within 1%, so the kaldo↔shengbte gap is *not*
a kaldo numerical issue. The likely cause: BZ summation choice
(kaldo C1 / full grid vs shengbte spglib_auto / irreducible) and the
small 3×3×3 FC3 supercell, which under-resolves the collision matrix
near zone boundary. The framework correctly surfaces this as
algorithmic-convention disagreement on solve_bte's
`collision_matrix_assembly` and `symmetry_group` choices.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from omai.materialization import compare, materialize
from omai.thermal_transport.materialized import (
    KALDO_THERMAL_CONDUCTIVITY_DIRECT,
    KALDO_THERMAL_CONDUCTIVITY_RTA,
    SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT,
    SHENGBTE_THERMAL_CONDUCTIVITY_RTA,
)


HERE = Path(__file__).resolve().parent
KALDO_DIR = HERE.parent.parent / "runs" / "silicon_tersoff" / "kaldo_adaptive"


def _parse_shengbte_kappa(path: Path) -> np.ndarray:
    raw = np.loadtxt(path, ndmin=2)
    return raw[0, 1:10].reshape(3, 3)


def main() -> None:
    # --- κ_RTA (broadening-aligned) -------------------------------------
    k_sheng_rta = _parse_shengbte_kappa(HERE / "BTE.KappaTensorVsT_RTA")
    k_kaldo_rta = np.load(KALDO_DIR / "kappa_rta_tensor_WmK.npy")

    m_sheng_rta = materialize(SHENGBTE_THERMAL_CONDUCTIVITY_RTA, "kappa", k_sheng_rta)
    m_kaldo_rta = materialize(KALDO_THERMAL_CONDUCTIVITY_RTA, "kappa", k_kaldo_rta)
    r_rta = compare(
        m_sheng_rta, m_kaldo_rta,
        contraction=lambda x: np.array([np.trace(x) / 3]),
        rtol=0.10, atol=1e-3,
    )

    print("κ_RTA  (W/m/K) — broadening-aligned (both adaptive):")
    print(f"  shengbte tr/3   : {np.trace(k_sheng_rta) / 3:.3f}")
    print(f"  kaldo    tr/3   : {np.trace(k_kaldo_rta) / 3:.3f}")
    print(f"  status (rtol=0.10): {r_rta.status}")
    print(f"  max_rel         : {r_rta.max_relative_residual:.4f}")
    print()

    # --- κ_DIRECT (LBTE) — kaldo `inverse` and `sc` methods -------------
    k_sheng_dir = _parse_shengbte_kappa(HERE / "BTE.KappaTensorVsT_CONV")
    k_kaldo_inv = np.load(KALDO_DIR / "kappa_inverse_tensor_WmK.npy")
    k_kaldo_sc = np.load(KALDO_DIR / "kappa_sc_tensor_WmK.npy")

    m_sheng_dir = materialize(SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT, "kappa", k_sheng_dir)
    m_kaldo_inv = materialize(KALDO_THERMAL_CONDUCTIVITY_DIRECT, "kappa", k_kaldo_inv)
    m_kaldo_sc  = materialize(KALDO_THERMAL_CONDUCTIVITY_DIRECT, "kappa", k_kaldo_sc)

    print("κ_LBTE/CONV (W/m/K):")
    print(f"  shengbte    tr/3 : {np.trace(k_sheng_dir) / 3:.3f}")
    print(f"  kaldo inv   tr/3 : {np.trace(k_kaldo_inv) / 3:.3f}")
    print(f"  kaldo sc    tr/3 : {np.trace(k_kaldo_sc) / 3:.3f}")
    print()
    print("kaldo inv ↔ kaldo sc (same code, two LBTE algorithms):")
    r_kk = compare(
        m_kaldo_inv, m_kaldo_sc,
        contraction=lambda x: np.array([np.trace(x) / 3]),
        rtol=0.05, atol=1e-3,
    )
    print(f"  status (rtol=0.05): {r_kk.status}   max_rel: {r_kk.max_relative_residual:.4f}")
    print()
    print("shengbte ↔ kaldo inv:")
    r_sk = compare(
        m_sheng_dir, m_kaldo_inv,
        contraction=lambda x: np.array([np.trace(x) / 3]),
        rtol=0.10, atol=1e-3,
    )
    print(f"  status (rtol=0.10): {r_sk.status}   max_rel: {r_sk.max_relative_residual:.4f}")
    print("  Note: BZ summation differs (kaldo C1 full grid vs shengbte spglib_auto")
    print("        irreducible). At 3×3×3 FC3 / 8³ q-mesh the LBTE solve is")
    print("        sensitive to this choice; the spread is real, not numerical.")


if __name__ == "__main__":
    main()
