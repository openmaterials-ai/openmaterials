# Silicon-Tersoff experiment

First end-to-end cross-code run for the openmaterials-ai project. Both kaldo and
phonopy produce the harmonic phonon dispersion of silicon, starting from a shared
ASE seed and the same Tersoff potential. Outputs are written to
`../../runs/silicon_tersoff/` (gitignored).

## Files

- `seed.py` — single source of truth: Si Atoms (diamond, 2-atom primitive),
  ASE-LAMMPS-Tersoff calculator, supercell / k-mesh / FD-displacement choices.
- `run_kaldo.py` — kaldo path. Computes FC2 via finite difference using the
  ASE calculator, then dispersion.
- `run_phonopy.py` — phonopy path. Generates symmetry-reduced displaced
  supercells, computes forces with the same calculator, assembles FC2,
  computes dispersion on the same Gamma-centered grid as kaldo.
- `compare.py` — loads both runs, aligns q-points, computes frequency
  differences sorted within each q.
- `Si.tersoff` — Tersoff parameter file (copy of LAMMPS distribution's).

## Running

The kaldo conda env contains all required packages:

```bash
conda activate kaldo
CUDA_VISIBLE_DEVICES="" python seed.py        # smoke test
CUDA_VISIBLE_DEVICES="" python run_kaldo.py
CUDA_VISIBLE_DEVICES="" python run_phonopy.py
python compare.py
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

For Si Tersoff at the chosen discretization (4×4×4 supercell, 8×8×8 mesh):

- Cohesive energy: 4.63 eV/atom
- Highest LO frequency (Γ): 16.66 THz
- Acoustic frequencies at Γ: ≈0 (within numerical precision)
- Cross-code |Δω| (after q-point alignment): max 1.2×10⁻³ THz, mean 5×10⁻⁴ THz

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

- 3rd-order force constants (FC3) and thermal conductivity. Adding these
  requires phono3py and kaldo's `forceconstants.third.calculate(...)`.
- Acoustic-sum-rule enforcement. Both codes ran with their respective defaults
  (kaldo: off; phonopy: on internally during FC production).
- Cross-code substrate adapters. Outputs are saved as plain numpy arrays in
  `runs/`; wrapping them as substrate `Materialization` objects is the next step.
