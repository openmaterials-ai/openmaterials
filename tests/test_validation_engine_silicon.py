"""Examples A & B: the validation engine against kaldo/phonopy ground truth.
Skips when the .npy artefacts are absent (run the run_*.py drivers first)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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

_REPO = Path(__file__).resolve().parent.parent
_KALDO = _REPO / "runs" / "silicon_tersoff" / "kaldo"
_PHONOPY = _REPO / "runs" / "silicon_tersoff" / "phonopy"


def _require(p: Path) -> None:
    if not p.exists():
        pytest.skip(f"missing {p.relative_to(_REPO)}; run the run_*.py drivers first.")


def _freq_source(root: Path) -> Representation:
    omega = np.load(root / "frequencies_THz.npy")
    return Representation(
        space_adapter_spec=operator_form_spec(FREQUENCY_STATE),
        observable_name="omega", data=omega, is_operator=True,
    )


def _temperature_source() -> Representation:
    return Representation(
        space_adapter_spec=operator_form_spec(TEMPERATURE_STATE),
        observable_name="temperature", data=np.asarray(300.0), is_operator=True,
    )


def test_example_a_molar_cv_matches_phonopy_ground_truth():
    _require(_PHONOPY / "frequencies_THz.npy")
    _require(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    _require(_PHONOPY / "temperatures_K.npy")

    sources = {"Frequency": _freq_source(_PHONOPY), "Temperature": _temperature_source()}
    result = compute(MOLAR_HEAT_CAPACITY, sources)
    derived = float(result.representation.data)

    T = np.load(_PHONOPY / "temperatures_K.npy")
    cv = np.load(_PHONOPY / "heat_capacity_J_per_K_per_mol.npy")
    idx = int(np.argmin(np.abs(T - 300.0)))
    ground_truth = float(cv[idx])
    rel = abs(derived - ground_truth) / abs(ground_truth)
    assert rel < 1e-2, f"derived molar Cv {derived:.4f} vs phonopy {ground_truth:.4f} (rel {rel:.2%})"


def test_example_a_cross_code_frequency_routes_agree():
    """MolarHeatCapacity derived from kaldo's vs phonopy's Frequency must agree
    (both reach the same Observable)."""
    _require(_KALDO / "frequencies_THz.npy")
    _require(_PHONOPY / "frequencies_THz.npy")
    routes = {
        "kaldo": {"Frequency": _freq_source(_KALDO), "Temperature": _temperature_source()},
        "phonopy": {"Frequency": _freq_source(_PHONOPY), "Temperature": _temperature_source()},
    }
    report = cross_check(MOLAR_HEAT_CAPACITY, routes, rtol=1e-2)
    assert report.ok(), report.render()


def test_example_b_kappa_direct_matches_kaldo():
    """Framework-contracted κ_LBTE (from loaded c-derivation + GV + MFD) agrees
    with kaldo's emitted kappa_inverse.

    Unit note: the executor's apply_edge bridge rescales the κ contraction by
    1e22 automatically, so result.representation.data is already in W/(m·K).
    """
    _require(_KALDO / "frequencies_THz.npy")
    _require(_KALDO / "group_velocities_AT.npy")
    _require(_KALDO / "mean_free_displacement.npy")
    _require(_KALDO / "kappa_inverse_tensor_WmK.npy")

    a = 5.431
    v_cell = a ** 3 / 4.0
    sources = {
        "Frequency": _freq_source(_KALDO),
        "Temperature": _temperature_source(),
        "GroupVelocity": Representation(
            space_adapter_spec=operator_form_spec(GROUP_VELOCITY), observable_name="v",
            data=np.load(_KALDO / "group_velocities_AT.npy"), is_operator=True),
        "MeanFreeDisplacement[bte_solver=direct_inverse]": Representation(
            space_adapter_spec=operator_form_spec(MEAN_FREE_DISPLACEMENT_DIRECT),
            observable_name="F",
            data=np.load(_KALDO / "mean_free_displacement.npy"), is_operator=True),
    }
    result = compute(THERMAL_CONDUCTIVITY_DIRECT, sources, constants={"V_{cell}": v_cell})
    # Bridge in apply_edge already rescaled to W/(m·K) — use data directly.
    kappa = np.asarray(result.representation.data)
    gt = np.load(_KALDO / "kappa_inverse_tensor_WmK.npy")
    rel = abs(np.trace(kappa) / 3.0 - np.trace(gt) / 3.0) / abs(np.trace(gt) / 3.0)
    assert rel < 0.05, f"framework κ {np.trace(kappa)/3:.3f} vs kaldo {np.trace(gt)/3:.3f} (rel {rel:.2%})"
