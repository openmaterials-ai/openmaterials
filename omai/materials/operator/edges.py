"""Operators (edges) for the materials domain (grown from AtomisticSkills)."""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.materials.operator.nodes import ACTIVATION_ENERGY, DIFFUSIVITY_STATE
from omai.materials.operator.shared_primitives import MEAN_SQUARED_DISPLACEMENT, TEMPERATURE

_D = sp.Symbol("D", positive=True)
_D0 = sp.Symbol("D_0", positive=True)
_Ea = sp.Symbol("E_a", positive=True)
_kB = sp.Symbol("k_B", positive=True)
_T = sp.Symbol("T", positive=True)
_d = sp.Symbol("d", positive=True, integer=True)
_slope = sp.Symbol(r"\mathrm{slope}_{MSD}", positive=True)

# Einstein relation: D = slope of MSD(t) / (2 d). Closed-form in the slope.
contract_diffusivity = Operator(
    name="contract_diffusivity",
    inputs=(MEAN_SQUARED_DISPLACEMENT,),
    outputs=(DIFFUSIVITY_STATE,),
    formula=sp.Eq(_D, _slope / (2 * _d)),
    description="Einstein relation: D = slope(MSD(t)) / (2 d) in the linear regime.",
)

# Arrhenius fit over D(T) at several temperatures. A regression, not a
# closed-form map from a single input, so mark it non-executable in sympy.
fit_arrhenius = Operator(
    name="fit_arrhenius",
    inputs=(DIFFUSIVITY_STATE, TEMPERATURE),
    outputs=(ACTIVATION_ENERGY,),
    formula=sp.Eq(sp.Function("D")(_T), _D0 * sp.exp(-_Ea / (_kB * _T))),
    is_executable_in_sympy_override=False,
    description="Weighted Arrhenius fit of D(T) = D0 exp(-E_a/k_B T) over temperatures.",
)

EDGES: tuple[Operator, ...] = (contract_diffusivity, fit_arrhenius)
