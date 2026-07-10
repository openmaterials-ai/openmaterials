r"""phonopy (PhonopyQHA) adapter specs for the quasi-harmonic domain.

The quasi-harmonic thermodynamics are produced by phonopy.PhonopyQHA, driven by
matcalc QHACalc (which wraps PhonopyQHA over an F(V,T) volume scan) and exercised
by the AtomisticSkills mat-qha-thermal-expansion skill (arXiv 2605.24002,
scripts/calculate_qha.py:33-41, eos='vinet', an 11-volume scan 0.95..1.05). The
matcalc QHACalc driver carries no rail of its own; its result-dict keys and the
volume-scan discretization ride these phonopy operator specs.

The PhonopyQHA property -> matcalc result key -> map node mapping (phonopy 3.5.1
qha/core.py; matcalc 0.5.1 _qha.py):

  property                    core.py  matcalc key                     unit         node
  --------------------------  -------  ------------------------------  -----------  ---------------------
  gibbs_temperature           312      gibbs_free_energies             kJ/mol       QHAGibbsEnergy
  thermal_expansion           291      thermal_expansion_coefficients  1/K          ThermalExpansion
  heat_capacity_P_polyfit     337      heat_capacity_P                 J/(K*mol)    HeatCapacityConstantP
  gruneisen_temperature       355      gruneisen_parameters            dimensionless ThermalGruneisen
  bulk_modulus_temperature    319      bulk_modulus_P                  GPa          BulkModulus (QHA route)

Basis (load-bearing). The QHA thermodynamics are per mole of the phonopy CELL
passed to PhonopyQHA (its natom). phonopy labels the harmonic thermal-properties
output 'per unit cell (natom)' (thermal_properties.py:664); the per-formula-unit
reduction needs divide_by_Z=True whose DEFAULT is False, and matcalc / PhononCalc
does NOT set it. In the matcalc path PhononCalc primitivizes the structure, so the
cell is the primitive / unit cell, NOT per formula unit and NOT per mole of atoms.
To cross-code to a CALPHAD per-mole-of-atoms quantity, divide by atoms-per-cell (Z).

Units (matcalc _qha.py:298-302 mixes bases in one result dict): Gibbs kJ/mol,
alpha 1/K, C_P J/(K*mol), gamma dimensionless, B GPa. The QHACalc.pressure axis is
GPa (not the eV/A^3 of MDCalc).
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.mechanics.operator.nodes import BULK_MODULUS
from omai.quasiharmonic.operator.edges import (
    compute_bulk_modulus_qha,
    compute_heat_capacity_p,
    compute_qha_gibbs,
    compute_thermal_expansion,
    contract_thermal_gruneisen,
)
from omai.quasiharmonic.operator.nodes import (
    HEAT_CAPACITY_CONSTANT_P,
    QHA_GIBBS_ENERGY,
    THERMAL_EXPANSION,
    THERMAL_GRUNEISEN,
)


PHONOPY_QHA_GIBBS_ENERGY = SpaceRepresentationSpec(
    space=QHA_GIBBS_ENERGY,
    representation_name="phonopy",
    observable_units={"G_qha": "kJ_per_mol"},
    code_api={"G_qha": "PhonopyQHA.gibbs_temperature (matcalc QHACalc 'gibbs_free_energies')"},
    notes=(
        "PhonopyQHA.gibbs_temperature (qha/core.py:312), surfaced by matcalc "
        "QHACalc as result['gibbs_free_energies'] in kJ/mol (_qha.py:299; the "
        "canonical J/mol carries the 1000 factor). PER MOLE OF THE PHONOPY CELL "
        "(natom; divide_by_Z default False, so NOT per formula unit; matcalc "
        "primitivizes, so the primitive/unit cell, NOT per mole of atoms). "
        "Constant pressure, from the F(V,T) phonon-gas surface minimized over an "
        "EOS volume scan (eos='vinet' default, 11 volumes 0.95..1.05). Distinct "
        "from the CALPHAD MolarGibbsEnergy (per mole of atoms) and the phonopy "
        "MolarHelmholtzFreeEnergy (constant volume); divide by atoms-per-cell to "
        "cross-code to CALPHAD."
    ),
)


PHONOPY_THERMAL_EXPANSION = SpaceRepresentationSpec(
    space=THERMAL_EXPANSION,
    representation_name="phonopy",
    observable_units={"alpha_V": "per_kelvin"},
    code_api={"alpha_V": "PhonopyQHA.thermal_expansion (matcalc QHACalc 'thermal_expansion_coefficients')"},
    notes=(
        "PhonopyQHA.thermal_expansion (qha/core.py:291), matcalc "
        "result['thermal_expansion_coefficients'] in 1/K (_qha.py:298). The "
        "volumetric coefficient alpha(T) = (1/V)(dV/dT)_P from V(T) at the QHA "
        "Gibbs minimum (volume_temperature at core.py:305 is the upstream V(T)). "
        "One value per temperature on the requested T-grid."
    ),
)


PHONOPY_HEAT_CAPACITY_CONSTANT_P = SpaceRepresentationSpec(
    space=HEAT_CAPACITY_CONSTANT_P,
    representation_name="phonopy",
    observable_units={"C_P_mol": "J_per_K_per_mol"},
    code_api={"C_P_mol": "PhonopyQHA.heat_capacity_P_polyfit (matcalc QHACalc 'heat_capacity_P')"},
    notes=(
        "PhonopyQHA.heat_capacity_P_polyfit (qha/core.py:337; matcalc defaults the "
        "polyfit estimator, _qha.py:271; the numerical estimator at core.py:326 is "
        "the alternative-producer sibling), matcalc result['heat_capacity_P'] in "
        "J/(K*mol) (_qha.py:301). PER MOLE OF THE PHONOPY CELL, constant pressure. "
        "The constant-P partner of the harmonic MolarHeatCapacity (C_V); they "
        "differ by C_P - C_V = alpha^2 B V T. Same J/(K*mol) unit as the C_V node, "
        "a distinct node by the heat_capacity_constant_p tag."
    ),
)


PHONOPY_THERMAL_GRUNEISEN = SpaceRepresentationSpec(
    space=THERMAL_GRUNEISEN,
    representation_name="phonopy",
    observable_units={"gamma_thermal": "dimensionless"},
    code_api={"gamma_thermal": "PhonopyQHA.gruneisen_temperature (matcalc QHACalc 'gruneisen_parameters')"},
    notes=(
        "PhonopyQHA.gruneisen_temperature (qha/core.py:355), matcalc "
        "result['gruneisen_parameters'], dimensionless (_qha.py:302). The single "
        "macroscopic gamma(T) = alpha B V / C_V per temperature, the "
        "heat-capacity-weighted average of the mode gammas. DISTINCT from the mode "
        "Gruneisen (gamma_G, (q,nu)-indexed, FC3-produced): this is a T-only "
        "scalar, a contraction of it (contract_thermal_gruneisen)."
    ),
)


PHONOPY_BULK_MODULUS_QHA = SpaceRepresentationSpec(
    space=BULK_MODULUS,
    representation_name="phonopy",
    observable_units={"K": "GPa"},
    code_api={"K": "PhonopyQHA.bulk_modulus_temperature (matcalc QHACalc 'bulk_modulus_P')"},
    notes=(
        "PhonopyQHA.bulk_modulus_temperature (qha/core.py:319), matcalc "
        "result['bulk_modulus_P'] in GPa (_qha.py:300). The QHA route to the "
        "existing BulkModulus node: an EOS fit at each temperature's equilibrium "
        "volume. B(T) values are INSTANCES of BulkModulus whose conditions carry "
        "the temperature (temperature is an evaluation condition). The third "
        "producer route alongside the elastic-tensor VRH (contract_bulk_modulus) "
        "and the T=0 Birch-Murnaghan E(V) curvature (compute_bulk_modulus_eos), "
        "all three emitting the same GPa scalar node."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (the matcalc QHACalc F(V,T) volume-scan discretization
# rides these phonopy operator specs; the driver carries no rail of its own).
# ---------------------------------------------------------------------------

_QHA_SCAN_CHOICES = {
    "volume_grid": (
        "the F(V,T) volume scan: matcalc QHACalc's default 11 scale factors "
        "0.95..1.05 (_qha.py:80), a PhononCalc run at each scaled volume; the "
        "number of volumes and the strain span are the discretization"
    ),
    "eos": (
        "the equation of state fit to F(V) at each temperature: matcalc default "
        "'vinet' (_qha.py:77); phonopy also offers 'birch_murnaghan' and "
        "'murnaghan'"
    ),
    "mlip_checkpoint": (
        "each per-volume PhononCalc carries the MLIP checkpoint provenance "
        "(the same double-provenance as the harmonic phonon rail): the QHA "
        "result inherits the checkpoint identity of the E(V) and F(V,T) inputs"
    ),
}


PHONOPY_COMPUTE_QHA_GIBBS = OperatorRepresentationSpec(
    operator=compute_qha_gibbs,
    representation_name="phonopy",
    discretization_choices=_QHA_SCAN_CHOICES,
    notes=(
        "matcalc QHACalc(...).calc(atoms) runs a PhononCalc at each scanned volume, "
        "then PhonopyQHA fits F(V,T) and minimizes G = F + pV over volume "
        "(gibbs_temperature). The volume grid and EOS are the discretization; the "
        "MLIP checkpoint rides the per-volume phonon runs."
    ),
)


PHONOPY_COMPUTE_BULK_MODULUS_QHA = OperatorRepresentationSpec(
    operator=compute_bulk_modulus_qha,
    representation_name="phonopy",
    discretization_choices=_QHA_SCAN_CHOICES,
    notes=(
        "PhonopyQHA.bulk_modulus_temperature: the EOS curvature at each "
        "temperature's equilibrium volume, matcalc 'bulk_modulus_P' in GPa. The "
        "third Pattern C route to the BulkModulus node; the EOS choice and volume "
        "grid are the discretization."
    ),
)


PHONOPY_COMPUTE_THERMAL_EXPANSION = OperatorRepresentationSpec(
    operator=compute_thermal_expansion,
    representation_name="phonopy",
    notes=(
        "PhonopyQHA.thermal_expansion: dV/dT of the QHA equilibrium volume, "
        "matcalc 'thermal_expansion_coefficients' in 1/K."
    ),
)


PHONOPY_COMPUTE_HEAT_CAPACITY_P = OperatorRepresentationSpec(
    operator=compute_heat_capacity_p,
    representation_name="phonopy",
    notes=(
        "PhonopyQHA.heat_capacity_P_polyfit (matcalc default) / _numerical (the "
        "sibling estimator), matcalc 'heat_capacity_P' in J/(K*mol)."
    ),
)


PHONOPY_CONTRACT_THERMAL_GRUNEISEN = OperatorRepresentationSpec(
    operator=contract_thermal_gruneisen,
    representation_name="phonopy",
    notes=(
        "PhonopyQHA.gruneisen_temperature: the heat-capacity-weighted contraction "
        "of the mode gammas, matcalc 'gruneisen_parameters', dimensionless."
    ),
)
