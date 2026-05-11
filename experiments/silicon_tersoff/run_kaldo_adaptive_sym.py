"""kaldo on silicon with adaptive broadening AND spglib IBZ reduction.

Companion to `run_kaldo_adaptive.py`. Same inputs, but also sets
`use_q_symmetry=True` so kaldo computes on the irreducible Brillouin
zone (via spglib) and replicates to symmetry-equivalent k-points. This
puts kaldo on the same BZ-summation footing as ShengBTE and tests
whether the κ_LBTE gap is caused by full-grid vs irreducible-grid
summation of the collision matrix.

Outputs land in runs/silicon_tersoff/kaldo_adaptive_sym/.
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
OUT = RUNS_DIR / "kaldo_adaptive_sym"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    t0 = time.time()
    print(f"[kaldo-adaptive-sym] loading cached FCs from {FC_DIR}")
    fc = ForceConstants.from_folder(
        folder=str(FC_DIR),
        supercell=SUPERCELL_FC2,
        third_supercell=SUPERCELL_FC3,
        format="numpy",
    )

    print("[kaldo-adaptive-sym] building Phonons with adaptive σ + use_q_symmetry=True")
    phonons = Phonons(
        forceconstants=fc,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=None,        # adaptive velocity-projection σ
        broadening_shape="gauss",
        use_q_symmetry=True,         # spglib IBZ reduction
        folder=str(OUT / "phonons"),
        storage="memory",
    )

    print("[kaldo-adaptive-sym] κ_RTA ...")
    t1 = time.time()
    rta = Conductivity(phonons=phonons, method="rta", n_iterations=0).conductivity.sum(axis=0)
    print(f"[kaldo-adaptive-sym]   RTA in {time.time() - t1:.1f} s")

    print("[kaldo-adaptive-sym] κ_inverse ...")
    t2 = time.time()
    inv = Conductivity(phonons=phonons, method="inverse").conductivity.sum(axis=0)
    print(f"[kaldo-adaptive-sym]   inverse in {time.time() - t2:.1f} s")

    print("[kaldo-adaptive-sym] κ_sc ...")
    t3 = time.time()
    sc = Conductivity(phonons=phonons, method="sc", n_iterations=50).conductivity.sum(axis=0)
    print(f"[kaldo-adaptive-sym]   sc in {time.time() - t3:.1f} s")

    rta_diag = float(np.mean(np.diag(rta)))
    inv_diag = float(np.mean(np.diag(inv)))
    sc_diag = float(np.mean(np.diag(sc)))
    print(f"[kaldo-adaptive-sym] κ_RTA     diag avg: {rta_diag:.3f} W/(m·K)")
    print(f"[kaldo-adaptive-sym] κ_inverse diag avg: {inv_diag:.3f} W/(m·K)")
    print(f"[kaldo-adaptive-sym] κ_sc      diag avg: {sc_diag:.3f} W/(m·K)")

    np.save(OUT / "kappa_rta_tensor_WmK.npy", rta)
    np.save(OUT / "kappa_inverse_tensor_WmK.npy", inv)
    np.save(OUT / "kappa_sc_tensor_WmK.npy", sc)

    summary = (
        f"kaldo silicon-Tersoff (adaptive σ + spglib IBZ reduction)\n"
        f"---------------------------------------------------------\n"
        f"third_bandwidth   : None (adaptive velocity-projection σ)\n"
        f"use_q_symmetry    : True\n"
        f"k/q-mesh          : {KMESH}\n"
        f"temperature       : {TEMPERATURE} K\n"
        f"kappa RTA  (W/m/K): {rta_diag:.3f}\n"
        f"kappa inv  (W/m/K): {inv_diag:.3f}\n"
        f"kappa sc   (W/m/K): {sc_diag:.3f}\n"
        f"total wallclock   : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
