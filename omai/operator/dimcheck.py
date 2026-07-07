"""Dimension evaluation over sympy expressions (kernel P1 dimensional gate).

Given a curated per-domain registry of `symbol base name -> Dimension`
(populated at import time, like the vocabulary registry), `dimension_of`
computes the physical dimension of a sympy expression by structural
recursion, returning None whenever any symbol it needs is unknown. Unknown
means *skip*, never guess: the report treats a None as SKIPPED rather than
inventing a dimension.

Two things are proven, not guessed, and raise `DimensionalViolation`:
  * an `Add` of two summands whose dimensions are both known and differ;
  * a known-dimensionful argument to a transcendental (`exp`, `log`,
    `sinh`, `cosh`, `tanh`) or to the Bose-Einstein occupation
    `n_{BE}(...)`.
Equality of two `Eq` sides is compared by the *caller* (see
`dimensional_report`), not inside `dimension_of`.

Opaque dimensions in a lookup are treated as unknown (None); the algebra
never runs on an opaque dimension.

The registry is seeded per domain (see
`omai/thermal_transport/operator/dimensions_registry.py` and
`omai/materials/operator/dimensions_registry.py`), imported for side
effect next to each domain's vocabulary module.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import DIMENSIONLESS, Dimension

__all__ = [
    "SYMBOL_DIMENSIONS",
    "register_symbol_dimensions",
    "dimension_of",
    "DimensionalViolation",
]


# Live registry: symbol base name -> Dimension. Domains populate it via
# register_symbol_dimensions at import time; dimension_of reads it at call
# time. A symbol absent here (and absent from a call's `local` mapping) is
# unknown, so the expression evaluates to None (skip).
SYMBOL_DIMENSIONS: dict[str, Dimension] = {}


class DimensionalViolation(Exception):
    """Raised when an expression is PROVEN dimensionally inconsistent.

    Only fires on inconsistencies both sides of which are known: an Add of
    two known, differing dimensions, or a known-dimensionful argument to a
    function that requires a dimensionless argument. An unknown never
    raises; it makes the surrounding expression None (skip).
    """


def register_symbol_dimensions(mapping) -> None:
    """Merge `mapping` (base name -> Dimension) into the global registry.

    Union semantics: two domains may register the same symbol with the same
    Dimension harmlessly. Re-registering a symbol with a *different*
    Dimension raises ValueError (a real conflict the domains must resolve).
    """
    for name, dim in mapping.items():
        existing = SYMBOL_DIMENSIONS.get(name)
        if existing is not None and existing != dim:
            raise ValueError(
                f"conflicting dimension registration for {name!r}: "
                f"{existing.name!r} != {dim.name!r}"
            )
        SYMBOL_DIMENSIONS[name] = dim


def _symbol_base_name(sym: sp.Basic) -> str:
    """Base name of a sympy free-symbol element.

    Mirrors omai.operator.validate._symbol_base_name: an Indexed keys on its
    IndexedBase name, a Symbol on its .name, anything else on str().
    """
    if isinstance(sym, sp.Indexed):
        return str(sym.base.name)
    if hasattr(sym, "name"):
        return str(sym.name)
    return str(sym)


def _lookup(name: str, local) -> Dimension | None:
    """Resolve a base name to a Dimension, consulting `local` first.

    `local` may map a name to None, an explicit "treat as unknown" override
    that shadows the global registry (used per-edge to blank a symbol whose
    global dimension is wrong for that edge's spaces). Opaque dimensions are
    treated as unknown.
    """
    if local is not None and name in local:
        dim = local[name]
    else:
        dim = SYMBOL_DIMENSIONS.get(name)
    if dim is None or dim.is_opaque:
        return None
    return dim


# Transcendental function classes whose argument must be dimensionless.
_DIMENSIONLESS_ARG_FUNCS = (sp.exp, sp.log, sp.sinh, sp.cosh, sp.tanh)
# Elementwise functions that pass their argument's dimension through.
_PASSTHROUGH_FUNCS = (sp.Abs, sp.conjugate, sp.re, sp.im)


def dimension_of(expr, local=None) -> Dimension | None:
    """Return the dimension of a sympy expression, or None if unknown.

    `local` is an optional {base name -> Dimension | None} mapping consulted
    before the global registry (per-edge parameters and explicit unknown
    overrides). A None dimension anywhere it is needed propagates to a None
    result (skip). Proven inconsistencies raise DimensionalViolation.
    """
    # Pure numbers (integers, rationals, floats, pi, I, oo) are dimensionless.
    if isinstance(expr, sp.Number) or (isinstance(expr, sp.Basic) and expr.is_number):
        return DIMENSIONLESS

    # Leaf symbols and indexed elements: registry lookup by base name.
    if isinstance(expr, (sp.Symbol, sp.Indexed)):
        return _lookup(_symbol_base_name(expr), local)

    # KroneckerDelta is a dimensionless indicator.
    if isinstance(expr, sp.KroneckerDelta):
        return DIMENSIONLESS

    # Addition: every known term must agree; unknown makes the sum unknown.
    if isinstance(expr, sp.Add):
        known: Dimension | None = None
        saw_unknown = False
        for term in expr.args:
            d = dimension_of(term, local)
            if d is None:
                saw_unknown = True
                continue
            if known is None:
                known = d
            elif known != d:
                raise DimensionalViolation(
                    f"add of incompatible dimensions: "
                    f"{known.canonical()} + {d.canonical()}"
                )
        if saw_unknown:
            return None
        return known

    # Multiplication: product of factor dimensions; unknown factor -> unknown.
    if isinstance(expr, sp.Mul):
        result = DIMENSIONLESS
        for factor in expr.args:
            d = dimension_of(factor, local)
            if d is None:
                return None
            result = result * d
        return result

    # Power: base ** exponent.
    if isinstance(expr, sp.Pow):
        base, exp = expr.args
        base_dim = dimension_of(base, local)
        if base_dim is None:
            return None
        if exp.is_Integer:
            return base_dim ** int(exp)
        # Non-integer / symbolic exponent: only sensible if the base is
        # dimensionless (then the whole thing stays dimensionless).
        if base_dim == DIMENSIONLESS:
            return DIMENSIONLESS
        return None

    # Sum / Integral over a summand.
    if isinstance(expr, (sp.Sum, sp.Integral)):
        summand_dim = dimension_of(expr.function, local)
        if summand_dim is None:
            return None
        if isinstance(expr, sp.Integral):
            # ∫ f dx carries an extra factor of dim(x) per integration
            # variable; unknown if any variable's dimension is unknown.
            for limit in expr.limits:
                var = limit[0]
                var_dim = dimension_of(var, local)
                if var_dim is None:
                    return None
                summand_dim = summand_dim * var_dim
        return summand_dim

    # Derivative(f, x1, x2, ...) -> dim(f) / prod(dim(xi)).
    if isinstance(expr, sp.Derivative):
        f_dim = dimension_of(expr.expr, local)
        if f_dim is None:
            return None
        result = f_dim
        for var, count in expr.variable_count:
            var_dim = dimension_of(var, local)
            if var_dim is None:
                return None
            result = result / (var_dim ** int(count))
        return result

    # Elementwise passthrough functions (|x|, conjugate, re, im).
    if isinstance(expr, _PASSTHROUGH_FUNCS):
        return dimension_of(expr.args[0], local)

    # Transcendentals whose argument must be dimensionless.
    if isinstance(expr, _DIMENSIONLESS_ARG_FUNCS):
        arg_dim = dimension_of(expr.args[0], local)
        if arg_dim is not None and arg_dim != DIMENSIONLESS:
            raise DimensionalViolation(
                f"{type(expr).__name__} of dimensionful argument "
                f"({arg_dim.canonical()})"
            )
        return DIMENSIONLESS

    # Undefined applied functions: n_{BE}(...) requires a dimensionless
    # argument and returns a dimensionless occupation; \delta(x) is a
    # Dirac delta carrying 1 / dim(x). Any other function is unknown.
    if isinstance(expr, sp.core.function.AppliedUndef):
        fname = type(expr).__name__
        if fname == "n_{BE}":
            arg_dim = dimension_of(expr.args[0], local)
            if arg_dim is not None and arg_dim != DIMENSIONLESS:
                raise DimensionalViolation(
                    f"n_{{BE}} of dimensionful argument ({arg_dim.canonical()})"
                )
            return DIMENSIONLESS
        if fname == r"\delta":
            arg_dim = dimension_of(expr.args[0], local)
            if arg_dim is None:
                return None
            return DIMENSIONLESS / arg_dim
        return None

    # Anything else: unknown (skip).
    return None
