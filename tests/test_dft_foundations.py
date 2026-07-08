"""Foundations for the DFT ground-state domain (Task 1).

The ground-state contribution needs one new named Dimension (FORCE = M L T^-2),
six new Units (energy: ev, ry; force: eV_per_A, Ry_per_bohr; pressure/energy-
density: kbar, GPa), and three new quantity tags (total_energy, force, stress).
Stress reuses the existing ENERGY_PER_LENGTH_CUBED dimension (its exponents are
identical to a pressure M L^-1 T^-2), so no new pressure Dimension is minted.
"""
from __future__ import annotations

import math

from omai.operator.dimensions import (
    DIMENSIONS,
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    FORCE,
    LENGTH,
)
from omai.operator.registry import QUANTITY_TAGS
from omai.representation.units import UNITS, conversion_factor


# --------------------------------------------------------------------------
# FORCE dimension: algebra and registration.
# --------------------------------------------------------------------------

def test_force_dimension_registered_with_right_exponents():
    assert FORCE.exponents == (1, 1, -2, 0, 0, 0, 0)
    assert DIMENSIONS["force"] is FORCE


def test_force_is_energy_over_length():
    # F = -dE/dx, so a force is an energy per unit length.
    assert ENERGY / LENGTH == FORCE


def test_stress_reuses_energy_per_length_cubed():
    # A pressure M L^-1 T^-2 has the exponents of an energy density, so Stress
    # is typed ENERGY_PER_LENGTH_CUBED; no separate PRESSURE Dimension is minted.
    assert ENERGY_PER_LENGTH_CUBED.exponents == (1, -1, -2, 0, 0, 0, 0)


# --------------------------------------------------------------------------
# Units: registration and conversion factors.
# --------------------------------------------------------------------------

def test_energy_units_registered():
    assert UNITS["ev"].dimension == ENERGY
    assert UNITS["ry"].dimension == ENERGY


def test_force_units_registered():
    assert UNITS["eV_per_A"].dimension == FORCE
    assert UNITS["Ry_per_bohr"].dimension == FORCE


def test_pressure_units_registered():
    assert UNITS["kbar"].dimension == ENERGY_PER_LENGTH_CUBED
    assert UNITS["GPa"].dimension == ENERGY_PER_LENGTH_CUBED


def test_ry_to_ev_conversion():
    # 1 Ry = 13.605693122994 eV (CODATA Rydberg energy in eV).
    assert conversion_factor("ry", "ev") == 13.605693122994


def test_ry_per_bohr_to_eV_per_A_conversion():
    # 1 Ry/bohr = 13.605693122994 / 0.529177210903 eV/A = 25.711034... eV/A
    # (the plan's "25.711043" transposes two digits of this exact quotient).
    assert math.isclose(
        conversion_factor("Ry_per_bohr", "eV_per_A"), 25.711034, abs_tol=1e-6
    )


def test_kbar_to_GPa_conversion():
    # 1 kbar = 0.1 GPa exactly.
    assert math.isclose(conversion_factor("kbar", "GPa"), 0.1, abs_tol=1e-12)


# --------------------------------------------------------------------------
# Quantity tags.
# --------------------------------------------------------------------------

def test_ground_state_quantity_tags_registered():
    # The Forces node name derives the tag "forces" (quantity_tag_for("Forces")
    # -> "forces"), so the registered tag is the plural to match node identity;
    # total_energy and stress derive directly.
    for tag in ("total_energy", "forces", "stress"):
        assert tag in QUANTITY_TAGS
        assert QUANTITY_TAGS[tag], f"{tag} needs a real one-line description"
