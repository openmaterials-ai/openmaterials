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
    MOLAR_HEAT_CAPACITY,
    TEMPERATURE_STATE,
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
