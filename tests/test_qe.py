"""Quantum ESPRESSO adapter smoke tests (per docs/skills/ingest_code.md).

QE grounds the source tier of the thermal-transport DAG: it produces the
FC2 / Born-charge / dielectric leaves the other codes consume. The specs
under test were derived from the scan catalog scans/qe-phonon.json; the
convention traps asserted here (linear cm-1 wavenumbers, Ry/bohr^2 force
constants) are the catalog's top findings.
"""
from __future__ import annotations

import math

import numpy as np

from omai.representation import compare, represent
from omai.representation.units import conversion_factor
from omai.thermal_transport.representation import (
    KALDO_FREQUENCY,
    QE_BORN_CHARGES,
    QE_FORCE_CONSTANTS_2,
    QE_FREQUENCY,
    SHENGBTE_FREQUENCY,
)
from omai.thermal_transport.representation.phonopy import PHONOPY_BORN_CHARGES

# 1 cm-1 (linear wavenumber) = c * 100 Hz = 0.0299792458 linear THz.
_CM1_TO_LINEAR_THZ = 0.0299792458
# 1 Ry/bohr^2 in eV/A^2, from CODATA Ry and bohr.
_RY_PER_BOHR2_TO_EV_PER_A2 = 13.605693122994 / 0.529177210903**2


def test_qe_frequency_cm1_to_kaldo_linear_thz():
    """matdyn.freq emits linear wavenumbers in cm-1; kaldo emits linear
    THz. Cross-code factor: c in cm/ps = 0.0299792458."""
    nu_thz = np.array([1.0, 5.0, 15.0])
    nu_cm1 = nu_thz / _CM1_TO_LINEAR_THZ
    mq = represent(QE_FREQUENCY, "omega", nu_cm1)
    mk = represent(KALDO_FREQUENCY, "omega", nu_thz)
    r = compare(mq, mk, rtol=1e-9)
    assert r.agreed
    assert math.isclose(r.factor, _CM1_TO_LINEAR_THZ, rel_tol=1e-9)


def test_qe_frequency_agrees_with_shengbte():
    """QE cm-1 (linear) vs ShengBTE rad/ps (angular): the compound factor
    is c * 2*pi. Compounding-unit trap from ingest_code.md."""
    nu_thz = np.array([2.0, 4.0])
    mq = represent(QE_FREQUENCY, "omega", nu_thz / _CM1_TO_LINEAR_THZ)
    ms = represent(SHENGBTE_FREQUENCY, "omega", nu_thz * 2 * math.pi)
    r = compare(mq, ms, rtol=1e-9)
    assert r.agreed


def test_qe_fc2_unit_conversion_factor():
    """flfrc force constants are Ry/bohr^2; the canonical FC2 unit is
    eV/A^2. 1 Ry/bohr^2 = 48.587 eV/A^2 (CODATA)."""
    factor = conversion_factor("Ry_per_bohr2", "eV_per_A2")
    assert math.isclose(factor, _RY_PER_BOHR2_TO_EV_PER_A2, rel_tol=1e-12)
    assert QE_FORCE_CONSTANTS_2.declared_unit("phi") == "Ry_per_bohr2"


def test_qe_born_charges_agree_with_phonopy():
    """Both codes emit Z* in units of the elementary charge; the phonopy
    BORN file is typically generated from exactly this ph.x output, so
    EXPECTED_AGREE with factor 1 is the ground truth."""
    z_star = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]])
    mq = represent(QE_BORN_CHARGES, "Z_star", z_star)
    mp = represent(PHONOPY_BORN_CHARGES, "Z_star", z_star)
    r = compare(mq, mp, rtol=1e-12)
    assert r.agreed
    assert math.isclose(r.factor, 1.0, rel_tol=1e-12)


def test_qe_discoverable_by_site_exporter():
    """build_codes must pick the qe module up automatically so the map's
    per-code selector shows QE."""
    from omai.map_data import DOMAINS, build_codes

    codes = build_codes(DOMAINS)
    assert "qe" in codes
    assert "Frequency" in codes["qe"]
    assert "ForceConstants[order=2]" in codes["qe"]
    assert len(codes["qe"]) >= 8
