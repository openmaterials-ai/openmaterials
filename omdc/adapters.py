"""Input adapters: omdc speaks pymatgen Structure; ASE Atoms convert on entry."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ase import Atoms
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

ROUND_DECIMALS = 5  # matches openmaterials configuration rounding


def to_structure(obj: Any) -> Structure:
    if isinstance(obj, Structure):
        return obj
    if isinstance(obj, Atoms):
        return AseAtomsAdaptor.get_structure(obj)
    raise TypeError(
        f"expected pymatgen Structure or ase Atoms, got {type(obj).__name__}"
    )


def structure_key(obj: Any) -> str:
    """sha256 over the sorted, wrapped, rounded structure. A cache key, not
    identity: when an openmaterials canonical_uid exists, prefer it upstream.
    A rounding collision at the wrap boundary costs a cache miss, never a
    wrong merge."""
    s = to_structure(obj).get_sorted_structure()
    lattice = [[round(x, ROUND_DECIMALS) for x in row] for row in s.lattice.matrix.tolist()]
    sites = sorted(
        [site.species_string, [round(x % 1.0, ROUND_DECIMALS) % 1.0 for x in site.frac_coords.tolist()]]
        for site in s
    )
    payload = json.dumps([lattice, sites], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
