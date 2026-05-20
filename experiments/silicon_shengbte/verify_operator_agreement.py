"""Check that the operator formulas the three codes implement are byte-identical.

By construction the operator layer attaches *one* sympy formula to each
Operation; kaldo, phono3py, and shengbte all reference the same Operation
in their adapter specs. So the formulas should be the same Python object,
not just equal — `is` comparison suffices.

The legitimate cross-code differences are in algorithmic_convention_overrides
and discretization_choices. This script tabulates both: identical formulas
on the left, divergent conventions on the right. The point is to make
clear that any residual κ disagreement is method-difference, not
physics-difference.
"""

from __future__ import annotations

import sympy as sp

from omai.representation.adapter import (
    representation_algorithmic_match,
    representation_discretization_match,
)
from omai.thermal_transport.representation import (
    KALDO_COMPUTE_FORCE_CONSTANTS_2,
    KALDO_COMPUTE_FORCE_CONSTANTS_3,
    KALDO_SOLVE_BTE_DIRECT,
    PHONO3PY_COMPUTE_FORCE_CONSTANTS_2,
    PHONO3PY_COMPUTE_FORCE_CONSTANTS_3,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_SOLVE_BTE_DIRECT,
    SHENGBTE_COMPUTE_FORCE_CONSTANTS_2,
    SHENGBTE_COMPUTE_FORCE_CONSTANTS_3,
    SHENGBTE_COMPUTE_LINEWIDTH,
    SHENGBTE_SOLVE_BTE_DIRECT,
    kaldo_compute_linewidth_spec,
)

# The kaldo silicon run used third_bandwidth=0.1 (linear THz) explicitly,
# so it operated in halfwidth mode, not the default adaptive scheme.
# Build a per-run spec rather than relying on the module-level default.
KALDO_COMPUTE_LINEWIDTH = kaldo_compute_linewidth_spec(broadening_param="halfwidth")


_CHAIN = [
    ("compute_force_constants[order=2]", [
        KALDO_COMPUTE_FORCE_CONSTANTS_2,
        PHONO3PY_COMPUTE_FORCE_CONSTANTS_2,
        SHENGBTE_COMPUTE_FORCE_CONSTANTS_2,
    ]),
    ("compute_force_constants[order=3]", [
        KALDO_COMPUTE_FORCE_CONSTANTS_3,
        PHONO3PY_COMPUTE_FORCE_CONSTANTS_3,
        SHENGBTE_COMPUTE_FORCE_CONSTANTS_3,
    ]),
    ("compute_linewidth", [
        KALDO_COMPUTE_LINEWIDTH,
        PHONO3PY_COMPUTE_LINEWIDTH,
        SHENGBTE_COMPUTE_LINEWIDTH,
    ]),
    ("solve_bte[bte_solver=direct_inverse]", [
        KALDO_SOLVE_BTE_DIRECT,
        PHONO3PY_SOLVE_BTE_DIRECT,
        SHENGBTE_SOLVE_BTE_DIRECT,
    ]),
]


def _check_identical_formula(specs: list) -> tuple[bool, sp.Basic | str | None]:
    """All specs must reference the same Operation (and therefore the
    same formula). Returns (identical, formula_object)."""
    ops = [s.operation for s in specs]
    if not all(op is ops[0] for op in ops):
        return False, None
    return True, ops[0].formula


def _collect_convention_diffs(specs: list) -> dict[str, dict[str, str]]:
    """For each algorithmic convention name appearing on any spec, return
    {convention_name: {representation_name: declared_value}}."""
    keys: set[str] = set()
    for s in specs:
        keys.update(s.operation.algorithmic_conventions.keys())
        keys.update(s.algorithmic_convention_overrides.keys())
    out: dict[str, dict[str, str]] = {}
    for k in sorted(keys):
        out[k] = {}
        for s in specs:
            try:
                out[k][s.representation_name] = s.declared_algorithmic_convention(k)
            except KeyError:
                out[k][s.representation_name] = "—"
    return out


def _collect_discretization(specs: list) -> dict[str, dict[str, str]]:
    keys: set[str] = set()
    for s in specs:
        keys.update(s.discretization_choices.keys())
    out: dict[str, dict[str, str]] = {}
    for k in sorted(keys):
        out[k] = {s.representation_name: s.discretization_choices.get(k, "—") for s in specs}
    return out


def main() -> None:
    for op_name, specs in _CHAIN:
        identical, formula = _check_identical_formula(specs)
        adapters = [s.representation_name for s in specs]
        op = specs[0].operation
        aux = getattr(op, "auxiliary_formulas", ())
        print("=" * 78)
        print(f"Operation: {op_name}")
        print(f"  adapters: {', '.join(adapters)}")
        print(f"  formula identical (same Operation object): {identical}")
        if isinstance(formula, sp.Basic):
            print(f"  LaTeX: {sp.latex(formula)}")
        elif isinstance(formula, str):
            print(f"  LaTeX (declared): {formula}")
        else:
            print(f"  formula: <none declared>")
        for i, aux_eq in enumerate(aux):
            if isinstance(aux_eq, sp.Basic):
                print(f"  auxiliary[{i}]: {sp.latex(aux_eq)}")
            else:
                print(f"  auxiliary[{i}]: {aux_eq}")

        conv = _collect_convention_diffs(specs)
        if conv:
            print(f"\n  Algorithmic conventions (per-code):")
            adapter_names = adapters
            header = "    " + "convention".ljust(28) + " | ".join(a.ljust(15) for a in adapter_names)
            print(header)
            print("    " + "-" * (len(header) - 4))
            for k, vals in conv.items():
                row = "    " + k.ljust(28) + " | ".join(vals[a].ljust(15) for a in adapter_names)
                print(row)

        disc = _collect_discretization(specs)
        if disc:
            print(f"\n  Discretization choices (per-code, diagnostic):")
            for k, vals in disc.items():
                row = "    " + k.ljust(28) + " | ".join(vals[a].ljust(15) for a in adapters)
                print(row)
        print()

    # Final cross-pair conformance check on the four cross-code-relevant ops.
    print("=" * 78)
    print("Cross-pair algorithmic-convention agreement matrix")
    print("=" * 78)
    for op_name, specs in _CHAIN:
        print(f"\n  {op_name}")
        keys: set[str] = set()
        for s in specs:
            keys.update(s.operation.algorithmic_conventions.keys())
            keys.update(s.algorithmic_convention_overrides.keys())
        for k in sorted(keys):
            row = f"    {k:<28}"
            for i, s_a in enumerate(specs):
                for s_b in specs[i + 1:]:
                    matched, _msg = representation_algorithmic_match(s_a, s_b, k)
                    sym = "✓" if matched else "✗"
                    row += f" {s_a.representation_name[0].upper()}-{s_b.representation_name[0].upper()}:{sym}"
            print(row)


if __name__ == "__main__":
    main()
