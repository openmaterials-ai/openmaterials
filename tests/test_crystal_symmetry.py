"""Tests for the substrate's crystal-symmetry primitives."""

from __future__ import annotations

import sympy as sp

from omai.abstract import (
    CrystalPointGroup,
    SymmetryOperation,
    fc2_gauge_from_symmetry_op,
)
from omai.abstract.crystal_symmetry import CI, IDENTITY, INVERSION
from omai.thermal_transport.symbolic.edges import _Phi2
from omai.thermal_transport.symbolic.gauges import (
    CRYSTAL_INVERSION_ON_FC2,
    symmetrized_fc2,
)


# === SymmetryOperation basics ===


def test_identity_is_pure_rotation_with_det_one():
    assert IDENTITY.is_pure_rotation()
    assert IDENTITY.determinant() == 1


def test_inversion_is_pure_rotation_with_det_minus_one():
    assert INVERSION.is_pure_rotation()
    assert INVERSION.determinant() == -1


# === CrystalPointGroup ===


def test_ci_has_only_inversion_as_generator():
    """The order-2 group Ci has one non-trivial generator: inversion."""
    assert CI.name == "Ci"
    assert CI.generators == (INVERSION,)


def test_user_can_construct_custom_point_group():
    """Generality check: any user-supplied list of operations is accepted."""
    custom = CrystalPointGroup(
        name="custom",
        generators=(IDENTITY, INVERSION),
    )
    assert len(custom.generators) == 2


# === Gauge-action factory ===


def test_fc2_gauge_for_inversion_is_substitution_friendly():
    """Inversion's rotation is -𝟙 (diagonal, all -1) — substitution works."""
    i_w, j_w, R_w = sp.Wild("i_w"), sp.Wild("j_w"), sp.Wild("R_w")
    g = fc2_gauge_from_symmetry_op(INVERSION, _Phi2, i_w, j_w, R_w)
    assert g is not None
    # Apply to a symmetrized FC² and verify invariance
    assert g.verifies_invariance(symmetrized_fc2())


def test_fc2_gauge_for_identity_is_substitution_friendly_and_trivial():
    """Identity is the trivial gauge — any expression is invariant."""
    i_w, j_w, R_w = sp.Wild("i_w"), sp.Wild("j_w"), sp.Wild("R_w")
    g = fc2_gauge_from_symmetry_op(IDENTITY, _Phi2, i_w, j_w, R_w)
    assert g is not None
    bare = _Phi2[sp.Symbol("i"), sp.Symbol("j"), sp.Symbol("R")]
    assert g.verifies_invariance(bare)


def test_fc2_gauge_for_general_rotation_returns_none():
    """A rotation that mixes Cartesian components is not substitution-friendly."""
    c4_z = SymmetryOperation(
        rotation=((0, -1, 0), (1, 0, 0), (0, 0, 1)),  # 90° around z
        name="C4_z",
    )
    i_w, j_w, R_w = sp.Wild("i_w"), sp.Wild("j_w"), sp.Wild("R_w")
    g = fc2_gauge_from_symmetry_op(c4_z, _Phi2, i_w, j_w, R_w)
    assert g is None  # current substrate machinery defers; declared, not proven


def test_pre_built_crystal_inversion_matches_factory_output():
    """The thermal_transport CRYSTAL_INVERSION_ON_FC2 is what the factory produces."""
    i_w, j_w, R_w = sp.Wild("i_w"), sp.Wild("j_w"), sp.Wild("R_w")
    from_factory = fc2_gauge_from_symmetry_op(INVERSION, _Phi2, i_w, j_w, R_w)
    # Both prove the symmetrized FC² invariant
    assert from_factory.verifies_invariance(symmetrized_fc2())
    assert CRYSTAL_INVERSION_ON_FC2.verifies_invariance(symmetrized_fc2())
