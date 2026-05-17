"""Diagnostic: does the empirical FC3 0.1 factor stay at 0.1 when the FC3
supercell changes from 3x3x3 to 2x2x2?

Procedure:
  1. Run phono3py with SUPERCELL_FC3=(2,2,2) (instead of (3,3,3)). Same FC2
     supercell (4,4,4), same FD displacement, same q-mesh. Save fc3.npy.
  2. Run phono3py's own thermal conductivity (gives reference kappa).
  3. Convert fc3.npy to ShengBTE's FORCE_CONSTANTS_3RD using the standard
     convert.py logic with the 0.1 factor.
  4. Run ShengBTE.
  5. Compare ShengBTE kappa vs phono3py kappa.

Interpretation:
  - If ShengBTE kappa (with 0.1) matches phono3py kappa within ~15% on
    2x2x2: the 0.1 is a code-pair convention. Proceed to Option B (trace
    the convention).
  - If ShengBTE kappa (with 0.1) is far off on 2x2x2: the converter has a
    per-supercell-size bug; the 0.1 happens to work for 3x3x3 by accident.

Outputs go to runs/silicon_tersoff_diag_222/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from phono3py import Phono3py
from phonopy.file_IO import write_FORCE_CONSTANTS
from phonopy.structure.atoms import PhonopyAtoms

from seed import (
    BROADENING_SIGMA_THZ,
    FD_DISPLACEMENT,
    KMESH,
    REPO_ROOT,
    SUPERCELL_FC2,
    TEMPERATURE,
    build_silicon_primitive,
    make_tersoff_calculator,
)


REPO = REPO_ROOT
SUPERCELL_FC3_DIAG = (2, 2, 2)
OUT = REPO / "runs" / "silicon_tersoff_diag_222"
PHONO3PY_OUT = OUT / "phono3py"
SHENGBTE_OUT = OUT / "shengbte"
PHONO3PY_OUT.mkdir(parents=True, exist_ok=True)
SHENGBTE_OUT.mkdir(parents=True, exist_ok=True)

# ShengBTE binary location
SHENGBTE_BIN = REPO / "shengbte" / "ShengBTE"
if not SHENGBTE_BIN.exists():
    SHENGBTE_BIN = Path("/mnt/data/Development/openmaterials-ai/shengbte/ShengBTE")

# Same 0.1 factor as the production convert.py uses for 3x3x3.
_FC3_PHONO3PY_TO_SHENGBTE = 0.1


def ase_to_phonopy(atoms) -> PhonopyAtoms:
    return PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(),
    )


def phonopy_to_ase(supercell: PhonopyAtoms):
    from ase import Atoms
    return Atoms(
        symbols=supercell.symbols,
        cell=supercell.cell,
        scaled_positions=supercell.scaled_positions,
        pbc=True,
    )


def compute_forces(supercells, calc):
    out = []
    for sc in supercells:
        if sc is None:
            out.append(None)
            continue
        ase_sc = phonopy_to_ase(sc)
        ase_sc.calc = calc
        out.append(ase_sc.get_forces())
    return out


def run_phono3py() -> tuple[Phono3py, float]:
    """Run phono3py at the diagnostic FC3 supercell. Returns the phono3py
    object and the RTA kappa (trace / 3)."""
    atoms = build_silicon_primitive()
    calc = make_tersoff_calculator()

    print(f"[diag] FC2 supercell {SUPERCELL_FC2}, FC3 supercell {SUPERCELL_FC3_DIAG}")
    unitcell = ase_to_phonopy(atoms)
    ph3 = Phono3py(
        unitcell,
        supercell_matrix=np.diag(SUPERCELL_FC3_DIAG),
        phonon_supercell_matrix=np.diag(SUPERCELL_FC2),
    )

    print("[diag] FC2 displacements + forces")
    ph3.generate_fc2_displacements(distance=FD_DISPLACEMENT)
    fc2_forces = compute_forces(ph3.phonon_supercells_with_displacements, calc)
    ph3.phonon_forces = np.array(fc2_forces)

    print("[diag] FC3 displacements + forces")
    ph3.generate_displacements(distance=FD_DISPLACEMENT)
    fc3_forces_raw = compute_forces(ph3.supercells_with_displacements, calc)
    fc3_forces = np.array([f for f in fc3_forces_raw if f is not None])
    ph3.forces = fc3_forces

    print("[diag] producing FC2, FC3")
    ph3.produce_fc2()
    ph3.produce_fc3()

    np.save(PHONO3PY_OUT / "fc2.npy", np.asarray(ph3.fc2))
    np.save(PHONO3PY_OUT / "fc3.npy", np.asarray(ph3.fc3))
    print(f"[diag] fc3 shape: {np.asarray(ph3.fc3).shape}")
    print(f"[diag] max |fc3|: {np.abs(ph3.fc3).max():.3f} eV/A^3")

    print("[diag] phono3py thermal conductivity (RTA)")
    ph3.mesh_numbers = list(KMESH)
    ph3.sigmas = [BROADENING_SIGMA_THZ]
    ph3.init_phph_interaction()
    ph3.run_thermal_conductivity(
        is_LBTE=False, temperatures=[TEMPERATURE], is_isotope=False, write_kappa=False,
    )
    tc = ph3.thermal_conductivity
    kappa_voigt = np.asarray(tc.kappa).reshape(-1)[:6]
    kappa_trace_over_3 = float(np.mean(kappa_voigt[:3]))
    print(f"[diag] phono3py kappa (RTA, avg xx/yy/zz): {kappa_trace_over_3:.3f} W/m/K")
    return ph3, kappa_trace_over_3


def write_fc3_shengbte(ph3: Phono3py, factor: float = _FC3_PHONO3PY_TO_SHENGBTE) -> Path:
    """Mirror of convert.py:write_fc3 but parameterised on the supercell of
    the diagnostic phono3py instance."""
    out = SHENGBTE_OUT / "FORCE_CONSTANTS_3RD"
    fc3 = np.asarray(ph3.fc3) * factor
    supercell = ph3.supercell
    positions = supercell.positions
    n_super = positions.shape[0]
    p2s_map = list(ph3.primitive.p2s_map)
    s2p_map = list(ph3.primitive.s2p_map)
    prim_of_super = []
    R_of_super = []
    for s in range(n_super):
        prim_eq = s2p_map[s]
        p_idx_0 = p2s_map.index(prim_eq)
        prim_of_super.append(p_idx_0 + 1)
        R_of_super.append(positions[s] - positions[prim_eq])

    triplets = []
    tol = 1e-10
    for p_i_0, i_super in enumerate(p2s_map):
        p_i = p_i_0 + 1
        for j_super in range(n_super):
            for k_super in range(n_super):
                block = fc3[i_super, j_super, k_super]
                if np.max(np.abs(block)) < tol:
                    continue
                triplets.append((
                    p_i, prim_of_super[j_super], prim_of_super[k_super],
                    R_of_super[j_super], R_of_super[k_super], block,
                ))

    with out.open("w") as f:
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
                        f.write(f"  {a+1}  {b+1}  {g+1}  {block[a,b,g]:.10E}\n")
    print(f"[diag] wrote {out} ({len(triplets)} triplets, factor={factor})")
    return out


def write_fc2_shengbte(ph3: Phono3py) -> Path:
    """Write FORCE_CONSTANTS_2ND in phonopy ASCII format."""
    out = SHENGBTE_OUT / "FORCE_CONSTANTS_2ND"
    fc2 = np.asarray(ph3.fc2)
    write_FORCE_CONSTANTS(fc2, filename=str(out))
    print(f"[diag] wrote {out}")
    return out


def write_control_file() -> Path:
    """Reuse the same crystal block as production CONTROL; only `scell`
    might need adjusting if the FC2 supercell changed. We keep FC2 at
    (4,4,4) so scell stays the same."""
    src = REPO / "experiments" / "silicon_shengbte" / "CONTROL"
    dst = SHENGBTE_OUT / "CONTROL"
    shutil.copy(src, dst)
    print(f"[diag] copied CONTROL from {src}")
    return dst


def run_shengbte() -> float:
    """Run ShengBTE in the diagnostic directory, parse the RTA kappa tensor."""
    cwd = SHENGBTE_OUT
    bin_path = SHENGBTE_BIN
    print(f"[diag] launching ShengBTE: {bin_path} (cwd={cwd})")
    t0 = time.time()
    proc = subprocess.run(
        [str(bin_path)], cwd=str(cwd), capture_output=True, text=True, timeout=600,
    )
    print(f"[diag]   ShengBTE done in {time.time()-t0:.1f} s, return code {proc.returncode}")
    if proc.returncode != 0:
        print("[diag] STDERR (tail):")
        print(proc.stderr[-2000:])
        raise RuntimeError("ShengBTE returned non-zero")

    rta_file = cwd / "BTE.KappaTensorVsT_RTA"
    if not rta_file.exists():
        # Sometimes ShengBTE writes to a T-named subdirectory.
        for sub in cwd.glob("T*K"):
            if (sub / "BTE.KappaTensorVsT_RTA").exists():
                rta_file = sub / "BTE.KappaTensorVsT_RTA"
                break
    if not rta_file.exists():
        raise RuntimeError(f"BTE.KappaTensorVsT_RTA not found in {cwd}")

    raw = np.loadtxt(rta_file, ndmin=2)
    # First column is T; next 9 are tensor components.
    kappa_tensor = raw[0, 1:10].reshape(3, 3)
    kappa_trace_over_3 = float(np.trace(kappa_tensor) / 3)
    print(f"[diag] ShengBTE kappa (RTA, tr/3): {kappa_trace_over_3:.3f} W/m/K")
    return kappa_trace_over_3


def main() -> int:
    print("=" * 78)
    print("Diagnostic A: does FC3 0.1 factor hold on 2x2x2 supercell?")
    print("=" * 78)

    ph3, kappa_phono3py = run_phono3py()
    write_fc2_shengbte(ph3)
    write_fc3_shengbte(ph3, factor=_FC3_PHONO3PY_TO_SHENGBTE)
    write_control_file()
    kappa_shengbte = run_shengbte()

    print()
    print("=" * 78)
    print(f"phono3py kappa(RTA, 2x2x2): {kappa_phono3py:.3f} W/m/K")
    print(f"ShengBTE  kappa(RTA, 2x2x2): {kappa_shengbte:.3f} W/m/K  (factor={_FC3_PHONO3PY_TO_SHENGBTE})")
    ratio = kappa_shengbte / kappa_phono3py if kappa_phono3py > 0 else float("inf")
    print(f"ratio: {ratio:.3f}")
    print("=" * 78)

    # Reference (3x3x3 run): both codes give kappa ~ 15-17 W/m/K, ratio ~ 1.0
    if 0.7 < ratio < 1.3:
        print(
            "VERDICT: 0.1 factor holds on 2x2x2 (ratio within +/-30 %) — "
            "consistent with a code-pair convention difference."
        )
    else:
        print(
            "VERDICT: 0.1 factor does NOT hold on 2x2x2 — converter has a "
            "per-supercell-size scaling bug to investigate."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
