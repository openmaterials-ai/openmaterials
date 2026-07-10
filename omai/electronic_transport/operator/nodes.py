r"""Operator nodes of the electronic-transport domain.

Carrier transport from ab-initio scattering (the amset scan, AtomisticSkills
arXiv 2605.24002): the electronic-transport tensors amset computes from an
interpolated dense band structure plus momentum-relaxation-time scattering
(ADP + IMP + PIE + POP), the electronic-carrier partner of the phonon
(lattice) transport already on the map.

Node table:

  Node                                  quantity tag                     dimension                indices
  ------------------------------------  -------------------------------  -----------------------  ---------------
  StaticDielectricTensor                static_dielectric_tensor         DIMENSIONLESS            (alpha, beta)
  ElectricalConductivity[carrier=       electrical_conductivity          ELECTRICAL_CONDUCTIVITY  ()
    electronic]
  SeebeckCoefficient                    seebeck_coefficient              SEEBECK                  ()
  ElectronicThermalConductivity         electronic_thermal_conductivity  THERMAL_CONDUCTIVITY     ()
  CarrierMobility                       carrier_mobility                 MOBILITY                 ()

The carrier family (load-bearing). The electronic electrical conductivity has
the EXACT ELECTRICAL_CONDUCTIVITY exponent vector (M=-1,L=-3,T=3,I=2) = S/m of
the config-thermo ElectricalConductivity[carrier=ionic]: same physical
quantity (electrical conductivity), same dimension, differing only in which
particle carries the charge (band electrons/holes vs mobile ions). It joins the
one electrical_conductivity family through the registered carrier LABEL_KEY:
ElectricalConductivity[carrier=electronic] and [carrier=ionic] share the tag and
the dimension and stay distinct nodes (distinct uids) only by the carrier label,
mirroring the ThermalConductivity[transport_model=...] family pattern. The
carrier label and the ELECTRICAL_CONDUCTIVITY dimension are already live (the
config-thermo landing registered them); this node reuses them, mints nothing.

The lattice-vs-electronic kappa firewall (MANDATORY). ElectronicThermalConductivity
REUSES the THERMAL_CONDUCTIVITY dimension W/(m K) (M=1,L=1,T=-3,Th=-1) shared with
the map's nine lattice ThermalConductivity[*] nodes. They are the two ADDITIVE
contributions to the total measured thermal conductivity
(kappa_total = kappa_lattice + kappa_electronic), from different carriers,
operators, and domains. Merging them, or letting them false-merge on the shared
dimension, is a physics error, so this node carries its OWN quantity tag
electronic_thermal_conductivity (not the lattice thermal_conductivity tag and
not a carrier label on it): the own tag gives it a distinct uid at the identity
level, the firewall the amset scan mandates. amset's own source flags the unit
as unconfirmed (data.py:483 '# TODO: confirm unit of kappa'; it serializes the
header unit as '?'); W/(m K) is the BoltzTraP2 calc_Onsager_coefficients
convention, recorded with that honesty caveat on the amset rail before any
cross-code EXPECTED_AGREE.

StaticDielectricTensor is a THIRD distinct dielectric quantity: the static
(zero-frequency) eps_0 = eps_inf + the ionic (lattice-polarization)
contribution, which amset needs for the POP / PIE / IMP screening alongside the
high-frequency eps_inf. It is EMPHATICALLY distinct from the mapped electronic
DielectricTensor (eps_inf at infinite frequency): same DIMENSIONLESS rank-2
(alpha, beta) shape, different physics (ion-clamped high-frequency response vs
the fully relaxed static response), kept apart by the static_dielectric_tensor
quantity tag. It sits in the Sources tier alongside DielectricTensor (the
dielectric family), not in the Electronic-transport tier, though it is produced
by compute_static_dielectric here.

Serving shape. amset's transport tensors are full (n_doping, n_temperature, 3, 3)
arrays (data.py to_data writes the upper triangle xx,xy,xz,yy,yz,zz per
(doping, T) row). The three transport nodes are served here as SCALARS
(sigma, S, kappa_e), matching the config-thermo sibling's scalar shape for
family consistency, with the (doping, T, 3, 3) tensor reality a
representation-layer packing recorded on the amset rail; the single-number GaAs
mobility is a tensor_average (isotropic trace/3) at one (doping, T) point.
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ELECTRICAL_CONDUCTIVITY,
    MOBILITY,
    SEEBECK,
    THERMAL_CONDUCTIVITY,
)
from omai.operator.space import Field, ObservableSpace, Space

STATIC_DIELECTRIC_TENSOR = ObservableSpace(
    name="StaticDielectricTensor",
    fields=(Field("epsilon_0", DIMENSIONLESS, indices=("alpha", "beta")),),
    tier="Sources",
    description=(
        "Static (zero-frequency) macroscopic dielectric tensor eps_0 = "
        "eps_inf + the ionic (lattice-polarization) contribution: the "
        "ion-relaxed dielectric response, dimensionless rank-2 tensor over the "
        "Cartesian (alpha, beta) legs. amset needs BOTH the static eps_0 (this "
        "node) and the high-frequency electronic eps_inf (the mapped "
        "DielectricTensor) for the polar-optical-phonon, piezoelectric, and "
        "ionized-impurity scattering screening (inelastic.py:62-64). A THIRD "
        "distinct dielectric quantity: EMPHATICALLY NOT the electronic "
        "DielectricTensor eps_inf at infinite frequency (ion-clamped), from "
        "which it differs by the ionic contribution, and not the "
        "frequency-dependent eps(omega); kept apart by the "
        "static_dielectric_tensor quantity tag. Sits in the Sources tier with "
        "the dielectric family though computed by compute_static_dielectric "
        "(eps_inf + BornCharges over the phonon Frequency)."
    ),
)

ELECTRICAL_CONDUCTIVITY_ELECTRONIC = ObservableSpace(
    name="ElectricalConductivity[carrier=electronic]",
    fields=(Field("sigma", ELECTRICAL_CONDUCTIVITY, indices=()),),
    labels={"carrier": "electronic"},
    tier="Electronic transport",
    description=(
        "Electronic electrical conductivity sigma from ab-initio scattering "
        "transport: the BoltzTraP2 Onsager conductivity over the interpolated "
        "dense band structure with amset's momentum-relaxation-time scattering "
        "(ADP + IMP + PIE + POP) replacing the constant relaxation time "
        "(transport.py:36-39). Dimension ELECTRICAL_CONDUCTIVITY "
        "(M=-1,L=-3,T=3,Theta=0,N=0,I=2,J=0), the S/m of siemens per metre, the "
        "EXACT exponent vector of the config-thermo ElectricalConductivity"
        "[carrier=ionic]: SAME quantity (electrical conductivity), SAME "
        "dimension, differing only in the charge carrier (band electrons/holes "
        "vs mobile ions). It joins the one electrical_conductivity family "
        "through the carrier=electronic label (a registered LABEL_KEY value): "
        "same tag and dimension as the ionic sibling, a distinct node only by "
        "the carrier label (the ThermalConductivity[transport_model=...] family "
        "pattern). amset serves it in S/m (data.py:484), NOT the ionic "
        "sibling's mS/cm (1 S/m = 10 mS/cm) nor S/cm (1 S/cm = 100 S/m): three "
        "serving units for one dimension. Served here as the scalar sigma, with "
        "the amset (n_doping, n_temperature, 3, 3) tensor a representation-layer "
        "packing; positive doping is p-type, negative n-type."
    ),
)

SEEBECK_COEFFICIENT = ObservableSpace(
    name="SeebeckCoefficient",
    fields=(Field("S_seebeck", SEEBECK, indices=()),),
    tier="Electronic transport",
    description=(
        "Seebeck (thermopower) coefficient S from ab-initio scattering "
        "transport: the BoltzTraP2 Onsager thermopower over the interpolated "
        "band structure (transport.py:36-39). Dimension SEEBECK "
        "(M=1,L=2,T=-3,Theta=-1,N=0,I=-1,J=0) = V/K, built from the volt "
        "(VOLTAGE, the intercalation node's dimension) divided by a "
        "temperature; the first map dimension to carry BOTH the "
        "electric-current axis (I=-1) and the temperature axis (Theta=-1). "
        "amset serves it in microvolts per kelvin (the raw V/K multiplied by "
        "1e6, transport.py:191; the source header unit is the micro-sign glyph "
        "muV/K, written ASCII in our notes), so the serving unit muv_per_k "
        "carries a 1e-6 factor to the canonical v_per_k. The SIGN carries the "
        "carrier type (positive for holes / p-type, negative for electrons / "
        "n-type). Served as the scalar S; the amset "
        "(n_doping, n_temperature, 3, 3) tensor is a representation-layer "
        "packing. Not part of a thermoelectric bundle here (power factor "
        "S^2 sigma and ZT are downstream contracts, deferred)."
    ),
)

ELECTRONIC_THERMAL_CONDUCTIVITY = ObservableSpace(
    name="ElectronicThermalConductivity",
    fields=(Field("kappa_e", THERMAL_CONDUCTIVITY, indices=()),),
    tier="Electronic transport",
    description=(
        "Electronic contribution kappa_e to the thermal conductivity from "
        "carrier transport: the BoltzTraP2 Onsager electronic thermal "
        "conductivity over the interpolated band structure "
        "(transport.py:36-39, data.py:80). REUSES the THERMAL_CONDUCTIVITY "
        "dimension W/(m K) (M=1,L=1,T=-3,Theta=-1) shared with the map's nine "
        "lattice ThermalConductivity[*] nodes, but is a DISTINCT quantity: the "
        "two are the ADDITIVE contributions to the total measured thermal "
        "conductivity (kappa_total = kappa_lattice + kappa_electronic), from "
        "different carriers, operators, and domains. It carries its OWN "
        "electronic_thermal_conductivity quantity tag (not the lattice "
        "thermal_conductivity tag, not a carrier label on it) so it gets a "
        "distinct uid: the MANDATORY firewall against a false-merge on the "
        "shared dimension. amset's own source flags the unit as unconfirmed "
        "(data.py:483 '# TODO: confirm unit of kappa'; it serializes the header "
        "unit as '?'); W/(m K) is the BoltzTraP2 calc_Onsager_coefficients "
        "convention, and the honesty caveat (confirm against BoltzTraP2 before "
        "any EXPECTED_AGREE) rides the amset rail. Served as the scalar "
        "kappa_e; the amset (n_doping, n_temperature, 3, 3) tensor is a "
        "representation-layer packing."
    ),
)

CARRIER_MOBILITY = ObservableSpace(
    name="CarrierMobility",
    fields=(Field("mu_carrier", MOBILITY, indices=()),),
    tier="Electronic transport",
    description=(
        "Charge-carrier mobility mu from ab-initio scattering transport: "
        "sigma / (n e) over the interpolated band structure with amset's "
        "per-mechanism scattering (transport.py:73-137). Dimension MOBILITY "
        "(M=-1,L=0,T=2,Theta=0,N=0,I=1,J=0) = m^2/(V s), derived L^2/(V s) = "
        "M^-1 T^2 I; the electric-current-axis I=+1 sign (as MagneticMoment "
        "carries), distinct exponents. amset serves it in cm^2/(V s) "
        "(transport.py:133-135), so the serving unit cm2_per_v_s carries a "
        "1e-4 factor to the canonical m2_per_v_s. COMPUTED FOR NON-METALS ONLY "
        "(transport.py:47-49; sigma / Seebeck / kappa_e are still computed for "
        "metals); with separate_mobility (default True) amset also reports a "
        "per-mechanism mobility breakdown (which channel limits mobility), a "
        "resolved-spectrum layer deferred here. Served as the scalar mu (the "
        "GaAs single-number ~8500 electron / ~400 hole cm^2/Vs at 300 K is a "
        "tensor_average at one (doping, T)); the amset "
        "(n_doping, n_temperature, 3, 3) tensor is a representation-layer "
        "packing."
    ),
)

NODES: tuple[Space, ...] = (
    STATIC_DIELECTRIC_TENSOR,
    ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    SEEBECK_COEFFICIENT,
    ELECTRONIC_THERMAL_CONDUCTIVITY,
    CARRIER_MOBILITY,
)
