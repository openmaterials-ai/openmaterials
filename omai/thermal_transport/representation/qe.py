"""Quantum ESPRESSO adapter specs for the thermal-transport DAG.

QE grounds the SOURCE tier of the DAG: where kaldo / phono3py / ShengBTE
consume force constants, Born charges, and dielectric tensors as given,
QE is the code that produces them from first principles (DFPT linear
response). The mapped chain is pw.x (SCF) -> ph.x (DFPT at q; Z*, eps_inf
at q=0) -> q2r.x (real-space FC2) -> matdyn.x (interpolation, NAC,
frequencies, DOS, eigenvectors).

Derived from the scan catalog `scans/qe-phonon.json` (QE 7.5, every entry
anchored to file:line in the vendored q-e/ tree). Output-file mapping:

  operator Space              QE artifact                        program
  --------------------------  ---------------------------------  --------
  Potential                   pseudo_dir/*.UPF + input_dft        pw.x
  ForceConstants[order=2]     flfrc (e.g. alas444.fc)             q2r.x
  BareDynamicalMatrix         fildyn{N} text / .xml               ph.x
  DynamicalMatrix             fldyn (matdyn; NAC applied)         matdyn.x
  Frequency                   fildyn tail; flfrq (matdyn.freq)    ph.x/matdyn.x
  Eigenvectors                fleig (orthonormal); flvec          matdyn.x
  BornCharges                 q=0 fildyn 'Effective Charges E-U'  ph.x
  DielectricTensor            q=0 fildyn 'Dielectric Tensor'      ph.x
  PhononDOS                   fldos (matdyn.dos)                  matdyn.x

Convention traps this module pins down (see scans/qe-phonon.md for the
full list with source anchors):

  * QE "dynamical matrix" files hold RAW force constants at q, in
    Ry/bohr^2: never mass-weighted, and (in fildyn) never NAC-corrected.
    Mass division by amu_ry*sqrt(m_a m_b) happens only at diagonalization
    (PHonon/PH/dyndia.f90:74, rigid.f90:452). The operator-layer
    DynamicalMatrix is the mass-weighted frequency^2 form, so per-element
    comparison against another code requires applying the mass weighting
    first; the specs below record that as a note rather than pretending a
    scalar unit factor exists.
  * Mass units flip with file format: text dyn/flfrc store amu*911.444
    (Rydberg atomic mass units, io_dyn_mat_old.f90:78, matdyn.f90:965);
    the XML variants store plain amu (io_dyn_mat.f90:95); input namelists
    take amu.
  * For polar solids flfrc is SHORT-RANGE ONLY: q2r subtracts the Gonze
    dipole-dipole term (do_q2r.f90:260) and matdyn re-adds it
    (matdyn.f90:1280) plus the q->0 non-analytic term. Comparing flfrc to
    a phonopy FORCE_CONSTANTS file verbatim is wrong whenever Z* != 0.
  * Frequencies are LINEAR (nu, not omega): ph.x prints THz and cm^-1
    side by side; matdyn.freq is cm^-1 only. Negative value = imaginary
    mode (omega^2 < 0).

FC3 is out of QE's tree (thirdorder.py / D3Q produce it); the FC3 node
stays grounded by the phono3py / ShengBTE adapters. Heat capacity, group
velocities, linewidths, and kappa are not produced by this slice: the
BTE-solving codes consume QE's outputs and produce those downstream.
"""

from __future__ import annotations

from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator.edges import (
    apply_nac_correction,
    compute_dispersion,
    compute_dos,
    compute_dynamical_matrix,
    compute_force_constants_2,
    provide_born_charges,
    provide_dielectric_tensor,
)
from omai.thermal_transport.operator.nodes import (
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FREQUENCY_STATE,
    PHONON_DOS,
    POTENTIAL,
)


QE_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="qe",
    code_api={"potential": "&SYSTEM input_dft + ATOMIC_SPECIES pseudopotentials"},
    notes=(
        "First-principles Born-Oppenheimer potential, parameterized by the "
        "pseudopotentials (UPF files in pseudo_dir), the XC functional "
        "(input_dft, else read from the UPFs), and the plane-wave cutoffs "
        "(ecutwfc/ecutrho). These four are the provenance a provide_potential "
        "instance must record for a QE-grounded run; two runs differing in "
        "any of them realize different Potentials."
    ),
)


QE_FORCE_CONSTANTS_2 = SpaceRepresentationSpec(
    space=FORCE_CONSTANTS_2,
    representation_name="qe",
    observable_units={"phi": "Ry_per_bohr2"},
    code_api={"phi": "q2r.x flfrc (text or .xml)"},
    notes=(
        "Real-space interatomic force constants from q2r.x, in Ry/bohr^2 "
        "(Rydberg atomic units; no unit string appears in the file). "
        "1 Ry/bohr^2 = 48.587 eV/A^2 vs the eV/A^2 codes (kaldo, phonopy, "
        "phono3py). Two traps: (1) for polar solids (lrigid=T) the file is "
        "short-range only, the Gonze dipole term having been subtracted at "
        "do_q2r.f90:260 and re-added by matdyn.f90:1280, so verbatim "
        "comparison against phonopy FORCE_CONSTANTS is wrong when Z* != 0; "
        "(2) the text format stores masses in Rydberg atomic mass units "
        "(amu*911.444), the XML format in plain amu."
    ),
)


QE_BARE_DYNAMICAL_MATRIX = SpaceRepresentationSpec(
    space=BARE_DYNAMICAL_MATRIX,
    representation_name="qe",
    code_api={"D_bare": "ph.x fildyn{N} (text) / fildyn{N}.xml"},
    notes=(
        "ph.x dynamical-matrix files at each computed q. Contents are the "
        "RAW force-constant matrices C(q) in Ry/bohr^2: NOT mass-weighted "
        "(division by amu_ry*sqrt(m_a m_b) happens only at diagonalization, "
        "dyndia.f90:74) and with NO non-analytic q->0 term (Z* and eps_inf "
        "are stored separately in the q=0 file). Matches the "
        "BareDynamicalMatrix node modulo the mass-weighting convention, "
        "which is structural (per-element matrix transform), not a scalar "
        "unit factor; hence no per-element unit declared here."
    ),
)


QE_DYNAMICAL_MATRIX = SpaceRepresentationSpec(
    space=DYNAMICAL_MATRIX,
    representation_name="qe",
    code_api={"D": "matdyn.x fldyn (off by default)"},
    notes=(
        "Interpolated dynamical matrix with the NAC/LO-TO handling applied "
        "(matdyn re-adds the Gonze dipole term and the q->0 non-analytic "
        "correction). Same write_dyn_on_file format as ph.x fildyn: "
        "un-mass-weighted C(q) in Ry/bohr^2, so the same structural "
        "mass-weighting note as BareDynamicalMatrix applies."
    ),
)


QE_FREQUENCY = SpaceRepresentationSpec(
    space=FREQUENCY_STATE,
    representation_name="qe",
    observable_units={"omega": "inverse_cm"},
    code_api={"omega": "matdyn.x flfrq (matdyn.freq); ph.x fildyn tail"},
    notes=(
        "Linear wavenumbers (nu = omega/2pi as a wavenumber), cm^-1 in "
        "matdyn.freq; ph.x prints THz and cm^-1 side by side "
        "('freq (i) = x [THz] = y [cm-1]', both LINEAR frequency). "
        "RY_TO_THZ = 3289.842, RY_TO_CMM1 = 109737.57. A negative value "
        "encodes an imaginary mode (omega^2 < 0)."
    ),
)


QE_EIGENVECTORS = SpaceRepresentationSpec(
    space=EIGENVECTORS,
    representation_name="qe",
    observable_units={"e": "dimensionless"},
    code_api={"e": "matdyn.x fleig (orthonormal; off by default)"},
    notes=(
        "fleig holds the orthonormal eigenvectors of the mass-weighted "
        "dynamical matrix: the node's canonical content. Beware the two "
        "sibling artifacts holding DISPLACEMENT PATTERNS instead: the tail "
        "of ph.x fildyn and matdyn.x flvec (matdyn.modes, on by default) "
        "are mass-divided and renormalized, differing per component by "
        "sqrt(amu_ry*m); they are not mutually orthogonal. HiddenSpace: "
        "per-element values carry U(1) phase and degenerate-subspace "
        "rotation freedom regardless of artifact."
    ),
)


QE_BORN_CHARGES = SpaceRepresentationSpec(
    space=BORN_CHARGES,
    representation_name="qe",
    observable_units={"Z_star": "dimensionless"},
    code_api={"Z_star": "ph.x q=0 fildyn 'Effective Charges E-U' (epsil=.true.)"},
    notes=(
        "Born effective charges in units of e, from DFPT (zeu = dF/dE "
        "route, written to the q=0 dyn file and XML ZSTAR tag; the "
        "transposed zue = dP/du route appears in stdout only, and "
        "cross-checking the two is an internal EXPECTED_AGREE pair). Index "
        "order in the file is (E-field alpha, atom s, displacement beta). "
        "No acoustic sum rule is applied in the file (zasr comes later, in "
        "q2r/matdyn). This is typically the very output a phonopy BORN "
        "file is built from."
    ),
)


QE_DIELECTRIC_TENSOR = SpaceRepresentationSpec(
    space=DIELECTRIC_TENSOR,
    representation_name="qe",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={"epsilon_infinity": "ph.x q=0 fildyn 'Dielectric Tensor' (epsil=.true.)"},
    notes=(
        "High-frequency (electronic) dielectric tensor eps_inf from DFPT, "
        "dimensionless; insulators only (ph.x stops on metallic "
        "occupations). This is eps_inf, not the static eps_0."
    ),
)


QE_PHONON_DOS = SpaceRepresentationSpec(
    space=PHONON_DOS,
    representation_name="qe",
    code_api={"g": "matdyn.x fldos (matdyn.dos), dos=.true."},
    notes=(
        "Phonon DOS in states/cm^-1 per unit cell against an omega axis in "
        "cm^-1, normalized so the integral is 3*nat: the same normalization "
        "as the operator-layer node (1/N_q sum of delta functions). "
        "Tetrahedron method by default; Gaussian broadening if degauss>0 "
        "(degauss itself in cm^-1). Axis-unit conversion to the canonical "
        "linear-THz axis is inverse_cm's factor; the DOS ordinate then "
        "scales inversely (states per unit frequency)."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how QE performs the operations)
# ---------------------------------------------------------------------------

QE_COMPUTE_FORCE_CONSTANTS_2 = OperatorRepresentationSpec(
    operator=compute_force_constants_2,
    representation_name="qe",
    scheme_overrides={"symmetry_group": "qe_spacegroup"},
    discretization_choices={
        "method": "dfpt_linear_response",
        "q_sampling": "regular nq1 x nq2 x nq3 grid (ldisp=.true.)",
        "acoustic_sum_rule": "zasr/asr applied downstream in q2r/matdyn, not in ph.x",
    },
    notes=(
        "QE computes FC2 by DFPT linear response on a regular q grid "
        "(ph.x), then Fourier-transforms to real space (q2r.x): no "
        "supercell finite displacements. Symmetry reduction uses QE's "
        "internal space-group machinery (not spglib); irreducible q set "
        "and irreducible perturbations per q."
    ),
)


QE_COMPUTE_DYNAMICAL_MATRIX = OperatorRepresentationSpec(
    operator=compute_dynamical_matrix,
    representation_name="qe",
    discretization_choices={
        "interpolation": "Fourier interpolation of flfrc (matdyn.x); exact at ph.x grid q's",
    },
    notes=(
        "At grid q's ph.x provides D(q) directly; off-grid q's come from "
        "Fourier interpolation of the real-space constants in matdyn.x."
    ),
)


QE_APPLY_NAC_CORRECTION = OperatorRepresentationSpec(
    operator=apply_nac_correction,
    representation_name="qe",
    scheme_overrides={},  # canonical nac_scheme=gonze_lee
    discretization_choices={
        "gamma_treatment": "direction-dependent nonanal term at q->0 (path geometry decides the limit direction)",
    },
    notes=(
        "matdyn.x implements the canonical Gonze dipole-dipole NAC "
        "(nac_scheme=gonze_lee, matdyn.f90:1280 re-adds what do_q2r.f90:260 "
        "subtracted; e^2=2 in Rydberg units internally, cancelling in the "
        "result). At Gamma the correction is direction-dependent: the value "
        "depends on the approach path."
    ),
)


QE_COMPUTE_DISPERSION = OperatorRepresentationSpec(
    operator=compute_dispersion,
    representation_name="qe",
    discretization_choices={
        "mass_weighting": "applied at diagonalization only (dyndia.f90:74; amu_ry*sqrt(m_a m_b))",
        "diagonalizer": "LAPACK Hermitian solve (cdiagh)",
    },
    notes=(
        "Diagonalization of the mass-weighted C(q); frequencies emitted as "
        "linear nu in THz and cm^-1. All stored matrices remain "
        "un-mass-weighted; the weighting exists only inside the "
        "diagonalization step."
    ),
)


QE_COMPUTE_DOS = OperatorRepresentationSpec(
    operator=compute_dos,
    representation_name="qe",
    discretization_choices={
        "integration": "tetrahedron by default; Gaussian if degauss > 0 (degauss in cm^-1)",
        "grid": "nk1 x nk2 x nk3 interpolation grid in matdyn.x",
    },
    notes="matdyn.x dos=.true.; normalization integral = 3*nat per cell.",
)


QE_PROVIDE_BORN_CHARGES = OperatorRepresentationSpec(
    operator=provide_born_charges,
    representation_name="qe",
    discretization_choices={"origin": "computed by DFPT (epsil=.true.), not provided"},
    notes=(
        "QE turns the provide_born_charges source edge into a computed "
        "quantity: Z* comes out of the same DFPT run as the dynamical "
        "matrix, rather than being supplied by the user."
    ),
)


QE_PROVIDE_DIELECTRIC_TENSOR = OperatorRepresentationSpec(
    operator=provide_dielectric_tensor,
    representation_name="qe",
    discretization_choices={"origin": "computed by DFPT (epsil=.true.), not provided"},
    notes="Same DFPT run computes eps_inf; see QE_PROVIDE_BORN_CHARGES.",
)
