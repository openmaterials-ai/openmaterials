"""Every registered distance across a small zoo of Si cells, on the hist
encoder so the example runs without extras. Swap encoder="mace" (pip install -e ".[distance,mace]") for the traversal-quality space."""
import numpy as np
from pymatgen.core import Lattice, Structure

import omdc

diamond = Structure.from_spacegroup("Fd-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
strained = diamond.copy()
strained.apply_strain(0.01)
fcc = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.87), ["Si"], [[0, 0, 0]])
big = diamond * (3, 3, 3)
rng = np.random.default_rng(1)
glass = Structure(
    big.lattice,
    big.species,
    big.cart_coords + rng.normal(0, 0.5, (len(big), 3)),
    coords_are_cartesian=True,
)
vacancy = big.copy()
vacancy.remove_sites([0])

zoo = {"strained 1%": strained, "fcc": fcc, "glass": glass, "vacancy": vacancy}
print(f"distance from Si diamond (default alias resolves to {omdc.DEFAULT_ALIAS}; hist encoder here)\n")
for name, s in zoo.items():
    cells = []
    for spec in omdc.DISTANCES.values():
        if spec.needs_encoder:
            d = omdc.distance(diamond, s, metric=spec.id, encoder="hist")
        else:
            d = omdc.distance(diamond, s, metric=spec.id)
        cells.append(f"{spec.id}={d:8.4f}")
    print(f"{name:12s} " + "  ".join(cells))
