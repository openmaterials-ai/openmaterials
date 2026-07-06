# QE phonon-DFPT slice: scan report

Scan of the vendored Quantum ESPRESSO source (`q-e/`, version 7.5 per
`include/qe_version.h`; the helpdoc-generated `PHonon/Doc/INPUT_*.txt` files
were built at 7.4). Companion catalog: `scans/qe-phonon.json` (33 entries).

## What the slice covers

The chain `pw.x -> ph.x -> q2r.x -> matdyn.x`, restricted to the quantities
that feed or realize the thermal-transport DAG:

- **pw.x** (12 entries): the structural inputs (cell, positions,
  species/masses, pseudopotentials, cutoffs, k-grid) and the SCF outputs the
  DFPT stage consumes: total energy, forces, stress on stdout/XML, and the
  converged charge density (`charge-density.dat`) plus Kohn-Sham
  wavefunctions (`wfc*.dat`) in `prefix.save/`, which are the implicit input
  state of `ph.x` (read via `read_file_ph`, `PHonon/PH/phq_readin.f90:741`).
- **ph.x** (10 entries): the DFPT products: dynamical-matrix files
  (`fildyn0..N`, text and XML), exact-q phonon frequencies, per-mode
  displacement patterns, Born effective charges by both routes (`zeu` = dF/dE,
  `zue` = dP/du), the macroscopic dielectric tensor, the q-grid machinery
  (`ldisp`, `nq1..3`), and the `fildvscf` response-potential file.
- **q2r.x** (2 entries): the real-space FC2 file (`flfrc`) and the `zasr`
  Born-charge sum rule.
- **matdyn.x** (9 entries): interpolated dispersions (`matdyn.freq`, `.gp`),
  phonon DOS with atom-projected columns (`matdyn.dos`), displacement/
  eigenvector files (`flvec` vs `fleig`), the interpolated dynamical matrix
  (`fldyn`), the FC acoustic sum rule (`asr`), the q-path input, and the NAC
  q->0 handling (note-level entry per scope).
- **FC3** (1 note-only entry): not produced in-tree; external
  `thirdorder.py` (finite differences over pw.x forces) or `D3Q`
  (per `PHonon/Doc/user_guide.tex:119`).

Out of scope, as instructed: bands/EOS/spectroscopy (lraman/elop are noted
only where they share flags with epsil), `dynmat.x` post-processing, EPW.

## The five most consequential convention traps

1. **"Dynamical Matrix" files do not contain the dynamical matrix.**
   Both `fildyn` blocks and `flfrc` store the raw force constants C(q)/C(R)
   in Ry/bohr^2, with no mass weighting and no NAC. Mass division happens
   only at diagonalization time, by `amu_ry*sqrt(m_a*m_b)`
   (`PHonon/PH/dyndia.f90:74`, `PHonon/PH/rigid.f90:452`). The catalog's
   `DynamicalMatrix` node is defined as the mass-weighted matrix with
   omega^2 eigenvalues, so a declared `mass_weighting=none` normalization is
   mandatory on the QE representation, otherwise every element is off by a
   factor of order 10^5 (amu_ry = 911.44 per amu).

2. **Mass units flip with the file format.** Text dyn files and text `flfrc`
   store masses in Rydberg atomic units (amu x 911.444, `AMU_RY = AMU_AU/2`,
   `Modules/constants.f90:57`; write at `io_dyn_mat_old.f90:78`, read-side
   division at `matdyn.f90:965`). The XML dyn/IFC files store plain amu
   (`io_dyn_mat.f90:95`; XML read path uses them undivided,
   `matdyn.f90:366`). All input namelists take amu. Any parser that treats
   the two formats alike gets masses wrong by 911x.

3. **For polar solids, `flfrc` is short-range only.** `q2r.x` subtracts the
   Gonze rigid-ion dipole-dipole term from C(q) before the FFT
   (`rgd_blk(..., -1.d0)`, `PHonon/PH/do_q2r.f90:260`), and `matdyn.x` adds
   it back analytically at every q (`+1.d0`, `matdyn.f90:1280`) plus the
   `nonanal` q->0 limit (`rigid.f90:305`, formula
   4pi e^2 (q.Z*a)(q.Z*b)/(q.eps.q)/Omega, Gonze PRB 50, 13035 (1994)).
   Ingesting `flfrc` as the total FC2 (e.g. comparing to phonopy's
   FORCE_CONSTANTS) is wrong whenever Z* != 0. The `write_lr`/`read_lr`
   column and the `alph` Ewald parameter in the header are part of this
   contract.

4. **QE frequencies are linear, and negative means imaginary.**
   `RY_TO_THZ = 1/AU_PS/(4pi)` (`Modules/constants.f90:116`) converts
   sqrt(w2) in Ry to nu in THz (not omega in rad/ps); cm-1 likewise
   (`RY_TO_CMM1 = 109737.57`). An unstable mode (omega^2 < 0) is printed as
   a negative frequency (`dyndia.f90:92`, `matdyn.f90:769`). Also note the
   unit split across artifacts: ph.x prints THz and cm-1 pairs; matdyn.freq
   and matdyn.dos are cm-1 only.

5. **Stdout Ry vs XML Hartree in pw.x, and two Born-charge layouts in
   ph.x.** Total energy, forces, and stress are Ry-based on stdout
   (`electrons.f90:1758`, `forces.f90:345` "Ry/au", `stress.f90:264`
   "Ry/bohr**3" next to kbar) but divided by e2=2 into Hartree units in
   `data-file-schema.xml` (`pw_restart_new.f90:728`,
   `qexsd_init.f90:1366,1394`). Separately, the dyn file stores
   `Z_{alpha}{s,beta}` with the E-field index first (zeu route,
   `write_epsilon_and_zeu.f90:40`), while the `zue` (dP/du) stdout block is
   stored transposed (`summarize.f90:144`, `zstarue(ipol,na,jpol)`); the file
   values carry no ASR (that is `q2r`'s `zasr` or matdyn's job).

Runner-up: all positions/q-vectors in dyn and flfrc files are cartesian in
alat / 2pi-per-alat units with alat = celldm(1) in bohr; crystal-coordinate
inputs are converted on read.

## Existing map nodes QE grounds

QE plugs in upstream of the thermal DAG exactly as expected: it produces the
leaves the DAG currently takes as given.

| Catalog node | QE grounding (entry) |
|---|---|
| `ForceConstants[order=2]` | `real-space-ifc-file` (flfrc, Ry/bohr^2, short-range for polar) |
| `BornCharges` | `born-effective-charges-zeu` and `-zue` (two routes, units of e) |
| `DielectricTensor` | `dielectric-tensor-eps-inf` (dimensionless, clamped-ion) |
| `BareDynamicalMatrix` | `dynamical-matrix-file` (C(q), pre-NAC, un-mass-weighted) |
| `DynamicalMatrix` | `interpolated-dynamical-matrix` (fldyn, NAC included) and the `nac-loto-splitting` edge realization |
| `Frequency` | `phonon-frequencies-at-q` (exact DFPT) and `interpolated-phonon-frequencies` (two distinct producing operations) |
| `PhononDOS` | `phonon-dos` (states/cm-1, integral = 3*nat, matches catalog normalization) |
| `Eigenvectors` (hidden) | `phonon-displacement-patterns-at-q`, `normalized-phonon-displacements` (flvec), `phonon-eigenvectors` (fleig); QE materializes the displacement-vs-eigenvector normalization split as two separate files |
| `AtomicMass` | ATOMIC_SPECIES plus the ph.x and matdyn.x `amass` overrides |
| `Potential` | pseudopotentials + XC as the provenance of the opaque Potential label |
| `ForceConstants[order=3]` | note-only: QE supplies forces to external thirdorder.py/D3Q |
| `CellVolume` | derivable from `cell-parameters` (flagged unclear: QE consumes full lattice vectors) |

18 of 33 entries map to existing nodes; 12 distinct nodes are grounded.

## Genuinely NEW node candidates (7)

Quantities QE emits/consumes that have no catalog counterpart:

- `atomic-positions` (a CrystalStructure/AtomicPositions source node),
- `scf-total-energy` (Ry stdout / Hartree XML),
- `atomic-forces` (Ry/bohr; the input of every finite-displacement FC route,
  so it matters for provenance even inside the existing DAG),
- `stress-tensor` (Ry/bohr^3 + kbar),
- `scf-charge-density` (hidden; DFPT reference state),
- `kohn-sham-wavefunctions` (hidden; band-phase gauge freedom),
- `dvscf-response-potential` (hidden; electron-phonon scaffolding).

The remaining 8 entries are scheme/discretization parameters (cutoff,
k-grid, q-grid, dyn0 bookkeeping, zasr, asr, q-path, cell-parameter form)
that belong in `scheme_overrides`/`discretization_choices` on the producing
edges rather than as Spaces; they are marked `unclear` with that note.

## Open questions

Carried verbatim in the JSON `open_questions` field:

1. `fildvscf` per-record normalization (irrep-pattern basis scaling) not
   traced to the write site; EPW's reader is the authoritative decoder.
2. The 4th column (`wq`) of `matdyn.freq` in band-path mode: written
   unconditionally at `matdyn.f90:778`, initialization off the DOS grid not
   fully traced (older reference outputs lack the column entirely).
3. PhononDOS normalization (integral = 3*nat) verified from docs and weight
   structure, not numerically.
4. Which QE `asr` flavor matches phonopy's default FC symmetrization
   (needed before EXPECTED_AGREE on near-Gamma acoustics).
5. XML-vs-text dyn selection rules (`xmldyn`) beyond the documented
   noncollinear/spin-orbit case.
6. `matdyn.x` can run q2r internally when given `fildyn` directly
   (`matdyn.f90:347`); treated as an alias of q2r.x, not a separate producer.
7. Stress sign convention unverified against a strained reference.

## Worked example anchor

`q-e/PHonon/examples/example02` (AlAs, 4x4x4 q-grid) exercises the whole
slice and its reference outputs pin concrete values: eps_inf = 13.742,
Z*(Al) = +1.88 e, Gamma TO = 375.52 cm-1 and LO = 410.56 cm-1 (the LO-TO
split appearing only after matdyn applies the NAC), artifacts
`alas.dyn0..8`, `alas444.fc`, `alas.freq`, `alas.phdos`, `matdyn.modes`.
