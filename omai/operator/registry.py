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
    "q": "qpoint",
    "nu": "branch",
    "R": "lattice_vector",
    "R'": "lattice_vector",
    "t": "timestep",
    "tau": "lag",
    "omega": "omega_bin",
    "omega_bin": "omega_bin",
    "mfp_bin": "mfp_bin",
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
    "activation_energy": "Arrhenius activation energy from the temperature dependence of diffusivity.",
    "cell_volume": "Volume of the primitive unit cell (promoted parameter).",
    "atomic_mass": "Per-atom masses (promoted parameter).",
    "atom_count": "Number of atoms in the cell (promoted parameter).",
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
}
