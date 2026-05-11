"""Abstract nodes of the lattice thermal-transport DAG.

Fourteen nodes, split into Observables (gauge-invariant, cross-code-comparable)
and HiddenStates (adapter-internal scaffolding, not cross-code-comparable
per-element). MeanFreeDisplacement and ThermalConductivity are parameterized
by the upstream `bte_solver` choice: the RTA variants are HiddenStates (the
approximation breaks gauge invariance), the direct-inverse / iterative
variants are Observables (the full LBTE solution preserves it).

  Observables (9):
    Potential, Temperature       — sources, scalar / opaque
    ForceConstants[order=2/3]    — real-space tensors, well-defined
    DynamicalMatrix              — Bloch sum, well-defined in standard basis
    Frequency                    — eigenvalues, basis-invariant
    HeatCapacity                 — function of ω and T, well-defined
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

from omai.abstract.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.abstract.physics_types import PhysicsType
from omai.abstract.state import Field, HiddenState, Observable, State


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

DYNAMICAL_MATRIX = Observable(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    fields=(Field("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Entries are dimensionally "
        "frequency² (mass-weighted Hessian); codes typically store the "
        "matrix with eigenvalues that are ω², not ω."
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
    DYNAMICAL_MATRIX,
    FREQUENCY_STATE,
    EIGENVECTORS,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT_RTA,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_DIRECT,
)
