"""Test whether ShengBTE's interpretation of FC3 depends on the CONTROL
file's lfactor convention.

Our CONTROL uses lfactor=0.5431 (Si lattice in nm) with fractional lattvec.
The reference Si bulk run uses lfactor=0.1 (= 1 Å) with Å-scale lattvec.
These are MATHEMATICALLY equivalent (same physical lattice).

If we take our UN-scaled FORCE_CONSTANTS_3RD (Φ values × 10 vs production)
and pair it with the reference's lfactor=0.1 CONTROL, does ShengBTE produce
the correct κ ~ 17 W/m·K?

  - If YES: ShengBTE has a hidden dependency on lfactor that affects FC3
    interpretation. Our convert.py's 0.1 is compensating for this.
  - If NO: the 0.1 is genuinely needed regardless of CONTROL convention.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


REPO = Path("/home/giuseppe/Development/openmaterials-ai")
SRC = REPO / "experiments" / "silicon_shengbte"
OUT = REPO / "runs" / "silicon_tersoff_diag_lfactor"
OUT.mkdir(parents=True, exist_ok=True)


# Our existing unscaled FC3 lives in the silicon_tersoff_diag_unscaled run dir
UNSCALED_FC3 = REPO / "runs" / "silicon_tersoff_diag_unscaled" / "FORCE_CONSTANTS_3RD"


# Reference-style CONTROL: lfactor=0.1 (= 1 Å), lattvec in Å.
# Si lattice = 5.431 Å. Primitive cell vectors a/2 (0, 1, 1), etc.
# In Å with lfactor=0.1: lattvec values are × 10 (to be in units of 0.1 nm = 1 Å).
# So 0.5431/2 nm × (0, 1, 1) becomes (0, 2.7155, 2.7155) in units of 1 Å (lfactor=0.1 nm).
CONTROL_LF01 = """&allocations
\tnelements=1,
\tnatoms=2,
\tngrid(:)=8 8 8
&end
&crystal
\tlfactor=0.1,
\tlattvec(:,1)= 0.0 2.7155 2.7155,
\tlattvec(:,2)= 2.7155 0.0 2.7155,
\tlattvec(:,3)= 2.7155 2.7155 0.0,
\telements="Si"
\ttypes=1 1,
\tpositions(:,1)=0.00  0.00  0.00,
\tpositions(:,2)=0.25  0.25  0.25
\tscell(:)=4 4 4
&end
&parameters
\tT=300.0
\tscalebroad=1.0
&end
&flags
\tnonanalytic=.false.,
\tconvergence=.true.,
\tisotopes=.false.,
\tnanowires=.false.,
\tonlyharmonic=.false.,
&end
"""


def main() -> int:
    # Copy unscaled FC3 + verbatim FC2
    if not UNSCALED_FC3.exists():
        print(f"ERROR: {UNSCALED_FC3} does not exist; run diagnostic_unscaled_fc3.py first.")
        return 1
    shutil.copy(UNSCALED_FC3, OUT / "FORCE_CONSTANTS_3RD")
    shutil.copy(SRC / "FORCE_CONSTANTS_2ND", OUT / "FORCE_CONSTANTS_2ND")
    # Write the lfactor=0.1 CONTROL
    (OUT / "CONTROL").write_text(CONTROL_LF01)
    print("Wrote lfactor=0.1 CONTROL")

    bin_path = REPO / "shengbte" / "ShengBTE"
    print(f"Running ShengBTE in {OUT} ...")
    t0 = time.time()
    proc = subprocess.run(
        [str(bin_path)], cwd=str(OUT), capture_output=True, text=True, timeout=600,
    )
    print(f"  done in {time.time()-t0:.1f} s, return code {proc.returncode}")
    if proc.returncode != 0:
        print("STDERR (tail):")
        print(proc.stderr[-1500:])
        return 1

    rta = OUT / "BTE.KappaTensorVsT_RTA"
    if not rta.exists():
        for sub in OUT.glob("T*K"):
            if (sub / "BTE.KappaTensorVsT_RTA").exists():
                rta = sub / "BTE.KappaTensorVsT_RTA"; break
    raw = np.loadtxt(rta, ndmin=2)
    k_iso = float(np.trace(raw[0, 1:10].reshape(3, 3)) / 3)
    print()
    print("=" * 70)
    print(f"ShengBTE κ with UN-scaled Φ (×10 vs production) and lfactor=0.1 CONTROL:")
    print(f"  κ (RTA, tr/3) = {k_iso:.4f} W/m/K")
    print()
    print("References:")
    print("  Production (lfactor=0.5431, Φ scaled by 0.1):  ~16.93 W/m/K")
    print("  Unscaled Φ with lfactor=0.5431 CONTROL:         0.169 W/m/K")
    print("=" * 70)
    if 10 < k_iso < 25:
        print(
            "VERDICT: lfactor=0.1 with unscaled Φ gives CORRECT κ. The 0.1 in "
            "convert.py is compensating for ShengBTE's hidden lfactor-dependent "
            "interpretation of FC3 magnitudes!"
        )
    elif 0.05 < k_iso < 0.5:
        print(
            "VERDICT: lfactor=0.1 with unscaled Φ still gives WRONG κ. The 0.1 "
            "is independent of CONTROL convention."
        )
    else:
        print(f"VERDICT: unexpected κ value {k_iso} — investigate further.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
