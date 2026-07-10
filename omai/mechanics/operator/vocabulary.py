r"""Formula symbol vocabulary of the mechanics domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.mechanics.operator` is imported. Union semantics per space.

The elastic-tensor edge differentiates the ground-state stress against a
homogeneous strain, so ElasticConstants carries both its own field symbol C and
the strain IndexedBase \varepsilon^{str}. That strain base name is the one the
dft ground-state domain already registered (under its Stress space, an input of
compute_elastic_constants, so it is derivable there already); registering it on
the output space too keeps it derivable for the future Pattern C energy-route
producer (TotalEnergy + Structure -> ElasticConstants), whose edge would not
touch Stress. The pressure contraction reads Stress's \sigma, already registered
by the dft domain and re-declared here for locality.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_formula_constants, register_space_symbols

# The equilibrium cell volume V_0 the EOS fit locates (the curvature point of
# the Birch-Murnaghan E(V) route to the bulk modulus). E_{tot} and V_{cell}
# are registered by the ground-state / thermal domains; V_0 is new.
register_formula_constants({"V_0"})

register_space_symbols({
    # The stiffness tensor C and the homogeneous strain it differentiates
    # against (varepsilon^{str}, shared with the dft domain).
    "ElasticConstants": {"C", r"\varepsilon^{str}"},
    # The isotropic Voigt moduli and the mechanical pressure, each its own
    # scalar field symbol. BulkModulus also carries the EOS-route symbols (the
    # total energy it curves and the equilibrium volume) for the Pattern C
    # alternative producer compute_bulk_modulus_eos.
    "BulkModulus": {"K", "E_{tot}", "V_{cell}", "V_0"},
    "ShearModulus": {"G"},
    "Pressure": {"P"},
    # The two remaining isotropic combinations of K and G (2026-07-09).
    # E_Y, not bare E (the thermal domain's per-atom MD energy); Latin nu,
    # not the generic branch dummy \nu (sympy renders it Greek regardless).
    "YoungsModulus": {"E_Y"},
    "PoissonRatio": {"nu"},
    # The stress the pressure contracts (already registered by the dft domain).
    "Stress": {r"\sigma"},
})
