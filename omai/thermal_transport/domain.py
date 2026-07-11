"""The thermal-transport Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.thermal_transport import representation as tt_rep
from omai.thermal_transport.operator import EDGES, NODES
from omai.thermal_transport.operator import edges as _edges

# Canonical LaTeX symbol per variable (consistent symbolic names, not words).
# Matches the IndexedBase symbols the operator-layer formulas are written in.
SYMBOLS = {
    "Potential": r"V",
    "Temperature": r"T",
    "BornCharges": r"Z^{*}",
    "DielectricTensor": r"\varepsilon_{\infty}",
    "IsotopeAbundances": r"g_{\mathrm{iso}}",
    "Trajectory": r"\mathbf{r}(t)",
    "ForceConstants[order=2]": r"\Phi^{(2)}",
    "ForceConstants[order=3]": r"\Phi^{(3)}",
    "HeatCurrent": r"\mathbf{J}",
    "BareDynamicalMatrix": r"D^{bare}",
    "MeanSquaredDisplacement": r"\langle u^{2}\rangle",
    "VelocityAutocorrelation": r"\langle v(0)v(t)\rangle",
    "DynamicalMatrix": r"D",
    "HeatCurrentACF": r"\langle JJ\rangle",
    "PhononDOS": r"g(\omega)",
    "ThermalConductivity[transport_model=hnemd]": r"\kappa_{\mathrm{hnemd}}",
    "ThermalConductivity[transport_model=nemd]": r"\kappa_{\mathrm{nemd}}",
    "Eigenvectors": r"e",
    "Frequency": r"\omega",
    "ThermalConductivity[transport_model=green_kubo]": r"\kappa_{\mathrm{gk}}",
    "GroupVelocity": r"v",
    "Linewidth[channel=anharmonic_3ph]": r"\Gamma_{\mathrm{3ph}}",
    "Linewidth[channel=isotope]": r"\Gamma_{\mathrm{iso}}",
    "Entropy": r"S",
    "Gruneisen": r"\gamma",
    "HeatCapacity": r"c",
    "HelmholtzFreeEnergy": r"F",
    "InternalEnergy": r"E",
    "PhaseSpace3Phonon": r"P_{3}",
    "Linewidth[channel=boundary]": r"\Gamma_{\mathrm{bnd}}",
    "MolarEntropy": r"S_{\mathrm{m}}",
    "MolarHeatCapacity": r"C_{\mathrm{m}}",
    "MolarHelmholtzFreeEnergy": r"F_{\mathrm{m}}",
    "MolarInternalEnergy": r"E_{\mathrm{m}}",
    "VolumetricHeatCapacity": r"C_{V}",
    "Linewidth[channel=total]": r"\Gamma",
    "MeanFreeDisplacement[bte_solver=rta]": r"\lambda_{\mathrm{rta}}",
    "ThermalConductivity[transport_model=qhgk]": r"\kappa_{\mathrm{qhgk}}",
    "MeanFreeDisplacement[bte_solver=direct_inverse]": r"\lambda_{\mathrm{dinv}}",
    "ThermalConductivity[transport_model=wigner_coherences]": r"\kappa_{\mathrm{coh}}",
    "ThermalConductivity[bte_solver=rta]": r"\kappa^{\mathrm{rta}}",
    "CumulativeKappa[wrt=mfp]": r"\kappa^{\mathrm{cum}}_{\lambda}",
    "CumulativeKappa[wrt=omega]": r"\kappa^{\mathrm{cum}}_{\omega}",
    "ThermalConductivity[bte_solver=direct_inverse]": r"\kappa^{\mathrm{dinv}}",
    "ThermalConductivity[transport_model=wigner_populations]": r"\kappa_{\mathrm{pop}}",
    "ThermalConductivity[transport_model=wigner]": r"\kappa",
}


THERMAL_TRANSPORT = Domain(
    name="thermal_transport",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(
        ("CellVolume", r"V_{\mathrm{cell}}", _edges._V_cell, "volume",
         "A derived view of a Structure value (the cell volume), never "
         "standalone evidence."),
        ("AtomicMass", r"M", _edges._M, "mass",
         "A derived view of a Structure value (the per-species atomic mass), "
         "never standalone evidence."),
        ("AtomCount", r"N", _edges._N_atoms, "dimensionless",
         "A derived view of a Structure value (the number of atoms in the "
         "cell), never standalone evidence."),
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
