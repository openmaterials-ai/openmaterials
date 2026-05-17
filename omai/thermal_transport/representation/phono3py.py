"""phono3py adapter specs for the thermal-transport DAG.

Constructed against the operator DAG in
`omai.thermal_transport.operator`. Cross-code comparison happens at the
operator level (Principle 7) via the shared states; differences
surface as unit factors, convention mismatches, and discretization choice
mismatches.

References to the phono3py API (https://phonopy.github.io/phono3py/):
  * thermal_conductivity.gamma                 — Gamma_qν in linear THz
  * thermal_conductivity.mode_heat_capacities  — c_qν(T) in eV/K
  * Phono3py.sigmas[0]                          — Gaussian stdev, linear THz
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import (
    apply_nac_correction,
    combine_kappa_wigner,
    compute_boundary_scattering,
    compute_dispersion,
    compute_dos,
    compute_dynamical_matrix,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_group_velocity,
    compute_gruneisen,
    compute_heat_capacity,
    compute_isotope_scattering,
    compute_kappa_wigner_coherences,
    compute_kappa_wigner_populations,
    compute_linewidth,
    compute_phase_space_3phonon,
    contract_kappa_direct,
    contract_kappa_rta,
    contract_molar_heat_capacity,
    contract_volumetric_heat_capacity,
    identity_dm,
    provide_born_charges,
    provide_dielectric_tensor,
    provide_isotope_abundances,
    provide_potential,
    provide_temperature,
    solve_bte_direct,
    solve_bte_rta,
    sum_linewidths,
)
from omai.thermal_transport.operator.nodes import (
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    BOUNDARY_LINEWIDTH,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    GRUNEISEN,
    HEAT_CAPACITY,
    ISOTOPE_ABUNDANCES,
    ISOTOPIC_LINEWIDTH,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    MOLAR_HEAT_CAPACITY,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_WIGNER,
    THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    TOTAL_LINEWIDTH,
    VOLUMETRIC_HEAT_CAPACITY,
)


PHONO3PY_FREQUENCY = StateAdapterSpec(
    state=FREQUENCY_STATE,
    adapter_name="phono3py",
    observable_units={"omega": "linear_THz"},
    code_api={"omega": "thermal_conductivity.frequencies"},
    notes="thermal_conductivity.frequencies in linear THz, shape (n_q, n_modes).",
)


PHONO3PY_GROUP_VELOCITY = StateAdapterSpec(
    state=GROUP_VELOCITY,
    adapter_name="phono3py",
    observable_units={"v": "angstrom_linear_THz"},
    code_api={"v": "thermal_conductivity.group_velocities"},
    notes="thermal_conductivity.group_velocities in Å·THz, shape (n_q, n_modes, 3).",
)


PHONO3PY_LINEWIDTH = StateAdapterSpec(
    state=LINEWIDTH,
    adapter_name="phono3py",
    observable_units={"Gamma": "linear_THz"},
    # No convention overrides: canonical "imag_self_energy".
    code_api={"Gamma": "thermal_conductivity.gamma"},
    notes=(
        "thermal_conductivity.gamma in linear THz, defined as the imaginary "
        "self-energy Gamma = Im Sigma (no factor of 2)."
    ),
)


PHONO3PY_HEAT_CAPACITY = StateAdapterSpec(
    state=HEAT_CAPACITY,
    adapter_name="phono3py",
    observable_units={"c": "eV_per_K"},
    code_api={"c": "thermal_conductivity.mode_heat_capacities"},
    notes="thermal_conductivity.mode_heat_capacities in eV/K per mode.",
)


PHONO3PY_THERMAL_CONDUCTIVITY_RTA = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_RTA,
    adapter_name="phono3py",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "run_thermal_conductivity(is_LBTE=False).kappa"},
    notes=(
        "run_thermal_conductivity(is_LBTE=False) yields kappa in W/(m·K), "
        "Voigt-tensor shape; xx/yy/zz are the first three components."
    ),
)


PHONO3PY_THERMAL_CONDUCTIVITY_DIRECT = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_DIRECT,
    adapter_name="phono3py",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "run_thermal_conductivity(is_LBTE=True).kappa"},
    notes=(
        "run_thermal_conductivity(is_LBTE=True) yields kappa in W/(m·K). "
        "phono3py's `is_LBTE=True` realizes the operator layer's canonical "
        "bte_solver=direct_inverse."
    ),
)


PHONO3PY_COMPUTE_LINEWIDTH = OperationAdapterSpec(
    operation=compute_linewidth,
    adapter_name="phono3py",
    parameter_units={"broadening_sigma": "linear_THz"},
    algorithmic_convention_overrides={
        # canonical broadening_param=stdev (no override).
        # phono3py calls spglib on the input structure and runs the BZ sum
        # on the irreducible wedge, unfolding via the resulting weights.
        "symmetry_group": "spglib_auto",
    },
    discretization_choices={
        "bz_summation": "symmetry_reduced",
        "delta_cutoff_sigmas": "infinity",
        "degeneracy_averaging": "on",
    },
    notes=(
        "Iterates symmetry-reduced triplets with explicit weights. "
        "ph3.sigmas[0] is the Gaussian stdev. Default no cutoff. "
        "average_by_degeneracy applied post-hoc to the per-mode Gamma."
    ),
)


PHONO3PY_COMPUTE_HEAT_CAPACITY = OperationAdapterSpec(
    operation=compute_heat_capacity,
    adapter_name="phono3py",
    notes="No parameters or algorithmic conventions exposed.",
)


PHONO3PY_COMPUTE_FORCE_CONSTANTS_2 = OperationAdapterSpec(
    operation=compute_force_constants_2,
    adapter_name="phono3py",
    algorithmic_convention_overrides={
        # Phono3py.produce_fc2 invokes the symfc / ALM backend, which uses
        # the structure's space group (spglib) to enumerate inequivalent
        # displacements and symmetrize the resulting Φ².
        "symmetry_group": "spglib_auto",
    },
    notes=(
        "Phono3py.generate_displacements + produce_fc2: spglib derives the "
        "irreducible displacement set; Φ² is symmetrized on read-back."
    ),
)


PHONO3PY_COMPUTE_FORCE_CONSTANTS_3 = OperationAdapterSpec(
    operation=compute_force_constants_3,
    adapter_name="phono3py",
    algorithmic_convention_overrides={
        "symmetry_group": "spglib_auto",
    },
    notes=(
        "Phono3py.produce_fc3: irreducible triplets via spglib; Φ³ is "
        "symmetrized over the full space group (rotational + permutation "
        "symmetries) on read-back."
    ),
)


PHONO3PY_SOLVE_BTE_DIRECT = OperationAdapterSpec(
    operation=solve_bte_direct,
    adapter_name="phono3py",
    algorithmic_convention_overrides={
        # is_LBTE=True builds and inverts the collision matrix on the
        # irreducible q-grid; the symmetry-unfolded F is then used to
        # contract κ.
        "symmetry_group": "spglib_auto",
    },
    discretization_choices={
        "collision_matrix_assembly": "irreducible_grid",
        "linear_solver": "lapack_pinv",
    },
    notes=(
        "run_thermal_conductivity(is_LBTE=True, pinv_solver='dsyevd'): "
        "M is built on BZ/G and pseudo-inverted via LAPACK. The output F "
        "is unfolded back to the full grid using the spglib star map."
    ),
)


# ---------------------------------------------------------------------------
# Additional state-adapter specs for states phono3py uses internally.
# Only code_api + notes — observable_units omitted for scaffolding states.
# ---------------------------------------------------------------------------


PHONO3PY_TEMPERATURE = StateAdapterSpec(
    state=TEMPERATURE_STATE,
    adapter_name="phono3py",
    code_api={"temperature": "Phono3py.temperatures"},
    notes="Array of temperatures passed via run_thermal_conductivity(temperatures=[...]).",
)


PHONO3PY_FORCE_CONSTANTS_2 = StateAdapterSpec(
    state=FORCE_CONSTANTS_2,
    adapter_name="phono3py",
    code_api={"phi": "Phono3py.fc2"},
    notes=(
        "Phono3py.fc2: ndarray of shape (n_supercell_atoms, n_supercell_atoms, "
        "3, 3) in eV/Å². Built by Phono3py.produce_fc2()."
    ),
)


PHONO3PY_FORCE_CONSTANTS_3 = StateAdapterSpec(
    state=FORCE_CONSTANTS_3,
    adapter_name="phono3py",
    code_api={"phi": "Phono3py.fc3"},
    notes=(
        "Phono3py.fc3: ndarray of shape (n_supercell_atoms, n_supercell_atoms, "
        "n_supercell_atoms, 3, 3, 3) in eV/Å³. Built by Phono3py.produce_fc3()."
    ),
)


PHONO3PY_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=DYNAMICAL_MATRIX,
    adapter_name="phono3py",
    code_api={"D": "Phono3py.dynamical_matrix"},
    notes=(
        "phono3py builds the DynamicalMatrix object for each q-point internally. "
        "The dynamical_matrix attribute exposes the object; per-q matrices are "
        "obtained by calling .run(q)."
    ),
)


PHONO3PY_EIGENVECTORS = StateAdapterSpec(
    state=EIGENVECTORS,
    adapter_name="phono3py",
    code_api={"e": "thermal_conductivity.get_eigenvectors()"},
    notes=(
        "Eigenvectors of D(q) for each q on the BZ mesh, exposed by the "
        "thermal_conductivity object after run_thermal_conductivity() has "
        "been called. Carries the U(1) phase + degenerate-subspace rotation "
        "freedom — per-element cross-code comparison is NOT_COMPARABLE."
    ),
)


PHONO3PY_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="phono3py",
    code_api={"potential": "Phono3py(...) + ASE calculator or DFT force sets"},
    notes=(
        "phono3py consumes a force source: either an ASE calculator wired "
        "through Phono3py.run_force_calculator(), or precomputed forces "
        "(VASP/ABINIT/QE FORCE_SETS files)."
    ),
)


PHONO3PY_MEAN_FREE_DISPLACEMENT_RTA = StateAdapterSpec(
    state=MEAN_FREE_DISPLACEMENT_RTA,
    adapter_name="phono3py",
    code_api={"F": "thermal_conductivity.mean_free_paths"},
    notes=(
        "After run_thermal_conductivity(is_LBTE=False), the "
        "thermal_conductivity object exposes mean_free_paths (per mode, "
        "RTA closed form v_qν / 2Γ_qν)."
    ),
)


PHONO3PY_MEAN_FREE_DISPLACEMENT_DIRECT = StateAdapterSpec(
    state=MEAN_FREE_DISPLACEMENT_DIRECT,
    adapter_name="phono3py",
    code_api={"F": "thermal_conductivity.f_vectors"},
    notes=(
        "After run_thermal_conductivity(is_LBTE=True), the "
        "thermal_conductivity object holds the F vector from the inverted "
        "collision matrix (used internally to contract κ_LBTE)."
    ),
)


PHONO3PY_VOLUMETRIC_HEAT_CAPACITY = StateAdapterSpec(
    state=VOLUMETRIC_HEAT_CAPACITY,
    adapter_name="phono3py",
    code_api={"C_V_vol": "np.sum(thermal_conductivity.mode_heat_capacities) / (V_cell * n_q)"},
    notes=(
        "Derived: one-line contraction of mode_heat_capacities (eV/K) / "
        "(V_cell × N_q), with eV→J conversion. No native phono3py output."
    ),
)


PHONO3PY_MOLAR_HEAT_CAPACITY = StateAdapterSpec(
    state=MOLAR_HEAT_CAPACITY,
    adapter_name="phono3py",
    code_api={"C_V_mol": "N_A * np.sum(thermal_conductivity.mode_heat_capacities) / n_q"},
    notes=(
        "Derived: one-line contraction of mode_heat_capacities × Avogadro / N_q, "
        "with eV→J unit conversion. No native phono3py output."
    ),
)


PHONO3PY_PHONON_DOS = StateAdapterSpec(
    state=PHONON_DOS,
    adapter_name="phono3py",
    code_api={"g": "Phonopy.get_total_DOS()"},
    notes="DOS via the parent Phonopy object's run_total_dos/get_total_DOS.",
)


PHONO3PY_GRUNEISEN = StateAdapterSpec(
    state=GRUNEISEN,
    adapter_name="phono3py",
    code_api={"gamma_G": "Phono3py.run_phonon_gruneisen_parameters()"},
    notes=(
        "phono3py computes mode Grüneisen via the Maradudin-Fein expression "
        "using fc2 and fc3. Stored on Phono3py.phonon_gruneisen_parameter."
    ),
)


PHONO3PY_PHASE_SPACE_3PH = StateAdapterSpec(
    state=PHASE_SPACE_3PH,
    adapter_name="phono3py",
    code_api={"P3": "Phono3py.run_phonon_phase_space()"},
    notes=(
        "Phono3py.phonon_phase_space contains the per-mode P3 array after "
        "run_phonon_phase_space() is called."
    ),
)


# ---------------------------------------------------------------------------
# Operation-adapter specs for phono3py. As with the kaldo module, trivial
# ops carry no algorithmic conventions and exist only to mark coverage.
# ---------------------------------------------------------------------------


PHONO3PY_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="phono3py",
    notes="Phono3py reads forces from an external DFT/MD code via FORCES_FC* files.",
)


PHONO3PY_PROVIDE_TEMPERATURE = OperationAdapterSpec(
    operation=provide_temperature,
    adapter_name="phono3py",
    notes="Set via Phono3py(temperatures=...).",
)


PHONO3PY_COMPUTE_DYNAMICAL_MATRIX = OperationAdapterSpec(
    operation=compute_dynamical_matrix,
    adapter_name="phono3py",
    notes=(
        "Inherited from the parent Phonopy object: DynamicalMatrix.get_dynamical_matrix() "
        "performs the Bloch sum over Φ²(R)."
    ),
)


PHONO3PY_COMPUTE_DISPERSION = OperationAdapterSpec(
    operation=compute_dispersion,
    adapter_name="phono3py",
    notes=(
        "Frequencies and eigenvectors come from a per-q numpy.linalg.eigh "
        "of the dynamical matrix (Phonopy.get_band_structure / get_mesh_dict). "
        "Degenerate subspaces inherit the arbitrary numpy basis."
    ),
)


PHONO3PY_COMPUTE_GROUP_VELOCITY = OperationAdapterSpec(
    operation=compute_group_velocity,
    adapter_name="phono3py",
    notes=(
        "Phonopy.GroupVelocity uses the analytic Hellmann-Feynman formula "
        "with finite-difference fallback only at exact band crossings."
    ),
)


PHONO3PY_SOLVE_BTE_RTA = OperationAdapterSpec(
    operation=solve_bte_rta,
    adapter_name="phono3py",
    notes=(
        "Phono3py.run_thermal_conductivity(is_LBTE=False): closed-form F = v / (2Γ) "
        "per mode, with kappa accumulated as the BZ sum is built."
    ),
)


PHONO3PY_CONTRACT_KAPPA_RTA = OperationAdapterSpec(
    operation=contract_kappa_rta,
    adapter_name="phono3py",
    notes="kappa_RTA: c·v⊗v·τ summed over (q, ν) and divided by volume.",
)


PHONO3PY_CONTRACT_KAPPA_DIRECT = OperationAdapterSpec(
    operation=contract_kappa_direct,
    adapter_name="phono3py",
    notes="kappa from the LBTE solve, accumulated as c·v⊗F over (q, ν).",
)


PHONO3PY_CONTRACT_VOLUMETRIC_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_volumetric_heat_capacity,
    adapter_name="phono3py",
    notes="Derived from the per-mode heat_capacity array by summing and dividing by cell volume.",
)


PHONO3PY_CONTRACT_MOLAR_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_molar_heat_capacity,
    adapter_name="phono3py",
    notes="Derived from the per-mode heat_capacity array via N_A × sum / N_q.",
)


PHONO3PY_COMPUTE_DOS = OperationAdapterSpec(
    operation=compute_dos,
    adapter_name="phono3py",
    algorithmic_convention_overrides={"dos_broadening": "tetrahedron"},
    notes=(
        "Phonopy.run_total_dos defaults to tetrahedron integration "
        "(is_tetrahedron=True); a Gaussian-broadened mode is available via "
        "the `sigma` argument."
    ),
)


PHONO3PY_COMPUTE_GRUNEISEN = OperationAdapterSpec(
    operation=compute_gruneisen,
    adapter_name="phono3py",
    notes=(
        "Phono3py.run_phonon_gruneisen_parameters: Maradudin-Fein closed form "
        "using fc2, fc3 and the harmonic eigensystem — matches the canonical "
        "gruneisen_method=maradudin_fein."
    ),
)


PHONO3PY_COMPUTE_PHASE_SPACE_3PH = OperationAdapterSpec(
    operation=compute_phase_space_3phonon,
    adapter_name="phono3py",
    notes=(
        "run_phonon_phase_space reuses the linewidth code's δ realisation; "
        "with the default smearing-method runner this is Gaussian, matching "
        "the canonical delta_broadening=gaussian."
    ),
)


# ---------------------------------------------------------------------------
# NAC inherits from phono3py's parent Phonopy object; the API is identical.
# ---------------------------------------------------------------------------


PHONO3PY_BORN_CHARGES = StateAdapterSpec(
    state=BORN_CHARGES,
    adapter_name="phono3py",
    observable_units={"Z_star": "dimensionless"},
    code_api={"Z_star": "Phono3py.nac_params['born']"},
    notes=(
        "Phono3py inherits NAC handling from its parent Phonopy: the Born "
        "charges live on phono3py.nac_params['born'] with shape "
        "(n_atoms_primitive, 3, 3)."
    ),
)


PHONO3PY_BARE_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=BARE_DYNAMICAL_MATRIX,
    adapter_name="phono3py",
    code_api={
        "D_bare": "DynamicalMatrix.get_dynamical_matrix() with NAC disabled"
    },
    notes=(
        "phono3py inherits the dynamical matrix machinery from phonopy: the "
        "bare Bloch sum is what `DynamicalMatrix.get_dynamical_matrix()` "
        "returns when nac_params is None. With NAC enabled the same call "
        "returns the corrected DM (our DynamicalMatrix node)."
    ),
)


PHONO3PY_DIELECTRIC_TENSOR = StateAdapterSpec(
    state=DIELECTRIC_TENSOR,
    adapter_name="phono3py",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={"epsilon_infinity": "Phono3py.nac_params['dielectric']"},
    notes="Phono3py.nac_params['dielectric'], shape (3, 3), inherited from Phonopy.",
)


PHONO3PY_PROVIDE_BORN_CHARGES = OperationAdapterSpec(
    operation=provide_born_charges,
    adapter_name="phono3py",
    notes=(
        "BORN file parsed via the Phonopy parser; attached to Phono3py via "
        "the same nac_params dict."
    ),
)


PHONO3PY_PROVIDE_DIELECTRIC_TENSOR = OperationAdapterSpec(
    operation=provide_dielectric_tensor,
    adapter_name="phono3py",
    notes="Same BORN file, dielectric block.",
)


PHONO3PY_IDENTITY_DM = OperationAdapterSpec(
    operation=identity_dm,
    adapter_name="phono3py",
    notes="Non-polar runs: bare Bloch sum passes through unchanged.",
)


PHONO3PY_APPLY_NAC_CORRECTION = OperationAdapterSpec(
    operation=apply_nac_correction,
    adapter_name="phono3py",
    algorithmic_convention_overrides={"nac_scheme": "gonze_lee"},
    notes=(
        "Polar phono3py runs apply NAC via the inherited Phonopy machinery — "
        "the default nac_method='gonze' is what BORN-using ph3 runs do "
        "out of the box."
    ),
)


# ---------------------------------------------------------------------------
# Linewidth channels. phono3py exposes the anharmonic three-phonon piece via
# `thermal_conductivity.gamma` (already specced as PHONO3PY_LINEWIDTH).
# Tamura isotopic scattering is exposed as `thermal_conductivity.gamma_isotope`
# when isotopes are enabled. Casimir boundary scattering is computed inline
# from `boundary_mfp` (private attribute `_gamma_boundary`); it is folded
# into the effective linewidth via `compute_effective_gamma` but not surfaced
# as a public attribute.
# ---------------------------------------------------------------------------


PHONO3PY_ISOTOPIC_LINEWIDTH = StateAdapterSpec(
    state=ISOTOPIC_LINEWIDTH,
    adapter_name="phono3py",
    observable_units={"Gamma": "linear_THz"},
    # No convention overrides: canonical "imag_self_energy".
    code_api={"Gamma": "thermal_conductivity.gamma_isotope"},
    notes=(
        "thermal_conductivity.gamma_isotope: per-mode Tamura isotopic "
        "linewidth in linear THz, shape (num_sigma, num_gp, num_band0). "
        "Active when --isotope is requested (or set via the API); uses "
        "natural-abundance defaults from atomic-weights when no explicit "
        "mass_variances are provided."
    ),
)


PHONO3PY_BOUNDARY_LINEWIDTH = StateAdapterSpec(
    state=BOUNDARY_LINEWIDTH,
    adapter_name="phono3py",
    observable_units={"Gamma": "linear_THz"},
    code_api={
        "Gamma": "thermal_conductivity._gamma_boundary "
        "(via compute_bulk_boundary_scattering)"
    },
    notes=(
        "phono3py computes Γ_boundary = |v|·1e6·Å / (4π·boundary_mfp) "
        "(boundary_mfp in micrometres) inside `_pre_main_loop`. The array "
        "is stored on the private `_gamma_boundary` attribute and folded "
        "into the effective linewidth via `compute_effective_gamma`; there "
        "is no public property exposing it directly."
    ),
)


PHONO3PY_TOTAL_LINEWIDTH = StateAdapterSpec(
    state=TOTAL_LINEWIDTH,
    adapter_name="phono3py",
    observable_units={"Gamma": "linear_THz"},
    code_api={
        "Gamma": "phono3py.conductivity.grid_point_data.compute_effective_gamma"
    },
    notes=(
        "phono3py's total linewidth that feeds the BTE solve is "
        "computed by `compute_effective_gamma(aggregates)`, which adds "
        "gamma (anharmonic), gamma_isotope, gamma_boundary, and gamma_elph "
        "into a single (num_sigma, num_temp, num_gp, num_band0) array. "
        "Not exposed as a separate output file — the sum is constructed in-"
        "memory during the κ solve."
    ),
)


PHONO3PY_ISOTOPE_ABUNDANCES = StateAdapterSpec(
    state=ISOTOPE_ABUNDANCES,
    adapter_name="phono3py",
    observable_units={"g": "dimensionless"},
    code_api={"g": "Phono3pyIsotope(mass_variances=...)"},
    notes=(
        "Per-atom g_i passed via Phono3pyIsotope or the Phono3py.run_isotope_*"
        " entry points (`mass_variances` keyword). Defaults to natural-"
        "abundance g_i computed from phonopy's atomic-weights table when "
        "no explicit array is supplied."
    ),
)


PHONO3PY_PROVIDE_ISOTOPE_ABUNDANCES = OperationAdapterSpec(
    operation=provide_isotope_abundances,
    adapter_name="phono3py",
    notes=(
        "Set via Phono3pyIsotope(mass_variances=...) or the CLI flag "
        "`--isotope`. Natural-abundance defaults from phonopy's "
        "atomic-weights table when no explicit array is supplied."
    ),
)


PHONO3PY_COMPUTE_ISOTOPE_SCATTERING = OperationAdapterSpec(
    operation=compute_isotope_scattering,
    adapter_name="phono3py",
    notes=(
        "phono3py.other.isotope.Isotope realises the Tamura δ with the same "
        "smearing scheme (sigma / tetrahedron) selected by the parent kappa "
        "calculation — Gaussian by default, matching the canonical "
        "delta_broadening=gaussian convention."
    ),
)


PHONO3PY_COMPUTE_BOUNDARY_SCATTERING = OperationAdapterSpec(
    operation=compute_boundary_scattering,
    adapter_name="phono3py",
    notes=(
        "phono3py.conductivity.scattering_solvers.compute_bulk_boundary_"
        "scattering: Γ_boundary = |v|·1e6·Å / (4π·L), with L the "
        "`boundary_mfp` parameter (in micrometres). The factor of 1/(4π) "
        "is phono3py's bulk-boundary convention — distinct from kaldo's "
        "1/L and ShengBTE's |v|/L; cross-code comparison at this Γ "
        "requires the convention factor."
    ),
)


PHONO3PY_SUM_LINEWIDTHS = OperationAdapterSpec(
    operation=sum_linewidths,
    adapter_name="phono3py",
    notes=(
        "Sum implemented by `compute_effective_gamma` in "
        "phono3py.conductivity.grid_point_data: anharmonic + isotope + "
        "boundary + el-ph. The total is built in-memory just before the "
        "BTE solve and is not written to a separate output file."
    ),
)


# ---------------------------------------------------------------------------
# Wigner transport. phono3py's `ms_smm19` plugin (named for Simoncelli-Marzari-
# Mauri 2019) provides the Wigner kappa solver, accessed via `--wigner` on
# the CLI. The solver returns the populations / coherences split (kappa_P_RTA
# / kappa_C) plus the combined kappa_TOT_RTA. There is no QHGK channel in
# phono3py.
# ---------------------------------------------------------------------------


PHONO3PY_THERMAL_CONDUCTIVITY_WIGNER = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER,
    adapter_name="phono3py",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "thermal_conductivity.kappa_TOT_RTA"},
    notes=(
        "Phono3py.run_thermal_conductivity(is_LBTE=False) with the "
        "WignerRTAKappaSolver (selected via the `--wigner` CLI flag or via "
        "the `is_wigner_kappa=True` setting) returns the combined Wigner "
        "kappa as `kappa_TOT_RTA` (or simply `.kappa`)."
    ),
)


PHONO3PY_THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    adapter_name="phono3py",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "thermal_conductivity.kappa_P_RTA"},
    notes=(
        "Population (diagonal-in-band) term of the Wigner kappa. Built by "
        "summing pair contributions where |ω_s1 - ω_s2| is below the "
        "DEGENERATE_FREQUENCY_THRESHOLD_THZ in the WignerRTAKappaSolver."
    ),
)


PHONO3PY_THERMAL_CONDUCTIVITY_WIGNER_COHERENCES = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    adapter_name="phono3py",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "thermal_conductivity.kappa_C"},
    notes=(
        "Coherence (off-diagonal) term of the Wigner kappa, accumulated "
        "from pair contributions with |ω_s1 - ω_s2| above the degeneracy "
        "threshold. Decomposed per-mode as `mode_kappa_C` of shape "
        "(num_sigma, num_temp, num_gp, num_band0, num_band, 6)."
    ),
)


PHONO3PY_COMPUTE_KAPPA_WIGNER_POPULATIONS = OperationAdapterSpec(
    operation=compute_kappa_wigner_populations,
    adapter_name="phono3py",
    notes=(
        "Computed inside WignerRTAKappaSolver.finalize alongside the "
        "coherences term; exposed as the kappa_P_RTA / mode_kappa property."
    ),
)


PHONO3PY_COMPUTE_KAPPA_WIGNER_COHERENCES = OperationAdapterSpec(
    operation=compute_kappa_wigner_coherences,
    adapter_name="phono3py",
    notes=(
        "Lorentzian-weighted off-diagonal mode overlap built from the "
        "velocity operator (vm_by_vm) inside WignerRTAKappaSolver. The "
        "broadening width is the per-mode total Γ (compute_effective_gamma "
        "output) — shared with the LBTE chain."
    ),
)


PHONO3PY_COMBINE_KAPPA_WIGNER = OperationAdapterSpec(
    operation=combine_kappa_wigner,
    adapter_name="phono3py",
    notes=(
        "WignerRTAKappaSolver.kappa returns self._kappa_P + self._kappa_C "
        "directly; also surfaced as the `kappa_TOT_RTA` attribute."
    ),
)
