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

from omai.materialization.adapter import StateAdapterSpec
from omai.thermal_transport.symbolic.nodes import (
    DYNAMICAL_MATRIX,
    EIGENVECTORS,
    FORCE_CONSTANTS_2,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
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
