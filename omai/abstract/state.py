"""Abstract states (nodes in the DAG).

Each State declares the typed claim that some physics quantity exists, with a
schedule of observables (named, dimensioned quantities the materialization
carries) and a schedule of conventions (named, canonical-valued semantic
choices that affect what the state's observables mean).

The abstract State carries no units and no concrete numerical values. Units
appear on materializations, declared by adapters.

Convention factors declare how non-canonical convention values scale specific
observables relative to canonical. For example, ScatteringRates has the
gamma_definition convention: when that takes the value
"linewidth_2x_imag_self_energy", the linewidth observable scales by a factor
of 2 relative to the canonical "imag_self_energy".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omai.abstract.dimensions import Dimension
from omai.abstract.physics_types import PhysicsType


@dataclass(frozen=True)
class Observable:
    name: str
    dimension: Dimension


@dataclass(frozen=True)
class State:
    physics_type: PhysicsType
    name: str
    observables: tuple[Observable, ...] = ()
    canonical_conventions: dict[str, str] = field(default_factory=dict)
    # Entries (convention_name, convention_value, observable_name, factor)
    # declaring that when `convention_name` takes `convention_value`, the
    # named observable is scaled by `factor` relative to canonical.
    convention_factors: tuple[tuple[str, str, str, float], ...] = ()
    # Optional integer parameters that further refine the type
    # (e.g. ForceConstants is parameterized by order n).
    type_parameters: dict[str, int] = field(default_factory=dict)
    description: str = ""

    def __hash__(self) -> int:
        # Identity by name: states are singletons in the substrate registry.
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return NotImplemented
        return self.name == other.name

    def observable(self, name: str) -> Observable:
        for o in self.observables:
            if o.name == name:
                return o
        raise KeyError(f"state {self.name!r} has no observable {name!r}")
