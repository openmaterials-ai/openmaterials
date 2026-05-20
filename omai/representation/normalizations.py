"""Normalizations for the representation layer.

A *normalization* is the numeric-world choice of definitional convention
for an observable. Where a `Unit` captures a measure choice (linear_THz
vs angular_THz; eV vs J), a `Normalization` captures a definitional
choice (`Γ = 2 Im Σ` vs `Γ = Im Σ`; FC3 in eV/Å³ vs mixed eV/(Å²·nm)).

Both kinds of choice produce multiplicative factors when converting an
adapter's emitted value to operator-canonical form; both live in the
numeric world, parallel to one another. A gauge (in the strict QM
sense) is an operator-layer automorphism with NO multiplicative effect
on observables — it does not appear here.

Registry shape mirrors `units.UNITS`: a flat dict keyed by name, each
entry carrying a `to_operator` multiplier such that

    operator_value = adapter_value · unit.to_operator · normalization.to_operator

The canonical normalization for any axis has `to_operator = 1.0`; other
values declare their multiplicative deviation from canonical.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Normalization:
    name: str
    to_operator: float


# Canonical normalization for any observable that hasn't picked a non-trivial
# convention. Most fields use this — only the entries below carry a
# multiplier-different-from-one.
CANONICAL = Normalization("canonical", 1.0)


# FC3 normalization. Phono3py and kaldo store the natural ∂³V/∂u³ in
# eV/Å³ (canonical). ShengBTE's reader uses a mixed-dimension form
# documented in gruneisen.f90:44 as "nm·eV/(amu·Å³·THz²)" — nm in the
# numerator with Å³ in the denominator; the implicit 10× factor (1 nm = 10 Å)
# makes ShengBTE's stored value 0.1× the canonical eV/Å³ value.
EV_PER_A3 = Normalization("eV_per_A3", 1.0)
EV_PER_A2_PER_NM = Normalization("eV_per_A2_per_nm", 10.0)
# adapter_value (eV/(Å²·nm)) × 10 = operator-canonical (eV/Å³).


# Linewidth definitional convention. Phono3py uses Γ = Im Σ (canonical).
# kaldo uses Γ = 2 Im Σ, so kaldo's emitted value × 0.5 = operator-canonical.
IMAG_SELF_ENERGY = Normalization("imag_self_energy", 1.0)
LINEWIDTH_2X_IMAG_SELF_ENERGY = Normalization("linewidth_2x_imag_self_energy", 0.5)


NORMALIZATIONS: dict[str, Normalization] = {
    n.name: n
    for n in [
        CANONICAL,
        EV_PER_A3,
        EV_PER_A2_PER_NM,
        IMAG_SELF_ENERGY,
        LINEWIDTH_2X_IMAG_SELF_ENERGY,
    ]
}


def normalization_factor(name: str) -> float:
    """Return the to_operator multiplier for a normalization by name."""
    return NORMALIZATIONS[name].to_operator
