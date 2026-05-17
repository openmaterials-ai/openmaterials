"""kaldo on silicon with **adaptive** broadening (third_bandwidth=None).

Companion to `run_kaldo.py`. Reuses the cached FC2/FC3 (no recomputation)
and runs the Phonons + Conductivity chain with kaldo's default adaptive
velocity-projection σ — the same scheme ShengBTE uses with scalebroad=1.0.

Purpose: align kaldo's broadening scheme with shengbte's so the cross-code
residual reflects pure physics convergence, not a broadening-scheme
mismatch.

Outputs land in runs/silicon_tersoff/kaldo_adaptive/.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from kaldo.conductivity import Conductivity
from kaldo.forceconstants import ForceConstants
from kaldo.phonons import Phonons

from seed import (
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    TEMPERATURE,
)


FC_DIR = RUNS_DIR / "kaldo" / "fc"
OUT = RUNS_DIR / "kaldo_adaptive"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    t0 = time.time()
    print(f"[kaldo-adaptive] loading cached FCs from {FC_DIR}")
    fc = ForceConstants.from_folder(
        folder=str(FC_DIR),
        supercell=SUPERCELL_FC2,
        third_supercell=SUPERCELL_FC3,
        format="numpy",
    )

    print("[kaldo-adaptive] building Phonons with third_bandwidth=None (adaptive)")
    phonons = Phonons(
        forceconstants=fc,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=None,  # ← adaptive velocity-projection σ (kaldo default)
        broadening_shape="gauss",
        folder=str(OUT / "phonons"),
        storage="memory",
    )

    print("[kaldo-adaptive] κ_RTA ...")
    t1 = time.time()
    rta = Conductivity(phonons=phonons, method="rta", n_iterations=0).conductivity.sum(axis=0)
    print(f"[kaldo-adaptive]   RTA in {time.time() - t1:.1f} s")

    print("[kaldo-adaptive] κ_inverse (direct LBTE) ...")
    t2 = time.time()
    inv = Conductivity(phonons=phonons, method="inverse").conductivity.sum(axis=0)
    print(f"[kaldo-adaptive]   inverse in {time.time() - t2:.1f} s")

    print("[kaldo-adaptive] κ_sc (self-consistent iterative) ...")
    t3 = time.time()
    sc = Conductivity(phonons=phonons, method="sc", n_iterations=50).conductivity.sum(axis=0)
    print(f"[kaldo-adaptive]   sc in {time.time() - t3:.1f} s")

    rta_diag = float(np.mean(np.diag(rta)))
    inv_diag = float(np.mean(np.diag(inv)))
    sc_diag = float(np.mean(np.diag(sc)))
    print(f"[kaldo-adaptive] κ_RTA     diag avg: {rta_diag:.3f} W/(m·K)")
    print(f"[kaldo-adaptive] κ_inverse diag avg: {inv_diag:.3f} W/(m·K)")
    print(f"[kaldo-adaptive] κ_sc      diag avg: {sc_diag:.3f} W/(m·K)")

    np.save(OUT / "kappa_rta_tensor_WmK.npy", rta)
    np.save(OUT / "kappa_inverse_tensor_WmK.npy", inv)
    np.save(OUT / "kappa_sc_tensor_WmK.npy", sc)

    # ----- κ_Wigner + κ_QHGK (Task 7C) ------------------------------------
    # Pattern-A terminal nodes that consume the linewidth chain. Wigner
    # exposes a populations / coherences split that must sum to the total.
    print("[kaldo-adaptive] κ_Wigner ...")
    t4 = time.time()
    cond_wigner = Conductivity(phonons=phonons, method="wigner")
    kappa_wigner_full = cond_wigner.conductivity  # (n_modes, 3, 3) per-mode
    kappa_wigner = kappa_wigner_full.sum(axis=0)
    # populations / coherences split — attribute names may differ across
    # kaldo versions, so we try a few and degrade gracefully if missing.
    pop_attr = next(
        (a for a in ("populations_conductivity", "kappa_populations", "kappa_pop")
         if hasattr(cond_wigner, a)),
        None,
    )
    coh_attr = next(
        (a for a in ("coherences_conductivity", "kappa_coherences", "kappa_coh")
         if hasattr(cond_wigner, a)),
        None,
    )
    if pop_attr is not None and coh_attr is not None:
        kappa_pop_full = np.asarray(getattr(cond_wigner, pop_attr))
        kappa_coh_full = np.asarray(getattr(cond_wigner, coh_attr))
        kappa_pop = (
            kappa_pop_full.sum(axis=0)
            if kappa_pop_full.ndim == 3
            else kappa_pop_full
        )
        kappa_coh = (
            kappa_coh_full.sum(axis=0)
            if kappa_coh_full.ndim == 3
            else kappa_coh_full
        )
        np.save(OUT / "kappa_wigner_populations_WmK.npy", kappa_pop)
        np.save(OUT / "kappa_wigner_coherences_WmK.npy", kappa_coh)
        print(
            f"[kaldo-adaptive]   Wigner pop tr/3:  "
            f"{float(np.trace(kappa_pop)) / 3:.3f}"
        )
        print(
            f"[kaldo-adaptive]   Wigner coh tr/3:  "
            f"{float(np.trace(kappa_coh)) / 3:.3f}"
        )
    else:
        print(
            "[kaldo-adaptive]   Wigner pop/coh attributes not exposed by this "
            "kaldo version; skipping decomposition dump."
        )
    np.save(OUT / "kappa_wigner_tensor_WmK.npy", kappa_wigner)
    print(
        f"[kaldo-adaptive]   κ_Wigner tr/3: "
        f"{float(np.trace(kappa_wigner)) / 3:.3f} in {time.time() - t4:.1f} s"
    )

    print("[kaldo-adaptive] κ_QHGK ...")
    t5 = time.time()
    cond_qhgk = Conductivity(phonons=phonons, method="qhgk")
    kappa_qhgk_full = cond_qhgk.conductivity
    kappa_qhgk = (
        kappa_qhgk_full.sum(axis=0) if kappa_qhgk_full.ndim == 3 else kappa_qhgk_full
    )
    np.save(OUT / "kappa_qhgk_tensor_WmK.npy", kappa_qhgk)
    print(
        f"[kaldo-adaptive]   κ_QHGK tr/3: "
        f"{float(np.trace(kappa_qhgk)) / 3:.3f} in {time.time() - t5:.1f} s"
    )

    # ----- Cumulative κ vs ω and vs MFP (Task 7D) -------------------------
    print("[kaldo-adaptive] cumulative κ ...")
    t6 = time.time()
    cond_inv = Conductivity(phonons=phonons, method="inverse")
    omega_max = float(np.asarray(phonons.frequency).max())
    omega_grid = np.linspace(0.0, omega_max * 1.05, 200)
    mfp_grid = np.logspace(-1, 4, 200)  # 0.1 Å to 1e4 Å
    cum_omega_attr = next(
        (a for a in ("cumulative_conductivity_per_omega", "cumulative_kappa_per_omega")
         if hasattr(cond_inv, a)),
        None,
    )
    cum_mfp_attr = next(
        (a for a in ("cumulative_conductivity_per_mfp", "cumulative_kappa_per_mfp")
         if hasattr(cond_inv, a)),
        None,
    )
    if cum_omega_attr is not None:
        cum_omega = np.asarray(getattr(cond_inv, cum_omega_attr)(omega_grid))
        np.save(OUT / "cumulative_kappa_vs_omega.npy", cum_omega)
        np.save(OUT / "cumulative_kappa_vs_omega_grid.npy", omega_grid)
    else:
        print(
            "[kaldo-adaptive]   cumulative_conductivity_per_omega missing; "
            "skipping cumulative-vs-ω dump."
        )
    if cum_mfp_attr is not None:
        cum_mfp = np.asarray(getattr(cond_inv, cum_mfp_attr)(mfp_grid))
        np.save(OUT / "cumulative_kappa_vs_mfp.npy", cum_mfp)
        np.save(OUT / "cumulative_kappa_vs_mfp_grid.npy", mfp_grid)
    else:
        print(
            "[kaldo-adaptive]   cumulative_conductivity_per_mfp missing; "
            "skipping cumulative-vs-mfp dump."
        )
    print(f"[kaldo-adaptive]   cumulative done in {time.time() - t6:.1f} s")

    summary = (
        f"kaldo silicon-Tersoff run (adaptive broadening)\n"
        f"-----------------------------------------------\n"
        f"third_bandwidth   : None (adaptive velocity-projection σ)\n"
        f"k/q-mesh          : {KMESH}\n"
        f"temperature       : {TEMPERATURE} K\n"
        f"kappa RTA  (W/m/K): {rta_diag:.3f}\n"
        f"kappa inv  (W/m/K): {inv_diag:.3f}\n"
        f"kappa Wig  (W/m/K): {float(np.trace(kappa_wigner)) / 3:.3f}\n"
        f"kappa QHGK (W/m/K): {float(np.trace(kappa_qhgk)) / 3:.3f}\n"
        f"total wallclock   : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
