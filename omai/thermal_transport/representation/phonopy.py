"""phonopy adapter specs for the thermal-transport DAG.

phonopy is a *harmonic* phonon code: it computes Φ², the dynamical matrix,
phonon frequencies, eigenvectors, and harmonic thermal properties (energy,
entropy, free energy, heat capacity at constant volume). It does not
compute three-phonon scattering or thermal conductivity; that is the
domain of its sibling phono3py (covered by a separate adapter module) or
downstream consumers like ShengBTE.

This adapter exposes only the states phonopy emits *directly* as part of
its standard thermal-properties output. Per-mode HeatCapacity is computed
internally but its exposed output form is the molar contraction, so the
adapter targets MolarHeatCapacity rather than the per-mode HeatCapacity.

References to the phonopy API (https://phonopy.github.io/phonopy/):
  * Phonopy.run_thermal_properties / get_thermal_properties_dict —
      yields heat_capacity in J/(K·mol), one value per temperature.
  * Phonopy.get_frequencies / get_band_structure / get_mesh_dict —
      phonon frequencies in THz (linear).
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import (
    apply_nac_correction,
    compute_dispersion,
    compute_dos,
    compute_dynamical_matrix,
    compute_force_constants_2,
    compute_group_velocity,
    compute_gruneisen,
    compute_heat_capacity,
    contract_molar_heat_capacity,
    contract_volumetric_heat_capacity,
    identity_dm,
    provide_born_charges,
    provide_dielectric_tensor,
    provide_potential,
    provide_temperature,
)
from omai.thermal_transport.operator.nodes import (
    BARE_DYNAMICAL_MATRIX,
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    GRUNEISEN,
    MOLAR_HEAT_CAPACITY,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    VOLUMETRIC_HEAT_CAPACITY,
)


PHONOPY_FREQUENCY = StateAdapterSpec(
    state=FREQUENCY_STATE,
    adapter_name="phonopy",
    observable_units={"omega": "linear_THz"},
    code_api={"omega": "Phonopy.get_mesh_dict()['frequencies']"},
    notes=(
        "Phonopy.get_mesh_dict()['frequencies'] in linear THz, shape "
        "(n_q, n_modes). Same convention as phono3py (which depends on "
        "phonopy for the harmonic side)."
    ),
)


PHONOPY_MOLAR_HEAT_CAPACITY = StateAdapterSpec(
    state=MOLAR_HEAT_CAPACITY,
    adapter_name="phonopy",
    observable_units={"C_V_mol": "J_per_K_per_mol"},
    code_api={"C_V_mol": "get_thermal_properties_dict()['heat_capacity']"},
    notes=(
        "Phonopy.get_thermal_properties_dict()['heat_capacity'] in "
        "J/(K·mol), one entry per temperature on the requested T-grid. "
        "phonopy's 'mol' is per mole of primitive unit cells (so for a "
        "two-atom cell like Si, divide by 2 to get per mole of atoms / "
        "formula units). The result is already contracted: phonopy "
        "internally sums per-mode c_qν over the q-mesh, multiplies by "
        "Avogadro's number, and divides by N_q. Cross-code comparison "
        "with kaldo or phono3py at this Observable requires contracting "
        "their per-mode HeatCapacity via contract_molar_heat_capacity."
    ),
)


# ---------------------------------------------------------------------------
# Additional state-adapter specs for states phonopy exposes
# (TEMPERATURE, FC2, DM, EIGENVECTORS). FC3 and BTE-related states are out
# of phonopy's scope; those belong to phono3py.
# ---------------------------------------------------------------------------


PHONOPY_TEMPERATURE = StateAdapterSpec(
    state=TEMPERATURE_STATE,
    adapter_name="phonopy",
    code_api={"temperature": "Phonopy.run_thermal_properties(temperatures=...)"},
    notes="Temperature grid for thermal_properties output, in K.",
)


PHONOPY_FORCE_CONSTANTS_2 = StateAdapterSpec(
    state=FORCE_CONSTANTS_2,
    adapter_name="phonopy",
    code_api={"phi": "Phonopy.force_constants"},
    notes=(
        "Phonopy.force_constants: ndarray of shape (n_satom, n_satom, 3, 3) in "
        "eV/Å². Produced by Phonopy.produce_force_constants()."
    ),
)


PHONOPY_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=DYNAMICAL_MATRIX,
    adapter_name="phonopy",
    code_api={"D": "Phonopy.dynamical_matrix"},
    notes=(
        "Phonopy.dynamical_matrix: DynamicalMatrix object; per-q matrices "
        "are obtained by calling .run(q)."
    ),
)


PHONOPY_EIGENVECTORS = StateAdapterSpec(
    state=EIGENVECTORS,
    adapter_name="phonopy",
    code_api={"e": "Phonopy.get_mesh_dict()['eigenvectors']"},
    notes=(
        "Eigenvectors of D(q) for each q on the mesh. Phase + degenerate-"
        "subspace rotation freedom; per-element cross-code comparison is "
        "NOT_COMPARABLE."
    ),
)


PHONOPY_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="phonopy",
    code_api={"potential": "Phonopy(...) + ASE calculator or FORCE_SETS"},
    notes=(
        "phonopy consumes either an ASE calculator (via "
        "Phonopy.set_forces_from_calculator() or equivalent) or "
        "precomputed forces in FORCE_SETS/vasprun.xml format."
    ),
)


PHONOPY_GROUP_VELOCITY = StateAdapterSpec(
    state=GROUP_VELOCITY,
    adapter_name="phonopy",
    observable_units={"v": "angstrom_linear_THz"},
    code_api={"v": "Phonopy.get_mesh_dict()['group_velocities']"},
    notes=(
        "Available when the mesh is run with with_group_velocities=True. "
        "Same convention as phono3py (Å·THz, shape (n_q, n_modes, 3))."
    ),
)


PHONOPY_VOLUMETRIC_HEAT_CAPACITY = StateAdapterSpec(
    state=VOLUMETRIC_HEAT_CAPACITY,
    adapter_name="phonopy",
    code_api={"C_V_vol": "get_thermal_properties_dict()['heat_capacity'] / (V_cell * N_A)"},
    notes=(
        "Derived from the molar form: divide phonopy's J/(K·mol) by "
        "(V_cell × N_A) — i.e., per-cell volume times Avogadro — to get J/(m³·K)."
    ),
)


PHONOPY_PHONON_DOS = StateAdapterSpec(
    state=PHONON_DOS,
    adapter_name="phonopy",
    code_api={"g": "Phonopy.run_total_dos() / .get_total_DOS()"},
    notes=(
        "Phonopy.run_total_dos() computes g(ω); access the array via "
        ".get_total_DOS() which returns (frequencies, DOS)."
    ),
)


PHONOPY_GRUNEISEN = StateAdapterSpec(
    state=GRUNEISEN,
    adapter_name="phonopy",
    code_api={"gamma_G": "PhonopyGruneisen.get_gruneisen()"},
    notes=(
        "Computed by the phonopy-gruneisen CLI / PhonopyGruneisen API from "
        "three Phonopy instances at slightly different volumes (V₀, V±ΔV). "
        "Returns mode γ_qν on a band path (GruneisenBandStructure) or on a "
        "q-mesh (GruneisenMesh)."
    ),
)


# ---------------------------------------------------------------------------
# Operation-adapter specs for phonopy. Phonopy covers only the harmonic
# chain; the BTE half of the DAG is out of its scope and lives in the
# phono3py adapter.
# ---------------------------------------------------------------------------


PHONOPY_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="phonopy",
    notes=(
        "Phonopy reads forces from an external DFT / ML code via the "
        "FORCE_SETS / FORCE_CONSTANTS files."
    ),
)


PHONOPY_PROVIDE_TEMPERATURE = OperationAdapterSpec(
    operation=provide_temperature,
    adapter_name="phonopy",
    notes="Set via Phonopy.run_thermal_properties(temperatures=...).",
)


PHONOPY_COMPUTE_FORCE_CONSTANTS_2 = OperationAdapterSpec(
    operation=compute_force_constants_2,
    adapter_name="phonopy",
    algorithmic_convention_overrides={"symmetry_group": "spglib_auto"},
    notes=(
        "Phonopy.produce_force_constants applies spglib-driven space-group "
        "reduction by default. Disable via Phonopy(symprec=0) for the C1 "
        "regime."
    ),
)


PHONOPY_COMPUTE_DYNAMICAL_MATRIX = OperationAdapterSpec(
    operation=compute_dynamical_matrix,
    adapter_name="phonopy",
    notes=(
        "DynamicalMatrix.get_dynamical_matrix(q) — Bloch sum over Φ²(R) "
        "with the phonopy phase convention."
    ),
)


PHONOPY_COMPUTE_DISPERSION = OperationAdapterSpec(
    operation=compute_dispersion,
    adapter_name="phonopy",
    notes=(
        "Eigenfrequencies / eigenvectors from numpy.linalg.eigh of D(q) — "
        "Phonopy.get_band_structure / .get_mesh_dict."
    ),
)


PHONOPY_COMPUTE_GROUP_VELOCITY = OperationAdapterSpec(
    operation=compute_group_velocity,
    adapter_name="phonopy",
    notes=(
        "Phonopy.GroupVelocity uses the analytic Hellmann-Feynman formula, "
        "with finite-difference fallback at exact band crossings."
    ),
)


PHONOPY_COMPUTE_HEAT_CAPACITY = OperationAdapterSpec(
    operation=compute_heat_capacity,
    adapter_name="phonopy",
    notes=(
        "Per-mode c_qν is computed internally via the Bose-Einstein form "
        "but only the molar contraction is exposed (heat_capacity in "
        "thermal_properties)."
    ),
)


PHONOPY_CONTRACT_VOLUMETRIC_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_volumetric_heat_capacity,
    adapter_name="phonopy",
    notes=(
        "Not emitted directly; derivable from the molar form by dividing "
        "by N_A and the cell volume."
    ),
)


PHONOPY_CONTRACT_MOLAR_HEAT_CAPACITY = OperationAdapterSpec(
    operation=contract_molar_heat_capacity,
    adapter_name="phonopy",
    notes=(
        "get_thermal_properties_dict()['heat_capacity'] in J/(K·mol of "
        "primitive cells)."
    ),
)


PHONOPY_COMPUTE_DOS = OperationAdapterSpec(
    operation=compute_dos,
    adapter_name="phonopy",
    algorithmic_convention_overrides={"dos_broadening": "tetrahedron"},
    notes=(
        "Phonopy.run_total_dos defaults to tetrahedron integration; "
        "Gaussian broadening is selectable via the `sigma` argument."
    ),
)


PHONOPY_COMPUTE_GRUNEISEN = OperationAdapterSpec(
    operation=compute_gruneisen,
    adapter_name="phonopy",
    algorithmic_convention_overrides={"gruneisen_method": "finite_difference"},
    notes=(
        "PhonopyGruneisen finite-differences ω(V) between three harmonic "
        "calculations at slightly different cell volumes — deviates from "
        "the canonical Maradudin-Fein closed form."
    ),
)


# ---------------------------------------------------------------------------
# NAC (LO-TO splitting) for polar materials. Phonopy is the reference
# implementation: BORN files in its native format, two NAC methods (gonze and
# wang) selectable via nac_method, and `apply_nac_correction` is the polar
# branch of the DM construction. Non-polar phonopy runs fire identity_dm.
# ---------------------------------------------------------------------------


PHONOPY_BORN_CHARGES = StateAdapterSpec(
    state=BORN_CHARGES,
    adapter_name="phonopy",
    observable_units={"Z_star": "dimensionless"},
    code_api={"Z_star": "Phonopy.nac_params['born']"},
    notes=(
        "Phonopy reads Born effective charges from a BORN file (first 9 "
        "numbers are ε∞, then 9 per atom are Z*_{i,αβ}); they are stored on "
        "the Phonopy instance as nac_params['born'] with shape "
        "(n_atoms_primitive, 3, 3) in units of the elementary charge."
    ),
)


PHONOPY_DIELECTRIC_TENSOR = StateAdapterSpec(
    state=DIELECTRIC_TENSOR,
    adapter_name="phonopy",
    observable_units={"epsilon_infinity": "dimensionless"},
    code_api={"epsilon_infinity": "Phonopy.nac_params['dielectric']"},
    notes=(
        "Phonopy stores the macroscopic ε∞ tensor read from the BORN file "
        "as nac_params['dielectric'] with shape (3, 3), dimensionless."
    ),
)


PHONOPY_BARE_DYNAMICAL_MATRIX = StateAdapterSpec(
    state=BARE_DYNAMICAL_MATRIX,
    adapter_name="phonopy",
    code_api={
        "D_bare": "DynamicalMatrix.get_dynamical_matrix() with NAC disabled"
    },
    notes=(
        "Phonopy does not expose the bare DM as a distinct attribute; the "
        "analytic Bloch sum is what `DynamicalMatrix.get_dynamical_matrix()` "
        "returns when nac_params is not set. With NAC enabled the same call "
        "returns the corrected DM (i.e. our DynamicalMatrix node, not "
        "BareDynamicalMatrix)."
    ),
)


PHONOPY_PROVIDE_BORN_CHARGES = OperationAdapterSpec(
    operation=provide_born_charges,
    adapter_name="phonopy",
    notes=(
        "Phonopy loads Born charges from a BORN file via "
        "`parse_BORN(primitive, filename)`, then attaches them through "
        "`Phonopy(nac_params={'born': ..., 'dielectric': ..., 'factor': ...})`."
    ),
)


PHONOPY_PROVIDE_DIELECTRIC_TENSOR = OperationAdapterSpec(
    operation=provide_dielectric_tensor,
    adapter_name="phonopy",
    notes="Read alongside Born charges from the BORN file (first 9 numbers).",
)


PHONOPY_IDENTITY_DM = OperationAdapterSpec(
    operation=identity_dm,
    adapter_name="phonopy",
    notes=(
        "Non-polar runs (no BORN file, nac_params is None): the bare Bloch "
        "sum is the dynamical matrix returned by Phonopy unchanged."
    ),
)


PHONOPY_APPLY_NAC_CORRECTION = OperationAdapterSpec(
    operation=apply_nac_correction,
    adapter_name="phonopy",
    algorithmic_convention_overrides={"nac_scheme": "gonze_lee"},
    notes=(
        "Polar runs: Phonopy(nac_params=...) adds the non-analytic correction "
        "via `DynamicalMatrixNAC.get_dynamical_matrix()`. The default scheme "
        "is gonze (Gonze-Lee 1997); set nac_method='wang' for the Wang Ewald "
        "alternative. The LO-TO direction is selected at the q→0 point by "
        "Phonopy.set_band_structure or the unit-vector argument to "
        "DynamicalMatrixNAC.run()."
    ),
)
