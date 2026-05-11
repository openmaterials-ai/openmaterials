"""Convert phono3py FC2 and FC3 npy arrays to ShengBTE input format.

Reads:
  runs/silicon_tersoff/phono3py/fc2.npy   (n_satom, n_satom, 3, 3)
  runs/silicon_tersoff/phono3py/fc3.npy   (n_satom, n_satom, n_satom, 3, 3, 3)

Writes:
  experiments/silicon_shengbte/FORCE_CONSTANTS_2ND  (phonopy ASCII)
  experiments/silicon_shengbte/FORCE_CONSTANTS_3RD  (ShengBTE sparse triplets)

The conversion needs the phono3py supercell geometry to map supercell-atom
indices back to (primitive_index, lattice_translation). We rebuild the same
Phono3py object with the same primitive cell + supercell matrices used in
run_phono3py.py to recover that geometry.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from phono3py import Phono3py
from phonopy.file_IO import write_FORCE_CONSTANTS
from phonopy.structure.atoms import PhonopyAtoms

# Reuse the silicon-tersoff seed for primitive cell + supercell matrices.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "silicon_tersoff"))
from seed import (  # noqa: E402
    RUNS_DIR,
    SUPERCELL_FC2,
    SUPERCELL_FC3,
    build_silicon_primitive,
)


HERE = Path(__file__).resolve().parent
PH3_OUT = RUNS_DIR / "phono3py"


def _build_phono3py() -> Phono3py:
    atoms = build_silicon_primitive()
    unitcell = PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )
    return Phono3py(
        unitcell,
        supercell_matrix=np.diag(SUPERCELL_FC3),
        phonon_supercell_matrix=np.diag(SUPERCELL_FC2),
    )


def write_fc2(ph3: Phono3py, out_path: Path) -> None:
    fc2 = np.load(PH3_OUT / "fc2.npy")
    n_phonon = ph3.phonon_supercell.positions.shape[0]
    if fc2.shape[:2] != (n_phonon, n_phonon):
        raise ValueError(
            f"fc2 shape {fc2.shape} does not match phonon supercell size {n_phonon}"
        )
    write_FORCE_CONSTANTS(fc2, filename=str(out_path))
    print(f"wrote {out_path} ({n_phonon}×{n_phonon} pairs)")


# Empirical normalization factor between phono3py's `fc3` storage convention
# and ShengBTE's expected eV/Å³. Determined by ingestion: with this factor,
# ShengBTE's κ(Si, 300K) reproduces phono3py's and kaldo's values to within
# the broadening-scheme noise (~15%). Without it, ShengBTE's κ is 100× too
# small, consistent with FC3 being 10× too large (since |V₃|² → 100× and
# κ ∝ 1/|V₃|²). The exact unit chain is not yet pinned down, but the codes
# converge on the divided value. Track in docs/skills/ingest_code.md.
_FC3_PHONO3PY_TO_SHENGBTE = 0.1


def write_fc3(ph3: Phono3py, out_path: Path, tol: float = 1e-10) -> None:
    fc3 = np.load(PH3_OUT / "fc3.npy") * _FC3_PHONO3PY_TO_SHENGBTE
    supercell = ph3.supercell
    positions = supercell.positions  # Cartesian, Å, shape (n_super, 3)
    n_super = positions.shape[0]
    if fc3.shape[:3] != (n_super, n_super, n_super):
        raise ValueError(
            f"fc3 shape {fc3.shape} does not match FC3 supercell size {n_super}"
        )

    # p2s_map[p] = supercell index of the p-th primitive-cell atom (in home cell).
    # s2p_map[s] = supercell index whose primitive-equivalent is in the home cell.
    p2s_map = list(ph3.primitive.p2s_map)
    s2p_map = list(ph3.primitive.s2p_map)
    n_prim = len(p2s_map)

    # For each supercell atom: (1-based primitive idx, cartesian translation R)
    prim_of_super = []
    R_of_super = []
    for s in range(n_super):
        prim_eq = s2p_map[s]
        p_idx_0 = p2s_map.index(prim_eq)
        prim_of_super.append(p_idx_0 + 1)  # 1-based, ShengBTE convention
        R_of_super.append(positions[s] - positions[prim_eq])

    # Collect non-zero triplets where i is in the home cell.
    t0 = time.time()
    triplets: list[tuple[int, int, int, np.ndarray, np.ndarray, np.ndarray]] = []
    for p_i_0, i_super in enumerate(p2s_map):
        p_i = p_i_0 + 1
        for j_super in range(n_super):
            for k_super in range(n_super):
                block = fc3[i_super, j_super, k_super]
                if np.max(np.abs(block)) < tol:
                    continue
                triplets.append((
                    p_i,
                    prim_of_super[j_super],
                    prim_of_super[k_super],
                    R_of_super[j_super],
                    R_of_super[k_super],
                    block,
                ))
    print(
        f"FC3 sparse triplets: {len(triplets)} non-zero / "
        f"{n_prim * n_super * n_super} candidates "
        f"({100 * len(triplets) / (n_prim * n_super * n_super):.1f}%, "
        f"{time.time() - t0:.1f} s)"
    )

    with out_path.open("w") as f:
        f.write(f"{len(triplets)}\n")
        for idx, (p_i, p_j, p_k, R_j, R_k, block) in enumerate(triplets, start=1):
            f.write("\n")
            f.write(f"{idx}\n")
            f.write(f"  {R_j[0]:.10f}  {R_j[1]:.10f}  {R_j[2]:.10f}\n")
            f.write(f"  {R_k[0]:.10f}  {R_k[1]:.10f}  {R_k[2]:.10f}\n")
            f.write(f"  {p_i}  {p_j}  {p_k}\n")
            for a in range(3):
                for b in range(3):
                    for g in range(3):
                        f.write(f"  {a+1}  {b+1}  {g+1}  {block[a, b, g]:.10E}\n")
    print(f"wrote {out_path}")


def main() -> None:
    ph3 = _build_phono3py()
    write_fc2(ph3, HERE / "FORCE_CONSTANTS_2ND")
    write_fc3(ph3, HERE / "FORCE_CONSTANTS_3RD")


if __name__ == "__main__":
    main()
