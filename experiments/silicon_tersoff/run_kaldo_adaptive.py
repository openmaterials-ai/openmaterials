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

    summary = (
        f"kaldo silicon-Tersoff run (adaptive broadening)\n"
        f"-----------------------------------------------\n"
        f"third_bandwidth   : None (adaptive velocity-projection σ)\n"
        f"k/q-mesh          : {KMESH}\n"
        f"temperature       : {TEMPERATURE} K\n"
        f"kappa RTA  (W/m/K): {rta_diag:.3f}\n"
        f"kappa inv  (W/m/K): {inv_diag:.3f}\n"
        f"total wallclock   : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
