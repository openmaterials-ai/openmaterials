r"""amset adapter specs for the electronic-transport domain.

amset 0.5.1 (PINNED here; the atomate2-agent env is unpinned) as used by the
AtomisticSkills mat-dft-electronic-transport skill, anchored in
`scans/amset-atomistic-skills.json` (deep review 2026-07-10; all 7 entries
confirmed with the full-rank-4 elastic input correction and the to_data unit
findings; source read from the pip-downloaded wheel
amset-0.5.1-py3-none-any.whl unzipped to /tmp/amsetsrc/amset_pkg). amset is NOT
importable in the miniconda base env; anchors are wheel-source references, not a
live import.

The skill never calls amset's Python API directly: it builds the VASP+AMSET
jobflow DAG through atomate2's VaspAmsetMaker (atomate2.vasp.flows.amset), which
runs the relax -> dense uniform bands -> elastic tensor -> deformation
potentials -> static+dielectric -> AMSET-run chain and reads the amset transport
JSON. So amset's to_data output contract (core/data.py:461-491) is the ground
truth and VaspAmsetMaker is the provenance layer.

  operator Space                                amset artifact                                     units
  ------------------------------------------    -------------------------------------------------  ---------------
  StaticDielectricTensor                        VaspAmsetMaker static+dielectric (flows/amset.py)  dimensionless
  ElectricalConductivity[carrier=electronic]    to_data cond (data.py:484)                         S/m
  SeebeckCoefficient                            to_data seebeck (data.py:484)                      muV/K
  ElectronicThermalConductivity                 to_data kappa (data.py:483-484)                    W/(m K) ('?')
  CarrierMobility                               to_data mobility (run.py:583,617)                  cm^2/(V s)

Convention traps this module pins (all review-verified):

  * The transport tensors are full (n_doping, n_temperature, 3, 3) arrays, NOT
    scalars: to_data (data.py:464-489) writes the upper triangle xx,xy,xz,yy,yz,zz
    (np.triu_indices(3)) per (doping, T) row. The nodes serve the scalar
    tensor_average (isotropic trace/3, run.py:588-590); the GaAs single-number
    mobility is a reduction at one (doping, T).
  * DOPING SIGN: positive = p-type, negative = n-type (defaults.yaml:8); cm^-3
    input, bohr^-3 internal.
  * sigma is S/m (data.py:484), NOT S/cm (1 S/cm = 100 S/m) and NOT the ionic
    sibling's mS/cm (1 mS/cm = 0.1 S/m): three serving units for the one
    ELECTRICAL_CONDUCTIVITY dimension.
  * Seebeck is served in microvolts per kelvin (the raw V/K x 1e6,
    transport.py:191; data.py:484 serializes the micro-sign glyph muV/K, ASCII
    here); the sign carries the carrier type.
  * kappa's unit is UNCONFIRMED BY amset ITSELF: data.py:483 verbatim
    '# TODO: confirm unit of kappa', and data.py:484 serializes the header unit
    as '?'. W/(m K) is the BoltzTraP2 calc_Onsager_coefficients convention;
    confirm against BoltzTraP2 bandlib before any EXPECTED_AGREE.
  * mobility is cm^2/(V s) (transport.py:133-135, run.py:583,617), COMPUTED FOR
    NON-METALS ONLY (transport.py:47-49); separate_mobility (default True) gives
    the per-mechanism breakdown (run.py:615-624).
  * amset works internally in Hartree atomic units (constants.py); all
    serving-unit conversions happen at output.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.electronic_transport.operator.edges import (
    compute_carrier_mobility,
    compute_electronic_conductivity,
    compute_electronic_thermal_conductivity,
    compute_seebeck,
    compute_static_dielectric,
)
from omai.electronic_transport.operator.nodes import (
    CARRIER_MOBILITY,
    ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    ELECTRONIC_THERMAL_CONDUCTIVITY,
    SEEBECK_COEFFICIENT,
    STATIC_DIELECTRIC_TENSOR,
)


# ---------------------------------------------------------------------------
# Space-level specs (the five nodes)
# ---------------------------------------------------------------------------

AMSET_STATIC_DIELECTRIC_TENSOR = SpaceRepresentationSpec(
    space=STATIC_DIELECTRIC_TENSOR,
    representation_name="amset",
    observable_units={"epsilon_0": "dimensionless"},
    code_api={
        "epsilon_0": "atomate2 VaspAmsetMaker static+dielectric outputs assembled to eps_0 = eps_inf + ionic (vasp/flows/amset.py:261-266); amset settings static_dielectric",
    },
    notes=(
        "The static dielectric tensor eps_0 = eps_inf + ionic contribution, "
        "dimensionless rank-2 (alpha, beta). amset needs BOTH eps_0 "
        "(static_dielectric) and the high-frequency eps_inf "
        "(high_frequency_dielectric) for the POP / PIE / IMP screening "
        "(inelastic.py:62-64); VaspAmsetMaker assembles them from the VASP "
        "dielectric + Born-charge outputs (vasp/flows/amset.py:261-266). "
        "Distinct from the mapped electronic DielectricTensor eps_inf (which is "
        "the ion-clamped infinite-frequency response). No unit (dimensionless)."
    ),
)

AMSET_ELECTRICAL_CONDUCTIVITY = SpaceRepresentationSpec(
    space=ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    representation_name="amset",
    observable_units={"sigma": "s_per_m"},
    code_api={
        "sigma": "amset.core.data.to_data cond, S/m (data.py:484); run.py:583 header 'sigma [S/m]'",
    },
    notes=(
        "Electronic electrical conductivity sigma, served in S/m: "
        "to_data (data.py:484) prop 'cond' unit 'S/m', from BoltzTraP2 "
        "calc_Onsager_coefficients over the interpolated bands "
        "(transport.py:36-39). S/m maps to ELECTRICAL_CONDUCTIVITY (canonical "
        "s_per_m, to_operator 1.0); NOT S/cm (1 S/cm = 100 S/m) and NOT the "
        "ionic sibling's mS/cm (1 mS/cm = 0.1 S/m). A full "
        "(n_doping, n_temperature, 3, 3) tensor (upper triangle per "
        "(doping, T), np.triu_indices(3), data.py:464); the node serves the "
        "tensor_average scalar (run.py:588-590). Positive doping = p-type, "
        "negative = n-type (defaults.yaml:8)."
    ),
)

AMSET_SEEBECK_COEFFICIENT = SpaceRepresentationSpec(
    space=SEEBECK_COEFFICIENT,
    representation_name="amset",
    observable_units={"S_seebeck": "muv_per_k"},
    code_api={
        "S_seebeck": "amset.core.data.to_data seebeck, muV/K (data.py:484; transport.py:191 *1e6); run.py:583 header 'S [muV/K]'",
    },
    notes=(
        "Seebeck coefficient S, served in microvolts per kelvin: to_data "
        "(data.py:484) prop 'seebeck' unit the micro-sign glyph muV/K (ASCII "
        "muv_per_k here); transport.py:191 multiplies the raw V/K by 1e6, so "
        "muv_per_k carries to_operator 1e-6 to the canonical v_per_k. The SIGN "
        "carries the carrier type (positive holes / p-type, negative electrons "
        "/ n-type). A full (n_doping, n_temperature, 3, 3) tensor served as the "
        "tensor_average scalar. amset computes S even for metals (only mobility "
        "is non-metal-only)."
    ),
)

AMSET_ELECTRONIC_THERMAL_CONDUCTIVITY = SpaceRepresentationSpec(
    space=ELECTRONIC_THERMAL_CONDUCTIVITY,
    representation_name="amset",
    observable_units={"kappa_e": "W_per_m_per_K"},
    code_api={
        "kappa_e": "amset.core.data.to_data kappa, header unit '?' (data.py:483-484); electronic_thermal_conductivity field (data.py:80)",
    },
    notes=(
        "Electronic thermal conductivity kappa_e, W/(m K) by the BoltzTraP2 "
        "convention. HONESTY CAVEAT: amset itself does NOT confirm the unit: "
        "data.py:483 verbatim '# TODO: confirm unit of kappa', and data.py:484 "
        "serializes the header unit as '?' (the third entry of "
        "[('cond','S/m'),('seebeck','muV/K'),('kappa','?')]). W/(m K) is the "
        "BoltzTraP2 calc_Onsager_coefficients convention; canonical "
        "W_per_m_per_K to_operator 1.0, BUT confirm against BoltzTraP2 bandlib "
        "before any cross-code EXPECTED_AGREE. The ELECTRONIC partner of the "
        "lattice thermal conductivity (kappa_total = lattice + electronic); the "
        "own electronic_thermal_conductivity tag is the firewall against a "
        "false-merge on the shared W/(m K) dimension. Full "
        "(n_doping, n_temperature, 3, 3) tensor served as the tensor_average "
        "scalar."
    ),
)

AMSET_CARRIER_MOBILITY = SpaceRepresentationSpec(
    space=CARRIER_MOBILITY,
    representation_name="amset",
    observable_units={"mu_carrier": "cm2_per_v_s"},
    code_api={
        "mu_carrier": "amset.core.run mobility, cm^2/(V s) (transport.py:133-135; run.py:583,617 header 'mu [cm^2/Vs]')",
    },
    notes=(
        "Carrier mobility mu, served in cm^2/(V s): transport.py:133-135 "
        "converts to cm^2/Vs, run.py:583,617 header 'mu [cm^2/Vs]'; so "
        "cm2_per_v_s carries to_operator 1e-4 to the canonical m2_per_v_s "
        "(1 cm^2 = 1e-4 m^2). COMPUTED FOR NON-METALS ONLY "
        "(transport.py:47-49). With separate_mobility (default True) amset "
        "reports the per-mechanism breakdown (which channel limits mobility, "
        "run.py:615-624), a resolved-spectrum layer deferred here. Full "
        "(n_doping, n_temperature, 3, 3) tensor; the GaAs 300 K electron "
        "~8500 / hole ~400 cm^2/Vs single numbers are a tensor_average at one "
        "(doping, T)."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how amset / VaspAmsetMaker realize the edges)
# ---------------------------------------------------------------------------

AMSET_COMPUTE_STATIC_DIELECTRIC = OperatorRepresentationSpec(
    operator=compute_static_dielectric,
    representation_name="amset",
    discretization_choices={
        "assembly": (
            "eps_0 = eps_inf + the ionic contribution, assembled by atomate2's "
            "VaspAmsetMaker from the VASP dielectric + Born-charge outputs "
            "(vasp/flows/amset.py:261-266); amset consumes it as the "
            "static_dielectric setting"
        ),
    },
    notes=(
        "Realized by VaspAmsetMaker's static+dielectric step: the static "
        "dielectric eps_0 is the high-frequency eps_inf plus the ionic "
        "(lattice-polarization) contribution built from the Born charges and "
        "phonon modes. The method scheme is ionic_contribution."
    ),
)

_TRANSPORT_OP_NOTE = (
    "Realized by amset through atomate2's VaspAmsetMaker (VASP+AMSET jobflow "
    "DAG): the dense uniform band structure interpolated by BoltzTraP2 "
    "(fite / sphere, bandstructure.py:10,53), then the Onsager transport "
    "tensors (transport.py:36-39) with momentum-relaxation-time scattering "
    "(scattering_type: auto picks ADP + IMP + PIE + POP) via an iterative BTE. "
    "The schemes are method=bte_ibte (iterative BTE), scattering=adp_imp_pop, "
    "interpolation=boltztrap2."
)

_TRANSPORT_DISCRETIZATION = {
    "elastic_input": (
        "the FULL rank-4 elastic tensor: amset's cast_elastic_tensor "
        "(util.py:115) expands any scalar / Voigt / full input to (3,3,3,3) "
        "C_ijkl, and c_long is derived per q-direction at run time via the "
        "Christoffel construction (elastic.py:180-183,266-267); VaspAmsetMaker "
        "wires elastic.output.elastic_tensor.raw (vasp/flows/amset.py:290)"
    ),
    "pop_frequency": (
        "the effective POP frequency: VaspAmsetMaker reduces Born charges + "
        "normal modes via calculate_polar_phonon_frequency(structure, "
        "normalmode_frequencies, normalmode_eigenvecs, outcar['born']) "
        "(vasp/flows/amset.py:245-250), the phonon-Frequency input"
    ),
    "deferred_inputs": (
        "two amset inputs are NOT map nodes: the dense uniform band structure / "
        "wavefunction amset interpolates, and the ADP deformation potentials "
        "(the strained-band step); the piezoelectric constant is likewise "
        "deferred (PIE is not auto-wired by VaspAmsetMaker unless the user "
        "supplies it via amset_settings)"
    ),
    "doping_temperature_grid": (
        "the transport tensors are a (n_doping, n_temperature, 3, 3) grid; the "
        "GaAs example sets doping=(1e16,1e17,1e18) cm^-3, "
        "temperatures=(300.,400.) K (generate_inputs.py); positive doping = "
        "p-type, negative = n-type"
    ),
}

AMSET_COMPUTE_ELECTRONIC_CONDUCTIVITY = OperatorRepresentationSpec(
    operator=compute_electronic_conductivity,
    representation_name="amset",
    discretization_choices=dict(_TRANSPORT_DISCRETIZATION),
    notes=_TRANSPORT_OP_NOTE,
)

AMSET_COMPUTE_SEEBECK = OperatorRepresentationSpec(
    operator=compute_seebeck,
    representation_name="amset",
    discretization_choices=dict(_TRANSPORT_DISCRETIZATION),
    notes=_TRANSPORT_OP_NOTE,
)

AMSET_COMPUTE_ELECTRONIC_THERMAL_CONDUCTIVITY = OperatorRepresentationSpec(
    operator=compute_electronic_thermal_conductivity,
    representation_name="amset",
    discretization_choices=dict(_TRANSPORT_DISCRETIZATION),
    notes=(
        _TRANSPORT_OP_NOTE
        + " kappa's serving unit is unconfirmed by amset (data.py:483 "
        "'# TODO: confirm unit of kappa', header '?'); W/(m K) by the "
        "BoltzTraP2 convention, confirm before EXPECTED_AGREE."
    ),
)

AMSET_COMPUTE_CARRIER_MOBILITY = OperatorRepresentationSpec(
    operator=compute_carrier_mobility,
    representation_name="amset",
    discretization_choices=dict(_TRANSPORT_DISCRETIZATION),
    notes=(
        _TRANSPORT_OP_NOTE
        + " Mobility is computed for non-metals only (transport.py:47-49); "
        "separate_mobility (default True) gives the per-mechanism breakdown."
    ),
)
