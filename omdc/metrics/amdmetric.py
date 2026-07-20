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


def amd_profile(s1: Structure, s2: Structure, ks=(10, 25, 50, 100)) -> dict[int, float]:
    """The k index of the AMD vector is a length-scale ladder; prefix maxima
    are monotone in k, so each rung is a nested lower bound of the full amd
    distance. One AMD computation at max(ks) per structure."""
    kmax = max(ks)
    a = np.asarray(_amd_vector(s1, kmax), dtype=np.float64)
    b = np.asarray(_amd_vector(s2, kmax), dtype=np.float64)
    diff = np.abs(a - b)
    return {int(k): float(diff[:k].max()) for k in sorted(ks)}
