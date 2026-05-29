"""Representation-layer executor.

For closed-form edges, lambdify the operator-layer formula and evaluate
it against input Representations. For implicit edges, refuse and point
at the adapter that should own the external solve.

The executor is the **runtime** of the operator-layer DAG: without it
the graph declares relationships but doesn't run them. The closed-form
subset (per-mode thermodynamics, identity edges, Matthiessen sums,
Wigner combination, contractions) can be evaluated directly off the
sympy formula via ``sympy.lambdify`` against numpy; implicit edges
(eigenvalue problems, linear BTE solves, NAC q→0 limits) require an
adapter-owned external solver and the executor raises
``ExternalSolveRequired`` for those.

Closed-form executability is opt-in via
``Operator.is_executable_in_sympy_override=True`` on the edge
declaration; the default heuristic in ``Operator.is_executable_in_sympy_default``
is conservative (LHS / RHS disjoint free symbols), so most indexed
formulas need the override to be marked executable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Union

import numpy as np
import sympy as sp

from omai.operator.operator import Operator
from omai.operator.space import Space
from omai.operator.validate import _SPACE_SYMBOLS
from omai.representation.adapter import SpaceRepresentationSpec
from omai.representation.instance import Representation


__all__ = [
    "ExternalSolveRequired",
    "NoSourceError",
    "Source",
    "TraceStep",
    "ComputeResult",
    "apply_edge",
    "compute",
    "operator_form_spec",
]


class ExternalSolveRequired(RuntimeError):
    """Raised by ``apply_edge`` when an Operator is not sympy-executable.

    The operator's formula encodes an implicit relation (e.g. an
    eigenvalue problem, a linear system in the unknown, or a q→0 limit
    that doesn't lambdify cleanly). The caller must dispatch to an
    adapter-owned external solver.
    """


class NoSourceError(RuntimeError):
    """Raised by ``compute`` when a space has neither a registered Source
    nor a producing Operator in the edge set."""


# ---------------------------------------------------------------------------
# Numerical values for the bare physics constants and BZ-mesh symbols that
# can appear in a closed-form RHS. Values in SI for ℏ and k_B; counters
# are filled in from the input data when possible.
# ---------------------------------------------------------------------------

# Canonical units in the operator layer:
#   Frequency      → linear THz  (= 1e12 cycles/s)
#   Temperature    → K
#   Heat capacity  → J/K
# To make the per-mode thermodynamic formulas (with ℏ, k_B) work in those
# canonical units we use values of ℏ and k_B that absorb the unit choice.
# ℏω with ω in linear THz must produce energy in J → use ℏ in J·s with an
# explicit 2π·1e12 conversion (since linear-THz is *cycles/s*, not rad/s):
#   ℏ_eff = h · 1e12 [J / (linear THz)]
# where h = 6.62607015e-34 J·s. Equivalently ℏω_lin = h · ω_THz_lin.
_h_PLANCK = 6.62607015e-34  # J·s
_HBAR_LINEAR_THZ_FACTOR = _h_PLANCK * 1.0e12  # J per (linear THz) — matches ℏω
_KB = 1.380649e-23  # J / K
_N_A_VALUE = 6.02214076e23  # 1 / mol


# Symbol-name → numeric-value table. Keys are the LaTeX names sympy uses on
# the Symbol/IndexedBase atoms in formulas (matching the registry in
# omai.operator.validate._PERMITTED_CONSTANTS).
_PHYSICS_CONSTANTS: dict[str, float] = {
    r"\hbar": _HBAR_LINEAR_THZ_FACTOR,
    "k_B": _KB,
    "N_A": _N_A_VALUE,
}


# ---------------------------------------------------------------------------
# Output operator-form spec helper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _OperatorFormSpaceAdapterSpec(SpaceRepresentationSpec):
    """Synthetic SpaceRepresentationSpec representing operator (canonical) form.

    Used as the ``space_adapter_spec`` on Representations produced by the
    executor. Carries no unit / normalization overrides — values are in
    canonical units by definition (``is_operator=True``).
    """


def operator_form_spec(space: Space) -> SpaceRepresentationSpec:
    """Return a synthetic SpaceRepresentationSpec representing operator form.

    The result has ``representation_name='operator'`` and declares no
    observable_units; any consumer that tries to canonicalise it via
    ``to_operator`` will see ``is_operator=True`` and skip the
    multiplication.
    """
    return _OperatorFormSpaceAdapterSpec(space=space, representation_name="operator")


# ---------------------------------------------------------------------------
# n_BE expansion (the entropy / internal-energy formulas use a sympy
# Function `n_{BE}(ω/T)` that lambdify can't evaluate directly; we
# substitute the explicit Bose-Einstein form before lambdifying).
# ---------------------------------------------------------------------------


def _expand_bose_einstein(expr: sp.Basic, hbar_sym: sp.Symbol, kB_sym: sp.Symbol,
                          T_sym: sp.Symbol) -> sp.Basic:
    """Substitute every ``n_BE(x)`` application in ``expr`` with the explicit
    Bose-Einstein occupation ``1 / (exp(ℏ · x / k_B) - 1)``.

    The formulas in this codebase use ``n_BE(ω/T)`` as a shorthand for
    ``1 / (exp(ℏω/k_BT) - 1)``: the function argument is ω/T, not the
    canonical ℏω/k_BT, so the substitution absorbs ℏ/k_B into the
    exponential. After substitution the resulting expression depends
    only on standard sympy operations and is lambdifiable to numpy.
    """
    n_BE = sp.Function("n_{BE}")
    # Find all applications of n_BE; replace with the explicit form.
    for n_app in list(expr.atoms(sp.Function)):
        if isinstance(n_app, n_BE):
            x = n_app.args[0]
            # x here is (ω / T); plug into the Bose-Einstein formula.
            replacement = 1 / (sp.exp(hbar_sym * x / kB_sym) - 1)
            expr = expr.subs(n_app, replacement)
    return expr


# ---------------------------------------------------------------------------
# Symbol mapping: which IndexedBase / Symbol on the RHS corresponds to which
# input Representation.
# ---------------------------------------------------------------------------


def _space_primary_symbols(space: Space) -> frozenset[str]:
    """Return the IndexedBase / Symbol base names associated with ``space``.

    Looks up the per-space symbol registry that ``omai.operator.validate``
    uses for the AOT formula-vocabulary check. The registry is the single
    source of truth for the field-name → sympy-symbol mapping.
    """
    return _SPACE_SYMBOLS.get(space.name, frozenset())


def _find_input_indexed_atoms(
    formula_rhs: sp.Basic,
    input_space: Space,
) -> list[sp.Indexed]:
    """Return the Indexed sub-expressions on the RHS that belong to
    ``input_space``.

    "Belong to" means: the underlying IndexedBase's name appears in the
    space's primary-symbol set (per ``_space_primary_symbols``).
    """
    primary = _space_primary_symbols(input_space)
    indexed_atoms: list[sp.Indexed] = []
    for atom in formula_rhs.atoms(sp.Indexed):
        if str(atom.base.name) in primary:
            indexed_atoms.append(atom)
    return indexed_atoms


def _find_input_scalar_symbol(
    formula_rhs: sp.Basic,
    input_space: Space,
) -> sp.Symbol | None:
    """Return the bare Symbol on the RHS that names ``input_space``.

    For scalar inputs (Temperature) the formula references the space via a
    plain ``sp.Symbol`` rather than an IndexedBase. We look for that symbol
    in the space's primary-symbol set.
    """
    primary = _space_primary_symbols(input_space)
    for atom in formula_rhs.atoms(sp.Symbol):
        if isinstance(atom, sp.Indexed):
            continue
        if str(atom.name) in primary:
            return atom
    return None


# ---------------------------------------------------------------------------
# Multi-channel state-name disambiguation
# ---------------------------------------------------------------------------
#
# Sum_linewidths has three Linewidth inputs (anharmonic, isotope, boundary)
# and the formula RHS uses three distinct IndexedBases (\Gamma^{anh},
# \Gamma^{iso}, \Gamma^{bnd}). The shared `_STATE_SYMBOLS` registry on the
# TOTAL channel state lists all four names; the *per-channel* states each
# list a single distinguishing name. We rely on that distinguishing name
# to wire each input to its formula symbol.


def _identify_single_indexed_for_input(
    formula_rhs: sp.Basic,
    input_space: Space,
) -> sp.Indexed:
    """Return the unique Indexed atom on RHS belonging to ``input_space``.

    Raises NotImplementedError if zero or multiple atoms match — both cases
    fall outside the closed-form subset the executor handles.
    """
    matches = _find_input_indexed_atoms(formula_rhs, input_space)
    if not matches:
        raise NotImplementedError(
            f"executor: no Indexed atom matches input space "
            f"{input_space.name!r} (primary symbols: "
            f"{sorted(_space_primary_symbols(input_space))}); "
            f"this edge may not be in the closed-form subset."
        )
    # Multiple Indexed expressions sharing the same IndexedBase (e.g. the
    # same Γ appearing twice in a sum at different (q, ν) tuples) are OK —
    # they all bind to the same input array. Pick one representative.
    bases_seen = {m.base.name for m in matches}
    if len(bases_seen) > 1:
        raise NotImplementedError(
            f"executor: input space {input_space.name!r} matches multiple "
            f"distinct IndexedBases {sorted(bases_seen)!r} in the RHS; "
            f"this is ambiguous in the current executor."
        )
    return matches[0]


# ---------------------------------------------------------------------------
# apply_edge
# ---------------------------------------------------------------------------


def apply_edge(
    op: Operator,
    *inputs: Representation,
    constants: dict[str, float] | None = None,
) -> Representation:
    """Evaluate ``op`` against the input Representations and return the
    output Representation.

    All inputs must be in operator form (``is_operator=True``).
    The output Representation is returned in operator form too.

    Raises:
        ExternalSolveRequired: if ``op.is_executable_in_sympy`` is False,
            indicating that the operator is implicit and must be solved
            externally by an adapter.
        ValueError: if the inputs don't match ``op.inputs`` in number or
            in space, or if any input is not in operator form.
        NotImplementedError: if the operator has multiple outputs (the
            current executor handles single-output edges only), or if the
            executor cannot identify a unique formula symbol for an input.
    """
    # 1. Executability gate.
    if not op.is_executable_in_sympy:
        raise ExternalSolveRequired(
            f"operator {op.name!r} is not sympy-executable; dispatch to an "
            f"adapter-owned external solver. Its formula encodes an "
            f"implicit relation (eigenvalue problem, linear system in the "
            f"unknown, or otherwise non-closed-form)."
        )

    # 2. Multi-output edges out of scope for this stage.
    if op.is_multi_output():
        raise NotImplementedError(
            f"operator {op.name!r} has multiple outputs "
            f"({[s.name for s in op.outputs]!r}); the current executor "
            f"handles single-output edges only."
        )

    # 3. Input count must match op.inputs.
    if len(inputs) != len(op.inputs):
        raise ValueError(
            f"operator {op.name!r} expects {len(op.inputs)} inputs, "
            f"got {len(inputs)}"
        )

    # 4. Per-input checks: same space, operator form.
    for rep, expected_space in zip(inputs, op.inputs):
        if rep.space != expected_space:
            raise ValueError(
                f"operator {op.name!r}: input space mismatch — expected "
                f"{expected_space.name!r}, got {rep.space.name!r}"
            )
        if not rep.is_operator:
            raise ValueError(
                f"operator {op.name!r}: input for space "
                f"{rep.space.name!r} is not in operator form; call "
                f"to_operator(rep) first."
            )

    # 5. Build the substitution map from formula symbols to numeric values
    #    / numpy arrays.
    formula = op.formula
    if not isinstance(formula, sp.Eq):
        raise NotImplementedError(
            f"operator {op.name!r}: executor requires a sympy.Eq formula "
            f"(got {type(formula).__name__}). Closed-form edges must "
            f"declare their formula as sp.Eq(LHS, RHS)."
        )
    rhs = formula.rhs

    # Bind physics constants by atomic symbol name (matches the LaTeX names
    # in _PHYSICS_CONSTANTS).
    physics_subs: dict[sp.Symbol, float] = {}
    for atom in rhs.atoms(sp.Symbol):
        if isinstance(atom, sp.Indexed):
            continue
        name = str(atom.name)
        if name in _PHYSICS_CONSTANTS:
            physics_subs[atom] = _PHYSICS_CONSTANTS[name]

    # Identify n_BE applications (sympy Function `n_{BE}`) and expand them
    # *before* the indexed-symbol substitutions, since the expansion uses
    # ℏ / k_B explicitly. The substitution happens against the *raw* ω/T
    # arguments.
    hbar_sym = None
    kB_sym = None
    T_sym = None
    for atom in rhs.atoms(sp.Symbol):
        if isinstance(atom, sp.Indexed):
            continue
        name = str(atom.name)
        if name == r"\hbar":
            hbar_sym = atom
        elif name == "k_B":
            kB_sym = atom
        elif name == "T":
            T_sym = atom
    # Some formulas use n_BE but don't carry an explicit `T` in their
    # *outermost* free symbols (sympy may detect `T` only inside the
    # function's argument); pull it out of the n_BE arguments as well.
    if T_sym is None:
        n_BE = sp.Function("n_{BE}")
        for n_app in rhs.atoms(sp.Function):
            if isinstance(n_app, n_BE):
                for s in n_app.args[0].atoms(sp.Symbol):
                    if str(s.name) == "T":
                        T_sym = s
                        break
            if T_sym is not None:
                break

    # If the formula uses n_BE we *must* have ℏ and k_B available so the
    # explicit expansion is well-formed.
    n_BE = sp.Function("n_{BE}")
    uses_n_BE = any(
        isinstance(f, n_BE) for f in rhs.atoms(sp.Function)
    )
    if uses_n_BE:
        if hbar_sym is None:
            hbar_sym = sp.Symbol(r"\hbar", positive=True)
            physics_subs[hbar_sym] = _HBAR_LINEAR_THZ_FACTOR
        if kB_sym is None:
            kB_sym = sp.Symbol("k_B", positive=True)
            physics_subs[kB_sym] = _KB
        rhs = _expand_bose_einstein(rhs, hbar_sym, kB_sym, T_sym)

    # 6. For each input, find its formula symbol and bind to a dummy.
    #    Inputs that are scalars (Temperature, dimensionless) bind to a
    #    plain Symbol; inputs that are arrays bind to a dummy Symbol that
    #    replaces every Indexed expression sharing the input's IndexedBase.
    input_dummies: list[tuple[sp.Symbol, np.ndarray | float]] = []
    # Map from input IndexedBase name → input data array. Used both for
    # the elementwise Indexed → dummy substitution AND for Sum elimination.
    base_name_to_array: dict[str, np.ndarray] = {}
    seen_replacements: dict[sp.Indexed, sp.Symbol] = {}
    for rep, space in zip(inputs, op.inputs):
        # Try IndexedBase first (most fields), fall back to scalar Symbol.
        indexed_matches = _find_input_indexed_atoms(rhs, space)
        if indexed_matches:
            base_names = {str(m.base.name) for m in indexed_matches}
            if len(base_names) > 1:
                raise NotImplementedError(
                    f"operator {op.name!r}: input space {space.name!r} "
                    f"matches multiple distinct IndexedBases "
                    f"{sorted(base_names)!r} in the RHS; ambiguous."
                )
            base_name = next(iter(base_names))
            data = np.asarray(rep.data)
            base_name_to_array[base_name] = data
            dummy = sp.Symbol(f"_{_sanitize(base_name)}_in", positive=False)
            for atom in list(rhs.atoms(sp.Indexed)):
                if str(atom.base.name) == base_name and atom not in seen_replacements:
                    seen_replacements[atom] = dummy
            input_dummies.append((dummy, data))
        else:
            # Scalar fallback: the formula uses a bare Symbol (Temperature).
            scalar_sym = _find_input_scalar_symbol(rhs, space)
            if scalar_sym is None:
                raise NotImplementedError(
                    f"operator {op.name!r}: cannot map input space "
                    f"{space.name!r} to a formula symbol. Neither an "
                    f"IndexedBase nor a scalar Symbol on the RHS matches "
                    f"its primary symbols "
                    f"({sorted(_space_primary_symbols(space))})."
                )
            data = np.asarray(rep.data)
            if data.shape == ():
                input_dummies.append((scalar_sym, float(data)))
            else:
                input_dummies.append((scalar_sym, data))

    # 6a. Eliminate full-range BZ Sums. The closed-form contraction edges
    #     (contract_molar_*, contract_volumetric_*) wrap a single Indexed
    #     summand in a Sum over the full BZ × mode grid. For each Sum we
    #     accept, the result is just np.sum(input_array_for_that_indexed)
    #     and we bind a dummy symbol to that scalar. We also bind the
    #     BZ-mesh counters (N_q, N) from the same input's shape.
    sum_dummies: list[tuple[sp.Symbol, float]] = []
    bzmesh_subs: dict[sp.Symbol, float] = {}
    for sum_atom in list(rhs.atoms(sp.Sum)):
        summand = sum_atom.function
        # The summand may be a single Indexed (c[q,ν]) or a product
        # containing one Indexed plus only constants / dummy indices.
        indexed_in_summand = list(summand.atoms(sp.Indexed))
        if len(indexed_in_summand) != 1:
            raise NotImplementedError(
                f"operator {op.name!r}: Sum {sum_atom!r} has "
                f"{len(indexed_in_summand)} Indexed atoms; executor only "
                f"handles single-Indexed summands."
            )
        ix = indexed_in_summand[0]
        base = str(ix.base.name)
        if base not in base_name_to_array:
            raise NotImplementedError(
                f"operator {op.name!r}: Sum summand uses IndexedBase "
                f"{base!r} which doesn't correspond to any input."
            )
        arr = base_name_to_array[base]
        sum_value = float(np.sum(arr))
        # Bind BZ-mesh counters from the array shape. Convention: 2-D BZ
        # array is shape (N_q, N_modes), and N_modes = 3 * N_atoms.
        for sym in rhs.atoms(sp.Symbol):
            if isinstance(sym, sp.Indexed):
                continue
            name = str(sym.name)
            if name == "N_q":
                bzmesh_subs[sym] = float(arr.shape[0])
            elif name == "N" and arr.ndim >= 2:
                bzmesh_subs[sym] = float(arr.shape[1]) / 3.0
        # Replace the Sum with a fresh dummy symbol carrying the summed value.
        dummy = sp.Symbol(f"_sum_{_sanitize(base)}", positive=False)
        rhs = rhs.xreplace({sum_atom: dummy})
        sum_dummies.append((dummy, sum_value))

    # Apply the elementwise Indexed → dummy substitutions in a single pass.
    if seen_replacements:
        rhs = rhs.xreplace(seen_replacements)

    # 7. Substitute physics constants and BZ-mesh counters.
    if physics_subs:
        rhs = rhs.xreplace(physics_subs)
    if bzmesh_subs:
        rhs = rhs.xreplace(bzmesh_subs)
    # Sum dummies bind directly as numeric scalars.
    if sum_dummies:
        rhs = rhs.xreplace({sym: val for sym, val in sum_dummies})

    # 8. Remaining free symbols: must all be input dummies (or stray index
    #    variables that should have been eliminated by Indexed → dummy
    #    substitution). Detect anything stray and bail.
    bound_symbols = {sym for sym, _ in input_dummies}
    leftover = set(rhs.free_symbols) - bound_symbols
    # Strip out anything that's an integer dummy index (q, nu, alpha, beta,
    # i, j, k, gamma, delta) — those should have been absorbed by the
    # Indexed → dummy substitution, but if the formula references the bare
    # index outside an Indexed expression we leave it alone (and let
    # lambdify complain).
    if leftover:
        # If we still have an Indexed leftover (e.g. the formula's RHS had a
        # form we couldn't identify with any input), bail clearly.
        leftover_names = sorted(str(s) for s in leftover)
        raise NotImplementedError(
            f"operator {op.name!r}: after substitution, the RHS still has "
            f"unbound free symbols {leftover_names!r}. The executor cannot "
            f"evaluate this formula. Likely cause: a space-side symbol that "
            f"isn't in the per-space symbol registry, or an n_BE/sum form "
            f"that needs special handling."
        )

    # 9. Lambdify the simplified RHS and call it.
    arg_symbols = [sym for sym, _ in input_dummies]
    arg_values = [val for _, val in input_dummies]
    try:
        fn = sp.lambdify(arg_symbols, rhs, modules="numpy")
    except Exception as exc:  # pragma: no cover — sympy lambdify failure
        raise NotImplementedError(
            f"operator {op.name!r}: sympy.lambdify failed on the simplified "
            f"RHS ({rhs!r}): {exc}"
        ) from exc
    result = fn(*arg_values)
    result_arr = np.asarray(result)

    # 10. Wrap as an operator-form Representation.
    out_space = op.outputs[0]
    out_field_name = out_space.fields[0].name
    return Representation(
        space_adapter_spec=operator_form_spec(out_space),
        observable_name=out_field_name,
        data=result_arr,
        is_operator=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize(s: str) -> str:
    """Turn a LaTeX-y symbol name into a valid Python identifier fragment."""
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in {"_", "-"}:
            out.append("_")
    name = "".join(out)
    return name or "sym"


# ---------------------------------------------------------------------------
# Lazy DAG resolver
# ---------------------------------------------------------------------------

Source = Union[Representation, Callable[[], Representation]]


@dataclass(frozen=True)
class TraceStep:
    kind: str    # "LOAD" | "LIFT" | "EXEC"
    space: str   # space.name produced by this step
    detail: str  # representation_name for LOAD/LIFT; operator.name for EXEC


@dataclass(frozen=True)
class ComputeResult:
    representation: Representation
    trace: tuple[TraceStep, ...]


def _materialize(src: "Source") -> Representation:
    return src() if callable(src) else src


def compute(
    target: Space,
    sources: dict[str, "Source"],
    *,
    edges: tuple | None = None,
    constants: dict[str, float] | None = None,
) -> ComputeResult:
    """Resolve ``target`` from ``sources`` over the operator DAG.

    A space is satisfied by a registered Source (materialized + lifted to
    operator form) or derived by executing its producing Operator via
    ``apply_edge``. Lazy (only resolves what ``target`` needs), memoized
    (each space resolved once), and traced.

    ``edges`` defaults to the thermal-transport ``EDGES`` (imported lazily
    to keep the executor domain-agnostic at module import time and avoid a
    circular import). Pass an explicit edge set for other domains.

    Raises NoSourceError for a space with no source and no producer;
    ExternalSolveRequired for a non-sympy-executable producer with no source.
    """
    from omai.representation.compare import to_operator

    if edges is None:
        from omai.thermal_transport.operator import EDGES as edges

    memo: dict[str, Representation] = {}
    trace: list[TraceStep] = []
    constants = constants or {}

    producers_by_space: dict[str, Operator] = {}
    for op in edges:
        for out in op.outputs:
            producers_by_space.setdefault(out.name, op)  # first by declaration order

    def resolve(space: Space) -> Representation:
        if space.name in memo:
            return memo[space.name]
        if space.name in sources:
            rep = _materialize(sources[space.name])
            trace.append(TraceStep("LOAD", space.name, rep.representation_name))
            op_rep = to_operator(rep)
            if op_rep is not rep:
                trace.append(TraceStep("LIFT", space.name, rep.representation_name))
            memo[space.name] = op_rep
            return op_rep
        op = producers_by_space.get(space.name)
        if op is None:
            raise NoSourceError(
                f"space {space.name!r} has no registered Source and no "
                f"producing Operator; register a Source for it in `sources`."
            )
        # Nullary operators (no inputs) are "provider" edges that inject an
        # external parameter (e.g. provide_temperature). They cannot be derived
        # automatically — a Source must be registered for the space.
        if op.is_nullary():
            raise NoSourceError(
                f"space {space.name!r} is produced by nullary operator "
                f"{op.name!r} which requires external parameter injection; "
                f"register a Source for it in `sources`."
            )
        if not op.is_executable_in_sympy:
            raise ExternalSolveRequired(
                f"space {space.name!r} is produced by implicit operator "
                f"{op.name!r} (external solve); register a Source carrying a "
                f"loaded array for it (e.g. the code's emitted .npy)."
            )
        inputs = [resolve(inp) for inp in op.inputs]
        out = apply_edge(op, *inputs, constants=constants)
        trace.append(TraceStep("EXEC", space.name, op.name))
        memo[space.name] = out
        return out

    rep = resolve(target)
    return ComputeResult(representation=rep, trace=tuple(trace))
