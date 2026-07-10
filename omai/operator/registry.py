"""Protocol registries: the controlled vocabularies that enter content hashes.

Kernel P2 makes a node's identity a content hash over its quantity tag, field
signatures (dimension + index-kind signature), gauge class, and labels; an
edge's identity adds the formula fingerprint and the schemes. Every *string*
that enters such a hash must be drawn from a controlled, versioned registry
rather than a free-form value, so that two contributors converge by mapping to
the same registered token and cross-domain identity is meaningful (a `qpoint`
means the same kind in every domain). This module holds the four registries:

  INDEX_KINDS   index NAME -> index KIND (atom, cartesian, qpoint, ...).
  QUANTITY_TAGS curated quantity tag -> one-line description.
  GAUGE_GROUPS  gauge-group identifier -> description (ascii, six in use).
  LABEL_KEYS    semantic label key -> frozenset of allowed values.

See docs/superpowers/specs/2026-07-06-map-kernel-design.md, "Resolved
decisions" #1 and #3.
"""
from __future__ import annotations

import re


# --------------------------------------------------------------------------
# Index kinds
# --------------------------------------------------------------------------
# Every index NAME used by any Field on the map maps to its KIND. Kinds carry
# the gauge / symmetry semantics the product assigns to indices; the tuple of
# kinds (not names) is what enters node identity, so a `q` in one domain and a
# `q` in another share identity iff they share the kind `qpoint`.
INDEX_KINDS: dict[str, str] = {
    "i": "atom",
    "j": "atom",
    "k": "atom",
    "alpha": "cartesian",
    "beta": "cartesian",
    # gamma, delta: the third and fourth Cartesian legs of the rank-4 elastic
    # stiffness tensor C_{alpha,beta,gamma,delta}. Same kind as alpha/beta.
    "gamma": "cartesian",
    "delta": "cartesian",
    "q": "qpoint",
    "nu": "branch",
    "R": "lattice_vector",
    "R'": "lattice_vector",
    "t": "timestep",
    "tau": "lag",
    "omega": "omega_bin",
    "omega_bin": "omega_bin",
    "mfp_bin": "mfp_bin",
    # CALPHAD (thermochemistry) axes. `c` is the species/component axis of the
    # chemical potentials (one MU per non-vacancy component); `p` is the phase
    # axis of the equilibrium assemblage (one NP per stable phase). New kinds:
    # neither the atom, cartesian, qpoint, nor branch axes carry the
    # component / phase semantics of a Gibbs-minimization output.
    "c": "component",
    "p": "phase",
    # The molecular normal-mode axis: the 3N-6 (or 3N-5) discrete vibrational
    # modes of a finite molecule, indexed by mode number. The map's FIRST
    # non-periodic frequency axis: a molecule has NO qpoint and NO phonon branch
    # (no Brillouin zone, only the gamma point), so the (q, nu) = (qpoint, branch)
    # signature of the periodic Frequency node does not fit. A distinct kind so a
    # molecular normal-mode index never aliases a phonon (q, nu) axis. Registered
    # for the ORCA / sella molecular vibrational frequencies; the MolecularFrequency
    # node that will carry it is deferred this slice (minting it means deciding the
    # imaginary-mode convention), so no field uses `m` yet.
    "m": "mode",
}


def index_kind_signature(indices: tuple[str, ...]) -> tuple[str, ...]:
    """Map a Field's index names to their registered kinds.

    Raises KeyError naming the offending index if a name is unregistered.
    """
    out = []
    for name in indices:
        try:
            out.append(INDEX_KINDS[name])
        except KeyError:
            raise KeyError(f"unregistered index name {name!r}") from None
    return tuple(out)


# --------------------------------------------------------------------------
# Quantity tags
# --------------------------------------------------------------------------
# The curated identifier that carries a quantity's semantic distinction. Pure
# type-content identity false-merges seven real pairs on today's map
# (Entropy=HeatCapacity, Potential=Structure, BareDM=DM, Gruneisen=PhaseSpace,
# and the free-energy / molar pairs); the tag is what keeps same-typed distinct
# quantities apart. Derived from a node's name by `quantity_tag_for`; every
# derived tag must be a registered key here, each with a real one-line
# description (written from the node descriptions in nodes.py).
QUANTITY_TAGS: dict[str, str] = {
    "potential": "Born-Oppenheimer potential of the material (opaque in Phase 1).",
    "structure": "Atomic structure: cell, species, and positions (opaque in Phase 1).",
    "total_energy": "DFT total energy of the converged Kohn-Sham ground state, per simulation cell.",
    "forces": "Per-atom Hellmann-Feynman forces on the nuclei in the ground state.",
    "stress": "Cell-averaged macroscopic stress tensor of the ground state (pressure convention).",
    "elastic_constants": "Rank-4 Cartesian elastic stiffness tensor C_{alpha,beta,gamma,delta}, the second strain derivative of the energy density (Voigt 6x6 is a representation packing).",
    "bulk_modulus": "Isotropic bulk modulus K, the Voigt average resistance to uniform (hydrostatic) compression from the elastic tensor.",
    "shear_modulus": "Isotropic shear modulus G, the Voigt average resistance to shape-changing (shear) deformation from the elastic tensor.",
    "youngs_modulus": "Isotropic Young's modulus E_Y = 9KG/(3K+G), the uniaxial stiffness contracted from the bulk and shear moduli.",
    "poisson_ratio": "Isotropic Poisson ratio nu = (3K-2G)/(2(3K+G)), the dimensionless transverse-contraction ratio from the bulk and shear moduli.",
    "formation_energy": "Formation energy per atom relative to elemental reference phases (intensive, eV/atom; distinct from the per-cell total energy).",
    "energy_above_hull": "Per-atom distance above the convex hull of formation energies; zero means thermodynamically stable.",
    "surface_energy": "Surface energy per unit area of a crystal facet, from the slab-bulk energy difference over twice the slab area.",
    "adsorption_energy": "Adsorption energy of an adsorbate on a surface, the adslab-minus-slab-minus-adsorbate energy difference per configuration (eV).",
    "voltage": "Average intercalation (open-circuit) voltage: the Nernst energy difference over the transferred charge.",
    "magnetic_moment": "Per-site magnetic moment of the spin-polarized ground state, in Bohr magnetons.",
    "band_gap": "Electronic band gap of the ground state, the Kohn-Sham eigenvalue gap (eV).",
    "pressure": "Mechanical pressure P = trace(stress)/3, positive under compression (the stress pressure convention).",
    "temperature": "Thermodynamic temperature at which the calculation is evaluated.",
    "force_constants": "Real-space interatomic force constants (harmonic or higher order).",
    "born_charges": "Per-atom Born effective-charge tensors driving the LO-TO splitting.",
    "dielectric_tensor": "Macroscopic electronic dielectric tensor at infinite frequency.",
    "bare_dynamical_matrix": "Analytic Bloch sum of the force constants, before any non-analytic correction.",
    "dynamical_matrix": "Dynamical matrix D(q) whose eigenvalues are the squared phonon frequencies.",
    "frequency": "Per-mode phonon angular frequencies omega_qnu.",
    "eigenvectors": "Per-mode eigenvectors of the dynamical matrix (phase / degenerate-subspace gauge).",
    "group_velocity": "Per-mode phonon group velocities from the dispersion gradient.",
    "heat_capacity": "Per-mode harmonic mode heat capacity c_qnu(T).",
    "volumetric_heat_capacity": "Total harmonic heat capacity per unit volume at temperature T.",
    "molar_heat_capacity": "Harmonic heat capacity per mole of primitive unit cells at temperature T.",
    "helmholtz_free_energy": "Per-mode Helmholtz free energy including the zero-point term.",
    "entropy": "Per-mode harmonic vibrational entropy s_qnu(T).",
    "internal_energy": "Per-mode internal energy (zero-point plus thermal occupation).",
    "molar_helmholtz_free_energy": "Helmholtz free energy per mole of primitive unit cells at temperature T.",
    "molar_entropy": "Vibrational entropy per mole of primitive unit cells at temperature T.",
    "molar_internal_energy": "Internal energy per mole of primitive unit cells at temperature T.",
    "linewidth": "Per-mode phonon linewidth Gamma_qnu for a given scattering channel.",
    "isotope_abundances": "Per-atom isotopic mass-variance factor g_i (Tamura model input).",
    "phonon_dos": "Phonon density of states g(omega) binned over frequency.",
    "gruneisen": "Mode Grueneisen parameters quantifying anharmonic volume dependence.",
    "phase_space3_phonon": "Three-phonon kinematic phase space available for scattering per mode.",
    "mean_free_displacement": "Per-mode mean free displacement F entering the BTE conductivity.",
    "thermal_conductivity": "Lattice thermal conductivity tensor kappa (BTE, Wigner, QHGK, or MD route).",
    "cumulative_kappa": "Cumulative thermal conductivity distributed over frequency or mean free path.",
    "trajectory": "Per-atom MD positions and velocities sampled at each timestep.",
    "heat_current": "Instantaneous MD heat-current vector J(t).",
    "heat_current_acf": "Time-correlation tensor of the MD heat current (Green-Kubo integrand).",
    "velocity_autocorrelation": "Atom-and-time-averaged velocity autocorrelation function.",
    "mean_squared_displacement": "Atom-and-time-averaged mean squared displacement (diffusion probe).",
    "diffusivity": "Self-diffusion coefficient from the Einstein relation.",
    "electrical_conductivity": "Electrical conductivity from a carrier flux; the ionic (Nernst-Einstein) carrier is a tracer-diffusivity conductivity, the electronic carrier the amset sibling (kept apart by the carrier label).",
    "configurational_energy": "Lattice-model (cluster-expansion) energy of a configuration on a fixed lattice; a fitted-Hamiltonian energy, distinct from a relaxed-structure DFT/MLIP total energy.",
    "reaction_energy": "Stoichiometric reaction energy of a balanced solid-state reaction, combined from the per-atom formation energies of reactants and products.",
    "activation_energy": "Arrhenius activation energy from the temperature dependence of diffusivity.",
    "cell_volume": "Volume of the primitive unit cell (promoted parameter).",
    "atomic_mass": "Per-atom masses (promoted parameter).",
    "atom_count": "Number of atoms in the cell (promoted parameter).",
    "assessed_database": "The CALPHAD TDB: the frozen human-assessed Gibbs-energy model set (lattice stabilities plus excess parameters); the thermochemistry input artifact, the CALPHAD analog of Potential.",
    "molar_gibbs_energy": "Assessed molar Gibbs energy of a phase or equilibrium assemblage, per mole of atoms at constant pressure, SER reference (distinct from the phonon-side per-cell Helmholtz molar node).",
    "molar_enthalpy": "Assessed molar enthalpy H_m = G - T dG/dT, per mole of atoms at constant pressure, SER reference.",
    "chemical_potential": "Equilibrium partial molar Gibbs energy per component: the common-tangent hyperplane of the Gibbs minimization.",
    "phase_fraction": "Equilibrium molar amount (fraction) of each stable phase in the assemblage (the lever rule), dimensionless.",
    "transition_temperature": "Computed phase-transition temperature (liquidus / solidus / solvus / invariant point), an equilibrium output distinct from the input Temperature.",
    "seebeck_coefficient": "Seebeck (thermopower) coefficient S from the ab-initio scattering transport tensor; V/K, sign carries the carrier type.",
    "electronic_thermal_conductivity": "Electronic contribution to the thermal conductivity kappa_e from carrier transport; W/(m K), the additive electronic partner of the lattice thermal_conductivity (kappa_total = lattice + electronic), kept apart by an own tag.",
    "carrier_mobility": "Charge-carrier mobility mu from the ab-initio scattering transport; m^2/(V s), computed for non-metals only.",
    "static_dielectric_tensor": "Static (zero-frequency) macroscopic dielectric tensor eps_0 = eps_inf + ionic contribution; distinct from the high-frequency electronic dielectric_tensor eps_inf.",
    "qha_gibbs_energy": "Quasi-harmonic Gibbs energy G(V,T) at constant pressure from the QHA F(V,T) surface minimized over volume plus pV, per mole of the phonopy cell (phonon-gas + EOS producer); distinct from the CALPHAD molar_gibbs_energy (per mole of atoms, assessed) and the constant-volume molar_helmholtz_free_energy.",
    "thermal_expansion": "Volumetric thermal expansion coefficient alpha(T) = (1/V)(dV/dT)_P from the temperature dependence of the QHA equilibrium volume; 1/K.",
    "heat_capacity_constant_p": "Constant-pressure molar heat capacity C_P(T) along the QHA equilibrium path, per mole of the phonopy cell; the constant-pressure partner of the harmonic constant-volume molar_heat_capacity (C_P - C_V = alpha^2 B V T).",
    "thermal_gruneisen": "Macroscopic (thermal) Gruneisen parameter gamma(T), a single scalar per temperature: the heat-capacity-weighted contraction of the mode gruneisen, distinct from the (q,nu)-indexed mode node.",
    "mass_density": "Mass density rho = total cell mass over cell volume, the LAMMPS metal-unit MD thermo output; g/cm^3.",
    "homolumo_gap": "Kohn-Sham HOMO-LUMO gap of a MOLECULE: the eV difference between the two discrete frontier molecular orbitals (highest occupied, lowest unoccupied) of a finite system with no bands; a cousin of the periodic band_gap (same ENERGY dimension, same KS-eigenvalue-gap family and caveats) but never equated (a molecule has no Brillouin zone, so no VBM/CBM). Tag derived from the node name HOMOLUMOGap (the HOMOLUMO acronym stays one token, exactly as PhononDOS -> phonon_dos).",
    "reaction_barrier": "Energy barrier of a reaction or migration: the peak-minus-reactant energy along a path (NEB minimum-energy path) or from a static saddle point (sella / ORCA transition state); one construction per label {neb_mep, static_ts_mlip, static_ts_dft}, cross-construction subtraction forbidden. Distinct from the Arrhenius activation_energy (a diffusivity-slope, not a PES barrier).",
    "bond_dissociation_energy": "Energy to cleave one chemical bond of a molecule: a difference of relaxed fragment total energies (homolytic radicals, or heterolytic charged fragments) on the per-molecule basis; a labeled sibling of the solid-state reaction_energy, kcal/mol native in the chemist's convention.",
}


def quantity_tag_for(name: str) -> str:
    """Derive a quantity tag from a node / parameter name.

    Rule: strip a trailing ``[...]`` label block, then convert CamelCase to
    snake_case. ``ThermalConductivity[bte_solver=rta] -> thermal_conductivity``,
    ``PhononDOS -> phonon_dos``, ``MeanSquaredDisplacement ->
    mean_squared_displacement``.
    """
    base = re.sub(r"\[.*\]$", "", name)
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", base)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def validate_quantity_tag(tag: str) -> str:
    """Return the tag if it is registered; raise KeyError otherwise."""
    if tag not in QUANTITY_TAGS:
        raise KeyError(f"unregistered quantity tag {tag!r}")
    return tag


# --------------------------------------------------------------------------
# Gauge groups
# --------------------------------------------------------------------------
# The named gauge equivalence acting on a HiddenSpace. Free-form strings (one
# with a unicode multiplication sign) are normalized into these six ascii
# identifiers before they enter any hash.
GAUGE_GROUPS: dict[str, str] = {
    "u1_phase_and_ud_degenerate_subspace": (
        "U(1) phase freedom per mode plus U(d) rotation within each degenerate "
        "eigenvector subspace."
    ),
    "ud_degenerate_subspace_on_eigenvectors": (
        "U(d) rotation freedom within degenerate eigenvector subspaces, "
        "inherited by quantities built from the eigenvectors."
    ),
    "bz_summation_permutation": (
        "Permutation gauge of the Brillouin-zone summation: weight redistributes "
        "between modes but the total is conserved."
    ),
    "bz_summation_permutation_via_1_over_gamma": (
        "BZ-summation permutation gauge propagated through the non-linear 1/Gamma "
        "weighting of the relaxation-time approximation."
    ),
    "bz_summation_permutation_via_lorentzian": (
        "BZ-summation permutation gauge propagated through Lorentzian mode "
        "broadening (QHGK)."
    ),
    "md_ensemble_noise": (
        "Stochastic MD ensemble noise: integrator, ensemble, thermostat, and "
        "initial-condition dependence of the realised trajectory."
    ),
}


# --------------------------------------------------------------------------
# Label keys and values
# --------------------------------------------------------------------------
# The semantic type parameters that carry the disambiguation work. Same-typed
# variants that must stay distinct (wigner_populations vs wigner_coherences;
# cumulative kappa wrt omega vs mfp) are distinct only by these labels, so the
# keys and values are part of the protocol. Values compare as strings (labels
# dicts may hold ints, e.g. order=2; callers normalize to str at hash time).
LABEL_KEYS: dict[str, frozenset[str]] = {
    "order": frozenset({"2", "3"}),
    "bte_solver": frozenset({"rta", "direct_inverse"}),
    "transport_model": frozenset(
        {"wigner", "wigner_populations", "wigner_coherences", "qhgk",
         "green_kubo", "nemd", "hnemd"}
    ),
    "channel": frozenset({"anharmonic_3ph", "isotope", "boundary", "total"}),
    "wrt": frozenset({"omega", "mfp"}),
    # The charge carrier of an electrical conductivity: ionic (Nernst-Einstein
    # from a tracer diffusivity, this contribution) vs electronic (the amset
    # sibling that joins the same ElectricalConductivity family). Same
    # electrical_conductivity tag and ELECTRICAL_CONDUCTIVITY dimension, kept
    # apart as distinct nodes only by this carrier label. Collision-free
    # against the other label keys (order, bte_solver, transport_model,
    # channel, wrt): no value or key overlaps.
    "carrier": frozenset({"ionic", "electronic"}),
    # The construction of a reaction barrier: neb_mep (a CI-NEB minimum-energy-path
    # barrier, chem-neb-barrier via ase.mep, eV, MLIP), static_ts_mlip (a static
    # saddle-point barrier from an MLIP transition state, chem-ts-optimization via
    # sella, eV), static_ts_dft (a static saddle from molecular DFT, chem-dft-orca,
    # Hartree->eV, all-electron zero). Same reaction_barrier tag and ENERGY
    # dimension, kept apart as distinct nodes ONLY by this construction label, so
    # the sella and ORCA routes join the ReactionBarrier family later WITHOUT a
    # re-mint (the carrier-label pattern). Cross-construction numeric comparison is
    # forbidden by the energy-zero split (MLIP eV vs all-electron Hartree->eV).
    # Collision-free against the other label keys (order, bte_solver,
    # transport_model, channel, wrt, carrier): no value or key overlaps.
    "construction": frozenset({"neb_mep", "static_ts_mlip", "static_ts_dft"}),
}
