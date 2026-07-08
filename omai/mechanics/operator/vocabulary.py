r"""Formula symbol vocabulary of the mechanics domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.mechanics.operator` is imported. Union semantics per space.

The elastic-tensor edge differentiates the ground-state energy against a
homogeneous strain, so ElasticConstants carries both its own field symbol C and
the strain IndexedBase \varepsilon^{str}. That strain base name is the one the
dft ground-state domain already registered (under its Stress space); registering
it here too, on this edge's output space, is what lets validate_dag derive it for
compute_elastic_constants (whose inputs are TotalEnergy and Structure, not
Stress). The pressure contraction reads Stress's \sigma, already registered by
the dft domain and re-declared here for locality.

V_{cell} is a global FORMULA_CONSTANT (registered by the thermal domain), so it
needs no per-space entry.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The stiffness tensor C and the homogeneous strain it is the second
    # derivative with respect to (varepsilon^{str}, shared with the dft domain).
    "ElasticConstants": {"C", r"\varepsilon^{str}"},
    # The isotropic Voigt moduli and the mechanical pressure, each its own
    # scalar field symbol.
    "BulkModulus": {"K"},
    "ShearModulus": {"G"},
    "Pressure": {"P"},
    # The stress the pressure contracts (already registered by the dft domain).
    "Stress": {r"\sigma"},
})
