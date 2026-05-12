"""Compare kaldo's and phonopy/phono3py's representations.

Reads dispersion (frequencies, eigenvectors, group velocities, q-points) from kaldo
and phonopy, plus thermal conductivity (RTA + full BTE) from kaldo and phono3py,
and reports where they agree / disagree.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from seed import RUNS_DIR


def load_run(name: str) -> dict[str, np.ndarray]:
    base = RUNS_DIR / name
    return {
        "frequencies": np.load(base / "frequencies_THz.npy"),
        "group_velocities": np.load(base / "group_velocities_AT.npy"),
        "q_points": np.load(base / "q_points.npy"),
    }


def load_kappa(name: str, scheme: str) -> np.ndarray | None:
    """Load kappa tensor from a code's output. Returns 3x3 tensor if available, else None.

    kaldo stores 3x3; phono3py stores Voigt-6 (xx, yy, zz, yz, xz, xy).
    """
    base = RUNS_DIR / name
    if name == "kaldo":
        f = base / f"kappa_{scheme}_tensor_WmK.npy"
        return np.load(f) if f.exists() else None
    if name == "phono3py":
        f = base / f"kappa_{scheme}_voigt_WmK.npy"
        if not f.exists():
            return None
        v = np.asarray(np.load(f)).reshape(-1)[:6]
        # Voigt -> 3x3
        t = np.array(
            [
                [v[0], v[5], v[4]],
                [v[5], v[1], v[3]],
                [v[4], v[3], v[2]],
            ]
        )
        return t
    return None


def _wrap_q(q: np.ndarray) -> np.ndarray:
    """Wrap reduced q-points into [0, 1)."""
    return np.mod(q + 1e-9, 1.0)


def align_q_points(q_a: np.ndarray, q_b: np.ndarray) -> np.ndarray | None:
    """Return permutation P such that q_a[P] ~ q_b, or None if no alignment found.

    Both arrays are (N, 3) in reduced (fractional) coordinates of the reciprocal lattice.
    """
    if q_a.shape != q_b.shape:
        return None
    a = _wrap_q(q_a)
    b = _wrap_q(q_b)
    # Build a key for each q to allow O(N log N) matching
    keys_a = np.round(a, 6)
    keys_b = np.round(b, 6)
    # for each row in b, find the matching row in a
    perm = np.full(len(b), -1, dtype=int)
    a_index = {tuple(k): i for i, k in enumerate(keys_a)}
    for i, k in enumerate(keys_b):
        j = a_index.get(tuple(k))
        if j is None:
            return None
        perm[i] = j
    return perm


def main() -> None:
    K = load_run("kaldo")
    P = load_run("phonopy")

    print("=" * 64)
    print("Cross-code comparison: kaldo vs phonopy")
    print("=" * 64)
    print()

    # ----- Shapes -----
    print(f"  shapes:")
    print(f"    kaldo   freq={K['frequencies'].shape}  q={K['q_points'].shape}")
    print(f"    phonopy freq={P['frequencies'].shape}  q={P['q_points'].shape}")
    print()

    # ----- q-point grid alignment -----
    perm = align_q_points(K["q_points"], P["q_points"])
    if perm is None:
        print("  q-point grids do NOT align as wrapped reduced coordinates.")
        print(f"    first kaldo q   = {K['q_points'][:3]}")
        print(f"    first phonopy q = {P['q_points'][:3]}")
        print(f"    last  kaldo q   = {K['q_points'][-3:]}")
        print(f"    last  phonopy q = {P['q_points'][-3:]}")
        print()
        print("  -> proceeding with element-wise comparison without alignment.")
        kaldo_freq = K["frequencies"]
        phono_freq = P["frequencies"]
    else:
        print(f"  q-point grids align under permutation. example: phonopy[0] -> kaldo[{perm[0]}]")
        kaldo_freq = K["frequencies"][perm]
        phono_freq = P["frequencies"]

    # ----- Frequency comparison (sorted within each q-point to compare absent mode-matching) -----
    kaldo_sorted = np.sort(kaldo_freq, axis=1)
    phono_sorted = np.sort(phono_freq, axis=1)
    diff = kaldo_sorted - phono_sorted
    abs_diff = np.abs(diff)

    print()
    print(f"  frequency comparison (sorted within each q):")
    print(f"    max |Δω|     = {abs_diff.max():.6f} THz")
    print(f"    mean |Δω|    = {abs_diff.mean():.6f} THz")
    print(f"    median |Δω|  = {np.median(abs_diff):.6f} THz")
    print(f"    RMS Δω       = {np.sqrt((diff**2).mean()):.6f} THz")
    print()

    # ----- High-symmetry-point summary -----
    print("  highest mode at each q (LO branch):")
    k_max = kaldo_sorted[:, -1]
    p_max = phono_sorted[:, -1]
    print(f"    kaldo:   min={k_max.min():.4f}  mean={k_max.mean():.4f}  max={k_max.max():.4f} THz")
    print(f"    phonopy: min={p_max.min():.4f}  mean={p_max.mean():.4f}  max={p_max.max():.4f} THz")
    print(f"    Δ:       max={np.abs(k_max - p_max).max():.6f}  mean={np.abs(k_max - p_max).mean():.6f} THz")
    print()

    print("  acoustic (lowest mode) min over grid:")
    k_min = kaldo_sorted[:, 0]
    p_min = phono_sorted[:, 0]
    print(f"    kaldo:   min={k_min.min():.4f} THz   (Gamma if grid includes 0,0,0)")
    print(f"    phonopy: min={p_min.min():.4f} THz   (Gamma if grid includes 0,0,0)")

    # ----- Thermal conductivity comparison -----
    print()
    print("-" * 64)
    print("  thermal conductivity (W/m/K, average of xx/yy/zz)")
    print("-" * 64)
    kappa_lines: list[str] = []
    for k_scheme, p_scheme in [("rta", "rta"), ("inverse", "lbte")]:
        K = load_kappa("kaldo", k_scheme)
        P = load_kappa("phono3py", p_scheme)
        k_avg = float("nan") if K is None else float(np.mean(np.diag(K)))
        p_avg = float("nan") if P is None else float(np.mean(np.diag(P)))
        line = (
            f"  {k_scheme:>10s} (kaldo {k_scheme}, phono3py {p_scheme}): "
            f"kaldo {k_avg:8.3f}  phono3py {p_avg:8.3f}"
        )
        if k_avg == k_avg and p_avg == p_avg:
            ratio = k_avg / p_avg
            line += f"  ratio kaldo/phono3py = {ratio:5.3f}"
        print(line)
        kappa_lines.append(line)

    print()
    print(
        "  Both codes are now explicitly forced to Gaussian broadening with\n"
        "  the same numerical sigma (set in seed.BROADENING_SIGMA_THZ).\n"
        "  Any residual kappa gap is therefore not from differing broadening\n"
        "  *defaults* but from the codes' differing internal use of sigma\n"
        "  (e.g., placement in the energy-conservation delta function,\n"
        "  per-mode adaptive corrections, or scattering-matrix normalization).\n"
        "  This residual is the next substrate-relevant discrimination."
    )

    # ----- Save the comparison -----
    out = RUNS_DIR / "comparison"
    out.mkdir(exist_ok=True)
    np.save(out / "freq_diff_sorted_THz.npy", diff)
    np.save(out / "freq_abs_diff_sorted_THz.npy", abs_diff)
    summary = (
        f"silicon-Tersoff cross-code comparison\n"
        f"-------------------------------------\n"
        f"DISPERSION\n"
        f"  max |delta omega|    = {abs_diff.max():.6f} THz\n"
        f"  mean |delta omega|   = {abs_diff.mean():.6f} THz\n"
        f"  median |delta omega| = {np.median(abs_diff):.6f} THz\n"
        f"  RMS delta omega      = {np.sqrt((diff**2).mean()):.6f} THz\n"
        f"  q-grid aligned       = {perm is not None}\n"
        f"\n"
        f"THERMAL CONDUCTIVITY (W/m/K, avg of xx/yy/zz)\n"
        + "\n".join(kappa_lines) + "\n"
    )
    (out / "summary.txt").write_text(summary)


if __name__ == "__main__":
    main()
