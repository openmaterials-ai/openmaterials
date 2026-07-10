r"""Operators (edges) of the electronic-transport domain.

Five edges, all implicit (is_executable_in_sympy_override=False): the static
dielectric assembly and the four ab-initio scattering transport tensors, each an
opaque applied function of its inputs with the method / scattering / interpolation
selection recorded as schemes, exactly like the thermochemistry Gibbs edges and
the materials Nernst-Einstein edge.

  compute_static_dielectric            : (DielectricTensor, BornCharges, Frequency)
                                             -> StaticDielectricTensor
  compute_electronic_conductivity      : (Structure, StaticDielectricTensor,
                                          ElasticConstants, Frequency)
                                             -> ElectricalConductivity[carrier=electronic]
  compute_seebeck                      : (Structure, StaticDielectricTensor,
                                          ElasticConstants, Frequency)
                                             -> SeebeckCoefficient
  compute_electronic_thermal_conductivity : (Structure, StaticDielectricTensor,
                                          ElasticConstants, Frequency)
                                             -> ElectronicThermalConductivity
  compute_carrier_mobility             : (Structure, StaticDielectricTensor,
                                          ElasticConstants, Frequency)
                                             -> CarrierMobility

Connectivity. The four transport edges share the same four inputs; three of them
(Structure, ElasticConstants, Frequency) are pre-existing store nodes and the
fourth (StaticDielectricTensor) is produced within this contribution by
compute_static_dielectric, which itself consumes the pre-existing DielectricTensor,
BornCharges, and Frequency. So the five added nodes plus five edges form ONE
weakly connected component that chains through compute_static_dielectric and
touches several pre-existing Sources leaves, satisfying the connectivity gate.

The elastic input is the FULL rank-4 ElasticConstants tensor (the review
correction): amset's cast_elastic_tensor expands any input to the full
(3,3,3,3) C_ijkl and derives the longitudinal modulus per q-direction at run
time via the Christoffel construction (elastic.py); atomate2's VaspAmsetMaker
wires elastic.output.elastic_tensor.raw, the full tensor. Two amset inputs are
NOT map nodes and stay deferred source parameters recorded in the notes: the
dense uniform band structure / wavefunction amset interpolates (BoltzTraP2
fite / sphere) and the deformation potentials (the strained-band ADP input);
the piezoelectric constant is likewise deferred (PIE is not auto-wired by
VaspAmsetMaker). BornCharges feed compute_static_dielectric (and, upstream
through the phonon calc, the effective POP frequency); the map carries them as
the phonon-side provenance, not as a direct transport-edge argument.

Symbols. The output field symbols (\varepsilon_0, \sigma_{el}, S, \kappa_e,
\mu_e) are new and collision-checked (\sigma_{el} is distinct from the materials
\sigma_{ion}); the input arguments \varepsilon_\infty (DielectricTensor), Z^*
(BornCharges), \omega (Frequency), \mathcal{S} (Structure), C (ElasticConstants)
are the existing registered source / phonon / mechanics symbols reused as the
opaque-function arguments. The opaque solver functions (\varepsilon_0^{stat},
\sigma^{bte}, S^{bte}, \kappa_e^{bte}, \mu^{bte}) are applied functions,
invisible to the free-symbol check, so they need no vocabulary entries.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.electronic_transport.operator.nodes import (
    CARRIER_MOBILITY,
    ELECTRICAL_CONDUCTIVITY_ELECTRONIC,
    ELECTRONIC_THERMAL_CONDUCTIVITY,
    SEEBECK_COEFFICIENT,
    STATIC_DIELECTRIC_TENSOR,
)
from omai.mechanics.operator.nodes import ELASTIC_CONSTANTS
from omai.materials.operator.shared_primitives import STRUCTURE
from omai.thermal_transport.operator.nodes import (
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    FREQUENCY_STATE,
)


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

# Output field symbols (new, registered in this domain's vocabulary).
_eps0 = sp.Symbol(r"\varepsilon_0")
_sigma_el = sp.Symbol(r"\sigma_{el}")
_S_see = sp.Symbol("S")
_kappa_e = sp.Symbol(r"\kappa_e")
_mu_e = sp.Symbol(r"\mu_e")
# Input arguments (existing registered source / phonon / mechanics symbols).
_eps_inf = sp.Symbol(r"\varepsilon_\infty")   # DielectricTensor
_Zstar = sp.Symbol(r"Z^*")                     # BornCharges
_omega = sp.Symbol(r"\omega")                  # Frequency
_S_struct = sp.Symbol(r"\mathcal{S}")          # Structure
_C = sp.Symbol("C")                            # ElasticConstants
# Opaque solver functions (applied functions, not free symbols).
_eps0_stat = sp.Function(r"\varepsilon_0^{stat}")
_sigma_bte = sp.Function(r"\sigma^{bte}")
_S_bte = sp.Function("S^{bte}")
_kappa_bte = sp.Function(r"\kappa_e^{bte}")
_mu_bte = sp.Function(r"\mu^{bte}")


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

compute_static_dielectric = Operator(
    name="compute_static_dielectric",
    inputs=(DIELECTRIC_TENSOR, BORN_CHARGES, FREQUENCY_STATE),
    outputs=(STATIC_DIELECTRIC_TENSOR,),
    schemes={"method": "ionic_contribution"},
    formula=sp.Eq(_eps0, _eps0_stat(_eps_inf, _Zstar, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Static dielectric tensor eps_0 = eps_0^{stat}[eps_inf, Z*, omega]: "
        "the high-frequency electronic dielectric tensor eps_inf plus the ionic "
        "(lattice-polarization) contribution built from the Born effective "
        "charges Z* and the phonon frequencies omega (the mode-oscillator-"
        "strength sum over the polar modes). eps_0^{stat} is an opaque function "
        "over the three phonon/dielectric inputs; the method scheme records the "
        "ionic_contribution assembly (eps_0 = eps_inf + ionic). atomate2's "
        "VaspAmsetMaker assembles it from the dielectric + Born-charge outputs "
        "(vasp/flows/amset.py:261-266). Implicit (a mode-strength sum over the "
        "polar phonons), so not sympy-executable."
    ),
)

_TRANSPORT_SCHEMES = {
    "method": "bte_ibte",
    "scattering": "adp_imp_pop",
    "interpolation": "boltztrap2",
}

compute_electronic_conductivity = Operator(
    name="compute_electronic_conductivity",
    inputs=(STRUCTURE, STATIC_DIELECTRIC_TENSOR, ELASTIC_CONSTANTS, FREQUENCY_STATE),
    outputs=(ELECTRICAL_CONDUCTIVITY_ELECTRONIC,),
    schemes=dict(_TRANSPORT_SCHEMES),
    formula=sp.Eq(_sigma_el, _sigma_bte(_S_struct, _eps0, _C, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Electronic conductivity sigma = sigma^{bte}[Structure, eps_0, C, "
        "omega]: the BoltzTraP2 Onsager conductivity over the amset-interpolated "
        "dense band structure with momentum-relaxation-time scattering "
        "(ADP + IMP + PIE + POP) replacing the constant relaxation time. "
        "sigma^{bte} is opaque over the Structure, the static dielectric eps_0 "
        "(POP / PIE / IMP screening), the FULL rank-4 elastic tensor C (the ADP "
        "and PIE longitudinal modulus, derived per q via the Christoffel "
        "construction), and the phonon frequencies omega (the effective POP "
        "frequency). The dense band structure / wavefunction amset interpolates "
        "and the ADP deformation potentials are amset inputs that are not map "
        "nodes (deferred source parameters). The schemes record the "
        "iterative-BTE method, the adp_imp_pop scattering, and the boltztrap2 "
        "interpolation. Implicit (an interpolated-BTE solve over a scattering "
        "model), so not sympy-executable."
    ),
)

compute_seebeck = Operator(
    name="compute_seebeck",
    inputs=(STRUCTURE, STATIC_DIELECTRIC_TENSOR, ELASTIC_CONSTANTS, FREQUENCY_STATE),
    outputs=(SEEBECK_COEFFICIENT,),
    schemes=dict(_TRANSPORT_SCHEMES),
    formula=sp.Eq(_S_see, _S_bte(_S_struct, _eps0, _C, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Seebeck coefficient S = S^{bte}[Structure, eps_0, C, omega]: the "
        "BoltzTraP2 Onsager thermopower over the amset-interpolated band "
        "structure with the same momentum-relaxation-time scattering. S^{bte} "
        "is opaque over the same four inputs as the conductivity edge (the "
        "static dielectric, the full rank-4 elastic tensor, and the phonon "
        "frequencies feed the identical scattering model; the deformation "
        "potentials and the dense bands are the deferred non-node inputs). The "
        "SIGN of S carries the carrier type. The schemes record the "
        "iterative-BTE method, the adp_imp_pop scattering, and the boltztrap2 "
        "interpolation. Implicit, so not sympy-executable."
    ),
)

compute_electronic_thermal_conductivity = Operator(
    name="compute_electronic_thermal_conductivity",
    inputs=(STRUCTURE, STATIC_DIELECTRIC_TENSOR, ELASTIC_CONSTANTS, FREQUENCY_STATE),
    outputs=(ELECTRONIC_THERMAL_CONDUCTIVITY,),
    schemes=dict(_TRANSPORT_SCHEMES),
    formula=sp.Eq(_kappa_e, _kappa_bte(_S_struct, _eps0, _C, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Electronic thermal conductivity kappa_e = kappa_e^{bte}[Structure, "
        "eps_0, C, omega]: the BoltzTraP2 Onsager electronic thermal "
        "conductivity over the amset-interpolated band structure with the same "
        "scattering model, the electronic partner of the lattice thermal "
        "conductivity (kappa_total = lattice + electronic). kappa_e^{bte} is "
        "opaque over the same four inputs (static dielectric, full rank-4 "
        "elastic tensor, phonon frequencies; deformation potentials and dense "
        "bands deferred). amset's own source flags the kappa unit as unconfirmed "
        "(data.py:483 '# TODO: confirm unit of kappa'; header '?'); W/(m K) is "
        "the BoltzTraP2 convention, carried with that caveat on the rail. The "
        "schemes record the iterative-BTE method, the adp_imp_pop scattering, "
        "and the boltztrap2 interpolation. Implicit, so not sympy-executable."
    ),
)

compute_carrier_mobility = Operator(
    name="compute_carrier_mobility",
    inputs=(STRUCTURE, STATIC_DIELECTRIC_TENSOR, ELASTIC_CONSTANTS, FREQUENCY_STATE),
    outputs=(CARRIER_MOBILITY,),
    schemes=dict(_TRANSPORT_SCHEMES),
    formula=sp.Eq(_mu_e, _mu_bte(_S_struct, _eps0, _C, _omega)),
    is_executable_in_sympy_override=False,
    description=(
        "Carrier mobility mu = mu^{bte}[Structure, eps_0, C, omega]: the "
        "mobility sigma / (n e) over the amset-interpolated band structure with "
        "the same momentum-relaxation-time scattering, COMPUTED FOR NON-METALS "
        "ONLY. mu^{bte} is opaque over the same four inputs (static dielectric, "
        "full rank-4 elastic tensor, phonon frequencies; deformation potentials "
        "and dense bands deferred); with separate_mobility amset also reports a "
        "per-mechanism breakdown (a resolved-spectrum layer deferred here). The "
        "schemes record the iterative-BTE method, the adp_imp_pop scattering, "
        "and the boltztrap2 interpolation. Implicit, so not sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    compute_static_dielectric,
    compute_electronic_conductivity,
    compute_seebeck,
    compute_electronic_thermal_conductivity,
    compute_carrier_mobility,
)
