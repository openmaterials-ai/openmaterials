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
    compute_force_constants_2,
    compute_force_constants_3,
    compute_heat_capacity,
    compute_linewidth,
    solve_bte_direct,
)
from omai.thermal_transport.operator.nodes import (
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    GRUNEISEN,
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
    THERMAL_CONDUCTIVITY_RTA,
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
