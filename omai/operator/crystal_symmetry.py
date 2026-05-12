"""Operator crystal symmetry at the operator level.

A `SymmetryGroup` is the operator layer's *operator* declaration of a crystal
symmetry: a name, an order, and (optionally) a description. The operator layer
does **not** enumerate group elements or store concrete rotation matrices.
That work — extracting symmetries from a crystal structure, applying them
to tensors, building irreducible-BZ reductions — belongs to the materials
codes (phonopy, kaldo, ShengBTE, …), typically via spglib.

The operator layer's role here is to *name* the group so that:

  * operations can declare which symmetry group they assume as a
    parameterized identity (`compute_force_constants[order=2,
    symmetry=Oh]` differs from `compute_force_constants[order=2,
    symmetry=C1]`),
  * adapter specs can declare which group the code assumed in a
    particular run,
  * cross-code comparison can refuse to compare two representations
    whose declared symmetry groups disagree.

This is parallel to how `Potential` is declared symbolically (a label,
Phase 1 stub) without the operator layer modeling its functional form.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymmetryGroup:
    """A finite subgroup of O(3) ⋉ ℝ³ acting on a crystal (operator).

    Declared by Hermann-Mauguin / Schoenflies symbol plus order. No
    element data: concrete matrices and group products are the codes'
    responsibility, not the operator layer's.
    """

    name: str
    order: int
    description: str = ""


# Common groups, listed for declaration purposes only. Adapters that need
# the concrete elements compute them on their side (e.g. via spglib).
OH = SymmetryGroup(name="Oh", order=48, description="Cubic centrosymmetric (silicon, NaCl, …)")
D6H = SymmetryGroup(name="D6h", order=24, description="Hexagonal centrosymmetric (graphite, ZnO basal)")
D4H = SymmetryGroup(name="D4h", order=16, description="Tetragonal centrosymmetric")
D2H = SymmetryGroup(name="D2h", order=8, description="Orthorhombic centrosymmetric")
C2H = SymmetryGroup(name="C2h", order=4, description="Monoclinic")
CI = SymmetryGroup(name="Ci", order=2, description="Inversion-only (triclinic centrosymmetric)")
C1 = SymmetryGroup(name="C1", order=1, description="No symmetry (trivial; lowest-symmetry triclinic)")
