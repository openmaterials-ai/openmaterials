"""Unified map data builders over one or more Domains."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType

import sympy as sp

from omai.operator.space import Space
from omai.operator.operator import Operator


@dataclass(frozen=True)
class Domain:
    """One physics domain's contribution to the unified map."""
    name: str
    nodes: tuple[Space, ...]
    edges: tuple[Operator, ...]
    symbols: dict[str, str]
    # (node_id, latex_symbol, sympy_symbol_or_indexedbase) promoted to parameter nodes
    param_promotions: tuple[tuple[str, str, object], ...]
    representation_package: ModuleType
