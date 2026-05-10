"""Materialization: a single concrete realization of one observable.

A `Materialization` wraps a numerical array with the metadata that makes it
comparable across adapters: which abstract state it materializes, which
adapter produced it, and which observable on that state it represents.

The substrate doc defines a materialization as `(s, Σ, x, U, ε_disc)`; this
class is the runtime representation. `Σ` (discretization scheme) and
`ε_disc` (discretization error) are deferred — the materialization carries
the array and its adapter spec, which together provide units and
convention via the spec layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from omai.materialization.adapter import StateAdapterSpec


@dataclass(frozen=True)
class Materialization:
    state_adapter_spec: StateAdapterSpec
    observable_name: str
    data: np.ndarray

    @property
    def state(self):  # type: ignore[no-untyped-def]
        return self.state_adapter_spec.state

    @property
    def adapter_name(self) -> str:
        return self.state_adapter_spec.adapter_name


def materialize(
    state_adapter_spec: StateAdapterSpec,
    observable_name: str,
    data: np.ndarray | float | list,
) -> Materialization:
    """Construct a Materialization, validating that the observable is declared.

    Coerces `data` to np.ndarray. Raises KeyError if `observable_name` isn't
    one of the state's observables.
    """
    state_adapter_spec.state.observable(observable_name)  # raises KeyError if absent
    arr = np.asarray(data)
    return Materialization(
        state_adapter_spec=state_adapter_spec,
        observable_name=observable_name,
        data=arr,
    )
