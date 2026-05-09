# Silicon-Tersoff experiment

First end-to-end cross-code run for the openmaterials-ai project. Both kaldo and
phonopy produce the harmonic phonon dispersion of silicon, starting from a shared
ASE seed and the same Tersoff potential. Outputs are written to
`../../runs/silicon_tersoff/` (gitignored).

## Files

- `seed.py` — single source of truth: Si Atoms (diamond, 2-atom primitive),
  ASE-LAMMPS-Tersoff calculator, supercell / k-mesh / FD-displacement choices.
- `run_kaldo.py` — kaldo path. FC2 + FC3 via finite difference, dispersion,
  thermal conductivity (RTA + direct inversion).
- `run_phonopy.py` — phonopy path. Harmonic only: FC2 + dispersion.
- `run_phono3py.py` — phono3py path. FC2 + FC3 via symmetry-reduced
  displacements, RTA + LBTE thermal conductivity.
- `compare.py` — loads kaldo/phonopy/phono3py runs, aligns q-points,
  computes dispersion frequency differences and kappa ratios.
- `Si.tersoff` — Tersoff parameter file (copy of LAMMPS distribution's).

## Running

The kaldo conda env contains all required packages:

```bash
conda activate kaldo
CUDA_VISIBLE_DEVICES="" python seed.py            # smoke test
CUDA_VISIBLE_DEVICES="" python run_kaldo.py       # FC2+FC3+dispersion+kappa
CUDA_VISIBLE_DEVICES="" python run_phonopy.py     # FC2+dispersion (harmonic only)
CUDA_VISIBLE_DEVICES="" python run_phono3py.py    # FC2+FC3+kappa
python compare.py                                  # cross-code summary
```

`CUDA_VISIBLE_DEVICES=""` is required because kaldo imports TensorFlow which
attempts CUDA initialization; the workstation's CUDA context is unavailable
in this conda env.

## Discretization choices (in `seed.py`)

- Lattice constant: 5.431 Å (experimental, not Tersoff-relaxed)
- 2nd-order FC supercell: 4×4×4
- k/q-mesh: 8×8×8 Gamma-centered
- FD displacement: 0.01 Å (phonopy default, also passed to kaldo's
  `delta_shift`)

## Reference numbers

For Si Tersoff at the chosen discretization (4×4×4 FC2 supercell,
3×3×3 FC3 supercell, 8×8×8 q-mesh, 300 K):

- Cohesive energy: 4.63 eV/atom
- Highest LO frequency (Γ): 16.66 THz
- Acoustic frequencies at Γ: ≈0 (within numerical precision)
- Cross-code dispersion |Δω| (after q-grid alignment): max 1.2×10⁻³ THz,
  mean 5×10⁻⁴ THz
- Thermal conductivity (avg of xx/yy/zz):

| Scheme | kaldo | phono3py | kaldo / phono3py |
|---|---|---|---|
| RTA | 15.76 | 17.48 | 0.902 |
| Direct (kaldo "inverse" / phono3py "LBTE") | 19.69 | 21.89 | 0.900 |

The ~10% kaldo↔phono3py difference is consistent across schemes, most
plausibly attributable to the broadening choice on the scattering-rates
operation: kaldo defaults to Gaussian, phono3py to tetrahedron. The ~1.25
RTA-to-direct ratio in both codes confirms internal physics consistency.

These κ values are well below the published Si Tersoff value (~250 W/m·K)
because of mesh under-convergence (literature uses 16×16×16+). Both codes
are equally under-converged at 8×8×8; the cross-code ratio is meaningful,
the absolute value is not.

## Known cross-code differences exposed by this run

1. **Default q-mesh shift convention**. Phonopy defaults to a Monkhorst-Pack
   shift; kaldo defaults to Gamma-centered. We force phonopy to
   Gamma-centered (`is_gamma_center=True`) for direct comparison. Without
   the override, the q-point grids do not align.
2. **FD method internals**. kaldo uses central differences atom-by-atom on the
   replicated supercell; phonopy applies its symmetry analysis to reduce to a
   minimal displacement set (1 displacement for diamond Si in this cell). Both
   reproduce the same FC2 to within ~10⁻³ THz in the dispersion.

## What this experiment does NOT yet exercise

- Aligned broadening across codes. Each runs with its default choice. The
  ~10% kappa discrepancy is the substrate-relevant signal here. Aligning
  broadening (e.g., both Gaussian with the same sigma) should close the gap
  and is the natural next discriminative test.
- Acoustic-sum-rule enforcement. Both codes ran with their respective
  defaults (kaldo: off; phonopy/phono3py: on internally during FC
  production).
- Mesh convergence. 8×8×8 is too coarse for absolute-κ comparison with
  literature; we check cross-code agreement at fixed (small) mesh.
- Isotopic scattering. Both runs used `is_isotope=False`.
- Cross-code substrate adapters. Outputs are saved as plain numpy arrays
  in `runs/`; wrapping them as substrate `Materialization` objects is the
  next architectural step.
