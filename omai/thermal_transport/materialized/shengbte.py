"""ShengBTE adapter specs for the thermal-transport DAG.

Constructed against the symbolic DAG in
`omai.thermal_transport.symbolic`. Cross-code comparison happens at the
symbolic level (Principle 7) via the shared states; differences
surface as unit factors, convention mismatches, and discretization choice
mismatches.

References to ShengBTE (https://bitbucket.org/sousaw/shengbte):
  * BTE.omega                 — phonon angular frequencies, rad/ps
  * BTE.v                     — mode group velocities, km/s (= nm·THz)
  * BTE.w_anharmonic          — three-phonon scattering rate, ps⁻¹
  * BTE.cv                    — *volumetric* specific heat, J/(m³·K)
                                (NOT per-mode; no symbolic counterpart)
  * BTE.KappaTensorVsT_RTA    — κ(T) tensor in RTA, W/(m·K)
  * BTE.KappaTensorVsT_CONV   — κ(T) tensor self-consistently converged
                                (realizes canonical bte_solver=direct_inverse),
                                W/(m·K)

ShengBTE outputs frequencies, velocities, and rates on the *irreducible
wedge* (`BTE.omega`, `BTE.v`, `BTE.w_anharmonic`). The full-grid analogues
exist for some quantities (e.g. `BTE.v_full`); for cross-code comparison
we use the full-grid forms when available.

Skipped states:
  * HeatCapacity (per-mode): ShengBTE exposes no per-mode c_qν array.
    The contracted form (`BTE.cv`) is captured below as the
    VolumetricHeatCapacity adapter spec. Cross-code comparison on a
    per-mode basis with kaldo or phono3py is not possible for shengbte;
    they meet at the volumetric contraction.
"""

from __future__ import annotations

from omai.materialization.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.symbolic.edges import (
    compute_force_constants_2,
    compute_force_constants_3,
    compute_linewidth,
    solve_bte_direct,
)
from omai.thermal_transport.symbolic.nodes import (
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    GRUNEISEN,
    LINEWIDTH,
    MOLAR_HEAT_CAPACITY,
    PHASE_SPACE_3PH,
    PHONON_DOS,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    VOLUMETRIC_HEAT_CAPACITY,
)


SHENGBTE_FREQUENCY = StateAdapterSpec(
    state=FREQUENCY_STATE,
    adapter_name="shengbte",
    observable_units={"omega": "angular_THz"},
    code_api={"omega": "BTE.omega"},
    notes=(
        "BTE.omega: phonon angular frequencies in rad/ps (= angular_THz), "
        "shape (n_q_irr, n_modes) over the irreducible wedge."
    ),
)


SHENGBTE_GROUP_VELOCITY = StateAdapterSpec(
    state=GROUP_VELOCITY,
    adapter_name="shengbte",
    observable_units={"v": "km_per_s"},
    code_api={"v": "BTE.v"},
    notes=(
        "BTE.v: mode group velocities in km/s, shape (n_q_irr, n_modes, 3). "
        "BTE.v_full is the full-grid analogue. 1 km/s = 1 nm·THz = 10 Å·THz."
    ),
)


SHENGBTE_LINEWIDTH = StateAdapterSpec(
    state=LINEWIDTH,
    adapter_name="shengbte",
    observable_units={"Gamma": "angular_THz"},
    observable_convention_overrides={
        # BTE.w_anharmonic is the three-phonon scattering rate 1/τ in ps⁻¹.
        # Under the lattice-dynamics convention where Γ is in angular
        # frequency, 1/τ = 2 Im Σ — same factor-of-2 relative to the bare
        # imaginary self-energy that kaldo's `bandwidth` carries. So
        # ShengBTE shares kaldo's gamma_definition value.
        "gamma_definition": "linewidth_2x_imag_self_energy",
    },
    code_api={"Gamma": "BTE.w_anharmonic"},
    notes=(
        "BTE.w_anharmonic: three-phonon scattering rate in ps⁻¹ "
        "(numerically equal to angular_THz; rad and dimensionless rotation "
        "are identified). Outputs are on the irreducible wedge; full-grid "
        "values are recovered via the BTE.qpoints_full → "
        "BTE.qpoints mapping."
    ),
)


SHENGBTE_VOLUMETRIC_HEAT_CAPACITY = StateAdapterSpec(
    state=VOLUMETRIC_HEAT_CAPACITY,
    adapter_name="shengbte",
    observable_units={"C_V_vol": "J_per_m3_per_K"},
    code_api={"C_V_vol": "BTE.cv"},
    notes=(
        "BTE.cv: total specific heat per unit volume at temperature T, "
        "in J/(m³·K). Already contracted: this is what ShengBTE prints "
        "to BTE.cv (per-T directory) and BTE.cvVsT (consolidated). To "
        "compare against kaldo or phono3py at this Observable, contract "
        "their per-mode HeatCapacity via contract_volumetric_heat_capacity "
        "(c_qν → Σ_qν c_qν / (V_cell N_q))."
    ),
)


SHENGBTE_THERMAL_CONDUCTIVITY_RTA = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_RTA,
    adapter_name="shengbte",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "BTE.KappaTensorVsT_RTA"},
    notes=(
        "BTE.KappaTensorVsT_RTA: κ(T) tensor in the relaxation-time "
        "approximation, W/(m·K). One row per temperature; the columns "
        "after the temperature are the nine tensor components in row-"
        "major order."
    ),
)


SHENGBTE_THERMAL_CONDUCTIVITY_DIRECT = StateAdapterSpec(
    state=THERMAL_CONDUCTIVITY_DIRECT,
    adapter_name="shengbte",
    observable_units={"kappa": "W_per_m_per_K"},
    code_api={"kappa": "BTE.KappaTensorVsT_CONV"},
    notes=(
        "BTE.KappaTensorVsT_CONV: κ(T) tensor from the self-consistently "
        "converged BTE solver. ShengBTE iterates F = F₀ + δF until "
        "|κ_n - κ_{n-1}| < eps (default 1e-5). This realizes the symbolic "
        "layer's canonical bte_solver=direct_inverse — same fixed point as "
        "kaldo's method='inverse' and phono3py's is_LBTE=True, different "
        "algorithm (iterative vs LAPACK pseudo-inverse). The convergence "
        "trail is in BTE.kappa within each temperature directory."
    ),
)


# ---------------------------------------------------------------------------
# Operation-level adapter specs
# ---------------------------------------------------------------------------


SHENGBTE_COMPUTE_FORCE_CONSTANTS_2 = OperationAdapterSpec(
    operation=compute_force_constants_2,
    adapter_name="shengbte",
    algorithmic_convention_overrides={
        # ShengBTE does not compute Φ²; it consumes FORCE_CONSTANTS_2ND in
        # phonopy format (or espresso.ifc2 in QE format). Symmetry handling
        # is whatever the upstream code applied. We declare spglib_auto
        # since both phonopy and QE typically use spglib reduction, but
        # the truthful answer is "depends on the input file's producer".
        "symmetry_group": "spglib_auto",
    },
    notes=(
        "ShengBTE is a downstream consumer: it reads FORCE_CONSTANTS_2ND "
        "(phonopy format, eV/Å²) or espresso.ifc2 (QE format). It does "
        "not compute force constants itself. The 'symmetry_group' value "
        "reflects what the upstream FC2 producer assumed, not ShengBTE's "
        "own choice."
    ),
)


SHENGBTE_COMPUTE_FORCE_CONSTANTS_3 = OperationAdapterSpec(
    operation=compute_force_constants_3,
    adapter_name="shengbte",
    algorithmic_convention_overrides={
        "symmetry_group": "spglib_auto",
    },
    notes=(
        "Analogous to the harmonic case: ShengBTE reads "
        "FORCE_CONSTANTS_3RD in the sparse triplet format described in "
        "the README, in eV/Å³. The companion thirdorder.py tool (separate "
        "package) is what typically generates this file with spglib-based "
        "triplet reduction."
    ),
)


SHENGBTE_COMPUTE_LINEWIDTH = OperationAdapterSpec(
    operation=compute_linewidth,
    adapter_name="shengbte",
    parameter_units={"broadening_sigma": "angular_THz"},
    algorithmic_convention_overrides={
        # ShengBTE's per-channel σ is computed by `base_sigma` in
        # Src/config.f90:462-476:
        #   σ_base = sqrt( Σ_ν=1..3 [(rlattvec_ν · Δv) / ngrid_ν]² / 6 )
        #   σ     = scalebroad × σ_base
        # This is the velocity-projection scheme — identical to kaldo's
        # default (kaldo/controllers/anharmonic.py:273-290) up to the
        # `scalebroad` prefactor. With scalebroad=1.0 (the default and
        # theoretically-guaranteed value per the README), ShengBTE and
        # kaldo-default compute the same σ for every scattering channel.
        "broadening_param": "adaptive_velocity_projection",
        "symmetry_group": "spglib_auto",
    },
    discretization_choices={
        "bz_summation": "symmetry_reduced",
        "scalebroad_default": "1.0",
    },
    notes=(
        "BTE.w_anharmonic is computed on the irreducible wedge with "
        "ShengBTE's adaptive Gaussian smearing (velocity-projection σ "
        "from config.f90:base_sigma, multiplied by &parameters scalebroad, "
        "default 1.0). Isotope scattering (BTE.w_isotopic) and boundary "
        "scattering (BTE.w_boundary) are separate output files combined "
        "into the total rate BTE.w by Matthiessen's rule. With "
        "scalebroad=1.0 the broadening is byte-equivalent to kaldo's "
        "default (third_bandwidth=None) adaptive mode."
    ),
)


SHENGBTE_SOLVE_BTE_DIRECT = OperationAdapterSpec(
    operation=solve_bte_direct,
    adapter_name="shengbte",
    algorithmic_convention_overrides={
        "symmetry_group": "spglib_auto",
    },
    discretization_choices={
        "collision_matrix_assembly": "irreducible_grid",
        "linear_solver": "shengbte_self_consistent_iteration",
        "convergence_eps_default": "1e-5",
        "max_iterations_default": "1000",
    },
    notes=(
        "When &flags convergence=.true. (the default), ShengBTE iterates "
        "F = F_RTA + collision-correction terms until ||κ_n - κ_{n-1}|| "
        "< eps. The fixed point coincides with the linearized BTE "
        "solution (the canonical direct_inverse). The convergence trail "
        "is preserved in BTE.kappa within each temperature directory."
    ),
)


# ---------------------------------------------------------------------------
# Input-state adapter specs: Temperature (in CONTROL) + FC2 + FC3.
# ShengBTE *consumes* these — it does not compute the dynamical matrix or
# eigenvectors as named outputs, so those remain dashed in the diagram.
# ---------------------------------------------------------------------------


SHENGBTE_TEMPERATURE = StateAdapterSpec(
    state=TEMPERATURE_STATE,
    adapter_name="shengbte",
    code_api={"temperature": "CONTROL &parameters T="},
    notes="Set in the CONTROL file under &parameters via T= (or T_min/T_max/T_step).",
)


SHENGBTE_FORCE_CONSTANTS_2 = StateAdapterSpec(
    state=FORCE_CONSTANTS_2,
    adapter_name="shengbte",
    code_api={"phi": "FORCE_CONSTANTS_2ND"},
    notes=(
        "Read from the FORCE_CONSTANTS_2ND file (phonopy ASCII format) "
        "or espresso.ifc2 (Quantum ESPRESSO format). In eV/Å². Supercell "
        "size declared via &crystal scell=."
    ),
)


SHENGBTE_FORCE_CONSTANTS_3 = StateAdapterSpec(
    state=FORCE_CONSTANTS_3,
    adapter_name="shengbte",
    code_api={"phi": "FORCE_CONSTANTS_3RD"},
    notes=(
        "Read from the FORCE_CONSTANTS_3RD file (sparse triplet format described "
        "in the ShengBTE README). Typically produced by thirdorder.py or "
        "thirdorder_espresso.py. In eV/Å³."
    ),
)


SHENGBTE_MOLAR_HEAT_CAPACITY = StateAdapterSpec(
    state=MOLAR_HEAT_CAPACITY,
    adapter_name="shengbte",
    code_api={"C_V_mol": "BTE.cv * V_cell * N_A"},
    notes=(
        "Derived from BTE.cv (volumetric, J/m³K) by multiplying by cell "
        "volume and Avogadro's number to get J/(K·mol of primitive cells)."
    ),
)


SHENGBTE_PHONON_DOS = StateAdapterSpec(
    state=PHONON_DOS,
    adapter_name="shengbte",
    code_api={"g": "BTE.dos"},
    notes="BTE.dos: phonon density of states vs angular frequency (rad/ps).",
)


SHENGBTE_GRUNEISEN = StateAdapterSpec(
    state=GRUNEISEN,
    adapter_name="shengbte",
    code_api={"gamma_G": "BTE.gruneisen"},
    notes=(
        "BTE.gruneisen: per-mode Grüneisen γ_qν, irreducible-wedge ordering. "
        "BTE.gruneisenVsT_total is the T-weighted total."
    ),
)


SHENGBTE_PHASE_SPACE_3PH = StateAdapterSpec(
    state=PHASE_SPACE_3PH,
    adapter_name="shengbte",
    code_api={"P3": "BTE.P3"},
    notes=(
        "BTE.P3: three-phonon kinematic phase space per irreducible (q, ν). "
        "BTE.P3_plus / BTE.P3_minus split absorption vs decay channels."
    ),
)
