"""Symbol-vocabulary registry for the formula free-symbol discipline.

`validate_dag` checks every free symbol in an edge's sympy formula against
a declared vocabulary: the symbols carried by the edge's input and output
spaces, the edge's declared parameters, and a pool of permitted bare
constants. This module holds that vocabulary as a *registry* which each
domain populates at import time (see
`omai/thermal_transport/operator/vocabulary.py` and
`omai/materials/operator/vocabulary.py`), so the core layer stays free of
domain-specific names and a new domain extends validation coverage by
registering, never by editing core.

Only truly generic content is seeded here: thermodynamic constants any
formula may reference and the plain dummy indices used across domains.
Everything tied to a physical setting (BZ meshes, MD timesteps, provided-
source placeholders, ...) belongs to the domain that owns it.

The registered symbol sets are validation vocabulary, not identity: they
never enter a node's type and are free to grow without re-minting anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


# Bare physics + math symbols that any formula in any domain may reference
# without declaring them on a space: thermodynamic parameters and the plain
# dummy indices used throughout sympy formulas.
GENERIC_CONSTANTS: frozenset[str] = frozenset({
    # Thermodynamic parameters and universal constants.
    "T",
    "k_B",
    r"\hbar",
    "N_A",
    "pi",
    # Plain dummy indices.
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
})


# Live registry state. Domains mutate these through the register_* calls
# below; consumers (validate_dag, the executor) read them at call time.
FORMULA_CONSTANTS: set[str] = set(GENERIC_CONSTANTS)
SPACE_SYMBOLS: dict[str, frozenset[str]] = {}


def register_formula_constants(names: Iterable[str]) -> None:
    """Add bare constant names any formula may reference.

    Idempotent; registration is a union, so two domains may safely declare
    the same constant.
    """
    FORMULA_CONSTANTS.update(names)


def register_space_symbols(mapping: Mapping[str, Iterable[str]]) -> None:
    """Register the sympy base-symbol names a space's formulas may carry.

    Keys are space names; values are the IndexedBase / Symbol base names
    that may appear in a formula whose inputs or outputs include that
    space. Registration is a union per key: a second domain that reuses a
    shared space (e.g. materials consuming thermal transport's
    MeanSquaredDisplacement) extends the shared space's vocabulary rather
    than replacing it.
    """
    for name, symbols in mapping.items():
        SPACE_SYMBOLS[name] = SPACE_SYMBOLS.get(name, frozenset()) | frozenset(symbols)
