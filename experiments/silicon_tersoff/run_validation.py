"""Validation engine on Si-Tersoff: run the framework's own composition and
check it against kaldo/phonopy ground truth.

Example A (no prerequisites): derive MolarHeatCapacity from Frequency +
Temperature via the operator DAG, compare to phonopy's emitted molar Cv,
and cross-check the kaldo-Frequency vs phonopy-Frequency routes.

Example B (needs run_kaldo.py MFD dump + one kaldo re-run): contract
ThermalConductivity[direct] from loaded GroupVelocity + MeanFreeDisplacement
and derived HeatCapacity, compare to kaldo's emitted kappa_inverse.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from omai.representation.executor import compute, operator_form_spec
from omai.representation.instance import Representation
from omai.representation.validation import cross_check
from omai.thermal_transport.operator import (
    FREQUENCY_STATE,
    GROUP_VELOCITY,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_DIRECT,
)

_REPO = Path(__file__).resolve().parent.parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"


def _op_rep(space, name, data):
    return Representation(
        space_adapter_spec=operator_form_spec(space),
        observable_name=name, data=np.asarray(data), is_operator=True,
    )


def _section(title):
    print("\n" + title + "\n" + "-" * len(title))


def example_a():
    _section("Example A — MolarHeatCapacity via the operator DAG")
    if not (_PHONOPY / "frequencies_THz.npy").exists():
        print("  phonopy data missing; run run_phonopy.py first.")
        return
    omega = _op_rep(FREQUENCY_STATE, "omega", np.load(_PHONOPY / "frequencies_THz.npy"))
    T = _op_rep(TEMPERATURE_STATE, "temperature", 300.0)
    result = compute(MOLAR_HEAT_CAPACITY, {"Frequency": omega, "Temperature": T})
    derived = float(result.representation.data)
    print("  framework-derived molar Cv : %.4f J/(K mol)" % derived)
    grid_T = np.load(_PHONOPY / "temperatures_K.npy")
    cv = np.load(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    gt = float(cv[int(np.argmin(np.abs(grid_T - 300.0)))])
    print("  phonopy emitted molar Cv   : %.4f J/(K mol)" % gt)
    print("  relative error             : %.3e" % (abs(derived - gt) / abs(gt)))
    print("  trace:")
    for s in result.trace:
        print("    %-5s %-22s %s" % (s.kind, s.space, s.detail))
    if (_KALDO / "frequencies_THz.npy").exists():
        routes = {
            "kaldo": {"Frequency": _op_rep(FREQUENCY_STATE, "omega",
                       np.load(_KALDO / "frequencies_THz.npy")), "Temperature": T},
            "phonopy": {"Frequency": omega, "Temperature": T},
        }
        print(cross_check(MOLAR_HEAT_CAPACITY, routes, rtol=1e-2).render())


def example_b():
    _section("Example B — ThermalConductivity[direct] via the operator DAG")
    mfd = _KALDO / "mean_free_displacement.npy"
    if not mfd.exists():
        print("  kaldo MFD dump missing; add the np.save to run_kaldo.py and")
        print("  re-run:  CUDA_VISIBLE_DEVICES='' python run_kaldo.py")
        return
    a = 5.431
    v_cell = a ** 3 / 4.0
    sources = {
        "Frequency": _op_rep(FREQUENCY_STATE, "omega", np.load(_KALDO / "frequencies_THz.npy")),
        "Temperature": _op_rep(TEMPERATURE_STATE, "temperature", 300.0),
        "GroupVelocity": _op_rep(GROUP_VELOCITY, "v", np.load(_KALDO / "group_velocities_AT.npy")),
        "MeanFreeDisplacement[bte_solver=direct_inverse]":
            _op_rep(MEAN_FREE_DISPLACEMENT_DIRECT, "F", np.load(mfd)),
    }
    result = compute(THERMAL_CONDUCTIVITY_DIRECT, sources, constants={"V_{cell}": v_cell})
    # Bridge in apply_edge rescales to W/(m·K) automatically — no manual factor needed.
    kappa = np.asarray(result.representation.data)
    gt = np.load(_KALDO / "kappa_inverse_tensor_WmK.npy")
    print("  framework kappa (tr/3)  : %.4f W/(m K)" % (np.trace(kappa) / 3.0))
    print("  kaldo emitted kappa     : %.4f W/(m K)" % (np.trace(gt) / 3.0))
    print("  relative error          : %.3e" % (abs(np.trace(kappa)/3 - np.trace(gt)/3) / abs(np.trace(gt)/3)))


if __name__ == "__main__":
    example_a()
    example_b()
