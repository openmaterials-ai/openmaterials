"""Run ShengBTE with the same FC3 our convert.py produces, but UN-scaled
(× 10). If the resulting κ is ~100× too small, that confirms kaldo's
save_third_order_matrix would produce wrong κ via ShengBTE — i.e. kaldo
needs the 0.1 factor too."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


REPO = Path("/home/giuseppe/Development/openmaterials-ai")
SRC = REPO / "experiments" / "silicon_shengbte"
OUT = REPO / "runs" / "silicon_tersoff_diag_unscaled"
OUT.mkdir(parents=True, exist_ok=True)


def rewrite_fc3_unscaled(src_path: Path, dst_path: Path, factor: float = 10.0) -> None:
    """Multiply every Φ value in src_path by `factor` (10 to UN-do 0.1) and
    write to dst_path."""
    with src_path.open() as fin, dst_path.open("w") as fout:
        first_line = fin.readline()
        ntri = int(first_line.strip())
        fout.write(first_line)
        for block_idx in range(ntri):
            # Blank line
            blank = fin.readline()
            fout.write(blank)
            # Sequential index
            idx_line = fin.readline()
            fout.write(idx_line)
            # R_j (Cartesian)
            fout.write(fin.readline())
            # R_k
            fout.write(fin.readline())
            # atom indices i j k
            fout.write(fin.readline())
            # 27 lines: ll mm nn Phi
            for _ in range(27):
                line = fin.readline()
                parts = line.split()
                a, b, g, phi = int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
                phi_new = phi * factor
                fout.write(f"  {a}  {b}  {g}  {phi_new:.10E}\n")
    print(f"wrote {dst_path} ({ntri} triplets, Φ values × {factor})")


def main() -> int:
    # Copy CONTROL and FORCE_CONSTANTS_2ND verbatim
    shutil.copy(SRC / "CONTROL", OUT / "CONTROL")
    shutil.copy(SRC / "FORCE_CONSTANTS_2ND", OUT / "FORCE_CONSTANTS_2ND")
    # Rescale FC3: multiply existing (with-0.1) values by 10 to recover the "unscaled" form
    rewrite_fc3_unscaled(SRC / "FORCE_CONSTANTS_3RD", OUT / "FORCE_CONSTANTS_3RD", factor=10.0)

    bin_path = REPO / "shengbte" / "ShengBTE"
    print(f"running ShengBTE in {OUT}")
    t0 = time.time()
    proc = subprocess.run([str(bin_path)], cwd=str(OUT), capture_output=True, text=True, timeout=600)
    print(f"  done in {time.time()-t0:.1f} s, return code {proc.returncode}")
    if proc.returncode != 0:
        print("STDERR (tail):"); print(proc.stderr[-2000:]); return 1

    rta = OUT / "BTE.KappaTensorVsT_RTA"
    if not rta.exists():
        for sub in OUT.glob("T*K"):
            if (sub / "BTE.KappaTensorVsT_RTA").exists():
                rta = sub / "BTE.KappaTensorVsT_RTA"; break
    if not rta.exists():
        print(f"BTE.KappaTensorVsT_RTA not found"); return 1

    raw = np.loadtxt(rta, ndmin=2)
    k_tensor = raw[0, 1:10].reshape(3, 3)
    k_iso = float(np.trace(k_tensor) / 3)
    print()
    print("=" * 70)
    print(f"ShengBTE κ (RTA, tr/3) with UN-scaled Φ (× 10 vs production): {k_iso:.4f} W/m/K")
    print(f"Production reference (with 0.1 factor): ~16.93 W/m/K")
    print(f"Ratio (unscaled / production): {k_iso / 16.93:.4f}")
    print("=" * 70)
    print(f"Expected if factor IS needed: κ ≈ 0.169 W/m/K (100× smaller)")
    print(f"Expected if factor NOT needed: κ ≈ 16.93 W/m/K (same)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
