"""exact@1: pymatgen StructureMatcher RMSD. Re-rank only: pairwise, slow, and
inf when the matcher finds no correspondence (for example across compositions)."""
from __future__ import annotations

from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure


def exact_rmsd(s1: Structure, s2: Structure) -> float:
    matcher = StructureMatcher(primitive_cell=True, scale=False, attempt_supercell=True)
    rms = matcher.get_rms_dist(s1, s2)
    return float("inf") if rms is None else float(rms[0])
