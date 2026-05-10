"""Abstract states (nodes) of the lattice thermal-transport DAG.

Twelve State instances declaring the typed witnesses that flow through the
DAG: their physics types, observables (with index signatures), and any
state-level conventions. No sympy, no calculation — that lives in `edges`.
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
from omai.abstract.state import Observable, State


POTENTIAL = State(
    physics_type=PhysicsType.POTENTIAL,
    name="Potential",
    observables=(Observable("potential", OPAQUE, indices=()),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = State(
    physics_type=PhysicsType.TEMPERATURE,
    name="Temperature",
    observables=(Observable("temperature", TEMPERATURE, indices=()),),
)

FORCE_CONSTANTS_2 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=2]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_SQUARED, indices=("i", "j", "R")),),
    type_parameters={"order": 2},
)

FORCE_CONSTANTS_3 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=3]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_CUBED, indices=("i", "j", "k", "R", "R'")),),
    type_parameters={"order": 3},
)

DYNAMICAL_MATRIX = State(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    observables=(Observable("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Entries are dimensionally "
        "frequency² (mass-weighted Hessian); codes typically store the "
        "matrix with eigenvalues that are ω², not ω."
    ),
)

FREQUENCY_STATE = State(
    physics_type=PhysicsType.FREQUENCY,
    name="Frequency",
    observables=(Observable("omega", FREQUENCY, indices=("q", "nu")),),
)

EIGENVECTORS = State(
    physics_type=PhysicsType.EIGENVECTORS,
    name="Eigenvectors",
    observables=(Observable("e", DIMENSIONLESS, indices=("i", "q", "nu")),),
    description=(
        "Per-mode eigenvectors of the dynamical matrix. Phase- and "
        "degenerate-subspace-rotation freedom: not directly comparable across "
        "adapters at the per-mode level."
    ),
)

GROUP_VELOCITY = State(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    observables=(Observable("v", LENGTH_TIMES_FREQUENCY, indices=("alpha", "q", "nu")),),
)

HEAT_CAPACITY = State(
    physics_type=PhysicsType.HEAT_CAPACITY,
    name="HeatCapacity",
    observables=(Observable("c", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
)

LINEWIDTH = State(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth",
    observables=(Observable("Gamma", FREQUENCY, indices=("q", "nu")),),
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
)

MEAN_FREE_DISPLACEMENT = State(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement",
    observables=(Observable("F", LENGTH, indices=("alpha", "q", "nu")),),
    description="Per-mode mean free displacement F_qν entering the BTE solution.",
)

THERMAL_CONDUCTIVITY_STATE = State(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity",
    observables=(Observable("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
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
