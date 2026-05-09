"""Per-mode cross-code diagnostics.

Run kaldo at sigma_kaldo = sqrt(2) * sigma_phono3py (matched effective stdev)
and phono3py at sigma_phono3py. Extract:

  * dispersion (frequency, group velocity)
  * heat capacities at T = 300 K
  * three-phonon linewidths Gamma_qν

Align q-points, compute per-mode ratios kaldo/phono3py, and print summary
statistics for each. The point: if frequencies and group velocities and
heat capacities all agree to numerical precision, the residual ~5% RTA
gap must live in Gamma. If Gamma also agrees, the gap is in the kappa
contraction itself (volume normalisation, RTA tau definition).
"""

from __future__ import annotations

import math

import numpy as np

from seed import (
    FD_DISPLACEMENT,
    KMESH,
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    TEMPERATURE,
    build_silicon_primitive,
    make_tersoff_calculator,
)


# Common effective standard deviation (THz). Both codes will run at this
# stdev: kaldo gets sigma_k = stdev * sqrt(2), phono3py gets sigma_p = stdev.
EFF_STDEV_THZ = 0.10


# ---------------------------------------------------------------------------
# kaldo: extract dispersion, group velocities, heat capacity, linewidth
# ---------------------------------------------------------------------------


def kaldo_extract(sigma_kaldo: float) -> dict[str, np.ndarray]:
    from kaldo.forceconstants import ForceConstants
    from kaldo.phonons import Phonons

    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()
    fc = ForceConstants(
        atoms=atoms,
        supercell=np.array(SUPERCELL_FC2),
        third_supercell=np.array(SUPERCELL_FC3),
        folder=str(RUNS_DIR / "kaldo" / "fc"),
    )
    fc.second.calculate(calc, delta_shift=FD_DISPLACEMENT)
    fc.third.calculate(calc, delta_shift=FD_DISPLACEMENT)
    ph = Phonons(
        forceconstants=fc,
        kpts=list(KMESH),
        is_classic=False,
        temperature=TEMPERATURE,
        third_bandwidth=sigma_kaldo,
        broadening_shape="gauss",
        folder=str(RUNS_DIR / "kaldo" / "phonons" / f"diag_{sigma_kaldo}"),
        storage="memory",
    )
    return {
        "frequencies": np.asarray(ph.frequency),                 # (n_q, n_modes), THz
        "group_velocities": np.asarray(ph.velocity),             # (n_q, n_modes, 3), Å·THz
        "heat_capacity": np.asarray(ph.heat_capacity),           # (n_q, n_modes), J/K (per mode)
        "bandwidth": np.asarray(ph.bandwidth),                   # (n_q, n_modes), THz
        "q_points": np.asarray(
            ph._reciprocal_grid.unitary_grid(is_wrapping=True)
        ),
    }


# ---------------------------------------------------------------------------
# phono3py: extract dispersion, group velocities, heat capacity, linewidth
# ---------------------------------------------------------------------------


def phono3py_extract(sigma_phono3py: float) -> dict[str, np.ndarray]:
    from phono3py import Phono3py
    from phonopy.structure.atoms import PhonopyAtoms
    from ase import Atoms

    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()

    unitcell = PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )
    ph3 = Phono3py(
        unitcell,
        supercell_matrix=np.diag(SUPERCELL_FC3),
        phonon_supercell_matrix=np.diag(SUPERCELL_FC2),
    )
    ph3.generate_fc2_displacements(distance=FD_DISPLACEMENT)
    fc2_forces = []
    for sc in ph3.phonon_supercells_with_displacements:
        a = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
        a.calc = calc
        fc2_forces.append(a.get_forces())
    ph3.phonon_forces = np.array(fc2_forces)
    ph3.generate_displacements(distance=FD_DISPLACEMENT)
    fc3_forces = []
    for sc in ph3.supercells_with_displacements:
        if sc is None:
            continue
        a = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
        a.calc = calc
        fc3_forces.append(a.get_forces())
    ph3.forces = np.array(fc3_forces)
    ph3.produce_fc2()
    ph3.produce_fc3()
    ph3.mesh_numbers = list(KMESH)
    ph3.sigmas = [sigma_phono3py]
    ph3.init_phph_interaction()
    # We need to set is_kappa_star=False to get the full unfolded grid (matches kaldo)
    ph3.run_thermal_conductivity(
        is_LBTE=False,
        temperatures=[TEMPERATURE],
        is_isotope=False,
        write_kappa=False,
        is_kappa_star=False,
    )
    tc = ph3.thermal_conductivity
    gamma = np.asarray(tc.gamma)            # (n_sigma, n_temp, n_q, n_modes), THz
    cv = np.asarray(tc.mode_heat_capacities) # (n_temp, n_q, n_modes), J/K
    gv = np.asarray(tc.group_velocities)     # (n_q, n_modes, 3)
    return {
        "frequencies": np.asarray(tc.frequencies),  # (n_q, n_modes), THz
        "group_velocities": gv,
        "heat_capacity": cv[0],                      # at T=TEMPERATURE
        "bandwidth": gamma[0, 0],                    # at sigma[0], T=TEMPERATURE
        "q_points": np.asarray(tc.qpoints),
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _wrap(q: np.ndarray) -> np.ndarray:
    return np.mod(q + 1e-9, 1.0)


def align_q_points(q_a: np.ndarray, q_b: np.ndarray) -> np.ndarray | None:
    if q_a.shape != q_b.shape:
        return None
    a = _wrap(q_a)
    b = _wrap(q_b)
    keys_a = np.round(a, 6)
    keys_b = np.round(b, 6)
    perm = np.full(len(b), -1, dtype=int)
    a_index = {tuple(k): i for i, k in enumerate(keys_a)}
    for i, k in enumerate(keys_b):
        j = a_index.get(tuple(k))
        if j is None:
            return None
        perm[i] = j
    return perm


def report(name: str, K: np.ndarray, P: np.ndarray) -> None:
    """Per-mode comparison report.

    Sorts within each q-point so mode ordering doesn't confound.
    """
    K_sorted = np.sort(K.reshape(K.shape[0], K.shape[1], -1)
                        if K.ndim == 3 else K, axis=1)
    P_sorted = np.sort(P.reshape(P.shape[0], P.shape[1], -1)
                        if P.ndim == 3 else P, axis=1)
    diff = K_sorted - P_sorted
    abs_diff = np.abs(diff)
    # ratios where denominator is non-tiny
    safe = np.abs(P_sorted) > 1e-10
    ratio = np.where(safe, K_sorted / np.where(safe, P_sorted, 1.0), np.nan)
    print(f"  {name}:")
    print(f"    kaldo  range = [{K_sorted.min():.6e}, {K_sorted.max():.6e}]")
    print(f"    ph3    range = [{P_sorted.min():.6e}, {P_sorted.max():.6e}]")
    print(f"    abs diff: max = {abs_diff.max():.6e}, mean = {abs_diff.mean():.6e}")
    print(f"    ratio kaldo/ph3 (where ph3 > 1e-10): "
          f"min = {np.nanmin(ratio):.4f}, mean = {np.nanmean(ratio):.4f}, max = {np.nanmax(ratio):.4f}")


def main() -> None:
    sigma_p = EFF_STDEV_THZ
    sigma_k = sigma_p * math.sqrt(2)
    print(f"effective stdev = {sigma_p:.4f} THz")
    print(f"kaldo nominal sigma   = {sigma_k:.4f} THz")
    print(f"phono3py nominal sigma = {sigma_p:.4f} THz")
    print()

    print("[1/2] running kaldo ...")
    K = kaldo_extract(sigma_k)

    print("[2/2] running phono3py ...")
    P = phono3py_extract(sigma_p)

    perm = align_q_points(K["q_points"], P["q_points"])
    if perm is None:
        print("WARN: q-point grids do not align; comparing element-wise without alignment")
        Kf = K
    else:
        print(f"q-grids aligned under permutation. e.g. ph3[0] -> kaldo[{perm[0]}]")
        Kf = {
            "frequencies": K["frequencies"][perm],
            "group_velocities": K["group_velocities"][perm],
            "heat_capacity": K["heat_capacity"][perm],
            "bandwidth": K["bandwidth"][perm],
            "q_points": K["q_points"][perm],
        }
    print()
    print("=" * 64)
    print("Per-mode diagnostics (sorted within each q to bypass mode ordering)")
    print("=" * 64)
    report("frequencies (THz)",        Kf["frequencies"],      P["frequencies"])
    report("group_velocity_norm",
           np.linalg.norm(Kf["group_velocities"], axis=-1),
           np.linalg.norm(P["group_velocities"], axis=-1))
    report("heat_capacity",            Kf["heat_capacity"],    P["heat_capacity"])
    report("bandwidth Gamma (THz)",    Kf["bandwidth"],        P["bandwidth"])

    out = RUNS_DIR / "comparison"
    out.mkdir(parents=True, exist_ok=True)
    np.savez(
        out / "diagnostics_at_stdev_0.10.npz",
        kaldo_freq=Kf["frequencies"], ph3_freq=P["frequencies"],
        kaldo_gv=Kf["group_velocities"], ph3_gv=P["group_velocities"],
        kaldo_cv=Kf["heat_capacity"], ph3_cv=P["heat_capacity"],
        kaldo_gamma=Kf["bandwidth"], ph3_gamma=P["bandwidth"],
    )


if __name__ == "__main__":
    main()
