r"""Symbol-dimension registry of the thermal-transport domain.

Registers, into the core registry (`omai.operator.dimcheck`), the physical
dimension of each unambiguous sympy base symbol the domain's edge formulas
use. Imported for its side effect by
`omai.thermal_transport.operator.__init__`, next to the vocabulary module,
so any consumer of the domain's edges can run the dimensional gate.

Discipline: never guess a symbol's dimension. Symbols whose base name is
ambiguous across two physical quantities are deliberately left
unregistered, which makes any edge that needs them SKIPPED (unknown), not
wrongly flagged. The intentionally-skipped symbols and why:

  * ``M``          - both the atomic-mass IndexedBase (mass) and the MSD
                     field symbol (length^2); registering either is wrong
                     for the other. Left unknown.
  * ``e``          - both the phonon eigenvector (dimensionless) and the
                     per-mode internal-energy field (energy). Ambiguous
                     globally, so left unregistered; edges touching the
                     InternalEnergy / MolarInternalEnergy spaces resolve it
                     to ENERGY via a per-edge ``local`` override in dimcheck
                     (eigenvectors never enter those formulas).
  * ``g``          - both the phonon DOS and the isotope mass-variance
                     factor. Ambiguous.
  * ``D``, ``D^{bare}`` - the dynamical matrix. Its field dimension is
                     frequency *squared* (the mass-weighted Hessian, whose
                     eigenvalues are omega^2: the dispersion equation reads
                     ``Sum(D e) = omega^2 e``), so the DynamicalMatrix /
                     BareDynamicalMatrix fields declare FREQUENCY_SQUARED.
                     The base name ``D`` is NOT registered globally here
                     because the materials domain registers ``D`` as
                     diffusivity (a different physical D) and the global
                     registry holds one dimension per base name. The two
                     never collide because dimcheck supplies a per-edge
                     ``local`` override binding ``D``/``D^{bare}`` to
                     FREQUENCY_SQUARED on the thermal DM-touching edges,
                     while materials edges keep the global diffusivity ``D``.
  * ``Jcorr``, ``Cv`` - the heat-current ACF and velocity-ACF kinds are
                     declared OPAQUE on their spaces; opaque never enters
                     algebra.
"""

from __future__ import annotations

from omai.operator.dimcheck import register_symbol_dimensions
from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_VOLUME,
    ENERGY_TIMES_LENGTH_PER_TIME,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    MASS,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
    TIME,
    VOLUME,
)

# hbar carries action (energy x time); N_A carries per-mole (composed from
# the molar-energy dimension over energy so no bare MOLE constant is needed).
_ACTION = ENERGY * TIME
_PER_MOLE = ENERGY_PER_MOLE / ENERGY

register_symbol_dimensions({
    # Universal thermodynamic constants and the BZ / cell counters.
    "T": TEMPERATURE,
    "k_B": ENERGY_PER_TEMPERATURE,
    r"\hbar": _ACTION,
    "N_A": _PER_MOLE,
    "V_{cell}": VOLUME,
    "N": DIMENSIONLESS,
    "N_q": DIMENSIONLESS,
    "pi": DIMENSIONLESS,
    "m": MASS,
    # Phonon spectrum and derived per-mode quantities.
    r"\omega": FREQUENCY,
    r"\omega_c": FREQUENCY,
    "c": ENERGY_PER_TEMPERATURE,
    "v": LENGTH_TIMES_FREQUENCY,
    "F": LENGTH,
    "f": ENERGY,
    "s": ENERGY_PER_TEMPERATURE,
    # Linewidths (scattering rates), all channels.
    r"\Gamma": FREQUENCY,
    r"\Gamma^{anh}": FREQUENCY,
    r"\Gamma^{iso}": FREQUENCY,
    r"\Gamma^{bnd}": FREQUENCY,
    r"\Gamma^{tot}": FREQUENCY,
    # Thermal conductivity, all variants and channels.
    r"\kappa": THERMAL_CONDUCTIVITY,
    r"\kappa^{W,pop}": THERMAL_CONDUCTIVITY,
    r"\kappa^{W,coh}": THERMAL_CONDUCTIVITY,
    r"\kappa^W": THERMAL_CONDUCTIVITY,
    r"\kappa^{QHGK}": THERMAL_CONDUCTIVITY,
    r"\kappa^{MD}": THERMAL_CONDUCTIVITY,
    r"\kappa^{cum}_\omega": THERMAL_CONDUCTIVITY,
    r"\kappa^{cum}_\Lambda": THERMAL_CONDUCTIVITY,
    # Molar thermodynamics.
    r"F_{mol}": ENERGY_PER_MOLE,
    r"S_{mol}": ENERGY_PER_TEMPERATURE_PER_MOLE,
    r"E_{mol}": ENERGY_PER_MOLE,
    r"C_V^{vol}": ENERGY_PER_TEMPERATURE_PER_VOLUME,
    r"C_V^{mol}": ENERGY_PER_TEMPERATURE_PER_MOLE,
    # Dimensionless derived observables.
    r"\gamma_G": DIMENSIONLESS,
    "P_3": DIMENSIONLESS,
    # Lengths and length-scale thresholds.
    r"\Lambda_c": LENGTH,
    "L": LENGTH,
    "r": LENGTH,
    # Times: MD timestep, correlation lag, GK integration bounds.
    r"\Delta t": TIME,
    r"\tau": TIME,
    r"\tau_{max}": TIME,
    r"\tau_{min}": TIME,
    # Heat current density (energy x velocity per volume, spelled energy x
    # length / time on the dimension).
    "J": ENERGY_TIMES_LENGTH_PER_TIME,
    # Force constants.
    r"\Phi^{(2)}": ENERGY_PER_LENGTH_SQUARED,
    r"\Phi^{(3)}": ENERGY_PER_LENGTH_CUBED,
    # Dimensionless response tensors.
    r"Z^*": DIMENSIONLESS,
    r"\varepsilon_\infty": DIMENSIONLESS,
})
