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
    description=(
        "Per-mode eigenvectors of the dynamical matrix. Phase- and "
        "degenerate-subspace-rotation freedom: not directly comparable "
        "across adapters."
    ),
)

GROUP_VELOCITY = HiddenState(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    fields=(Field("v", LENGTH_TIMES_FREQUENCY, indices=("alpha", "q", "nu")),),
    description=(
        "Per-mode group velocity. Inherits eigenvector-rotation freedom "
        "at degenerate ω; per-element comparison is not meaningful in "
        "general."
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
    description=(
        "Per-mode three-phonon linewidth. Per-element values depend on "
        "BZ-summation choice; contractions (ΣΓ over modes / over the BZ) "
        "are the gauge-invariant content."
    ),
)

MEAN_FREE_DISPLACEMENT_RTA = HiddenState(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement[bte_solver=rta]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    type_parameters={"bte_solver": "rta"},
    description=(
        "F = v / (2Γ) under the relaxation-time approximation. Inherits "
        "Linewidth's per-element looseness via the 1/Γ weighting."
    ),
)

THERMAL_CONDUCTIVITY_RTA = HiddenState(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[bte_solver=rta]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"bte_solver": "rta"},
    description=(
        "Lattice thermal conductivity from the RTA. The 1/Γ weighting is "
        "non-linear in Γ, so RTA κ inherits Linewidth's gauge-dependence "
        "(unlike the LBTE solution, which preserves gauge-invariance via "
        "off-diagonal collision terms)."
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
