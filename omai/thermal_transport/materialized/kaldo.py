"""kaldo adapter specs for the thermal-transport DAG.

Constructed against the symbolic DAG in
`omai.thermal_transport.symbolic`. Cross-code comparison happens at the
symbolic level (Principle 7) via the shared states; differences
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

from omai.materialization.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.symbolic.edges import (
    compute_force_constants_2,
    compute_force_constants_3,
    compute_heat_capacity,
    compute_linewidth,
    solve_bte_direct,
)
from omai.thermal_transport.symbolic.nodes import (
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
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
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
        "shape (3, 3). kaldo's 'inverse' method realizes the symbolic layer's "
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
# pass it through compare()/materialize() explicitly.
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
