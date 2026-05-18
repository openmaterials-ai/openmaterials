"""NaCl-rd phonopy run with non-analytical correction (NAC).

The first polar material the framework touches. The point is to
demonstrate that the operator-layer's *polar branch* — BornCharges,
DielectricTensor, the Pattern-C apply_nac_correction edge (sibling to
identity_dm), and the LO-TO splitting at q→0 — runs end-to-end on a real
ionic crystal, with no operator-layer or representation code changes.

Inputs (copied from phonopy/example/NaCl-rd/):
  - POSCAR-unitcell : conventional 8-atom (4 Na + 4 Cl) rocksalt cell
  - phonopy_disp.yaml : 2×2×2 supercell, primitive_axes auto (Fm-3m)
  - FORCE_SETS : precomputed forces from 10 random-displacement
    supercells (DFT reference, not Tersoff).
  - BORN : ε_∞ = 2.435 isotropic, Z*_{Na} = +1.087, Z*_{Cl} = -1.087.

Output: runs/nacl_polar/phonopy/, containing the
mesh-sampled ω(q,ν) WITH NAC and a "Γ-approach" sweep that pulls q
toward zero along [100] and reports the LO-TO splitting — the polar
fingerprint that's invisible on Si.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import phonopy


EXP_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXP_DIR.parent.parent
RUNS_DIR = REPO_ROOT / "runs" / "nacl_polar"
OUT = RUNS_DIR / "phonopy"
OUT.mkdir(parents=True, exist_ok=True)


KMESH = (16, 16, 16)


def main() -> None:
    # phonopy.load reads POSCAR-unitcell + phonopy_disp.yaml + FORCE_SETS
    # automatically; BORN is read explicitly with is_nac=True.
    # NaCl-rd uses random displacements ⇒ FORCE_SETS is "type-II"; the
    # canonical FC solver can't process it. Use symfc instead (small
    # external dep already on this host).
    phonon = phonopy.load(
        supercell_filename=str(EXP_DIR / "phonopy_disp.yaml"),
        unitcell_filename=str(EXP_DIR / "POSCAR-unitcell"),
        force_sets_filename=str(EXP_DIR / "FORCE_SETS"),
        born_filename=str(EXP_DIR / "BORN"),
        is_nac=True,
        fc_calculator="symfc",
        log_level=0,
    )

    print(f"[phonopy:NaCl] NAC active : {phonon.nac_params is not None}")
    if phonon.nac_params is not None:
        eps = np.asarray(phonon.nac_params["dielectric"])
        zstars = np.asarray(phonon.nac_params["born"])
        print(f"  ε_∞ diagonal     : {np.diag(eps).tolist()}")
        print(f"  Z*_Na diagonal   : {np.diag(zstars[0]).tolist()}")
        print(f"  Z*_Cl diagonal   : {np.diag(zstars[-1]).tolist()}")

    # ---- mesh-sampled dispersion ------------------------------------------
    phonon.run_mesh(
        mesh=list(KMESH),
        with_eigenvectors=True,
        is_mesh_symmetry=False,
        is_gamma_center=True,
    )
    mesh = phonon.get_mesh_dict()
    q_points = np.asarray(mesh["qpoints"])
    frequencies = np.asarray(mesh["frequencies"])
    print(f"[phonopy:NaCl] mesh dispersion: {frequencies.shape}, "
          f"min={frequencies.min():.4f} THz, max={frequencies.max():.4f} THz")
    np.save(OUT / "q_points.npy", q_points)
    np.save(OUT / "frequencies_THz.npy", frequencies)

    # ---- LO-TO sweep: approach Γ along [100] in fine steps ----------------
    # The phonopy NAC routine kicks in for |q| > 0 with a direction-
    # dependent correction. We sample a fine sweep from very small to
    # moderate q to see the LO-TO splitting saturate to its q→0+ value.
    eps_qs = np.geomspace(1e-3, 0.2, 12)
    direction = np.array([1.0, 0.0, 0.0])
    sweep_freqs = []
    for eps_q in eps_qs:
        q = direction * eps_q
        # phonopy band_structure interface for a single q.
        phonon.run_band_structure(
            [np.array([[0.0, 0.0, 0.0], q])],
            path_connections=[True],
            labels=["Γ", "→[100]"],
            with_eigenvectors=False,
        )
        bands = phonon.get_band_structure_dict()["frequencies"][0]
        # bands shape: (n_points_along_segment, n_modes); the second
        # point is the q we asked for.
        sweep_freqs.append(bands[-1])
    sweep_freqs = np.asarray(sweep_freqs)
    print(f"[phonopy:NaCl] Γ-approach sweep along [100]:")
    print(f"  |q| (rec.units)     LO (THz)    TO_avg (THz)    splitting")
    # NaCl has 2 atoms per primitive cell → 6 modes: 3 acoustic + 3 optical
    # at Γ. The optical modes pick up LO-TO. Per band index the optical
    # modes are the top 3.
    for eps_q, modes in zip(eps_qs, sweep_freqs):
        sorted_modes = np.sort(modes)
        top3 = sorted_modes[-3:]
        LO = float(top3[-1])
        TO_avg = float(np.mean(top3[:-1]))
        splitting = LO - TO_avg
        print(f"  {eps_q:.3e}        {LO:.4f}      {TO_avg:.4f}        {splitting:+.4f}")
    np.save(OUT / "loto_sweep_qs.npy", eps_qs)
    np.save(OUT / "loto_sweep_freqs.npy", sweep_freqs)

    # ---- harmonic thermodynamics for the cross-material identity ----------
    phonon.run_thermal_properties(t_min=0.0, t_max=1000.0, t_step=10.0)
    td = phonon.get_thermal_properties_dict()
    F_kJ = td["free_energy"]
    S_JK = td["entropy"]
    T_arr = td["temperatures"]
    Cv_JK = td["heat_capacity"]
    E_J = F_kJ * 1000.0 + T_arr * S_JK
    np.save(OUT / "temperatures_K.npy", T_arr)
    np.save(OUT / "free_energy_kJ_per_mol.npy", F_kJ)
    np.save(OUT / "entropy_J_per_K_per_mol.npy", S_JK)
    np.save(OUT / "heat_capacity_J_per_K_per_mol.npy", Cv_JK)
    np.save(OUT / "internal_energy_J_per_mol.npy", E_J)

    summary = (
        f"phonopy NaCl-rd run (NAC on)\n"
        f"-----------------------------\n"
        f"k/q-mesh          : {KMESH}\n"
        f"n_q               : {frequencies.shape[0]}\n"
        f"n_modes           : {frequencies.shape[1]}\n"
        f"freq min / max    : {frequencies.min():.4f} / "
        f"{frequencies.max():.4f} THz\n"
        f"NAC               : True (ε_∞ = {np.diag(eps)[0]:.3f}, "
        f"Z*_Na = {np.diag(zstars[0])[0]:+.3f})\n"
    )
    (OUT / "summary.txt").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
