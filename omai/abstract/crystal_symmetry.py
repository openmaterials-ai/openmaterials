"""Crystal symmetry as substrate-level data.

A `SymmetryOperation` is a 3×3 integer rotation matrix plus a 3-vector
translation, matching the data spglib (and most crystallographic codes)
expose. A `CrystalPointGroup` is a finite list of generators; the full
group is closed under their products, and invariance under the
generators implies invariance under the full group.

The substrate is **spglib-agnostic** by design: it consumes the same
data model spglib produces but does not depend on spglib. Materials
adapters that use spglib internally translate its output into
`SymmetryOperation` / `CrystalPointGroup` instances and hand them to
the substrate. Adapters that bring their own symmetry analyzer
(phonopy, kaldo's recent main, ...) do the same.

Conventions
-----------
- Rotations are integer 3×3 matrices in **lattice (fractional) coordinates**.
  This matches spglib. For point-group operations on Cartesian tensors,
  Bravais-lattice / Cartesian conversion is handled at the gauge-action
  construction site.
- Translations are 3-tuples of fractions (`Fraction`) in units of the
  lattice vectors. Pure-point-group operations have translation `(0, 0, 0)`.
- Each operation has an optional human-readable `name` (e.g., "E", "i",
  "C4_z", "sigma_h"). Not load-bearing — only used in error messages and
  diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


_RotationRow = tuple[int, int, int]
RotationMatrix = tuple[_RotationRow, _RotationRow, _RotationRow]
TranslationVector = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True)
class SymmetryOperation:
    rotation: RotationMatrix
    translation: TranslationVector = (Fraction(0), Fraction(0), Fraction(0))
    name: str = ""

    def is_pure_rotation(self) -> bool:
        """True if translation is zero (point-group element, not screw / glide)."""
        return all(t == 0 for t in self.translation)

    def determinant(self) -> int:
        """Determinant of the rotation. +1 for proper, -1 for improper rotations."""
        r = self.rotation
        return (
            r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
            - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
            + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
        )


@dataclass(frozen=True)
class CrystalPointGroup:
    """A finite point group, given as a tuple of generators.

    Invariance under the full group is equivalent to invariance under each
    generator (by closure). For our purposes the substrate verifies
    operation-formula invariance under each generator separately.
    """

    name: str
    generators: tuple[SymmetryOperation, ...]


# === Common operations as named constants ===

IDENTITY = SymmetryOperation(
    rotation=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    name="E",
)

INVERSION = SymmetryOperation(
    rotation=((-1, 0, 0), (0, -1, 0), (0, 0, -1)),
    name="i",
)


# === Some illustrative groups (for tests / examples) ===

CI = CrystalPointGroup(name="Ci", generators=(INVERSION,))
"""The order-2 group {E, i} — inversion symmetry only."""

C1 = CrystalPointGroup(name="C1", generators=())
"""The trivial group — only the identity. Used to express 'no symmetry imposed'."""


# === spglib integration sketch (adapter-side, not implemented here) ===
#
# A materials adapter that uses spglib would translate spglib's output
# into a CrystalPointGroup roughly like this:
#
#     import spglib
#     dataset = spglib.get_symmetry_dataset((lattice, positions, numbers))
#     # dataset['rotations']    — N × 3 × 3 array of integer rotation matrices
#     # dataset['translations'] — N × 3 array of float translations
#     # dataset['pointgroup']   — Hermann-Mauguin point group symbol
#     ops = tuple(
#         SymmetryOperation(
#             rotation=tuple(tuple(int(x) for x in row) for row in rot),
#             translation=tuple(Fraction(t).limit_denominator(48) for t in trans),
#         )
#         for rot, trans in zip(dataset['rotations'], dataset['translations'])
#     )
#     point_group = CrystalPointGroup(name=dataset['pointgroup'], generators=ops)
#
# Note: spglib returns the full set of group elements (not just generators).
# That's fine for the substrate — verifying invariance under the full set
# is strictly stronger than under generators, and computationally cheap
# at the formula-substitution level.
