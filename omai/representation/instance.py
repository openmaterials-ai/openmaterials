"""Representation: a single concrete realization of one observable.

A `Representation` wraps a numerical array with the metadata that makes it
comparable across adapters: which operator state it represents, which
adapter produced it, and which observable on that state it represents.

The operator layer doc defines a representation as `(s, Σ, x, U, ε_disc)`; this
class is the runtime representation. `Σ` (discretization scheme) and
`ε_disc` (discretization error) are deferred — the representation carries
the array and its adapter spec, which together provide units and
convention via the spec layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from omai.representation.adapter import StateAdapterSpec


@dataclass(frozen=True)
class Representation:
    """A representation of one observable in some adapter's form.

    By analogy with quantum mechanics: a operator State is an abstract
    operator, and a Representation is that operator expressed in a
    specific representation (basis). The adapter spec encodes which
    representation. `to_operator(m)` removes the basis (canonical form);
    `to_representation(m_op, spec)` re-expresses in a target basis.
    `is_operator_form=True` flags a representation that has been
    canonicalized — its data is already in the operator layer's
    canonical units and conventions.
    """

    state_adapter_spec: StateAdapterSpec
    observable_name: str
    data: np.ndarray
    is_operator_form: bool = False

    @property
    def state(self):  # type: ignore[no-untyped-def]
        return self.state_adapter_spec.state

    @property
    def adapter_name(self) -> str:
        return self.state_adapter_spec.adapter_name


def represent(
    state_adapter_spec: StateAdapterSpec,
    observable_name: str,
    data: np.ndarray | float | list,
) -> Representation:
    """Construct a Representation, validating that the observable is declared.

    Coerces `data` to np.ndarray. Raises KeyError if `observable_name` isn't
    one of the state's observables.
    """
    state_adapter_spec.state.field(observable_name)  # raises KeyError if absent
    arr = np.asarray(data)
    return Representation(
        state_adapter_spec=state_adapter_spec,
        observable_name=observable_name,
        data=arr,
    )
