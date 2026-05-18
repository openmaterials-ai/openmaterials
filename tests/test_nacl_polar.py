"""NaCl-rd polar branch verification.

The third material the framework touches and the first polar one:

  * Si-Tersoff (non-polar diamond) — phase 1 anchor.
  * Ge-Tersoff (non-polar diamond, different mass) — framework
    portability check.
  * NaCl-rd (polar rocksalt) — exercises the BornCharges /
    DielectricTensor / apply_nac_correction code path that's dead on
    Si and Ge.

Skip behaviour follows the pattern of `test_silicon_consolidation.py`:
each test skips if the .npy artefact hasn't been generated yet
(`experiments/nacl_polar/run_phonopy_nacl.py`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


_REPO = Path(__file__).resolve().parent.parent
_NACL = _REPO / "runs" / "nacl_polar" / "phonopy"


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(
            f"NaCl diagnostic file not present: {path.relative_to(_REPO)}; "
            f"run experiments/nacl_polar/run_phonopy_nacl.py first."
        )


def test_nacl_harmonic_thermo_identity_E_equals_F_plus_TS():
    """E = F + T·S must hold round-off-tight on NaCl too — the identity
    is operator-layer, not material-specific."""
    fpath = _NACL / "free_energy_kJ_per_mol.npy"
    _require(fpath)
    F_kJ = np.load(fpath)
    S = np.load(_NACL / "entropy_J_per_K_per_mol.npy")
    E = np.load(_NACL / "internal_energy_J_per_mol.npy")
    T = np.load(_NACL / "temperatures_K.npy")
    residual = float(np.max(np.abs(F_kJ * 1000.0 + T * S - E)))
    assert residual < 1e-3, (
        f"NaCl harmonic thermo identity violated by {residual:.3e} J/mol"
    )


def test_nacl_loto_splitting_at_gamma_is_nonzero():
    """LO-TO splitting at q→0+ along [100] must be nonzero on NaCl.

    On non-polar Si/Ge this would be exactly 0; the polar branch makes
    it finite and direction-dependent. Experimental NaCl Γ LO-TO
    splitting is ~3 THz (~100 cm⁻¹). We require ≥ 1.5 THz to allow for
    DFT-functional drift but reject the non-polar (≈0) outcome.
    """
    qs_path = _NACL / "loto_sweep_qs.npy"
    freqs_path = _NACL / "loto_sweep_freqs.npy"
    _require(qs_path)
    _require(freqs_path)
    sweep_freqs = np.load(freqs_path)
    # NaCl: 2 atoms → 6 modes; top 3 are the optical branches at Γ.
    sorted_at_smallest_q = np.sort(sweep_freqs[0])
    top3 = sorted_at_smallest_q[-3:]
    LO = float(top3[-1])
    TO_avg = float(np.mean(top3[:-1]))
    splitting = LO - TO_avg
    assert splitting > 1.5, (
        f"NaCl LO-TO splitting at q→0+ is {splitting:.3f} THz; "
        f"polar branch may be inactive"
    )
    # Sanity bound (the experimental value is ~3.0 THz; we allow a
    # generous DFT band ±50%).
    assert splitting < 5.0, (
        f"NaCl LO-TO splitting at q→0+ is {splitting:.3f} THz, "
        f"unusually large"
    )


def test_nacl_loto_splitting_decreases_with_increasing_q():
    """The NAC correction is q→0+ peaked; as |q| moves away from Γ the
    splitting must decrease. This is the empirical fingerprint of the
    Gonze-Lee (or Wang or Ewald) NAC kernel.
    """
    qs_path = _NACL / "loto_sweep_qs.npy"
    freqs_path = _NACL / "loto_sweep_freqs.npy"
    _require(qs_path)
    _require(freqs_path)
    qs = np.load(qs_path)
    sweep_freqs = np.load(freqs_path)
    splittings = []
    for modes in sweep_freqs:
        top3 = np.sort(modes)[-3:]
        splittings.append(float(top3[-1]) - float(np.mean(top3[:-1])))
    splittings = np.asarray(splittings)
    # The smallest |q| should produce the largest splitting; allow some
    # round-off near the smallest q where NAC saturates.
    assert splittings[0] >= splittings[-1], (
        f"LO-TO splitting did not decrease with |q|: "
        f"{splittings[0]:.3f} (smallest q) vs {splittings[-1]:.3f} (largest)"
    )
