r"""Operator nodes of the composites (effective-medium) domain.

Domain eleven: the effective thermal conductivity of a two-phase composite (a
dispersed filler in a continuous matrix) with interfacial (Kapitza) resistance,
via Nan-type effective-medium theory (Nan et al., J. Appl. Phys. 81, 6692
(1997)), cross-checked in the spherical limit against Hasselman-Johnson
(J. Compos. Mater. 21, 508 (1987)). The physics this domain adds that no other
domain carries is the INTERFACE: a per-direction thermal boundary conductance G
that lumps interface chemistry and dispersion quality, whose reciprocal
R = 1/G gives the Kapitza radius a_K = km/G (a length), the crossover below which
adding a conductive filler LOWERS the composite conductivity.

Seven nodes:

  Node                                                   quantity tag           dimension                indices
  -----------------------------------------------------  ---------------------  -----------------------  -----------------
  ThermalConductivity[role=matrix]                       thermal_conductivity   THERMAL_CONDUCTIVITY     ()
  ThermalConductivity[role=filler]                       thermal_conductivity   THERMAL_CONDUCTIVITY     (alpha, beta)
  InterfaceConductance                                   interface_conductance  INTERFACE_CONDUCTANCE    ()
  FillerVolumeFraction                                   filler_volume_fraction  DIMENSIONLESS           ()
  DepolarizationFactor                                   depolarization_factor  DIMENSIONLESS            ()
  ThermalConductivity[effective_medium=nan,orientation=random]   thermal_conductivity   THERMAL_CONDUCTIVITY  ()
  ThermalConductivity[effective_medium=nan,orientation=aligned]  thermal_conductivity   THERMAL_CONDUCTIVITY  ()

The four ThermalConductivity[...] nodes all JOIN the thermal_conductivity family
(the SAME thermal_conductivity tag and THERMAL_CONDUCTIVITY dimension as the
neutral ThermalConductivity observable and its nine lattice / Landauer route
siblings), kept DISTINCT nodes only by their labels (identity keys on
quantity + fields + gauge + labels, so a fresh label set is a fresh uid). This
is the method-neutral kappa ruling applied to composites: the matrix and filler
conductivities are thermal conductivities playing INPUT roles (role=matrix /
role=filler), and the composite effective conductivity is a thermal conductivity
produced by a homogenization THEORY (effective_medium=nan) at an ORIENTATION
(random / aligned). Distinct node ids are mandatory because an edge cannot
self-loop on the neutral kappa node; the random effective-kappa RESOLVES into
the neutral ThermalConductivity observable (a measured composite kappa is
evidence of THAT node), exactly the resolve_thermal_conductivity precedent.

The filler node carries a rank-2 Cartesian tensor field kappa_f[alpha,beta] (the
anisotropic principal-frame conductivity of a spheroidal inclusion), reusing the
registered cartesian index kinds and mirroring the neutral kappa tensor. Its
diagonal components are the transverse k11 = kappa_f[1,1] (in-plane) and the
axial k33 = kappa_f[3,3] (through-plane); the mixing formulas read those two
diagonal entries. The particle dimensions d1 (equatorial) and d3 (polar) and the
orientation ride in instance conditions (the elastic-constants precedent for
tensor components in conditions).
"""
from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    INTERFACE_CONDUCTANCE,
    THERMAL_CONDUCTIVITY,
)
from omai.operator.space import Field, ObservableSpace, Space

MATRIX_CONDUCTIVITY = ObservableSpace(
    name="ThermalConductivity[role=matrix]",
    fields=(Field("k_m", THERMAL_CONDUCTIVITY, indices=()),),
    labels={"role": "matrix"},
    tier="Composite",
    description=(
        "The bulk thermal conductivity km of the continuous MATRIX (host) phase "
        "of a composite: the conductivity the effective-medium theory blends the "
        "filler into. Scalar (an isotropic host, e.g. an epoxy). Dimension "
        "THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0) = W/(m K). JOINS the "
        "thermal_conductivity family (the SAME thermal_conductivity tag and "
        "dimension as the neutral ThermalConductivity observable and its route "
        "siblings) and is kept a DISTINCT node ONLY by the role=matrix LABEL, so "
        "a Nan / Hasselman-Johnson edge can consume 'the matrix kappa' as its own "
        "node without self-looping on the neutral kappa node. The host material "
        "rides in instance conditions (identity is per quantity, not per "
        "material); a computed or measured bulk km of the host is the input here."
    ),
)

FILLER_CONDUCTIVITY = ObservableSpace(
    name="ThermalConductivity[role=filler]",
    fields=(Field("k_f", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"role": "filler"},
    tier="Composite",
    description=(
        "The intrinsic thermal conductivity tensor of the dispersed FILLER "
        "(inclusion) phase of a composite, in the inclusion's principal frame "
        "(polar axis 3): a rank-2 Cartesian tensor kappa_f[alpha,beta] whose "
        "diagonal carries the transverse (in-plane) k11 = kappa_f[1,1] and the "
        "axial (through-plane) k33 = kappa_f[3,3]. Anisotropic for a real "
        "platelet or fiber (a graphene nanoplatelet has k11 >> k33). Dimension "
        "THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0) = W/(m K), the SAME tag and "
        "dimension as the neutral ThermalConductivity observable, kept a DISTINCT "
        "node ONLY by the role=filler LABEL. Reuses the registered cartesian "
        "index kinds (alpha, beta), mirroring the neutral kappa tensor; the two "
        "diagonal components the mixing formulas read (k11, k33) and the particle "
        "dimensions (d1 equatorial, d3 polar) ride in instance conditions (the "
        "elastic-constants precedent for tensor components in conditions)."
    ),
)

INTERFACE_CONDUCTANCE_NODE = ObservableSpace(
    name="InterfaceConductance",
    fields=(Field("G_int", INTERFACE_CONDUCTANCE, indices=()),),
    tier="Composite",
    description=(
        "The Kapitza (interfacial) thermal boundary conductance G at the "
        "filler/matrix interface: power per unit area per kelvin, the genuinely "
        "NEW physics this domain adds. Dimension INTERFACE_CONDUCTANCE "
        "(1,0,-3,-1,0,0,0) = W/(m^2 K), a conductance PER AREA (THERMAL_CONDUCTANCE "
        "W/K over an area) and equally THERMAL_CONDUCTIVITY over a length, so the "
        "Kapitza radius a_K = km/G is exactly a LENGTH (the dimensional gate "
        "proves the EMT edges on this). Enters the mixing formulas as the series "
        "interface film per principal direction, kc_ii = k_ii / (1 + 2 R k_ii / "
        "d_i) with R = 1/G. It LUMPS interface chemistry AND dispersion quality; "
        "the intended workflow calibrates G against one measured composite point, "
        "then ranks filler scenarios, and a computed thermal boundary conductance "
        "(NEMD) can replace the calibrated value. Served in MW/(m^2 K) (the "
        "practitioner scale) or the canonical W/(m^2 K)."
    ),
)

FILLER_VOLUME_FRACTION = ObservableSpace(
    name="FillerVolumeFraction",
    fields=(Field("f_vol", DIMENSIONLESS, indices=()),),
    tier="Composite",
    description=(
        "The volume fraction f of the dispersed filler phase in the composite: "
        "dimensionless, the loading knob of the effective-medium mixing. Valid "
        "for the non-interacting (ideal-dispersion) EMT in roughly [0, 0.25); "
        "above that, or near a filler-filler contact network, the Nan result is a "
        "lower bound (no percolation is modeled). Zero loading returns the matrix "
        "conductivity exactly. The reference epoxy draft uses f = 0.05 (5 vol%)."
    ),
)

DEPOLARIZATION_FACTOR = ObservableSpace(
    name="DepolarizationFactor",
    fields=(
        Field("L11", DIMENSIONLESS, indices=()),
        Field("L33", DIMENSIONLESS, indices=()),
    ),
    tier="Composite",
    description=(
        "The spheroid depolarization (Eshelby) factors (L11, L33) of an "
        "axially-symmetric inclusion, polar axis 3, with the sum rule "
        "2 L11 + L33 = 1: dimensionless geometry from the aspect ratio p = d3/d1. "
        "Analytic limits sphere (1/3, 1/3), long fiber p -> infinity (1/2, 0), "
        "thin disk p -> 0 (0, 1). The shape input to the Nan mixing formulas; a "
        "closed form (an atanh branch for prolate p>1, an atan branch for oblate "
        "p<1, the (1/3, 1/3) sphere at p=1). Two scalar fields (the two "
        "independent factors); the aspect ratio rides in conditions."
    ),
)

EFFECTIVE_CONDUCTIVITY_RANDOM = ObservableSpace(
    name="ThermalConductivity[effective_medium=nan,orientation=random]",
    fields=(Field("kappa_c", THERMAL_CONDUCTIVITY, indices=()),),
    labels={"effective_medium": "nan", "orientation": "random"},
    tier="Composite",
    description=(
        "The composite effective thermal conductivity for RANDOMLY oriented "
        "filler: the isotropic scalar kappa_c a measurement of a randomly-mixed "
        "composite reports, from the Nan et al. (1997) effective-medium theory "
        "with a per-direction interfacial (Kapitza) series film. Dimension "
        "THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0) = W/(m K). JOINS the "
        "thermal_conductivity family (same tag, same dimension) and is kept a "
        "DISTINCT node by the effective_medium=nan and orientation=random LABELS; "
        "it RESOLVES into the neutral ThermalConductivity observable (a measured "
        "composite kappa is evidence of that node). SECOND-PRODUCER home of the "
        "Hasselman-Johnson cross-check: in the spherical limit (aspect -> 1, "
        "isotropic filler) the HJ sphere formula produces this SAME node and must "
        "agree numerically (the blessed redundant-route pattern). The reference "
        "epoxy + 5 vol% GNP formulation gives kappa_c = 1.2452 W/(m K)."
    ),
)

EFFECTIVE_CONDUCTIVITY_ALIGNED = ObservableSpace(
    name="ThermalConductivity[effective_medium=nan,orientation=aligned]",
    fields=(Field("kappa_c", THERMAL_CONDUCTIVITY, indices=()),),
    labels={"effective_medium": "nan", "orientation": "aligned"},
    tier="Composite",
    description=(
        "The composite effective thermal conductivity for PERFECTLY ALIGNED "
        "filler: the anisotropic result of the Nan et al. (1997) EMT with the "
        "interfacial series film, a different mixing formula from the random "
        "orientation. Dimension THERMAL_CONDUCTIVITY (1,1,-3,-1,0,0,0) = W/(m K), "
        "the same thermal_conductivity family, kept DISTINCT from the random node "
        "by the orientation=aligned label. The two tensor components (the "
        "transverse / in-plane al11, transverse to the alignment axis 3, and the "
        "axial / through-plane al33 along axis 3) ride in instance conditions "
        "(the elastic-constants precedent); the declared closed form is the axial "
        "al33 = km (1 + f beta33 (1 - L33)) / (1 - f beta33 L33), with the "
        "transverse al11 its L11/beta11 companion (documented on the operator). "
        "Aligned platelets are the enhancement geometry a real thermal-interface "
        "material targets."
    ),
)

NODES: tuple[Space, ...] = (
    MATRIX_CONDUCTIVITY,
    FILLER_CONDUCTIVITY,
    INTERFACE_CONDUCTANCE_NODE,
    FILLER_VOLUME_FRACTION,
    DEPOLARIZATION_FACTOR,
    EFFECTIVE_CONDUCTIVITY_RANDOM,
    EFFECTIVE_CONDUCTIVITY_ALIGNED,
)
