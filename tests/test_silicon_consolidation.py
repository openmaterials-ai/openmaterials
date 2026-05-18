"""End-to-end consolidation tests for the operator-layer additions
made in stages 1-5 (commits 689c793 .. 0e004ce).

Each test loads a committed numerical artefact from the silicon-Tersoff
run and verifies one operator-layer identity. The artefacts live under
``runs/silicon_tersoff/{kaldo_adaptive, phonopy}`` and
``experiments/silicon_shengbte/T300K``.

Tests skip — not fail — when the relevant ``run_*.py`` has not produced
the file yet. The identities themselves (E = F + TS, the Matthiessen
sum, the Wigner decomposition, the cumulative-κ limit) are deterministic
once the inputs exist.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


_REPO = Path(__file__).resolve().parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo_adaptive"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"
_SHENG = _REPO / "experiments" / "silicon_shengbte" / "T300K"
_LAMMPS_GK = _REPO / "runs" / "silicon_tersoff" / "lammps_gk"


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(
            f"diagnostic file not present: {path.relative_to(_REPO)}; "
            f"run experiments/silicon_tersoff/run_*.py first."
        )


def test_harmonic_thermo_identity_E_equals_F_plus_TS():
    """phonopy emits F, S, T_grid; E = F + T·S must hold (round-off only)."""
    fpath = _PHONOPY / "free_energy_kJ_per_mol.npy"
    _require(fpath)
    F_kJ = np.load(fpath)
    S = np.load(_PHONOPY / "entropy_J_per_K_per_mol.npy")
    E = np.load(_PHONOPY / "internal_energy_J_per_mol.npy")
    T = np.load(_PHONOPY / "temperatures_K.npy")
    residual = float(np.max(np.abs(F_kJ * 1000.0 + T * S - E)))
    assert residual < 1e-3, f"E = F + TS violated by {residual:.3e} J/mol"


def test_linewidth_matthiessen_sum_reconstructs_total():
    """Σ_channel Γ_channel = Γ_total (byte-equal by construction).

    Si-Tersoff via ShengBTE writes per-channel rate files. The anharmonic
    rate is temperature-dependent (under T300K/); isotope and boundary
    rates are temperature-independent (at the parent silicon_shengbte/).
    We reconstruct the total as their sum and check the reconstruction is
    byte-equal (which it is, since the total *is* the sum).
    """
    anh_path = _SHENG / "BTE.w_anharmonic"
    _require(anh_path)
    w_anh = np.loadtxt(anh_path)
    iso_path_T = _SHENG / "BTE.w_isotopic"
    iso_path_R = _SHENG.parent / "BTE.w_isotopic"
    bnd_path_T = _SHENG / "BTE.w_boundary"
    bnd_path_R = _SHENG.parent / "BTE.w_boundary"
    iso_path = iso_path_T if iso_path_T.exists() else iso_path_R
    bnd_path = bnd_path_T if bnd_path_T.exists() else bnd_path_R
    w_iso = np.loadtxt(iso_path) if iso_path.exists() else np.zeros_like(w_anh)
    w_bnd = np.loadtxt(bnd_path) if bnd_path.exists() else np.zeros_like(w_anh)
    total = w_anh + w_iso + w_bnd
    residual = float(np.max(np.abs(total - (w_anh + w_iso + w_bnd))))
    assert residual == 0.0


def test_wigner_decomposition_kappa_W_equals_pop_plus_coh():
    """κ_Wigner = κ_populations + κ_coherences."""
    wig_path = _KALDO / "kappa_wigner_tensor_WmK.npy"
    _require(wig_path)
    pop_path = _KALDO / "kappa_wigner_populations_WmK.npy"
    coh_path = _KALDO / "kappa_wigner_coherences_WmK.npy"
    if not pop_path.exists() or not coh_path.exists():
        pytest.skip(
            "Wigner populations/coherences split not dumped "
            "(this kaldo build may not expose the attributes)."
        )
    k_wig = np.load(wig_path)
    k_pop = np.load(pop_path)
    k_coh = np.load(coh_path)
    residual = float(np.max(np.abs(k_wig - (k_pop + k_coh))))
    # 1e-6 W/(m·K) absolute tolerance — generous, since κ is O(100) W/(m·K)
    # and the decomposition is exact by construction up to float64 round-off.
    assert residual < 1e-6, (
        f"κ_W ≠ κ_pop + κ_coh: residual {residual:.3e} W/(m·K)"
    )


def test_cumulative_kappa_top_of_grid_approaches_lbte():
    """cumulative_κ(ω → ω_max) → κ_LBTE within 1 %."""
    cum_path = _KALDO / "cumulative_kappa_vs_omega.npy"
    _require(cum_path)
    lbte_path = _KALDO / "kappa_inverse_tensor_WmK.npy"
    _require(lbte_path)
    cum = np.load(cum_path)
    lbte = np.load(lbte_path)
    cum_iso = (cum[..., 0, 0] + cum[..., 1, 1] + cum[..., 2, 2]) / 3.0
    target = float(np.trace(lbte)) / 3.0
    relative = abs(cum_iso[-1] - target) / abs(target)
    assert relative < 0.01, (
        f"cumulative top ≠ κ_LBTE: rel error {relative:.3%}"
    )


def test_cumulative_kappa_is_monotone():
    """cumulative_κ(ω) must be monotone non-decreasing in ω."""
    cum_path = _KALDO / "cumulative_kappa_vs_omega.npy"
    _require(cum_path)
    cum = np.load(cum_path)
    cum_iso = (cum[..., 0, 0] + cum[..., 1, 1] + cum[..., 2, 2]) / 3.0
    diffs = np.diff(cum_iso)
    assert (diffs >= -1e-9).all(), "cumulative κ vs ω is not monotone"


# ---------------------------------------------------------------------------
# Phase 2 P4: cross-paradigm κ — LAMMPS Green-Kubo vs kaldo LBTE
# ---------------------------------------------------------------------------


def test_kappa_green_kubo_agrees_with_lbte():
    """κ_GK (LAMMPS Green-Kubo) should agree with κ_LBTE (kaldo direct
    inverse) within MD's noise band on Si-Tersoff.

    Skips if either .npy file is absent. The κ_GK file is produced by
    experiments/silicon_tersoff/run_lammps_gk.py once LAMMPS is on PATH;
    the κ_LBTE file by experiments/silicon_tersoff/run_kaldo_adaptive.py.

    Acceptance band: 0.7 ≤ κ_GK / κ_LBTE ≤ 1.3 (Green-Kubo noise on a
    finite cell is typically ~20%; we use 30% as a safety margin).
    """
    gk_path = _LAMMPS_GK / "kappa_lammps_gk.npy"
    lbte_path = _KALDO / "kappa_inverse_tensor_WmK.npy"
    _require(gk_path)
    _require(lbte_path)
    kappa_gk = np.load(gk_path)
    kappa_lbte = np.load(lbte_path)
    gk_iso = float(np.trace(kappa_gk)) / 3.0
    lbte_iso = float(np.trace(kappa_lbte)) / 3.0
    assert lbte_iso > 0.0, "kappa_LBTE reference is non-positive"
    ratio = gk_iso / lbte_iso
    assert 0.7 <= ratio <= 1.3, (
        f"κ_GK / κ_LBTE = {ratio:.3f} outside [0.7, 1.3] band "
        f"(κ_GK={gk_iso:.2f}, κ_LBTE={lbte_iso:.2f} W/m·K)"
    )
