"""kaldo path for the silicon-Tersoff experiment.

Steps:
  1. Build the silicon Atoms and the LAMMPS-Tersoff calculator (from seed.py).
  2. Compute 2nd-order force constants via finite difference.
  3. Compute 3rd-order force constants via finite difference.
  4. Build a Phonons object.
  5. Save dispersion (frequencies, eigenvectors, group velocities).
  6. Compute thermal conductivity (RTA + direct inversion).

Outputs land in runs/silicon_tersoff/kaldo/.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from seed import (
    BROADENING_SIGMA_THZ,
    FD_DISPLACEMENT,
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    TEMPERATURE,
    build_silicon_primitive,
    make_tersoff_calculator,
)

from kaldo.conductivity import Conductivity
from kaldo.forceconstants import ForceConstants
from kaldo.phonons import Phonons


OUT = RUNS_DIR / "kaldo"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    t0 = time.time()
    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()

    print(
        f"[kaldo] supercell FC2 {SUPERCELL_FC2}, FC3 {SUPERCELL_FC3}, "
        f"kmesh {KMESH}, FD delta {FD_DISPLACEMENT} A"
    )

    # ----- Force constants (2nd and 3rd order) -----
    fc_folder = OUT / "fc"
    fc_folder.mkdir(exist_ok=True)
    forceconstants = ForceConstants(
        atoms=atoms,
        supercell=np.array(SUPERCELL_FC2),
        third_supercell=np.array(SUPERCELL_FC3),
        folder=str(fc_folder),
    )
    print("[kaldo] computing 2nd-order force constants ...")
    t1 = time.time()
    forceconstants.second.calculate(calc, delta_shift=FD_DISPLACEMENT)
    print(f"[kaldo]   FC2 done in {time.time() - t1:.1f} s")

    print("[kaldo] computing 3rd-order force constants ...")
    t_fc3 = time.time()
    forceconstants.third.calculate(calc, delta_shift=FD_DISPLACEMENT)
    print(f"[kaldo]   FC3 done in {time.time() - t_fc3:.1f} s")

    # ----- Phonons (lazy; access frequencies/eigenvectors/velocities to materialize) -----
    phonons = Phonons(
        forceconstants=forceconstants,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=BROADENING_SIGMA_THZ,
        broadening_shape="gauss",
        folder=str(OUT / "phonons"),
        storage="memory",
    )

    print("[kaldo] computing dispersion (frequencies, eigenvectors, velocities) ...")
    t2 = time.time()
    frequencies = np.asarray(phonons.frequency)        # (n_q, n_modes), THz
    eigenvectors = np.asarray(phonons.eigenvectors)    # (n_q, n_modes, n_modes), complex
    velocities = np.asarray(phonons.velocity)          # (n_q, n_modes, 3), Å·THz
    print(f"[kaldo]   dispersion done in {time.time() - t2:.1f} s")

    print(
        f"[kaldo] frequencies shape={frequencies.shape}, "
        f"min={frequencies.min():.4f} THz, "
        f"max={frequencies.max():.4f} THz"
    )

    # ----- Save outputs -----
    np.save(OUT / "frequencies_THz.npy", frequencies)
    np.save(OUT / "eigenvectors.npy", eigenvectors)
    np.save(OUT / "group_velocities_AT.npy", velocities)

    # Save the q-point grid (kaldo's default Monkhorst-Pack grid for the chosen kmesh)
    try:
        q_points = np.asarray(phonons._reciprocal_grid.unitary_grid(is_wrapping=True))
    except TypeError:
        q_points = np.asarray(phonons._reciprocal_grid.unitary_grid())
    np.save(OUT / "q_points.npy", q_points)

    # ----- Thermal conductivity -----
    print("[kaldo] computing thermal conductivity (RTA) ...")
    t4 = time.time()
    rta = Conductivity(phonons=phonons, method="rta", n_iterations=0).conductivity.sum(axis=0)
    print(f"[kaldo]   RTA done in {time.time() - t4:.1f} s")

    print("[kaldo] computing thermal conductivity (direct inversion) ...")
    t5 = time.time()
    inv = Conductivity(phonons=phonons, method="inverse").conductivity.sum(axis=0)
    print(f"[kaldo]   inverse done in {time.time() - t5:.1f} s")

    kappa_rta_diag_avg = float(np.mean(np.diag(rta)))
    kappa_inv_diag_avg = float(np.mean(np.diag(inv)))
    print(f"[kaldo] kappa (RTA, avg of diagonal):     {kappa_rta_diag_avg:.3f} W/m/K")
    print(f"[kaldo] kappa (inverse, avg of diagonal): {kappa_inv_diag_avg:.3f} W/m/K")

    np.save(OUT / "kappa_rta_tensor_WmK.npy", rta)
    np.save(OUT / "kappa_inverse_tensor_WmK.npy", inv)

    summary = (
        f"kaldo silicon-Tersoff run\n"
        f"-------------------------\n"
        f"supercell FC2     : {SUPERCELL_FC2}\n"
        f"supercell FC3     : {SUPERCELL_FC3}\n"
        f"k/q-mesh          : {KMESH}\n"
        f"FD displacement   : {FD_DISPLACEMENT} A\n"
        f"temperature       : {TEMPERATURE} K\n"
        f"n_q               : {frequencies.shape[0]}\n"
        f"n_modes           : {frequencies.shape[1]}\n"
        f"freq min / max    : {frequencies.min():.4f} / {frequencies.max():.4f} THz\n"
        f"kappa RTA  (W/m/K): {kappa_rta_diag_avg:.3f}\n"
        f"kappa inv  (W/m/K): {kappa_inv_diag_avg:.3f}\n"
        f"total wallclock   : {time.time() - t0:.1f} s\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
