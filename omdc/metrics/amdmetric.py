"""amd@1: Average Minimum Distance (Widdowson and Kurlin), Chebyshev form.

Geometry only and species-blind: pair it with comp when chemistry matters.
Deterministic, milliseconds even on multi-thousand-atom cells."""
from __future__ import annotations

import numpy as np
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

from omdc.errors import MissingExtraError

AMD_K = 100


def _amd_vector(structure: Structure, k: int):
    try:
        import amd
    except ImportError as exc:
        raise MissingExtraError("the amd distance", "amd") from exc
    for fn_name in ("periodicset_from_pymatgen_structure", "periodicset_from_ase_atoms"):
        fn = getattr(amd, fn_name, None) or getattr(getattr(amd, "io", amd), fn_name, None)
        if fn is None:
            continue
        obj = structure if "pymatgen" in fn_name else AseAtomsAdaptor.get_atoms(structure)
        return amd.AMD(fn(obj), k)
    raise RuntimeError("average-minimum-distance API not recognized; upgrade the amd extra")


def amd_distance(s1: Structure, s2: Structure, k: int = AMD_K) -> float:
    a, b = _amd_vector(s1, k), _amd_vector(s2, k)
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
