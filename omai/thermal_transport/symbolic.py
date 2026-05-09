"""Abstract DAG for lattice thermal transport.

Twelve nodes (states) and eleven edges (operations) producing the lattice
thermal conductivity κ(T) from the Born–Oppenheimer potential and a chosen
temperature. Every edge carries a symbolic formula — sympy expression for
closed-form ops, sympy.Eq for implicit ones, LaTeX text where indexed sums
make sympy encoding awkward.

This is the Phase 1 substrate target. Adapters (kaldo, phono3py, ShengBTE)
declare their unit/convention/discretization choices against these abstract
nodes and operations.
"""

from __future__ import annotations

import sympy as sp

from omai.abstract.dimensions import (
    DIMENSIONLESS,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_TEMPERATURE,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.abstract.operation import Operation, Parameter
from omai.abstract.physics_types import PhysicsType
from omai.abstract.state import Observable, State


# ---------------------------------------------------------------------------
# Nodes (states)
# ---------------------------------------------------------------------------

POTENTIAL = State(
    physics_type=PhysicsType.POTENTIAL,
    name="Potential",
    observables=(Observable("potential", OPAQUE),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = State(
    physics_type=PhysicsType.TEMPERATURE,
    name="Temperature",
    observables=(Observable("temperature", TEMPERATURE),),
)

FORCE_CONSTANTS_2 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=2]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_SQUARED),),
    type_parameters={"order": 2},
)

FORCE_CONSTANTS_3 = State(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=3]",
    observables=(Observable("phi", ENERGY_PER_LENGTH_CUBED),),
    type_parameters={"order": 3},
)

DYNAMICAL_MATRIX = State(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    observables=(Observable("D", FREQUENCY),),
    description="D(q) such that D e_qν = ω²_qν e_qν; entries have dimension frequency² but are commonly stored as frequency for convenience.",
)

FREQUENCY_STATE = State(
    physics_type=PhysicsType.FREQUENCY,
    name="Frequency",
    observables=(Observable("omega", FREQUENCY),),
)

EIGENVECTORS = State(
    physics_type=PhysicsType.EIGENVECTORS,
    name="Eigenvectors",
    observables=(Observable("e", DIMENSIONLESS),),
    description=(
        "Per-mode eigenvectors of the dynamical matrix. Phase- and "
        "degenerate-subspace-rotation freedom: not directly comparable across "
        "adapters at the per-mode level."
    ),
)

GROUP_VELOCITY = State(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    observables=(Observable("v", LENGTH_TIMES_FREQUENCY),),
)

HEAT_CAPACITY = State(
    physics_type=PhysicsType.HEAT_CAPACITY,
    name="HeatCapacity",
    observables=(Observable("c", ENERGY_PER_TEMPERATURE),),
)

LINEWIDTH = State(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth",
    observables=(Observable("Gamma", FREQUENCY),),
    canonical_conventions={
        # Whether the emitted Gamma is the imaginary self-energy or twice it
        # ("the linewidth"). Adapters that emit 2 Im Sigma override.
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
)

MEAN_FREE_DISPLACEMENT = State(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement",
    observables=(Observable("F", LENGTH),),
    description="Per-mode mean free displacement F_qν = v_qν · τ_qν · (energy gradient term); the BTE-solution observable.",
)

THERMAL_CONDUCTIVITY_STATE = State(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity",
    observables=(Observable("kappa", THERMAL_CONDUCTIVITY),),
)


NODES: tuple[State, ...] = (
    POTENTIAL,
    TEMPERATURE_STATE,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    DYNAMICAL_MATRIX,
    FREQUENCY_STATE,
    EIGENVECTORS,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    LINEWIDTH,
    MEAN_FREE_DISPLACEMENT,
    THERMAL_CONDUCTIVITY_STATE,
)


# ---------------------------------------------------------------------------
# Symbols used in the formulas below
# ---------------------------------------------------------------------------

_q, _qp, _qpp = sp.symbols("q q' q''", real=True)
_nu, _nup, _nupp = sp.symbols("nu nu' nu''", integer=True)
_omega, _omegap, _omegapp = sp.symbols(r"omega_{q\nu} omega_{q'\nu'} omega_{q''\nu''}", positive=True)
_T = sp.Symbol("T", positive=True)
_kB, _hbar = sp.symbols("k_B hbar", positive=True)
_alpha, _beta = sp.symbols("alpha beta")
_V = sp.Symbol("V", positive=True)
_Nq = sp.Symbol("N_q", positive=True, integer=True)
_v_alpha = sp.Symbol(r"v^\alpha_{q\nu}")
_v_beta = sp.Symbol(r"v^\beta_{q\nu}")
_F_beta = sp.Symbol(r"F^\beta_{q\nu}")
_c_qnu = sp.Symbol("c_{q\\nu}")
_Gamma = sp.Symbol(r"\Gamma_{q\nu}", positive=True)
_n_BE = sp.Function("n_BE")(_omega / _T)


# ---------------------------------------------------------------------------
# Edges (operations)
# ---------------------------------------------------------------------------

provide_potential = Operation(
    name="provide_potential",
    inputs=(),
    outputs=(POTENTIAL,),
    formula=None,
    description="Source: an opaque label for the chosen potential (Tersoff, PBE, ...).",
)

provide_temperature = Operation(
    name="provide_temperature",
    inputs=(),
    outputs=(TEMPERATURE_STATE,),
    parameters=(Parameter("temperature", TEMPERATURE),),
    formula=None,
    description="Source: the temperature at which subsequent T-dependent observables are evaluated.",
)

compute_force_constants_2 = Operation(
    name="compute_force_constants[order=2]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_2,),
    formula=r"\Phi^{(2)}_{ij}(R) = \left.\frac{\partial^2 V}{\partial u_i(0)\,\partial u_j(R)}\right|_{u=0}",
    description="Second derivative of the potential at equilibrium, after harmonic truncation.",
)

compute_force_constants_3 = Operation(
    name="compute_force_constants[order=3]",
    inputs=(POTENTIAL,),
    outputs=(FORCE_CONSTANTS_3,),
    formula=r"\Phi^{(3)}_{ijk}(R, R') = \left.\frac{\partial^3 V}{\partial u_i(0)\,\partial u_j(R)\,\partial u_k(R')}\right|_{u=0}",
    description="Third derivative of the potential at equilibrium, after cubic truncation.",
)

compute_dynamical_matrix = Operation(
    name="compute_dynamical_matrix",
    inputs=(FORCE_CONSTANTS_2,),
    outputs=(DYNAMICAL_MATRIX,),
    formula=r"D_{ij}(\mathbf{q}) = \frac{1}{\sqrt{M_i M_j}}\sum_{R} \Phi^{(2)}_{ij}(R)\, e^{i\mathbf{q}\cdot R}",
    description="Bloch sum over lattice vectors, mass-weighted.",
)

compute_dispersion = Operation(
    name="compute_dispersion",
    inputs=(DYNAMICAL_MATRIX,),
    outputs=(FREQUENCY_STATE, EIGENVECTORS),  # multi-output
    formula=sp.Eq(
        sp.Symbol(r"D(\mathbf{q})") * sp.Symbol(r"e_{q\nu}"),
        sp.Symbol(r"\omega^2_{q\nu}") * sp.Symbol(r"e_{q\nu}"),
    ),
    description=(
        "Eigendecomposition of D(q): produces ω_qν and orthonormal e_qν. "
        "Implicit equation; degenerate subspaces have rotation freedom on e."
    ),
)

compute_group_velocity = Operation(
    name="compute_group_velocity",
    inputs=(DYNAMICAL_MATRIX, FREQUENCY_STATE, EIGENVECTORS),
    outputs=(GROUP_VELOCITY,),
    formula=r"v^\alpha_{q\nu} = \frac{1}{2\omega_{q\nu}}\, e^\dagger_{q\nu}\,\frac{\partial D(\mathbf{q})}{\partial q^\alpha}\, e_{q\nu}",
    description="Hellmann-Feynman applied to the eigenvalue equation.",
)

compute_heat_capacity = Operation(
    name="compute_heat_capacity",
    inputs=(FREQUENCY_STATE, TEMPERATURE_STATE),
    outputs=(HEAT_CAPACITY,),
    formula=(_hbar * _omega) ** 2
    / (4 * _kB * _T**2 * sp.sinh(_hbar * _omega / (2 * _kB * _T)) ** 2),
    description="Quantum (Bose-Einstein) per-mode heat capacity at temperature T.",
)

compute_linewidth = Operation(
    name="compute_linewidth",
    inputs=(FREQUENCY_STATE, EIGENVECTORS, FORCE_CONSTANTS_3, TEMPERATURE_STATE),
    outputs=(LINEWIDTH,),
    parameters=(Parameter("broadening_sigma", FREQUENCY),),
    algorithmic_conventions={
        "broadening_param": "stdev",  # canonical: σ = stdev of Gaussian
    },
    formula=(
        r"\Gamma_{q\nu} = \frac{\pi}{N\hbar^2}\sum_{q'\nu',\,q''\nu''} "
        r"|V_3(q\nu, q'\nu', q''\nu'')|^2 \,\Big["
        r"(1 + n' + n'')\,\delta(\omega-\omega'-\omega'') "
        r"+ 2(n' - n'')\,\delta(\omega+\omega'-\omega'')\Big]"
    ),
    description=(
        "Imaginary self-energy from three-phonon scattering (Fermi's golden "
        "rule). Energy delta is replaced by a Gaussian of canonical width "
        "σ = stdev. n_BE = (e^{ℏω/k_B T} - 1)^{-1}."
    ),
)

solve_bte = Operation(
    name="solve_bte",
    inputs=(FREQUENCY_STATE, GROUP_VELOCITY, LINEWIDTH, TEMPERATURE_STATE),
    outputs=(MEAN_FREE_DISPLACEMENT,),
    algorithmic_conventions={
        "bte_solver": "rta",  # canonical: relaxation-time approximation
        # Other values: "iterative", "direct_inverse"
    },
    formula=(
        r"\text{RTA: } F_{q\nu} = \frac{v_{q\nu}}{2\Gamma_{q\nu}};\quad "
        r"\text{LBTE: solve } \mathcal{M}\mathbf{F} = \mathbf{c}\cdot\mathbf{v}"
    ),
    description=(
        "BTE solution. RTA is closed-form. Iterative/direct/LBTE solve a "
        "linear system involving the full collision matrix M; the off-"
        "diagonal terms capture inter-mode redistribution."
    ),
)

contract_kappa = Operation(
    name="contract_kappa",
    inputs=(HEAT_CAPACITY, GROUP_VELOCITY, MEAN_FREE_DISPLACEMENT),
    outputs=(THERMAL_CONDUCTIVITY_STATE,),
    formula=(
        sp.Rational(1, 1)
        / (_V * _Nq)
        * sp.Sum(_c_qnu * _v_alpha * _F_beta, (_nu, 0, sp.oo))
    ),
    description=r"\kappa^{\alpha\beta} = \frac{1}{V N_q}\sum_{q\nu} c_{q\nu}\, v^\alpha_{q\nu}\, F^\beta_{q\nu}.",
)


EDGES: tuple[Operation, ...] = (
    provide_potential,
    provide_temperature,
    compute_force_constants_2,
    compute_force_constants_3,
    compute_dynamical_matrix,
    compute_dispersion,
    compute_group_velocity,
    compute_heat_capacity,
    compute_linewidth,
    solve_bte,
    contract_kappa,
)
