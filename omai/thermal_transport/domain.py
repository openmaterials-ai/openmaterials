"""The thermal-transport Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.thermal_transport import representation as tt_rep
from omai.thermal_transport.operator import EDGES, NODES
from omai.thermal_transport.operator import edges as _edges
from omai.thermal_transport.site_data import SYMBOLS

THERMAL_TRANSPORT = Domain(
    name="thermal_transport",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(
        ("CellVolume", r"V_{\mathrm{cell}}", _edges._V_cell, "volume"),
        ("AtomicMass", r"M", _edges._M, "mass"),
        ("AtomCount", r"N", _edges._N_atoms, "dimensionless"),
    ),
    tiers=(
        ("Sources", "Inputs a calculation is given: the potential, temperature, force constants, and polar-response tensors."),
        ("Harmonic", "The harmonic phonon picture: dynamical matrix, frequencies, eigenvectors, group velocities, density of states."),
        ("Thermodynamics", "Equilibrium thermodynamics of the phonon gas: heat capacity, entropy, free energy, and their molar forms."),
        ("Scattering", "Phonon lifetimes: anharmonic, isotope, and boundary linewidth channels, phase space, and Gruneisen anharmonicity."),
        ("Transport", "Thermal conductivity from the Boltzmann transport equation, the Wigner and QHGK models, and cumulative-kappa distributions."),
        ("Molecular dynamics", "Direct MD: trajectories, heat current, correlation functions, and the Green-Kubo / NEMD / HNEMD conductivities."),
    ),
    representation_package=tt_rep,
)
