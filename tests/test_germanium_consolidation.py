"""Framework-portability tests on a second material (germanium-Tersoff).

These tests demonstrate that the operator layer's identities and the
cross-code agreement that hold on silicon-Tersoff *also* hold on a
different material, with no framework code changes — only
`experiments/germanium_tersoff/seed.py` differs from the silicon seed.

All tests skip if the relevant artefact hasn't been produced by
running `experiments/germanium_tersoff/run_*.py`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


_REPO = Path(__file__).resolve().parent.parent
_GE_KALDO = _REPO / "runs" / "germanium_tersoff" / "kaldo"
_GE_PHONOPY = _REPO / "runs" / "germanium_tersoff" / "phonopy"


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(
            f"germanium diagnostic file not present: "
            f"{path.relative_to(_REPO)}; "
            f"run experiments/germanium_tersoff/run_*.py first."
        )


def test_germanium_harmonic_thermo_identity_E_equals_F_plus_TS():
    """E = F + T·S must hold (round-off only) on Ge as it does on Si."""
    fpath = _GE_PHONOPY / "free_energy_kJ_per_mol.npy"
    _require(fpath)
    F_kJ = np.load(fpath)
    S = np.load(_GE_PHONOPY / "entropy_J_per_K_per_mol.npy")
    E = np.load(_GE_PHONOPY / "internal_energy_J_per_mol.npy")
    T = np.load(_GE_PHONOPY / "temperatures_K.npy")
    residual = float(np.max(np.abs(F_kJ * 1000.0 + T * S - E)))
    assert residual < 1e-3, (
        f"Ge harmonic thermo identity violated by {residual:.3e} J/mol"
    )


def test_germanium_kaldo_phonopy_frequencies_agree():
    """Kaldo and phonopy must agree on ω(q,ν) per the operator-layer
    promise (both in linear THz; no convention factor)."""
    kaldo_path = _GE_KALDO / "frequencies_THz.npy"
    phonopy_path = _GE_PHONOPY / "frequencies_THz.npy"
    _require(kaldo_path)
    _require(phonopy_path)
    kaldo_freq = np.load(kaldo_path)
    phonopy_freq = np.load(phonopy_path)
    # Sort modes per q-point to remove ordering ambiguity at degeneracies.
    k_sorted = np.sort(kaldo_freq, axis=1)
    p_sorted = np.sort(phonopy_freq, axis=1)
    max_abs = float(np.max(np.abs(k_sorted - p_sorted)))
    fmax = float(kaldo_freq.max())
    rel = max_abs / max(fmax, 1e-9)
    assert rel < 0.01, (
        f"Ge ω(kaldo) vs ω(phonopy) disagreement {rel:.3%} exceeds 1% band"
    )


def test_germanium_kappa_lbte_exceeds_kappa_rta():
    """Operator-layer prediction: gauge-invariant κ_LBTE ≥ κ_RTA (the RTA
    HiddenState gauge-loss propagates into κ_RTA, biasing it low).

    This is true on Si; should reproduce on Ge with no framework changes.
    """
    rta_path = _GE_KALDO / "kappa_rta_tensor_WmK.npy"
    inv_path = _GE_KALDO / "kappa_inverse_tensor_WmK.npy"
    _require(rta_path)
    _require(inv_path)
    rta_iso = float(np.trace(np.load(rta_path))) / 3.0
    inv_iso = float(np.trace(np.load(inv_path))) / 3.0
    assert rta_iso > 0.0 and inv_iso > 0.0, (
        f"non-positive κ on Ge: RTA={rta_iso}, LBTE={inv_iso}"
    )
    assert inv_iso >= 0.95 * rta_iso, (
        f"Ge κ_LBTE={inv_iso:.3f} < 0.95·κ_RTA={0.95*rta_iso:.3f}; "
        f"operator-layer prediction violated"
    )
