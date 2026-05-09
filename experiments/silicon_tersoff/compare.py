"""Compare kaldo's and phonopy's dispersion materializations.

Reads frequencies, eigenvectors, group velocities, and q-points from both runs
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

    # ----- Save the comparison -----
    out = RUNS_DIR / "comparison"
    out.mkdir(exist_ok=True)
    np.save(out / "freq_diff_sorted_THz.npy", diff)
    np.save(out / "freq_abs_diff_sorted_THz.npy", abs_diff)
    summary = (
        f"silicon-Tersoff cross-code comparison\n"
        f"-------------------------------------\n"
        f"max |delta omega|    = {abs_diff.max():.6f} THz\n"
        f"mean |delta omega|   = {abs_diff.mean():.6f} THz\n"
        f"median |delta omega| = {np.median(abs_diff):.6f} THz\n"
        f"RMS delta omega      = {np.sqrt((diff**2).mean()):.6f} THz\n"
        f"q-grid aligned       = {perm is not None}\n"
    )
    (out / "summary.txt").write_text(summary)


if __name__ == "__main__":
    main()
