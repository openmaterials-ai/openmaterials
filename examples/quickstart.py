"""openmaterials-ai quickstart.

A self-contained tour of the framework that runs with no external codes
(only omai, numpy, sympy). It shows the three things the framework does:

  1. Declares a typed operator DAG of physics quantities.
  2. Runs a calculation over that DAG (the validation engine's `compute`),
     deriving molar heat capacity from a phonon-frequency array.
  3. Cross-checks two independent inputs at a gauge-invariant Observable,
     with the agree/disagree verdict governed by the operator-layer typing.

Run it:
    python examples/quickstart.py
"""

from __future__ import annotations

import numpy as np

from omai.representation.executor import compute, operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import cross_check
from omai.thermal_transport.operator import (
    EDGES,
    NODES,
    FREQUENCY_STATE,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
)


def _operator_form(space, field_name, data) -> Representation:
    """Wrap a numpy array as an operator-form Representation of `space`.

    `operator_form` means the values are already in the operator layer's
    canonical units (here: frequency in linear THz, temperature in K), so
    no unit conversion is applied when the executor consumes them.
    """
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=field_name,
        data=np.asarray(data),
        is_operator=True,
    )


def main() -> None:
    # 1. The operator DAG: typed physics spaces (nodes) connected by
    #    operators (edges), each edge carrying a sympy formula.
    print(f"operator DAG: {len(NODES)} spaces, {len(EDGES)} operators")

    # 2. Run a calculation. We supply two leaves, a per-mode phonon
    #    frequency array omega(q, nu) in linear THz and a temperature in K,
    #    and ask the engine for the molar heat capacity. The engine derives
    #    per-mode HeatCapacity (closed-form sinh kernel) and contracts it to
    #    the molar value, executing the operators' sympy formulas directly.
    omega = np.array([[5.0, 10.0], [15.0, 20.0]])  # (n_q=2, n_modes=2), THz
    sources = {
        "Frequency": _operator_form(FREQUENCY_STATE, "omega", omega),
        "Temperature": _operator_form(TEMPERATURE_STATE, "temperature", 300.0),
    }
    result = compute(MOLAR_HEAT_CAPACITY, sources)
    cv_molar = float(result.representation.data)
    print(f"derived molar heat capacity at 300 K: {cv_molar:.4f} J/(K mol)")

    # The trace records how the target was reached: leaves LOADed, derived
    # quantities EXECuted edge by edge.
    print("derivation trace:")
    for step in result.trace:
        print(f"  {step.kind:<5s} {step.space:<22s} {step.detail}")

    # 3. Cross-check. Two independent frequency inputs that should describe
    #    the same physics must agree at MolarHeatCapacity (an Observable).
    #    cross_check computes the target each way and compares; the verdict
    #    is EXPECTED_AGREE because the target is gauge-invariant.
    routes = {
        "input_a": {
            "Frequency": _operator_form(FREQUENCY_STATE, "omega", omega),
            "Temperature": _operator_form(TEMPERATURE_STATE, "temperature", 300.0),
        },
        "input_b": {
            "Frequency": _operator_form(FREQUENCY_STATE, "omega", omega.copy()),
            "Temperature": _operator_form(TEMPERATURE_STATE, "temperature", 300.0),
        },
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, routes)
    print("cross-check:")
    print("  " + report.render().replace("\n", "\n  "))

    # Sanity checks so this example doubles as a smoke test.
    assert cv_molar > 0.0
    assert report.ok()
    print("\nquickstart OK")


if __name__ == "__main__":
    main()
