"""Operator nodes of the lattice thermal-transport DAG.

Sixteen nodes, split into Observables (gauge-invariant, cross-code-comparable)
and HiddenStates (adapter-internal scaffolding, not cross-code-comparable
per-element). MeanFreeDisplacement and ThermalConductivity are parameterized
by the upstream `bte_solver` choice: the RTA variants are HiddenStates (the
approximation breaks gauge invariance), the direct-inverse / iterative
variants are Observables (the full LBTE solution preserves it).

  Observables (11):
    Potential, Temperature       — sources, scalar / opaque
    ForceConstants[order=2/3]    — real-space tensors, well-defined
    DynamicalMatrix              — Bloch sum, well-defined in standard basis
    Frequency                    — eigenvalues, basis-invariant
    HeatCapacity                 — per-mode c_qν(T), function of ω and T
    VolumetricHeatCapacity       — Σ_qν c_qν / (V_cell N_q), J/(m³K)
    MolarHeatCapacity            — N_A Σ_qν c_qν / N_q, J/(K·mol_of_cells)
    MeanFreeDisplacement[direct] — full LBTE solution; gauge-invariant
    ThermalConductivity[direct]  — contracted tensor; gauge-invariant

  HiddenStates (5):
    Eigenvectors                 — phase + degenerate-subspace rotation
    GroupVelocity                — inherits eigenvector rotation at degenerate ω
    Linewidth                    — BZ-summation redistribution
    MeanFreeDisplacement[rta]    — RTA closed form; inherits Linewidth's looseness
    ThermalConductivity[rta]     — RTA κ; inherits MFD[rta]'s looseness via 1/Γ
"""

from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_TEMPERATURE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_VOLUME,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.operator.physics_types import PhysicsType
from omai.operator.state import Field, HiddenState, Observable, State


# ---------------------------------------------------------------------------
# Observables (gauge-invariant; cross-code agreement required)
# ---------------------------------------------------------------------------

POTENTIAL = Observable(
    physics_type=PhysicsType.POTENTIAL,
    name="Potential",
    fields=(Field("potential", OPAQUE, indices=()),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = Observable(
    physics_type=PhysicsType.TEMPERATURE,
    name="Temperature",
    fields=(Field("temperature", TEMPERATURE, indices=()),),
)

FORCE_CONSTANTS_2 = Observable(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=2]",
    fields=(Field("phi", ENERGY_PER_LENGTH_SQUARED, indices=("i", "j", "R")),),
    type_parameters={"order": 2},
)

FORCE_CONSTANTS_3 = Observable(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=3]",
    fields=(Field("phi", ENERGY_PER_LENGTH_CUBED, indices=("i", "j", "k", "R", "R'")),),
    type_parameters={"order": 3},
)

BORN_CHARGES = Observable(
    physics_type=PhysicsType.BORN_CHARGES,
    name="BornCharges",
    fields=(Field("Z_star", DIMENSIONLESS, indices=("i", "alpha", "beta")),),
    description=(
        "Per-atom Born effective-charge tensor Z*_{i,αβ}, in units of the "
        "elementary charge e. Source-tier Observable: read from a BORN file "
        "or DFT linear-response output. Together with the macroscopic "
        "DielectricTensor ε∞ it parameterises the non-analytic correction "
        "(LO-TO splitting) for polar materials."
    ),
)

DIELECTRIC_TENSOR = Observable(
    physics_type=PhysicsType.DIELECTRIC_TENSOR,
    name="DielectricTensor",
    fields=(Field("epsilon_infinity", DIMENSIONLESS, indices=("alpha", "beta")),),
    description=(
        "Macroscopic (electronic) dielectric tensor ε∞ at infinite "
        "frequency, dimensionless. Source-tier Observable. Enters the "
        "non-analytic correction to D(q) at q→0."
    ),
)

BARE_DYNAMICAL_MATRIX = Observable(
    physics_type=PhysicsType.BARE_DYNAMICAL_MATRIX,
    name="BareDynamicalMatrix",
    fields=(Field("D_bare", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "Analytic Bloch sum of Φ²(R) — the dynamical matrix before any "
        "non-analytic correction is applied. Always produced by "
        "compute_dynamical_matrix(FC2). For non-polar materials the "
        "downstream DynamicalMatrix is identical to this (via identity_dm); "
        "for polar materials apply_nac_correction adds the q→0 non-analytic "
        "term involving BornCharges and DielectricTensor."
    ),
)

DYNAMICAL_MATRIX = Observable(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    fields=(Field("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Produced from BareDynamicalMatrix "
        "by either identity_dm (non-polar) or apply_nac_correction (polar). "
        "Entries are dimensionally frequency² (mass-weighted Hessian); codes "
        "typically store the matrix with eigenvalues that are ω², not ω."
    ),
)

FREQUENCY_STATE = Observable(
    physics_type=PhysicsType.FREQUENCY,
    name="Frequency",
    fields=(Field("omega", FREQUENCY, indices=("q", "nu")),),
)

HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.HEAT_CAPACITY,
    name="HeatCapacity",
    fields=(Field("c", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
)

VOLUMETRIC_HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.VOLUMETRIC_HEAT_CAPACITY,
    name="VolumetricHeatCapacity",
    fields=(Field("C_V_vol", ENERGY_PER_TEMPERATURE_PER_VOLUME, indices=()),),
    description=(
        "Total heat capacity per unit volume at temperature T, "
        "C_V/V = (1/V_cell N_q) Σ_qν c_qν(T). Scalar in (q, ν); a function "
        "of T only. ShengBTE emits this directly as BTE.cv; codes that "
        "emit per-mode HeatCapacity reach it via the contraction edge."
    ),
)

MOLAR_HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.MOLAR_HEAT_CAPACITY,
    name="MolarHeatCapacity",
    fields=(Field("C_V_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, indices=()),),
    description=(
        "Heat capacity per mole of primitive unit cells at temperature T, "
        "C_V_mol = (N_A / N_q) Σ_qν c_qν(T). Phonopy emits this as part "
        "of its harmonic thermal_properties output (J/K/mol). Codes that "
        "emit per-mode HeatCapacity reach it via the contraction edge."
    ),
)

THERMAL_CONDUCTIVITY_DIRECT = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[bte_solver=direct_inverse]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"bte_solver": "direct_inverse"},
    description=(
        "Lattice thermal conductivity from the direct/iterative LBTE solver. "
        "Gauge-invariant: the collision matrix's off-diagonals preserve "
        "invariance under per-mode Γ redistribution."
    ),
)

MEAN_FREE_DISPLACEMENT_DIRECT = Observable(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement[bte_solver=direct_inverse]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    type_parameters={"bte_solver": "direct_inverse"},
    description=(
        "F obtained from the full linearized BTE (direct inversion or "
        "iterative solution). Gauge-invariant by construction."
    ),
)


# ---------------------------------------------------------------------------
# HiddenStates (gauge-dependent; not cross-code comparable per-element)
# ---------------------------------------------------------------------------

EIGENVECTORS = HiddenState(
    physics_type=PhysicsType.EIGENVECTORS,
    name="Eigenvectors",
    fields=(Field("e", DIMENSIONLESS, indices=("i", "q", "nu")),),
    gauge_group="U(1)_per_mode × U(d)_per_degenerate_subspace",
    kind="scaffolding",
    gauge_invariant_contractions=("Frequency", "ThermalConductivity[bte_solver=direct_inverse]"),
    description=(
        "Per-mode eigenvectors of the dynamical matrix. U(1) phase freedom "
        "per mode plus U(d) rotation within each degenerate subspace; "
        "per-element values are not directly comparable across adapters. "
        "Contracted gauge-invariants live in Frequency (eigenvalues) and κ_LBTE."
    ),
)

GROUP_VELOCITY = HiddenState(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    fields=(Field("v", LENGTH_TIMES_FREQUENCY, indices=("alpha", "q", "nu")),),
    gauge_group="U(d)_per_degenerate_subspace_on_eigenvectors",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode group velocity. Per-mode v is invariant under U(1) phase, "
        "but inherits the U(d) rotation freedom at degenerate ω. Contracted "
        "gauge-invariants live in κ (Σ c v² τ over the BZ)."
    ),
)

LINEWIDTH = HiddenState(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode three-phonon linewidth. Per-element values depend on "
        "BZ-summation choice (a permutation gauge: weights redistribute "
        "between modes but conserve the total). Contractions (ΣΓ, κ_LBTE) "
        "are the gauge-invariant content."
    ),
)

PHONON_DOS = Observable(
    physics_type=PhysicsType.PHONON_DOS,
    name="PhononDOS",
    fields=(Field("g", FREQUENCY, indices=("omega",)),),
    description=(
        "Density of states g(ω) = (1/N_q) Σ_qν δ(ω − ω_qν). A 1-D array "
        "binned in ω. Gauge-invariant: ω_qν are basis-independent and the "
        "sum over (q, ν) is uniformly weighted."
    ),
)

GRUNEISEN = Observable(
    physics_type=PhysicsType.GRUNEISEN,
    name="Gruneisen",
    fields=(Field("gamma_G", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Mode Grüneisen parameter γ_qν = −(V/ω_qν) ∂ω_qν/∂V. Quantifies "
        "anharmonicity-driven volume dependence; computed from FC2 and FC3 "
        "via the standard Maradudin-Fein expression. Dimensionless."
    ),
)

PHASE_SPACE_3PH = Observable(
    physics_type=PhysicsType.PHASE_SPACE_3PH,
    name="PhaseSpace3Phonon",
    fields=(Field("P3", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Three-phonon phase space P3_qν = (1/N) Σ_q'ν'ν'' [δ(ω−ω'−ω'') + "
        "2 δ(ω+ω'−ω'')] available for scattering channels involving mode "
        "(q, ν). Doesn't include |V₃|² — purely the kinematic volume."
    ),
)

MEAN_FREE_DISPLACEMENT_RTA = HiddenState(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement[bte_solver=rta]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    type_parameters={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),  # terminal — no Observable downstream
    description=(
        "F = v / (2Γ) under the relaxation-time approximation. The 1/Γ "
        "non-linearity is the gauge-breaking step. Approximation HiddenState: "
        "terminal; there is no downstream operation that contracts it into "
        "a gauge-invariant Observable. The LBTE branch (MFD[direct_inverse]) "
        "is the gauge-invariant analogue."
    ),
)

THERMAL_CONDUCTIVITY_RTA = HiddenState(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[bte_solver=rta]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),
    description=(
        "Lattice thermal conductivity from the RTA. The 1/Γ weighting is "
        "non-linear in Γ, so RTA κ inherits Linewidth's gauge-dependence "
        "(unlike the LBTE solution, which preserves gauge-invariance via "
        "off-diagonal collision terms). Terminal approximation HiddenState."
    ),
)


NODES: tuple[State, ...] = (
    POTENTIAL,
    TEMPERATURE_STATE,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    BARE_DYNAMICAL_MATRIX,
    DYNAMICAL_MATRIX,
    FREQUENCY_STATE,

    EIGENVECTORS,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    VOLUMETRIC_HEAT_CAPACITY,
    MOLAR_HEAT_CAPACITY,
    LINEWIDTH,
    PHONON_DOS,
    GRUNEISEN,
    PHASE_SPACE_3PH,
    MEAN_FREE_DISPLACEMENT_RTA,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_DIRECT,
)
