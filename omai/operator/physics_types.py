"""Registry of physics types as a closed enum.

Per Decision 8.1 (Lean-compatibility discipline #1), the registry is a closed union
implemented as an enum. Adding a new physics type means adding an entry here; downstream
code can pattern-match exhaustively. Open inheritance is deliberately avoided.
"""

from __future__ import annotations

from enum import Enum


class PhysicsType(str, Enum):
    """The physics types our operator states can carry.

    Members are split into two groups by role (derived vs. parameter), although
    the type itself does not encode that distinction; provenance does. See
    `omai.operator.state.SymbolicState`.
    """

    # --- parameter / source types (outputs of nullary `provide_*` operations) ---
    POTENTIAL = "Potential"
    TEMPERATURE = "Temperature"
    LATTICE_CONSTANT = "LatticeConstant"
    PRESSURE = "Pressure"
    STRUCTURE = "Structure"
    BORN_CHARGES = "BornCharges"                  # per-atom effective-charge tensor Z*
    DIELECTRIC_TENSOR = "DielectricTensor"        # macroscopic ε∞

    # --- derived types in the thermal-transport scope ---
    # Each is one observable = one node in the operator DAG.
    FORCE_CONSTANTS = "ForceConstants"            # parameterized by order (=2 or =3)
    BARE_DYNAMICAL_MATRIX = "BareDynamicalMatrix"
    DYNAMICAL_MATRIX = "DynamicalMatrix"
    FREQUENCY = "Frequency"
    EIGENVECTORS = "Eigenvectors"
    GROUP_VELOCITY = "GroupVelocity"
    HEAT_CAPACITY = "HeatCapacity"
    VOLUMETRIC_HEAT_CAPACITY = "VolumetricHeatCapacity"
    MOLAR_HEAT_CAPACITY = "MolarHeatCapacity"
    HELMHOLTZ_FREE_ENERGY = "HelmholtzFreeEnergy"
    ENTROPY = "Entropy"
    INTERNAL_ENERGY = "InternalEnergy"
    MOLAR_HELMHOLTZ_FREE_ENERGY = "MolarHelmholtzFreeEnergy"
    MOLAR_ENTROPY = "MolarEntropy"
    MOLAR_INTERNAL_ENERGY = "MolarInternalEnergy"
    LINEWIDTH = "Linewidth"                       # parameterized by channel
    ISOTOPE_ABUNDANCES = "IsotopeAbundances"
    MEAN_FREE_DISPLACEMENT = "MeanFreeDisplacement"
    THERMAL_CONDUCTIVITY = "ThermalConductivity"
    CUMULATIVE_THERMAL_CONDUCTIVITY = "CumulativeKappa"
    PHONON_DOS = "PhononDOS"
    GRUNEISEN = "Gruneisen"
    PHASE_SPACE_3PH = "PhaseSpace3Phonon"

    # --- experimental/measured observables ---
    MEASURED_THERMAL_CONDUCTIVITY = "MeasuredThermalConductivity"
