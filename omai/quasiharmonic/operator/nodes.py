r"""Operator nodes of the quasi-harmonic domain.

Finite-temperature thermodynamics from the quasi-harmonic approximation (the
phonopy/LAMMPS delta scan, AtomisticSkills arXiv 2605.24002: matcalc QHACalc over
phonopy.PhonopyQHA, driven by the mat-qha-thermal-expansion skill). Four
ObservableSpaces, the constant-PRESSURE (Gibbs side) partner of the harmonic
constant-VOLUME (Helmholtz side) phonon thermodynamics already on the map.

Node table:

  Node                   quantity tag              dimension              indices
  ---------------------  ------------------------  ---------------------  -------
  QHAGibbsEnergy         qha_gibbs_energy          ENERGY_PER_MOLE        ()
  ThermalExpansion       thermal_expansion         THERMAL_EXPANSIVITY    ()
  HeatCapacityConstantP  heat_capacity_constant_p  ENERGY_PER_TEMPERATURE_PER_MOLE  ()
  ThermalGruneisen       thermal_gruneisen         DIMENSIONLESS          ()

The constant-P / constant-V guardrail (load-bearing), enforced by DISTINCT NAMES.
Node identity is NAME-based: omai/operator/space.py Space.__hash__/__eq__ hash and
compare on the node NAME, and the derived quantity tag (the name in snake_case)
is what enters the identity hash. The dimension exponent vector does no separating
work. So a QHA node stays distinct from its harmonic sibling PURELY by carrying a
fresh name / quantity tag; the constant-pressure, per-phonopy-cell, EOS-scan facts
live in the DESCRIPTION prose, exactly as the thermochemistry Molar* guardrail
(omai/thermochemistry/operator/nodes.py) records the CALPHAD basis in prose, not
in a composite identity key.

  * QHAGibbsEnergy REUSES the ENERGY_PER_MOLE exponent vector (1,2,-2,0,-1,0,0)
    shared with the phonopy MolarHelmholtzFreeEnergy (constant-V, per mole of the
    phonopy cell) and the CALPHAD MolarGibbsEnergy (constant-P, per mole of atoms,
    assessed). It is a THIRD region of that mole-energy space: constant-P (like
    CALPHAD) but per mole of the phonopy cell and a phonon-gas + EOS producer (like
    phonopy). Kept apart from BOTH by its qha_gibbs_energy tag; it must never alias
    either.
  * HeatCapacityConstantP REUSES the ENERGY_PER_TEMPERATURE_PER_MOLE exponent
    vector of the harmonic MolarHeatCapacity (C_V). It is C_P, which differs from
    C_V by C_P - C_V = alpha^2 * B * V * T (the expansion / anharmonic correction)
    and by the thermodynamic potential (constant-P vs constant-V). Kept apart by
    its heat_capacity_constant_p tag; if it reused the C_V node name it would
    silently alias.
  * ThermalGruneisen is a T-indexed SCALAR (here served with no index; a function
    of T only), the heat-capacity-weighted average of the mode gammas. It MUST NOT
    alias the existing MODE Gruneisen (omai/thermal_transport/operator/nodes.py:
    field gamma_G, DIMENSIONLESS, indices (q,nu), FC2/FC3-produced): different
    index signature, different producer, kept apart by its thermal_gruneisen tag.
    The honest relationship is a contraction edge mode-Gruneisen -> ThermalGruneisen.

Serving basis. The QHA thermodynamics are per mole of the phonopy CELL passed to
PhonopyQHA (its natom); in the matcalc path PhononCalc primitivizes the structure,
so the basis is the primitive/unit cell, NOT per formula unit (phonopy's
divide_by_Z defaults False) and NOT per mole of atoms (the CALPHAD basis). To
cross-code to CALPHAD, divide by atoms-per-cell. matcalc serves G in kJ/mol,
alpha in 1/K, C_P in J/(K*mol), gamma dimensionless (one result dict, mixed bases;
_qha.py:298-302).
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    THERMAL_EXPANSIVITY,
)
from omai.operator.space import Field, ObservableSpace, Space

QHA_GIBBS_ENERGY = ObservableSpace(
    name="QHAGibbsEnergy",
    fields=(Field("G_qha", ENERGY_PER_MOLE, indices=()),),
    tier="Quasi-harmonic",
    description=(
        "Quasi-harmonic Gibbs energy G(T) at constant pressure: the Legendre "
        "transform G = min_V[F(V,T) + pV] of the phonon Helmholtz surface F(V,T) "
        "minimized over volume at each temperature, phonopy PhonopyQHA's "
        "gibbs_temperature (qha/core.py:312), matcalc QHACalc's "
        "gibbs_free_energies. PER MOLE OF THE PHONOPY CELL (its natom; matcalc "
        "primitivizes the structure, so per primitive/unit cell, NOT per formula "
        "unit and NOT per mole of atoms), CONSTANT PRESSURE, from a phonon-gas "
        "F(V,T) plus an equation-of-state volume scan. J/mol, dimension "
        "ENERGY_PER_MOLE (1,2,-2,0,-1,0,0). EXPLICITLY DISTINCT (a distinct uid by "
        "the qha_gibbs_energy tag) from BOTH the CALPHAD MolarGibbsEnergy "
        "(constant-P but per mole of ATOMS, assessed Gibbs minimization) AND the "
        "phonopy MolarHelmholtzFreeEnergy (per mole of the phonopy cell but "
        "constant VOLUME, Helmholtz side): same ENERGY_PER_MOLE exponent vector, "
        "different potential / basis / producer, kept apart by the name / quantity "
        "tag (the constant-P / constant-V guardrail; identity is name-based, the "
        "basis lives in this prose). matcalc serves it in kJ/mol (_qha.py:299; the "
        "canonical J/mol carries a 1000 factor). To cross-code to a CALPHAD G_m "
        "(per mole of atoms) divide by atoms-per-cell."
    ),
)

THERMAL_EXPANSION = ObservableSpace(
    name="ThermalExpansion",
    fields=(Field("alpha_V", THERMAL_EXPANSIVITY, indices=()),),
    tier="Quasi-harmonic",
    description=(
        "Volumetric thermal expansion coefficient alpha(T) = (1/V)(dV/dT)_P from "
        "the temperature dependence of the QHA equilibrium volume V(T) at the "
        "Gibbs minimum, phonopy PhonopyQHA's thermal_expansion (qha/core.py:291), "
        "matcalc QHACalc's thermal_expansion_coefficients. Dimension "
        "THERMAL_EXPANSIVITY (0,0,0,-1,0,0,0) = 1/K, the map's first pure "
        "inverse-temperature dimension. Related to the mode Gruneisen and the "
        "constant-volume heat capacity by alpha = gamma_thermal * C_V / (B V) "
        "(the thermodynamic Gruneisen relation). matcalc serves it in 1/K "
        "(_qha.py:298), the canonical per_kelvin. Scalar, a function of T only."
    ),
)

HEAT_CAPACITY_CONSTANT_P = ObservableSpace(
    name="HeatCapacityConstantP",
    fields=(Field("C_P_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, indices=()),),
    tier="Quasi-harmonic",
    description=(
        "Constant-pressure molar heat capacity C_P(T) along the QHA equilibrium "
        "path, phonopy PhonopyQHA's heat_capacity_P_polyfit (qha/core.py:337; the "
        "numerical estimator at :326 is the alternative), matcalc QHACalc's "
        "heat_capacity_P. PER MOLE OF THE PHONOPY CELL, at CONSTANT PRESSURE. "
        "REUSES the ENERGY_PER_TEMPERATURE_PER_MOLE exponent vector "
        "(1,2,-2,-1,-1,0,0) = J/(K*mol) of the harmonic MolarHeatCapacity (C_V), "
        "but is a DISTINCT node (a distinct uid by the heat_capacity_constant_p "
        "tag): C_P is the constant-pressure heat capacity, differing from the "
        "constant-volume C_V by C_P - C_V = alpha^2 * B * V * T (the expansion "
        "correction) and by the thermodynamic potential. Same dimension, different "
        "quantity, kept apart by the name / quantity tag (never molar_heat_capacity); "
        "the constant-pressure fact lives in this prose. matcalc serves it in "
        "J/(K*mol) (_qha.py:301), the canonical J_per_K_per_mol. Scalar, a function "
        "of T only."
    ),
)

THERMAL_GRUNEISEN = ObservableSpace(
    name="ThermalGruneisen",
    fields=(Field("gamma_thermal", DIMENSIONLESS, indices=()),),
    tier="Quasi-harmonic",
    description=(
        "Macroscopic (thermal) Gruneisen parameter gamma(T) = alpha B V / C_V, a "
        "single SCALAR per temperature: the heat-capacity-weighted thermodynamic "
        "average of the mode Gruneisen parameters, phonopy PhonopyQHA's "
        "gruneisen_temperature (qha/core.py:355), matcalc QHACalc's "
        "gruneisen_parameters. Dimensionless. EXPLICITLY DISTINCT (a distinct uid "
        "by the thermal_gruneisen tag) from the existing MODE Gruneisen "
        "(field gamma_G, DIMENSIONLESS, indices (q,nu), computed from FC2/FC3 via "
        "the Maradudin-Fein expression): the mode node is (q,nu)-indexed and "
        "FC3-produced, this is a T-only scalar from the EOS volume scan, a genuine "
        "CONTRACTION of the mode gammas (the honest edge mode-Gruneisen -> "
        "ThermalGruneisen). Same DIMENSIONLESS dimension, different index "
        "signature and producer, kept apart by the name / quantity tag. Scalar, a "
        "function of T only."
    ),
)

NODES: tuple[Space, ...] = (
    QHA_GIBBS_ENERGY,
    THERMAL_EXPANSION,
    HEAT_CAPACITY_CONSTANT_P,
    THERMAL_GRUNEISEN,
)
