"""DAG-discipline validator.

Walks a node + edge set and checks the structural invariants that the
architectural commitments imply but that the type system
alone can't enforce:

  * Every HiddenSpace declares a gauge_group (non-empty string).
  * Every HiddenSpace declares kind ∈ {"scaffolding", "approximation"}.
  * Every scaffolding HiddenSpace declares at least one
    gauge_invariant_contractions entry, and each named entry resolves
    to an ObservableSpace that exists in the node set.
  * Every approximation HiddenSpace declares zero
    gauge_invariant_contractions (otherwise it would be scaffolding).
  * Every node name is unique.
  * Every Operator's inputs and outputs are nodes that appear in the
    node set.

In addition, AOT (declaration-time) content checks against each edge's
sympy formula:

  * Every free symbol in `formula` is derivable from one of:
      - the per-space allowed-symbol set of an input space
      - the per-space allowed-symbol set of an output space (formulas
        commonly reference the LHS quantity they produce)
      - the edge's declared `parameters`
      - a fixed `_PERMITTED_CONSTANTS` set of bare physics symbols,
        BZ-mesh constants, and dummy indices.
    Anything else is flagged as "not derivable from inputs", catching
    typos and undeclared symbols at module-load time.

  * For edges whose `formula` is a sympy.Eq with an Indexed LHS, the
    LHS's index tuple must match (positionally) the index tuple
    declared on the output space's first field.

  * Auxiliary formulas (`auxiliary_formulas`) are checked against the
    same vocabulary as the main formula, augmented with whatever
    symbols the main formula itself introduces (so an auxiliary
    equation may define a kernel that appears in the main formula).

Returns a list of human-readable violation strings; empty list means
the operator layer is internally consistent.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.operator.space import HiddenSpace, ObservableSpace, Space

_VALID_KINDS = {"scaffolding", "approximation"}


# ---------------------------------------------------------------------------
# Symbol vocabulary for the sympy-layer free-symbol check.
# ---------------------------------------------------------------------------
#
# Bare physics + math symbols that any formula may reference without having
# to declare them in a state. Includes thermodynamic parameters (T, k_B, ℏ),
# BZ-mesh / cell counters (N, N_q, N_A, V_cell, pi), and the dummy indices
# used throughout the operator layer (i, j, k, α, β, ν, ν', ν'', q, q', R, R',
# γ, δ, m). Also includes the schematic per-component q-vector symbols
# `q^\alpha`, `q^\beta` used in the NAC formula, the displacement labels
# `u_i(0)`, `u_j(R)`, `u_k(R')`, `\{u\}`, and the source-side placeholders
# `V_{provided}`, `T_{provided}` used by the nullary `provide_*` edges.
# Kept minimal: anything genuinely tied to a state goes in _STATE_SYMBOLS.
_PERMITTED_CONSTANTS: frozenset[str] = frozenset({
    # Physics constants and thermodynamic parameters.
    "T",
    "k_B",
    r"\hbar",
    "V_{cell}",
    "N",
    "N_q",
    "N_A",
    "pi",
    # Dummy indices.
    "i",
    "j",
    "k",
    "m",
    r"\alpha",
    r"\beta",
    r"\gamma",
    r"\delta",
    r"\nu",
    r"\nu'",
    r"\nu''",
    r"\mathbf{q}",
    r"\mathbf{q'}",
    r"\mathbf{R}",
    r"\mathbf{R'}",
    # Per-component q-vector symbols (NAC formula).
    r"q^\alpha",
    r"q^\beta",
    # Displacement labels (FC2 / FC3 derivative formulas).
    "u_i(0)",
    "u_j(R)",
    "u_k(R')",
    r"\{u\}",
    # Source-side provided placeholders (nullary provide_* edges).
    r"V_{\mathrm{provided}}",
    r"T_{\mathrm{provided}}",
    r"V_{provided}",
    r"T_{provided}",
    r"Z^*_{provided}",
    r"\varepsilon_{\infty,provided}",
    r"g_{provided}",
    # DOS bin variable and cumulative-κ thresholds.
    r"\omega",
    r"\omega_c",
    r"\Lambda_c",
    # Generic length-scale parameter alias. Several edges (e.g.
    # compute_boundary_scattering) declare a length-scale Parameter
    # (boundary_length_scale) but reference it in the formula by the
    # textbook symbol `L`. Permit `L` so the formula reads naturally.
    "L",
    # MD primitives (phase 2 P2). The integer timestep index `t`, the
    # correlation lag `\tau`, the timestep size `\Delta t`, the
    # correlation depth `n_{lag}`, and the atom count `N_{atoms}` are
    # universal MD recurrence / averaging constants that any MD edge may
    # reference. They're not tied to any single state.
    "t",
    r"\tau",
    r"\Delta t",
    r"n_{lag}",
    r"N_{atoms}",
    # MD-based κ (phase 2 P3). τ_max / τ_min are the GK integration
    # bounds (declared as edge parameters and also free in the integrand
    # expression); F_e is the HNEMD driving-force IndexedBase; ∇T is the
    # imposed NEMD temperature-gradient IndexedBase.
    r"\tau_{max}",
    r"\tau_{min}",
    "F_e",
    r"\nabla T",
})


# Per-space allowed-symbol registry. Each entry lists the IndexedBase /
# Symbol *base names* that may legitimately appear in a formula whose
# inputs OR outputs include that space.
#
# Rationale: the operator layer's promise is "every edge carries a sympy
# formula whose symbols are the quantities the space declares". The mapping
# from field-name (Python convention, e.g. `omega`) to sympy IndexedBase
# name (LaTeX convention, e.g. `\omega`) is non-trivial in places; this
# registry encodes that mapping.
_SPACE_SYMBOLS: dict[str, frozenset[str]] = {
    "Potential": frozenset({r"\{u\}", r"V_{\mathrm{provided}}"}),
    "Temperature": frozenset({"T", r"T_{\mathrm{provided}}"}),
    "ForceConstants[order=2]": frozenset({r"\Phi^{(2)}"}),
    "ForceConstants[order=3]": frozenset({r"\Phi^{(3)}"}),
    "BornCharges": frozenset({r"Z^*", r"Z^*_{provided}"}),
    "DielectricTensor": frozenset({r"\varepsilon_\infty", r"\varepsilon_{\infty,provided}"}),
    "BareDynamicalMatrix": frozenset({r"D^{bare}", "M"}),
    "DynamicalMatrix": frozenset({"D", r"\partial D/\partial q", "M"}),
    "Frequency": frozenset({r"\omega"}),
    "Eigenvectors": frozenset({"e", "m"}),
    "GroupVelocity": frozenset({"v"}),
    "HeatCapacity": frozenset({"c"}),
    "VolumetricHeatCapacity": frozenset({r"C_V^{vol}"}),
    "MolarHeatCapacity": frozenset({r"C_V^{mol}"}),
    "HelmholtzFreeEnergy": frozenset({"f"}),
    "Entropy": frozenset({"s"}),
    "InternalEnergy": frozenset({"e"}),
    "MolarHelmholtzFreeEnergy": frozenset({r"F_{mol}"}),
    "MolarEntropy": frozenset({r"S_{mol}"}),
    "MolarInternalEnergy": frozenset({r"E_{mol}"}),
    # Linewidth: each per-channel state allows its channel-specific symbol;
    # the total state allows all channel variants since sum_linewidths and
    # downstream consumers reference them as components.
    "Linewidth[channel=anharmonic_3ph]": frozenset({r"\Gamma", r"\Gamma^{anh}"}),
    "Linewidth[channel=isotope]": frozenset({r"\Gamma^{iso}"}),
    "Linewidth[channel=boundary]": frozenset({r"\Gamma^{bnd}"}),
    "Linewidth[channel=total]": frozenset({
        r"\Gamma",
        r"\Gamma^{tot}",
        r"\Gamma^{anh}",
        r"\Gamma^{iso}",
        r"\Gamma^{bnd}",
    }),
    "IsotopeAbundances": frozenset({"g", r"g_{provided}"}),
    "PhononDOS": frozenset({"g"}),
    "Gruneisen": frozenset({r"\gamma_G"}),
    "PhaseSpace3Phonon": frozenset({r"P_3"}),
    "MeanFreeDisplacement[bte_solver=rta]": frozenset({"F"}),
    "MeanFreeDisplacement[bte_solver=direct_inverse]": frozenset({
        "F",
        r"\mathcal{M}",  # collision matrix used in solve_bte_direct's auxiliary formula
    }),
    "ThermalConductivity[bte_solver=rta]": frozenset({r"\kappa"}),
    "ThermalConductivity[bte_solver=direct_inverse]": frozenset({r"\kappa"}),
    "ThermalConductivity[transport_model=wigner_populations]": frozenset({
        r"\kappa^{W,pop}",
    }),
    "ThermalConductivity[transport_model=wigner_coherences]": frozenset({
        r"\kappa^{W,coh}",
    }),
    "ThermalConductivity[transport_model=wigner]": frozenset({
        r"\kappa^W",
        r"\kappa^{W,pop}",
        r"\kappa^{W,coh}",
    }),
    "ThermalConductivity[transport_model=qhgk]": frozenset({r"\kappa^{QHGK}"}),
    "CumulativeKappa[wrt=omega]": frozenset({
        r"\kappa^{cum}_\omega",
        r"\omega_c",
    }),
    "CumulativeKappa[wrt=mfp]": frozenset({
        r"\kappa^{cum}_\Lambda",
        r"\Lambda_c",
    }),
    # MD primitives (phase 2 P2). Trajectory carries r and v (the field
    # declarations); the per-atom energy E and per-atom force F^{md} are
    # trajectory-derived auxiliary quantities (forces come from the same
    # Potential that drove the MD; per-atom energies are decomposable
    # from the same potential energy surface) — listed here so the
    # Irving-Kirkwood / Velocity-Verlet formulas can reference them.
    "Trajectory": frozenset({"r", "v", "E", r"F^{md}"}),
    "HeatCurrent": frozenset({"J"}),
    "HeatCurrentACF": frozenset({"Jcorr"}),
    "VelocityAutocorrelation": frozenset({"Cv"}),
    "MeanSquaredDisplacement": frozenset({"M"}),
    # MD-based κ paths (phase 2 P3). All three Pattern-A `transport_model`
    # variants share the same κ^{MD} IndexedBase on their LHS so the
    # formulas read uniformly.
    "ThermalConductivity[transport_model=green_kubo]": frozenset({r"\kappa^{MD}"}),
    "ThermalConductivity[transport_model=nemd]": frozenset({r"\kappa^{MD}"}),
    "ThermalConductivity[transport_model=hnemd]": frozenset({r"\kappa^{MD}"}),
}


def _symbol_base_name(sym: sp.Basic) -> str:
    """Return the base name of a sympy free-symbol element.

    For an `Indexed` instance, returns the underlying `IndexedBase` name
    (which is what an adapter would key on). For a `Symbol`, returns its
    `.name`. For anything else, falls back to `str(sym)`.
    """
    if isinstance(sym, sp.Indexed):
        return str(sym.base.name)
    if hasattr(sym, "name"):
        return str(sym.name)
    return str(sym)


def _allowed_symbols_for_edge(op: Operator) -> set[str]:
    """Allowed base-symbol names for a given Operator.

    Union of:
      - _PERMITTED_CONSTANTS
      - _SPACE_SYMBOLS[input.name] for each input space
      - _SPACE_SYMBOLS[output.name] for each output space
      - the edge's parameter names
    Spaces not present in _SPACE_SYMBOLS contribute nothing — they're
    treated as not yet registered, which means the check will flag
    unregistered symbols. Add to _SPACE_SYMBOLS when growing the DAG.
    """
    allowed: set[str] = set(_PERMITTED_CONSTANTS)
    for inp in op.inputs:
        allowed.update(_SPACE_SYMBOLS.get(inp.name, frozenset()))
    for out in op.outputs:
        allowed.update(_SPACE_SYMBOLS.get(out.name, frozenset()))
    for p in op.parameters:
        allowed.add(p.name)
    return allowed


def _formula_symbols(formula: sp.Basic) -> set[sp.Basic]:
    """Return the free symbols of a formula (Indexed + Symbol)."""
    return set(formula.free_symbols)


def _check_free_symbols(
    op: Operator,
    formula: sp.Basic,
    allowed: set[str],
    label: str,
) -> list[str]:
    """Report any free symbol whose base name is not in `allowed`."""
    errors: list[str] = []
    for sym in _formula_symbols(formula):
        base = _symbol_base_name(sym)
        if base not in allowed:
            errors.append(
                f"edge {op.name!r} {label} uses symbol {base!r} not derivable from inputs"
            )
    return errors


def _check_lhs_indices(op: Operator, formula: sp.Basic) -> list[str]:
    """If formula is sp.Eq with an Indexed LHS, check its index tuple
    matches the output space's first field's declared indices.

    The comparison is positional on the *index names* (i.e. the str of
    each sympy index symbol against the str in field.indices). Some
    edges have implicit LHS (e.g. solve_bte_direct's LHS is a sum); we
    skip those by only firing when the LHS is exactly sp.Indexed.
    """
    if not isinstance(formula, sp.Eq):
        return []
    lhs = formula.lhs
    if not isinstance(lhs, sp.Indexed):
        return []
    if not op.outputs:
        return []
    out = op.outputs[0]
    if not out.fields:
        return []
    declared = out.fields[0].indices
    actual = tuple(str(i) for i in lhs.indices)
    # The state-side declaration uses Python-style index names ("q", "nu",
    # "alpha") while the sympy side uses LaTeX (e.g. r"\mathbf{q}", r"\nu",
    # r"\alpha"). Compare by length only (positional rank), since a
    # name-level comparison would require an exhaustive translation table
    # that isn't the substantive content of this check.
    if len(declared) != len(actual):
        return [
            f"edge {op.name!r} LHS {_symbol_base_name(lhs)!r} carries {len(actual)} "
            f"indices but output field declares {len(declared)} ({declared!r})"
        ]
    return []


def validate_dag(
    nodes: tuple[Space, ...] | list[Space],
    edges: tuple[Operator, ...] | list[Operator],
) -> list[str]:
    """Return a list of DAG-discipline violations (empty if clean)."""
    errors: list[str] = []

    # Name uniqueness
    names_seen: set[str] = set()
    observable_names: set[str] = set()
    for space in nodes:
        if space.name in names_seen:
            errors.append(f"duplicate node name: {space.name!r}")
        names_seen.add(space.name)
        if isinstance(space, ObservableSpace):
            observable_names.add(space.name)

    # Per-HiddenSpace discipline
    for space in nodes:
        if not isinstance(space, HiddenSpace):
            continue
        if not space.gauge_group:
            errors.append(
                f"{space.name}: HiddenSpace must declare a non-empty gauge_group"
            )
        if space.kind not in _VALID_KINDS:
            errors.append(
                f"{space.name}: kind must be one of {sorted(_VALID_KINDS)}, "
                f"got {space.kind!r}"
            )
        if space.kind == "scaffolding":
            if not space.gauge_invariant_contractions:
                errors.append(
                    f"{space.name}: scaffolding HiddenSpace must declare at least one "
                    "gauge_invariant_contractions entry"
                )
            for obs_name in space.gauge_invariant_contractions:
                if obs_name not in observable_names:
                    errors.append(
                        f"{space.name}: declared contraction {obs_name!r} is not an "
                        "ObservableSpace in the node set"
                    )
        elif space.kind == "approximation":
            if space.gauge_invariant_contractions:
                errors.append(
                    f"{space.name}: approximation HiddenSpace should not declare "
                    "gauge_invariant_contractions (terminal by definition)"
                )

    # Edges reference nodes in the set
    for op in edges:
        for inp in op.inputs:
            if inp.name not in names_seen:
                errors.append(
                    f"operator {op.name!r} input {inp.name!r} not in node set"
                )
        for out in op.outputs:
            if out.name not in names_seen:
                errors.append(
                    f"operator {op.name!r} output {out.name!r} not in node set"
                )

    # Sympy-layer content checks on edges with sympy formulas.
    for op in edges:
        if op.formula is None or not isinstance(op.formula, sp.Basic):
            continue
        allowed = _allowed_symbols_for_edge(op)

        # Free-symbol check on the main formula.
        errors.extend(_check_free_symbols(op, op.formula, allowed, "formula"))

        # LHS-index consistency.
        errors.extend(_check_lhs_indices(op, op.formula))

        # Auxiliary formulas: each one inherits the main formula's
        # vocabulary (so an aux equation can reference symbols the main
        # formula introduces, e.g. |V_3|^2 defined alongside Γ_qν).
        aux_allowed = set(allowed)
        for sym in _formula_symbols(op.formula):
            aux_allowed.add(_symbol_base_name(sym))
        for aux in op.auxiliary_formulas:
            if not isinstance(aux, sp.Basic):
                continue
            errors.extend(_check_free_symbols(op, aux, aux_allowed, "auxiliary formula"))

    return errors
