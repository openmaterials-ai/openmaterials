import numpy as np
from pymatgen.core import Lattice, Structure


def diamond_si(a: float = 5.43) -> Structure:
    return Structure.from_spacegroup("Fd-3m", Lattice.cubic(a), ["Si"], [[0, 0, 0]])


def fcc_si(a: float = 3.87) -> Structure:
    return Structure.from_spacegroup("Fm-3m", Lattice.cubic(a), ["Si"], [[0, 0, 0]])


def strained(s: Structure, eps: float = 0.01) -> Structure:
    out = s.copy()
    out.apply_strain(eps)
    return out


def rattled(s: Structure, sigma: float, seed: int) -> Structure:
    rng = np.random.default_rng(seed)
    coords = s.cart_coords + rng.normal(0.0, sigma, size=(len(s), 3))
    return Structure(s.lattice, s.species, coords, coords_are_cartesian=True)


def glass(seed: int, rep: int = 4) -> Structure:
    return rattled(diamond_si() * (rep, rep, rep), sigma=0.5, seed=seed)


def rotated(s: Structure, axis=(1.0, 2.0, 3.0), angle_deg: float = 37.0) -> Structure:
    from scipy.spatial.transform import Rotation

    ax = np.asarray(axis, dtype=float)
    R = Rotation.from_rotvec(np.deg2rad(angle_deg) * ax / np.linalg.norm(ax)).as_matrix()
    return Structure(s.lattice.matrix @ R.T, s.species, s.frac_coords)


def permuted(s: Structure, seed: int = 7) -> Structure:
    order = np.random.default_rng(seed).permutation(len(s))
    return Structure(s.lattice, [s.species[i] for i in order], s.frac_coords[order])


def translated(s: Structure, shift=(0.13, 0.29, 0.41)) -> Structure:
    return Structure(s.lattice, s.species, (s.frac_coords + np.asarray(shift)) % 1.0)


def pristine_216() -> Structure:
    return diamond_si() * (3, 3, 3)


def vacancy(idx: int = 0) -> Structure:
    s = pristine_216()
    s.remove_sites([idx])
    return s


def doped(idx: int = 0) -> Structure:
    s = pristine_216()
    s.replace(idx, "P")
    return s


