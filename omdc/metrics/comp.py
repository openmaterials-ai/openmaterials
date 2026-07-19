"""comp@1: Element Mover's Distance over the Pettifor chemical scale.

Wasserstein-1 in one dimension between fractional compositions placed on
pymatgen's mendeleev_no axis (Pettifor's scale, unit spacing), computed as the
L1 difference of the two cumulative distributions. A true metric on
compositions; chemistry only, so every Si polymorph sits at zero from every
other. Distances are in Pettifor-scale units."""
from __future__ import annotations

import numpy as np
from pymatgen.core import Composition, Element

_AXIS = 104  # mendeleev_no runs 1..103


def _profile(comp: Composition) -> np.ndarray:
    axis = np.zeros(_AXIS, dtype=np.float64)
    total = comp.num_atoms
    for el, amt in comp.get_el_amt_dict().items():
        m = Element(el).mendeleev_no
        if m is None:
            raise ValueError(f"no Pettifor number for element {el}")
        axis[int(m)] += amt / total
    return axis


def elmd(a, b) -> float:
    ca = a if isinstance(a, Composition) else Composition(a)
    cb = b if isinstance(b, Composition) else Composition(b)
    return float(np.abs(np.cumsum(_profile(ca) - _profile(cb))).sum())
