"""Abstract nodes of the lattice thermal-transport DAG.

Twelve nodes, split into Observables (gauge-invariant, cross-code-comparable)
and HiddenStates (adapter-internal scaffolding, not cross-code-comparable
per-element). The taxonomy:

  Observables (8):
    Potential, Temperature       — sources, scalar / opaque
    ForceConstants[order=2/3]    — real-space tensors, well-defined
    DynamicalMatrix              — Bloch sum, well-defined in standard basis
    Frequency                    — eigenvalues, basis-invariant
    HeatCapacity                 — function of ω and T, well-defined
    ThermalConductivity          — contracted tensor, gauge-invariant

  HiddenStates (4):
    Eigenvectors                 — phase + degenerate-subspace rotation
    GroupVelocity                — inherits eigenvector rotation at degenerate ω
    Linewidth                    — BZ-summation redistribution; basis at degen.
    MeanFreeDisplacement         — inherits Linewidth's looseness via the BTE
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

THERMAL_CONDUCTIVITY_STATE = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
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

MEAN_FREE_DISPLACEMENT = HiddenState(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    description=(
        "Per-mode mean free displacement F_qν entering the BTE solution. "
        "Inherits Linewidth's per-element looseness via the BTE solver."
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
    MEAN_FREE_DISPLACEMENT,
    THERMAL_CONDUCTIVITY_STATE,
)
