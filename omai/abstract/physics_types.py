"""Registry of physics types as a closed enum.

Per Decision 8.1 (Lean-compatibility discipline #1), the registry is a closed union
implemented as an enum. Adding a new physics type means adding an entry here; downstream
code can pattern-match exhaustively. Open inheritance is deliberately avoided.
"""

from __future__ import annotations

from enum import Enum


class PhysicsType(str, Enum):
    """The physics types our abstract states can carry.

    Members are split into two groups by role (derived vs. parameter), although
    the type itself does not encode that distinction; provenance does. See
    `omai.abstract.state.AbstractState`.
    """

    # --- parameter types (no upstream operations modeled in Phase 1) ---
    POTENTIAL = "Potential"
    LATTICE_CONSTANT = "LatticeConstant"
    TEMPERATURE = "Temperature"
    PRESSURE = "Pressure"
    STRUCTURE = "Structure"

    # --- derived types in the thermal-transport scope ---
    FORCE_CONSTANT_OPERATOR = "ForceConstantOperator"
    FORCE_CONSTANTS = "ForceConstants"
    DYNAMICAL_MATRIX = "DynamicalMatrix"
    DISPERSION = "Dispersion"
    GROUP_VELOCITIES = "GroupVelocities"
    SCATTERING_RATES = "ScatteringRates"
    BOLTZMANN_SOLUTION = "BoltzmannSolution"
    THERMAL_CONDUCTIVITY = "ThermalConductivity"

    # --- experimental/measured observables ---
    MEASURED_THERMAL_CONDUCTIVITY = "MeasuredThermalConductivity"
