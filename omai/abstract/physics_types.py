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

    # --- parameter / source types (outputs of nullary `provide_*` operations) ---
    POTENTIAL = "Potential"
    TEMPERATURE = "Temperature"
    LATTICE_CONSTANT = "LatticeConstant"
    PRESSURE = "Pressure"
    STRUCTURE = "Structure"

    # --- derived types in the thermal-transport scope ---
    # Each is one observable = one node in the abstract DAG.
    FORCE_CONSTANTS = "ForceConstants"            # parameterized by order (=2 or =3)
    DYNAMICAL_MATRIX = "DynamicalMatrix"
    FREQUENCY = "Frequency"
    EIGENVECTORS = "Eigenvectors"
    GROUP_VELOCITY = "GroupVelocity"
    HEAT_CAPACITY = "HeatCapacity"
    LINEWIDTH = "Linewidth"
    MEAN_FREE_DISPLACEMENT = "MeanFreeDisplacement"
    THERMAL_CONDUCTIVITY = "ThermalConductivity"

    # --- experimental/measured observables ---
    MEASURED_THERMAL_CONDUCTIVITY = "MeasuredThermalConductivity"
