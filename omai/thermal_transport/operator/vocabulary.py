"""Formula symbol vocabulary of the thermal-transport domain.

Registers, into the core registry (`omai.operator.vocabulary`), the sympy
base-symbol names each thermal-transport space may carry in edge formulas,
plus the domain's bare constants (BZ-mesh counters, MD recurrence symbols,
provided-source placeholders, cumulative-κ thresholds). Imported for its
side effect by `omai.thermal_transport.operator.__init__`, so any consumer
of the domain's nodes/edges sees the vocabulary registered.

Rationale for the per-space sets: the operator layer's promise is "every
edge carries a sympy formula whose symbols are the quantities the space
declares". The mapping from field name (Python convention, e.g. `omega`)
to sympy IndexedBase name (LaTeX convention, e.g. `\\omega`) is non-trivial
in places; this table encodes that mapping. Add an entry whenever the DAG
grows a space.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_formula_constants, register_space_symbols

# Domain constants any thermal-transport formula may reference.
register_formula_constants({
    # Cell / BZ-mesh counters.
    "V_{cell}",
    "N",
    "N_q",
    # Lattice / BZ dummy labels.
    r"\mathbf{q}",
    r"\mathbf{q'}",
    r"\mathbf{R}",
    r"\mathbf{R'}",
    # Per-component q-vector symbols (NAC formula).
    r"q^\alpha",
    r"q^\beta",
    # Displacement labels (FC2 / FC3 derivative formulas).
    "u_i(0)",
    "u_j(R)",
    "u_k(R')",
    r"\{u\}",
    # Source-side provided placeholders (nullary provide_* edges).
    r"V_{\mathrm{provided}}",
    r"T_{\mathrm{provided}}",
    r"V_{provided}",
    r"T_{provided}",
    r"Z^*_{provided}",
    r"\varepsilon_{\infty,provided}",
    r"g_{provided}",
    # DOS bin variable and cumulative-κ thresholds.
    r"\omega",
    r"\omega_c",
    r"\Lambda_c",
    # Generic length-scale parameter alias. Several edges (e.g.
    # compute_boundary_scattering) declare a length-scale Parameter
    # (boundary_length_scale) but reference it in the formula by the
    # textbook symbol `L`. Permit `L` so the formula reads naturally.
    "L",
    # MD primitives (phase 2 P2). The integer timestep index `t`, the
    # correlation lag `\tau`, the timestep size `\Delta t`, the
    # correlation depth `n_{lag}`, and the atom count `N_{atoms}` are
    # universal MD recurrence / averaging constants that any MD edge may
    # reference.
    "t",
    r"\tau",
    r"\Delta t",
    r"n_{lag}",
    r"N_{atoms}",
    # MD-based κ (phase 2 P3). τ_max / τ_min are the GK integration
    # bounds (declared as edge parameters and also free in the integrand
    # expression); F_e is the HNEMD driving-force IndexedBase; ∇T is the
    # imposed NEMD temperature-gradient IndexedBase.
    r"\tau_{max}",
    r"\tau_{min}",
    "F_e",
    r"\nabla T",
})

# Per-space allowed sympy base-symbol names.
register_space_symbols({
    "Potential": {r"\{u\}", r"V_{\mathrm{provided}}"},
    "Temperature": {"T", r"T_{\mathrm{provided}}"},
    "ForceConstants[order=2]": {r"\Phi^{(2)}"},
    "ForceConstants[order=3]": {r"\Phi^{(3)}"},
    "BornCharges": {r"Z^*", r"Z^*_{provided}"},
    "DielectricTensor": {r"\varepsilon_\infty", r"\varepsilon_{\infty,provided}"},
    "BareDynamicalMatrix": {r"D^{bare}", "M"},
    "DynamicalMatrix": {"D", r"\partial D/\partial q", "M"},
    "Frequency": {r"\omega"},
    "Eigenvectors": {"e", "m"},
    "GroupVelocity": {"v"},
    "HeatCapacity": {"c"},
    "VolumetricHeatCapacity": {r"C_V^{vol}"},
    "MolarHeatCapacity": {r"C_V^{mol}"},
    "HelmholtzFreeEnergy": {"f"},
    "Entropy": {"s"},
    "InternalEnergy": {"e"},
    "MolarHelmholtzFreeEnergy": {r"F_{mol}"},
    "MolarEntropy": {r"S_{mol}"},
    "MolarInternalEnergy": {r"E_{mol}"},
    # Linewidth: each per-channel space allows its channel-specific symbol;
    # the total space allows all channel variants since sum_linewidths and
    # downstream consumers reference them as components.
    "Linewidth[channel=anharmonic_3ph]": {r"\Gamma", r"\Gamma^{anh}"},
    "Linewidth[channel=isotope]": {r"\Gamma^{iso}"},
    "Linewidth[channel=boundary]": {r"\Gamma^{bnd}"},
    "Linewidth[channel=total]": {
        r"\Gamma",
        r"\Gamma^{tot}",
        r"\Gamma^{anh}",
        r"\Gamma^{iso}",
        r"\Gamma^{bnd}",
    },
    "IsotopeAbundances": {"g", r"g_{provided}"},
    "PhononDOS": {"g"},
    "Gruneisen": {r"\gamma_G"},
    "PhaseSpace3Phonon": {r"P_3"},
    "MeanFreeDisplacement[bte_solver=rta]": {"F"},
    "MeanFreeDisplacement[bte_solver=direct_inverse]": {
        "F",
        r"\mathcal{M}",  # collision matrix used in solve_bte_direct's auxiliary formula
    },
    "ThermalConductivity[bte_solver=rta]": {r"\kappa"},
    "ThermalConductivity[bte_solver=direct_inverse]": {r"\kappa"},
    "ThermalConductivity[transport_model=wigner_populations]": {r"\kappa^{W,pop}"},
    "ThermalConductivity[transport_model=wigner_coherences]": {r"\kappa^{W,coh}"},
    "ThermalConductivity[transport_model=wigner]": {
        r"\kappa^W",
        r"\kappa^{W,pop}",
        r"\kappa^{W,coh}",
    },
    "ThermalConductivity[transport_model=qhgk]": {r"\kappa^{QHGK}"},
    "CumulativeKappa[wrt=omega]": {r"\kappa^{cum}_\omega", r"\omega_c"},
    "CumulativeKappa[wrt=mfp]": {r"\kappa^{cum}_\Lambda", r"\Lambda_c"},
    # MD primitives (phase 2 P2). Trajectory carries r and v (the field
    # declarations); the per-atom energy E and per-atom force F^{md} are
    # trajectory-derived auxiliary quantities (forces come from the same
    # Potential that drove the MD; per-atom energies are decomposable
    # from the same potential energy surface) — listed here so the
    # Irving-Kirkwood / Velocity-Verlet formulas can reference them.
    "Trajectory": {"r", "v", "E", r"F^{md}"},
    "HeatCurrent": {"J"},
    "HeatCurrentACF": {"Jcorr"},
    "VelocityAutocorrelation": {"Cv"},
    "MeanSquaredDisplacement": {"M"},
    # MD-based κ paths (phase 2 P3). All three Pattern-A `transport_model`
    # variants share the same κ^{MD} IndexedBase on their LHS so the
    # formulas read uniformly.
    "ThermalConductivity[transport_model=green_kubo]": {r"\kappa^{MD}"},
    "ThermalConductivity[transport_model=nemd]": {r"\kappa^{MD}"},
    "ThermalConductivity[transport_model=hnemd]": {r"\kappa^{MD}"},
    # Amorphous / localization diagnostics (kaldo delta scan, records 208-211).
    # ParticipationRatio carries its output field p and the per-atom amplitude
    # a_i = sum_cart |e|^2 the auxiliary formula introduces (the eigenvector e
    # itself rides in via the Eigenvectors input space). ModalDiffusivity
    # carries its output field D_{mode}; its formula's ω / e / Γ^{tot} arguments
    # ride in via the Frequency / Eigenvectors / Linewidth[channel=total] inputs.
    "ParticipationRatio": {"p", "a"},
    "ModalDiffusivity": {r"D_{mode}"},
})
