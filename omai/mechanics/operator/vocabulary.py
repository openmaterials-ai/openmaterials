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

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The stiffness tensor C and the homogeneous strain it differentiates
    # against (varepsilon^{str}, shared with the dft domain).
    "ElasticConstants": {"C", r"\varepsilon^{str}"},
    # The isotropic Voigt moduli and the mechanical pressure, each its own
    # scalar field symbol.
    "BulkModulus": {"K"},
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
