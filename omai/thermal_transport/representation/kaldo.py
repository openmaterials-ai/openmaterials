"""kaldo adapter specs for the thermal-transport DAG.

Constructed against the operator DAG in
`omai.thermal_transport.operator`. Cross-code comparison happens at the
operator level (Principle 7) via the shared states; differences
surface as unit factors, convention mismatches, and discretization choice
mismatches.

References to the kaldo API (https://nanotheorygroup.github.io/kaldo/):
  * Phonons.bandwidth     — the linewidth Gamma_qν, in angular THz
  * Phonons.heat_capacity — per-mode c_qν(T), in J/K
  * Phonons(third_bandwidth=σ) — broadening parameter, half-width-style

Run-mode parameterization
-------------------------
kaldo's compute_linewidth supports two broadening modes determined at
construction time:

  * `third_bandwidth=None` (default) → adaptive velocity-projection σ
    (the same scheme ShengBTE uses).
  * `third_bandwidth=σ_linear_THz`   → fixed σ interpreted as a halfwidth.

The module-level `KALDO_COMPUTE_LINEWIDTH` constant describes the
*default* mode (adaptive). Use the `kaldo_compute_linewidth_spec(...)`
factory when ingesting a run that explicitly set `third_bandwidth`; the
returned spec records the actual mode and parameters used in that run,
which is what cross-code comparison should reference.
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import (
    apply_nac_correction,
    combine_kappa_wigner,
    compute_dispersion,
    compute_dos,
    compute_dynamical_matrix,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_group_velocity,
    compute_heat_capacity,
    compute_kappa_qhgk,
    compute_kappa_wigner_coherences,
    compute_kappa_wigner_populations,
    compute_linewidth,
    compute_phase_space_3phonon,
    contract_cumulative_kappa_mfp,
    contract_cumulative_kappa_omega,
    contract_kappa_direct,
    contract_kappa_rta,
    contract_molar_heat_capacity,
    contract_volumetric_heat_capacity,
    identity_dm,
    provide_born_charges,
    provide_dielectric_tensor,
    provide_potential,
    provide_temperature,
    solve_bte_direct,
    solve_bte_rta,
)
from omai.thermal_transport.operator.nodes import (
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    CUMULATIVE_KAPPA_MFP,
    CUMULATIVE_KAPPA_OMEGA,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MEAN_FREE_DISPLACEMENT_RTA,
    MOLAR_HEAT_CAPACITY,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_QHGK,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_WIGNER,
    THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    VOLUMETRIC_HEAT_CAPACITY,
)


KALDO_FREQUENCY = StateAdapterSpec(
    state=FREQUENCY_STATE,
    adapter_name="kaldo",
    observable_units={"omega": "linear_THz"},
    code_api={"omega": "Phonons.frequency"},
    notes="Phonons.frequency in linear THz, shape (n_q, n_modes).",
)


KALDO_GROUP_VELOCITY = StateAdapterSpec(
    state=GROUP_VELOCITY,
    adapter_name="kaldo",
    observable_units={"v": "angstrom_linear_THz"},
    code_api={"v": "Phonons.velocity"},
    notes="Phonons.velocity in Å·THz, shape (n_q, n_modes, 3).",
)


KALDO_LINEWIDTH = StateAdapterSpec(
    state=LINEWIDTH,
    adapter_name="kaldo",
    observable_units={"Gamma": "angular_THz"},
    observable_convention_overrides={
        "gamma_definition": "linewidth_2x_imag_self_energy",
    },
    code_api={"Gamma": "Phonons.bandwidth"},
    notes=(
        "Phonons.bandwidth array is in angular THz, defined as the linewidth "
        "Gamma = 2 Im Sigma (factor of 2 from the linewidth-vs-self-energy "
        "convention)."
    ),
)


KALDO_HEAT_CAPACITY = StateAdapterSpec(
    state=HEAT_CAPACITY,
    adapter_name="kaldo",
    observable_units={"c": "J_per_K"},
    code_api={"c": "Phonons.heat_capacity"},
    notes="Phonons.heat_capacity in J/K per mode.",
)


KALDO_THERMAL_CONDUCTIVITY_RTA = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_RTA,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='rta').conductivity"},
    notes="Conductivity(method='rta').conductivity in W/(m·K), tensor shape (3, 3).",
)


KALDO_THERMAL_CONDUCTIVITY_DIRECT = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_DIRECT,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='inverse').conductivity"},
    notes=(
        "Conductivity(method='inverse').conductivity in W/(m·K), tensor "
        "shape (3, 3). kaldo's 'inverse' method realizes the operator layer's "
        "canonical bte_solver=direct_inverse. 'sc' (self-consistent "
        "iterative) is an alternative realization of the same canonical."
    ),
)


def kaldo_compute_linewidth_spec(
    *,
    broadening_param: str = "adaptive_velocity_projection",
    symmetry_group: str = "C1",
) -> OperationAdapterSpec:
    """Build a kaldo compute_linewidth adapter spec for a specific run mode.

    kaldo's broadening behavior is set at Phonons() construction:
      * ``third_bandwidth=None`` (default) → adaptive velocity-projection σ
        (per-channel σ from sqrt(Σ_ν [δk_ν · Δv]² / 6); identical to
        ShengBTE's `base_sigma` with scalebroad=1.0).
      * ``third_bandwidth=σ`` (a positive float in linear THz) → fixed σ
        interpreted as halfwidth: σ_input = stdev × √2.

    Args:
        broadening_param: One of ``"adaptive_velocity_projection"`` or
            ``"halfwidth"``. Defaults to the kaldo default.
        symmetry_group: One of ``"C1"`` (stable kaldo, no spglib reduction)
            or ``"spglib_auto"`` (kaldo `main` with `use_symmetry=True`).

    Returns:
        An OperationAdapterSpec describing the requested run mode.
    """
    if broadening_param == "adaptive_velocity_projection":
        broadening_note = (
            "Default mode (third_bandwidth=None): per-channel adaptive σ "
            "from sqrt(Σ_ν [δk_ν · Δv]² / 6) — identical to ShengBTE's "
            "base_sigma with scalebroad=1.0."
        )
    elif broadening_param == "halfwidth":
        broadening_note = (
            "Fixed-σ mode (third_bandwidth=σ in linear THz): kaldo uses σ "
            "as a halfwidth-style param, σ_input = stdev × √2."
        )
    else:
        broadening_note = f"Non-standard broadening_param={broadening_param!r}."

    return OperationAdapterSpec(
        operation=compute_linewidth,
        adapter_name="kaldo",
        parameter_units={"broadening_sigma": "linear_THz"},
        algorithmic_convention_overrides={
            "broadening_param": broadening_param,
            "symmetry_group": symmetry_group,
        },
        discretization_choices={
            "bz_summation": "full_grid",
            "delta_cutoff_sigmas": "2",
            "degeneracy_averaging": "off",
        },
        notes=(
            f"{broadening_note} Iterates the full BZ grid (ordered triplets) "
            "with a 0.5 factor on the decay channel to compensate the "
            "double-count. Truncates the Gaussian at 2σ in the dirac-delta "
            "replacement."
        ),
    )


# Module-level default: kaldo's out-of-the-box configuration (adaptive
# velocity-projection broadening on the stable branch). Discovery picks
# this up; runs that used third_bandwidth=σ should construct a per-run
# spec via kaldo_compute_linewidth_spec(broadening_param="halfwidth") and
# pass it through compare()/represent() explicitly.
KALDO_COMPUTE_LINEWIDTH = kaldo_compute_linewidth_spec()


KALDO_COMPUTE_HEAT_CAPACITY = OperationAdapterSpec(
    operation=compute_heat_capacity,
    adapter_name="kaldo",
    notes="No parameters or algorithmic conventions exposed.",
)


KALDO_COMPUTE_FORCE_CONSTANTS_2 = OperationAdapterSpec(
    operation=compute_force_constants_2,
    adapter_name="kaldo",
    algorithmic_convention_overrides={
        # Stable kaldo's ForceConstants(second) consumes a precomputed
        # Φ² (numpy array or hiPhive object) without internal symmetrization.
        # `main` adds spglib-driven symmetry reduction.
        "symmetry_group": "C1",
    },
    notes=(
        "kaldo.ForceConstants.from_folder loads Φ² as-is; the stable branch "
        "performs no spglib reduction. Switch to symmetry_group='spglib_auto' "
        "if targeting kaldo main with use_symmetry=True."
    ),
)


KALDO_COMPUTE_FORCE_CONSTANTS_3 = OperationAdapterSpec(
    operation=compute_force_constants_3,
    adapter_name="kaldo",
    algorithmic_convention_overrides={
        "symmetry_group": "C1",
    },
    notes=(
        "Analogous to the harmonic adapter: Φ³ is loaded verbatim on the "
        "stable branch. Triplet symmetry reduction lives in kaldo main."
    ),
)


KALDO_SOLVE_BTE_DIRECT = OperationAdapterSpec(
    operation=solve_bte_direct,
    adapter_name="kaldo",
    algorithmic_convention_overrides={
        # Conductivity(method='inverse') assembles M on the full BZ grid
        # and calls scipy.linalg.solve. No irreducible-wedge reduction.
        "symmetry_group": "C1",
    },
    discretization_choices={
        "collision_matrix_assembly": "full_grid",
        "linear_solver": "scipy.linalg.solve",
    },
    notes=(
        "Conductivity(method='inverse'): the collision matrix M is "
        "(N_q·N_modes)² in size and inverted directly with scipy. "
        "method='sc' is an alternative realization of the same canonical "
        "direct_inverse, with iterative refinement instead."
    ),
)


# ---------------------------------------------------------------------------
# Additional state-adapter specs covering states kaldo uses internally
# (Temperature, FC2/FC3, dynamical matrix, eigenvectors, MFD). Most of these
# are intermediate scaffolding — no cross-code numerical comparison is
# expected on the raw values — so observable_units are omitted; only
# code_api is recorded so the diagram can show them as covered.
# ---------------------------------------------------------------------------


KALDO_TEMPERATURE = StateAdapterSpec(
    state=TEMPERATURE_STATE,
    adapter_name="kaldo",
    code_api={"temperature": "Phonons(temperature=...)"},
    notes="Scalar parameter passed to the Phonons constructor.",
)


KALDO_FORCE_CONSTANTS_2 = StateAdapterSpec(
    state=FORCE_CONSTANTS_2,
    adapter_name="kaldo",
    code_api={"phi": "ForceConstants.second.value"},
    notes=(
        "kaldo stores FC2 as a numpy array under ForceConstants.second.value, "
        "shape (n_supercell_atoms, 3, n_supercell_atoms, 3) in eV/Å²."
    ),
)


KALDO_FORCE_CONSTANTS_3 = StateAdapterSpec(
    state=FORCE_CONSTANTS_3,
    adapter_name="kaldo",
    code_api={"phi": "ForceConstants.third.value"},
    notes=(
        "kaldo stores FC3 as a sparse COO array under ForceConstants.third.value, "
        "in eV/Å³."
    ),
)


KALDO_EIGENVECTORS = StateAdapterSpec(
    state=EIGENVECTORS,
    adapter_name="kaldo",
    code_api={"e": "Phonons.eigenvectors"},
    notes=(
        "Phonons.eigenvectors: complex array of shape (n_q, n_modes, n_modes). "
        "Carries the U(1) phase + degenerate-subspace rotation freedom; "
        "per-element cross-code comparison is NOT_COMPARABLE."
    ),
)


KALDO_MEAN_FREE_DISPLACEMENT_RTA = StateAdapterSpec(
    state=MEAN_FREE_DISPLACEMENT_RTA,
    adapter_name="kaldo",
    code_api={"F": "Conductivity(method='rta').mean_free_path"},
    notes=(
        "kaldo computes F = v / (2Γ) per-mode under RTA. Exposed as the "
        "mean_free_path attribute of a Conductivity(method='rta') instance."
    ),
)


KALDO_MEAN_FREE_DISPLACEMENT_DIRECT = StateAdapterSpec(
    state=MEAN_FREE_DISPLACEMENT_DIRECT,
    adapter_name="kaldo",
    code_api={"F": "Conductivity(method='inverse').mean_free_path"},
    notes=(
        "Full LBTE F: kaldo solves M·F = c·v via scipy.linalg.solve and "
        "exposes the result through Conductivity(method='inverse').mean_free_path."
    ),
)


KALDO_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=DYNAMICAL_MATRIX,
    adapter_name="kaldo",
    code_api={"D": "HarmonicWithQ(q).dynmat"},
    notes=(
        "kaldo builds D(q) per q-point inside HarmonicWithQ. There is no "
        "global cached array; instantiate HarmonicWithQ for the desired q "
        "to access its `dynmat` attribute (units: angular_THz²)."
    ),
)


KALDO_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="kaldo",
    code_api={"potential": "ForceConstants(calculator=<ASE calculator>)"},
    notes=(
        "kaldo consumes an ASE-compatible calculator (LAMMPS+Tersoff, "
        "Quantum ESPRESSO, GPAW, or any custom calc.Calculator). Forces "
        "are obtained from the calculator during FC finite-difference."
    ),
)


KALDO_VOLUMETRIC_HEAT_CAPACITY = StateAdapterSpec(
    state=VOLUMETRIC_HEAT_CAPACITY,
    adapter_name="kaldo",
    code_api={"C_V_vol": "np.sum(Phonons.heat_capacity) / (V_cell * n_q_points)"},
    notes=(
        "Derived from the per-mode form (no native API for the volumetric "
        "contraction). One-line application of contract_volumetric_heat_capacity "
        "to Phonons.heat_capacity."
    ),
)


KALDO_MOLAR_HEAT_CAPACITY = StateAdapterSpec(
    state=MOLAR_HEAT_CAPACITY,
    adapter_name="kaldo",
    code_api={"C_V_mol": "N_A * np.sum(Phonons.heat_capacity) / n_q_points"},
    notes=(
        "Derived from the per-mode form. One-line application of "
        "contract_molar_heat_capacity to Phonons.heat_capacity."
    ),
)


KALDO_PHONON_DOS = StateAdapterSpec(
    state=PHONON_DOS,
    adapter_name="kaldo",
    code_api={"g": "plotter.plot_dos(phonons, bandwidth, n_points)"},
    notes=(
        "kaldo computes a Gaussian-broadened DOS internally inside "
        "controllers.plotter.plot_dos. The array isn't exposed as a clean "
        "attribute, but the underlying Phonons.frequency + a histogram "
        "reproduces it: g(ω) ← sum of Gaussians of width `bandwidth` "
        "centered on each ω_qν."
    ),
)


KALDO_PHASE_SPACE_3PH = StateAdapterSpec(
    state=PHASE_SPACE_3PH,
    adapter_name="kaldo",
    code_api={"P3": "Phonons.phase_space"},
    notes=(
        "Phonons.phase_space: per-mode 3-phonon phase-space density "
        "computed alongside the linewidth projection, shape (n_k_points, "
        "n_modes). Independent of |V_3|² — pure kinematic count."
    ),
)


# ---------------------------------------------------------------------------
# Operation-adapter specs for kaldo. Trivial source / contraction ops
# (`provide_*`, `contract_*`, `solve_bte_rta`) carry no algorithmic
# conventions; their adapters exist only to mark coverage in the
# visualization. Ops with a meaningful per-code algorithmic choice
# (compute_group_velocity, compute_dos, compute_phase_space_3phonon)
# override the canonical value where kaldo deviates.
# ---------------------------------------------------------------------------


KALDO_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="kaldo",
    notes="kaldo runs against an external calculator (LAMMPS, ASE, ML).",
)


KALDO_PROVIDE_TEMPERATURE = OperationAdapterSpec(
    operation=provide_temperature,
    adapter_name="kaldo",
    notes="Set via Phonons(temperature=...).",
)


KALDO_COMPUTE_DYNAMICAL_MATRIX = OperationAdapterSpec(
    operation=compute_dynamical_matrix,
    adapter_name="kaldo",
    notes=(
        "ForceConstants.dynamical_matrix(q): Bloch sum implemented as a "
        "mass-weighted Fourier transform of Φ²(R)."
    ),
)


KALDO_COMPUTE_DISPERSION = OperationAdapterSpec(
    operation=compute_dispersion,
    adapter_name="kaldo",
    notes=(
        "Phonons.frequency / Phonons.eigenvectors come from a per-q "
        "numpy.linalg.eigh of the dynamical matrix. Degenerate subspaces "
        "inherit numpy's arbitrary basis choice — the standard reason "
        "Eigenvectors and any quantity built from them are HiddenStates."
    ),
)


KALDO_COMPUTE_GROUP_VELOCITY = OperationAdapterSpec(
    operation=compute_group_velocity,
    adapter_name="kaldo",
    notes=(
        "Phonons.velocity uses the analytic Hellmann-Feynman form "
        "v_qν = (1/2ω_qν) ⟨e_qν| ∂D/∂q |e_qν⟩ — matches the canonical "
        "gv_method=hellmann_feynman."
    ),
)


KALDO_SOLVE_BTE_RTA = OperationAdapterSpec(
    operation=solve_bte_rta,
    adapter_name="kaldo",
    notes=(
        "Conductivity(method='rta'): closed-form F = v / (2Γ), no "
        "algorithmic choice beyond the inherited Linewidth conventions."
    ),
)


KALDO_CONTRACT_KAPPA_RTA = OperationAdapterSpec(
    operation=contract_kappa_rta,
    adapter_name="kaldo",
    notes="Conductivity(method='rta').conductivity — per-mode contraction.",
)


KALDO_CONTRACT_KAPPA_DIRECT = OperationAdapterSpec(
    operation=contract_kappa_direct,
    adapter_name="kaldo",
    notes=(
        "Conductivity(method='inverse'|'sc').conductivity — per-mode "
        "contraction after the BTE solve."
    ),
)


KALDO_CONTRACT_VOLUMETRIC_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_volumetric_heat_capacity,
    adapter_name="kaldo",
    notes="Derived from Phonons.heat_capacity by summing and dividing by cell volume.",
)


KALDO_CONTRACT_MOLAR_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_molar_heat_capacity,
    adapter_name="kaldo",
    notes="Derived from Phonons.heat_capacity via N_A × sum / N_q.",
)


KALDO_COMPUTE_DOS = OperationAdapterSpec(
    operation=compute_dos,
    adapter_name="kaldo",
    algorithmic_convention_overrides={"dos_broadening": "gaussian"},
    notes=(
        "controllers.plotter.plot_dos sums Gaussians of fixed width "
        "`bandwidth` centred on each ω_qν. Matches the canonical "
        "dos_broadening=gaussian."
    ),
)


KALDO_COMPUTE_PHASE_SPACE_3PH = OperationAdapterSpec(
    operation=compute_phase_space_3phonon,
    adapter_name="kaldo",
    algorithmic_convention_overrides={"delta_broadening": "gaussian"},
    notes=(
        "Phonons.phase_space reuses the same Gaussian δ as the linewidth "
        "calculation, with width set by `third_bandwidth` (or the "
        "adaptive scheme when None)."
    ),
)


# ---------------------------------------------------------------------------
# NAC. kaldo reads Born charges and ε∞ from the ASE Atoms.info dict (the
# shengbte_io reader populates atoms.info['born_charges'] and
# atoms.info['dielectric']); the HarmonicWithQ machinery applies the
# correction whenever those keys are present.
# ---------------------------------------------------------------------------


KALDO_BORN_CHARGES = StateAdapterSpec(
    state=BORN_CHARGES,
    adapter_name="kaldo",
    observable_units={"Z_star": "dimensionless"},
    code_api={"Z_star": "atoms.info['born_charges']"},
    notes=(
        "kaldo expects Z* on the ASE Atoms object's info dict; the shengbte "
        "BORN-file reader (kaldo.interfaces.shengbte_io) is the standard "
        "way to populate it. Shape (n_atoms_primitive, 3, 3)."
    ),
)


KALDO_BARE_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=BARE_DYNAMICAL_MATRIX,
    adapter_name="kaldo",
    code_api={"D_bare": "HarmonicWithQ(q)._dynmat_fourier"},
    notes=(
        "kaldo builds the bare Bloch sum inside HarmonicWithQ as "
        "`_dynmat_fourier` (private attribute). The NAC long-range piece is "
        "added inside `calculate_eigensystem` only when `is_nac=True` "
        "(triggered by atoms.info['dielectric']); the corrected DM is what "
        "subsequent operators consume."
    ),
)


KALDO_DIELECTRIC_TENSOR = StateAdapterSpec(
    state=DIELECTRIC_TENSOR,
    adapter_name="kaldo",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={"epsilon_infinity": "atoms.info['dielectric']"},
    notes=(
        "Stored on atoms.info['dielectric'] (3×3, dimensionless). The "
        "presence of this key triggers HarmonicWithQ.is_nac = True."
    ),
)


KALDO_PROVIDE_BORN_CHARGES = OperationAdapterSpec(
    operation=provide_born_charges,
    adapter_name="kaldo",
    notes=(
        "Populated via kaldo.interfaces.shengbte_io's BORN reader, which "
        "fills atoms.info from a ShengBTE-format BORN file."
    ),
)


KALDO_PROVIDE_DIELECTRIC_TENSOR = OperationAdapterSpec(
    operation=provide_dielectric_tensor,
    adapter_name="kaldo",
    notes="Same BORN reader; the dielectric tensor sits at the top of the file.",
)


KALDO_IDENTITY_DM = OperationAdapterSpec(
    operation=identity_dm,
    adapter_name="kaldo",
    notes=(
        "Non-polar runs (atoms.info has no 'dielectric' key): "
        "HarmonicWithQ.is_nac is False and the bare DM is used directly."
    ),
)


KALDO_APPLY_NAC_CORRECTION = OperationAdapterSpec(
    operation=apply_nac_correction,
    adapter_name="kaldo",
    algorithmic_convention_overrides={"nac_scheme": "gonze_lee"},
    notes=(
        "Polar runs: HarmonicWithQ inserts the Gonze-Lee NAC term into the "
        "dynamical matrix whenever atoms.info['dielectric'] is set. The "
        "reciprocal-space cutoff is hard-coded in kaldo (no Wang variant "
        "exposed)."
    ),
)


# ---------------------------------------------------------------------------
# Wigner + QHGK transport models. kaldo is the only one of the four
# adapters that implements either: Conductivity(method='wigner') and
# Conductivity(method='qhgk').
# ---------------------------------------------------------------------------


KALDO_THERMAL_CONDUCTIVITY_WIGNER = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='wigner').conductivity"},
    notes=(
        "kaldo's Conductivity(method='wigner') emits the unified Wigner κ "
        "tensor. The populations / coherences split is also exposed as "
        "Conductivity.populations_conductivity / .coherences_conductivity "
        "on the same object."
    ),
)


KALDO_THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='wigner').populations_conductivity"},
    notes="The diagonal-in-band (particle) part of the Wigner κ.",
)


KALDO_THERMAL_CONDUCTIVITY_WIGNER_COHERENCES = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='wigner').coherences_conductivity"},
    notes="The off-diagonal (coherence / wave-like) part of the Wigner κ.",
)


KALDO_THERMAL_CONDUCTIVITY_QHGK = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_QHGK,
    adapter_name="kaldo",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "Conductivity(method='qhgk').conductivity"},
    notes=(
        "kaldo's Conductivity(method='qhgk'): Lorentzian-broadened mode "
        "overlap, primary tool for amorphous systems. The broadening width "
        "is the per-mode Linewidth from compute_linewidth (so QHGK "
        "shares its broadening scheme with the LBTE chain)."
    ),
)


KALDO_COMPUTE_KAPPA_WIGNER_POPULATIONS = OperationAdapterSpec(
    operation=compute_kappa_wigner_populations,
    adapter_name="kaldo",
    notes=(
        "Computed alongside the coherences channel inside "
        "Conductivity(method='wigner'); exposed separately via "
        "populations_conductivity."
    ),
)


KALDO_COMPUTE_KAPPA_WIGNER_COHERENCES = OperationAdapterSpec(
    operation=compute_kappa_wigner_coherences,
    adapter_name="kaldo",
    notes=(
        "Lorentzian-weighted off-diagonal mode overlap; the linewidth "
        "feeds in as the broadening width."
    ),
)


KALDO_COMBINE_KAPPA_WIGNER = OperationAdapterSpec(
    operation=combine_kappa_wigner,
    adapter_name="kaldo",
    notes=(
        "The kaldo Conductivity object exposes the sum directly as "
        ".conductivity when method='wigner'."
    ),
)


KALDO_COMPUTE_KAPPA_QHGK = OperationAdapterSpec(
    operation=compute_kappa_qhgk,
    adapter_name="kaldo",
    notes=(
        "Conductivity(method='qhgk'): time-integrated heat-flux "
        "autocorrelation with Lorentzian mode broadening of width Γ "
        "(per-mode linewidth from compute_linewidth)."
    ),
)


# ---------------------------------------------------------------------------
# Cumulative κ distributions. kaldo's Conductivity object exposes
# .cumulative_conductivity_per_omega and .cumulative_conductivity_per_mfp
# for plotting.
# ---------------------------------------------------------------------------


KALDO_CUMULATIVE_KAPPA_OMEGA = StateAdapterSpec(
    state=CUMULATIVE_KAPPA_OMEGA,
    adapter_name="kaldo",
    observable_units={"kappa_cum": "W_per_m_per_K"},
    code_api={"kappa_cum": "Conductivity.cumulative_conductivity_per_omega"},
    notes=(
        "Cumulative κ thresholded on phonon frequency, computed via the "
        "LBTE F (Conductivity(method='inverse')). Available for the "
        "Wigner κ as well by switching method='wigner'."
    ),
)


KALDO_CUMULATIVE_KAPPA_MFP = StateAdapterSpec(
    state=CUMULATIVE_KAPPA_MFP,
    adapter_name="kaldo",
    observable_units={"kappa_cum": "W_per_m_per_K"},
    code_api={"kappa_cum": "Conductivity.cumulative_conductivity_per_mfp"},
    notes="Cumulative κ vs |F| (mean-free-path threshold).",
)


KALDO_CONTRACT_CUMULATIVE_KAPPA_OMEGA = OperationAdapterSpec(
    operation=contract_cumulative_kappa_omega,
    adapter_name="kaldo",
    algorithmic_convention_overrides={"binning": "linear"},
    notes="Linear ω-axis binning by default.",
)


KALDO_CONTRACT_CUMULATIVE_KAPPA_MFP = OperationAdapterSpec(
    operation=contract_cumulative_kappa_mfp,
    adapter_name="kaldo",
    algorithmic_convention_overrides={"binning": "log"},
    notes="Logarithmic Λ-axis binning to span the wide MFP distribution.",
)
