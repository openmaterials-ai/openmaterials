"""Operator nodes of the lattice thermal-transport DAG.

Sixteen nodes, split into Observables (gauge-invariant, cross-code-comparable)
and HiddenStates (adapter-internal scaffolding, not cross-code-comparable
per-element). MeanFreeDisplacement and ThermalConductivity are parameterized
by the upstream `bte_solver` choice: the RTA variants are HiddenStates (the
approximation breaks gauge invariance), the direct-inverse / iterative
variants are Observables (the full LBTE solution preserves it).

  Observables (11):
    Potential, Temperature       — sources, scalar / opaque
    ForceConstants[order=2/3]    — real-space tensors, well-defined
    DynamicalMatrix              — Bloch sum, well-defined in standard basis
    Frequency                    — eigenvalues, basis-invariant
    HeatCapacity                 — per-mode c_qν(T), function of ω and T
    VolumetricHeatCapacity       — Σ_qν c_qν / (V_cell N_q), J/(m³K)
    MolarHeatCapacity            — N_A Σ_qν c_qν / N_q, J/(K·mol_of_cells)
    MeanFreeDisplacement[direct] — full LBTE solution; gauge-invariant
    ThermalConductivity[direct]  — contracted tensor; gauge-invariant

  HiddenStates (5):
    Eigenvectors                 — phase + degenerate-subspace rotation
    GroupVelocity                — inherits eigenvector rotation at degenerate ω
    Linewidth                    — BZ-summation redistribution
    MeanFreeDisplacement[rta]    — RTA closed form; inherits Linewidth's looseness
    ThermalConductivity[rta]     — RTA κ; inherits MFD[rta]'s looseness via 1/Γ
"""

from __future__ import annotations

from omai.operator.dimensions import (
    DIMENSIONLESS,
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    ENERGY_PER_LENGTH_SQUARED,
    ENERGY_PER_MOLE,
    ENERGY_PER_TEMPERATURE,
    ENERGY_PER_TEMPERATURE_PER_MOLE,
    ENERGY_PER_TEMPERATURE_PER_VOLUME,
    FREQUENCY,
    LENGTH,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.operator.physics_types import PhysicsType
from omai.operator.state import Field, HiddenState, Observable, State


# ---------------------------------------------------------------------------
# Observables (gauge-invariant; cross-code agreement required)
# ---------------------------------------------------------------------------

POTENTIAL = Observable(
    physics_type=PhysicsType.POTENTIAL,
    name="Potential",
    fields=(Field("potential", OPAQUE, indices=()),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = Observable(
    physics_type=PhysicsType.TEMPERATURE,
    name="Temperature",
    fields=(Field("temperature", TEMPERATURE, indices=()),),
)

FORCE_CONSTANTS_2 = Observable(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=2]",
    fields=(Field("phi", ENERGY_PER_LENGTH_SQUARED, indices=("i", "j", "R")),),
    type_parameters={"order": 2},
)

FORCE_CONSTANTS_3 = Observable(
    physics_type=PhysicsType.FORCE_CONSTANTS,
    name="ForceConstants[order=3]",
    fields=(Field("phi", ENERGY_PER_LENGTH_CUBED, indices=("i", "j", "k", "R", "R'")),),
    type_parameters={"order": 3},
    canonical_conventions={
        # Canonical: the natural ∂³V/∂u³ in eV/Å³ — the form kaldo and
        # phono3py store. ShengBTE's reader silently uses a mixed-dimension
        # form (see convention_factors below) that is numerically 10× smaller
        # for the same physical quantity; declare its convention value at
        # the ShengBTE adapter's spec to mechanise the cross-code factor.
        "fc3_normalization": "eV_per_A3",
    },
    convention_factors=(
        # ShengBTE's gruneisen.f90:44 documents the FC3-related unit chain
        # as "nm·eV/(amu·Å³·THz²)" — nm in the numerator and Å³ in the
        # denominator. Since 1 nm = 10 Å, 1 eV/Å³ = 10 eV/(Å²·nm), so the
        # value ShengBTE implicitly expects is 0.1× the canonical eV/Å³
        # value. processes.f90's comment claims "(eV/Å³)²·…" but the
        # numerical implementation follows gruneisen.f90; the empirical
        # cross-code agreement on Si-Tersoff (3×3×3 and 2×2×2 FC3
        # supercells) confirms the factor is exactly 0.1, independent of
        # supercell size.
        ("fc3_normalization", "eV_per_A2_per_nm", "phi", 0.1),
    ),
)

BORN_CHARGES = Observable(
    physics_type=PhysicsType.BORN_CHARGES,
    name="BornCharges",
    fields=(Field("Z_star", DIMENSIONLESS, indices=("i", "alpha", "beta")),),
    description=(
        "Per-atom Born effective-charge tensor Z*_{i,αβ}, in units of the "
        "elementary charge e. Source-tier Observable: read from a BORN file "
        "or DFT linear-response output. Together with the macroscopic "
        "DielectricTensor ε∞ it parameterises the non-analytic correction "
        "(LO-TO splitting) for polar materials."
    ),
)

DIELECTRIC_TENSOR = Observable(
    physics_type=PhysicsType.DIELECTRIC_TENSOR,
    name="DielectricTensor",
    fields=(Field("epsilon_infinity", DIMENSIONLESS, indices=("alpha", "beta")),),
    description=(
        "Macroscopic (electronic) dielectric tensor ε∞ at infinite "
        "frequency, dimensionless. Source-tier Observable. Enters the "
        "non-analytic correction to D(q) at q→0."
    ),
)

BARE_DYNAMICAL_MATRIX = Observable(
    physics_type=PhysicsType.BARE_DYNAMICAL_MATRIX,
    name="BareDynamicalMatrix",
    fields=(Field("D_bare", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "Analytic Bloch sum of Φ²(R) — the dynamical matrix before any "
        "non-analytic correction is applied. Always produced by "
        "compute_dynamical_matrix(FC2). For non-polar materials the "
        "downstream DynamicalMatrix is identical to this (via identity_dm); "
        "for polar materials apply_nac_correction adds the q→0 non-analytic "
        "term involving BornCharges and DielectricTensor."
    ),
)

DYNAMICAL_MATRIX = Observable(
    physics_type=PhysicsType.DYNAMICAL_MATRIX,
    name="DynamicalMatrix",
    fields=(Field("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Produced from BareDynamicalMatrix "
        "by either identity_dm (non-polar) or apply_nac_correction (polar). "
        "Entries are dimensionally frequency² (mass-weighted Hessian); codes "
        "typically store the matrix with eigenvalues that are ω², not ω."
    ),
)

FREQUENCY_STATE = Observable(
    physics_type=PhysicsType.FREQUENCY,
    name="Frequency",
    fields=(Field("omega", FREQUENCY, indices=("q", "nu")),),
)

HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.HEAT_CAPACITY,
    name="HeatCapacity",
    fields=(Field("c", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
)

VOLUMETRIC_HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.VOLUMETRIC_HEAT_CAPACITY,
    name="VolumetricHeatCapacity",
    fields=(Field("C_V_vol", ENERGY_PER_TEMPERATURE_PER_VOLUME, indices=()),),
    description=(
        "Total heat capacity per unit volume at temperature T, "
        "C_V/V = (1/V_cell N_q) Σ_qν c_qν(T). Scalar in (q, ν); a function "
        "of T only. ShengBTE emits this directly as BTE.cv; codes that "
        "emit per-mode HeatCapacity reach it via the contraction edge."
    ),
)

MOLAR_HEAT_CAPACITY = Observable(
    physics_type=PhysicsType.MOLAR_HEAT_CAPACITY,
    name="MolarHeatCapacity",
    fields=(Field("C_V_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, indices=()),),
    description=(
        "Heat capacity per mole of primitive unit cells at temperature T, "
        "C_V_mol = (N_A / N_q) Σ_qν c_qν(T). Phonopy emits this as part "
        "of its harmonic thermal_properties output (J/K/mol). Codes that "
        "emit per-mode HeatCapacity reach it via the contraction edge."
    ),
)


# Per-mode harmonic thermodynamics (parallel to HeatCapacity). No code emits
# these directly today; phonopy / phono3py compute them internally and
# contract before exposing. The per-mode states are still declared at the
# operator layer to keep the DAG honest and to give the contracted molar
# variants a well-defined source.

HELMHOLTZ_FREE_ENERGY = Observable(
    physics_type=PhysicsType.HELMHOLTZ_FREE_ENERGY,
    name="HelmholtzFreeEnergy",
    fields=(Field("f", ENERGY, indices=("q", "nu")),),
    description=(
        "Per-mode Helmholtz free energy f_qν(T) = (ℏω/2) + "
        "k_B T ln(1 - exp(-ℏω/k_B T)). The 1/2 is the zero-point part; "
        "the log term carries the temperature dependence."
    ),
)

ENTROPY = Observable(
    physics_type=PhysicsType.ENTROPY,
    name="Entropy",
    fields=(Field("s", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
    description=(
        "Per-mode entropy s_qν(T) = (1/T)·ℏω·n_BE(ω,T) - "
        "k_B ln(1 - exp(-ℏω/k_B T)). Equivalently -∂f/∂T."
    ),
)

INTERNAL_ENERGY = Observable(
    physics_type=PhysicsType.INTERNAL_ENERGY,
    name="InternalEnergy",
    fields=(Field("e", ENERGY, indices=("q", "nu")),),
    description=(
        "Per-mode internal energy e_qν(T) = ℏω(1/2 + n_BE(ω/T)). "
        "Sums the zero-point energy and the thermal occupation."
    ),
)


# Contracted per-mole-of-primitive-cells variants. Phonopy's harmonic
# thermal_properties output exposes these directly.

MOLAR_HELMHOLTZ_FREE_ENERGY = Observable(
    physics_type=PhysicsType.MOLAR_HELMHOLTZ_FREE_ENERGY,
    name="MolarHelmholtzFreeEnergy",
    fields=(Field("F_mol", ENERGY_PER_MOLE, indices=()),),
    description=(
        "Helmholtz free energy per mole of primitive unit cells at "
        "temperature T, F_mol = (N_A / N_q) Σ_qν f_qν(T). Phonopy emits "
        "this as part of its thermal_properties output (kJ/mol)."
    ),
)

MOLAR_ENTROPY = Observable(
    physics_type=PhysicsType.MOLAR_ENTROPY,
    name="MolarEntropy",
    fields=(Field("S_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, indices=()),),
    description=(
        "Entropy per mole of primitive unit cells at temperature T, "
        "S_mol = (N_A / N_q) Σ_qν s_qν(T). Phonopy emits this as "
        "thermal_properties['entropy'] in J/(K·mol)."
    ),
)

MOLAR_INTERNAL_ENERGY = Observable(
    physics_type=PhysicsType.MOLAR_INTERNAL_ENERGY,
    name="MolarInternalEnergy",
    fields=(Field("E_mol", ENERGY_PER_MOLE, indices=()),),
    description=(
        "Internal energy per mole of primitive unit cells at temperature T, "
        "E_mol = (N_A / N_q) Σ_qν e_qν(T). Phonopy emits this as "
        "thermal_properties['internal_energy'] in kJ/mol."
    ),
)

THERMAL_CONDUCTIVITY_DIRECT = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[bte_solver=direct_inverse]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"bte_solver": "direct_inverse"},
    description=(
        "Lattice thermal conductivity from the direct/iterative LBTE solver. "
        "Gauge-invariant: the collision matrix's off-diagonals preserve "
        "invariance under per-mode Γ redistribution."
    ),
)

MEAN_FREE_DISPLACEMENT_DIRECT = Observable(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement[bte_solver=direct_inverse]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    type_parameters={"bte_solver": "direct_inverse"},
    description=(
        "F obtained from the full linearized BTE (direct inversion or "
        "iterative solution). Gauge-invariant by construction."
    ),
)


# ---------------------------------------------------------------------------
# HiddenStates (gauge-dependent; not cross-code comparable per-element)
# ---------------------------------------------------------------------------

EIGENVECTORS = HiddenState(
    physics_type=PhysicsType.EIGENVECTORS,
    name="Eigenvectors",
    fields=(Field("e", DIMENSIONLESS, indices=("i", "q", "nu")),),
    gauge_group="U(1)_per_mode × U(d)_per_degenerate_subspace",
    kind="scaffolding",
    gauge_invariant_contractions=("Frequency", "ThermalConductivity[bte_solver=direct_inverse]"),
    description=(
        "Per-mode eigenvectors of the dynamical matrix. U(1) phase freedom "
        "per mode plus U(d) rotation within each degenerate subspace; "
        "per-element values are not directly comparable across adapters. "
        "Contracted gauge-invariants live in Frequency (eigenvalues) and κ_LBTE."
    ),
)

GROUP_VELOCITY = HiddenState(
    physics_type=PhysicsType.GROUP_VELOCITY,
    name="GroupVelocity",
    fields=(Field("v", LENGTH_TIMES_FREQUENCY, indices=("alpha", "q", "nu")),),
    gauge_group="U(d)_per_degenerate_subspace_on_eigenvectors",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode group velocity. Per-mode v is invariant under U(1) phase, "
        "but inherits the U(d) rotation freedom at degenerate ω. Contracted "
        "gauge-invariants live in κ (Σ c v² τ over the BZ)."
    ),
)

ANHARMONIC_LINEWIDTH = HiddenState(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth[channel=anharmonic_3ph]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    type_parameters={"channel": "anharmonic_3ph"},
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode three-phonon anharmonic linewidth from Fermi's golden "
        "rule (the channel the existing compute_linewidth produces). "
        "Per-element values depend on BZ-summation choice (a permutation "
        "gauge: weights redistribute between modes but conserve the total). "
        "Contractions (ΣΓ, κ_LBTE) are the gauge-invariant content."
    ),
)

# Backwards-compatible alias. `LINEWIDTH` is what the codebase referenced
# before the per-channel split; it now points to the anharmonic channel
# (semantically: the existing compute_linewidth was always the anharmonic
# 3-phonon piece). Use the explicit ANHARMONIC_LINEWIDTH in new code.
LINEWIDTH = ANHARMONIC_LINEWIDTH


ISOTOPIC_LINEWIDTH = HiddenState(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth[channel=isotope]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    type_parameters={"channel": "isotope"},
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode isotopic scattering rate from the Tamura model: "
        "Γ_iso(qν) = (π/2) ω² Σ_i g_i |e_iqν|² δ(ω - ω'). Per-element "
        "is gauge-dependent (depends on eigenvector basis at degenerate ω); "
        "the BZ-summed total is the cross-code observable."
    ),
)


BOUNDARY_LINEWIDTH = HiddenState(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth[channel=boundary]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    type_parameters={"channel": "boundary"},
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode boundary scattering rate from the Casimir / Matthiessen "
        "form: Γ_boundary(qν) = |v_qν| / L where L is the boundary length "
        "scale (operation parameter). Gauge-dependent inherits "
        "GroupVelocity's basis dependence at degenerate ω."
    ),
)


TOTAL_LINEWIDTH = HiddenState(
    physics_type=PhysicsType.LINEWIDTH,
    name="Linewidth[channel=total]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    type_parameters={"channel": "total"},
    canonical_conventions={
        "gamma_definition": "imag_self_energy",
    },
    convention_factors=(
        ("gamma_definition", "linewidth_2x_imag_self_energy", "Gamma", 2.0),
    ),
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Sum of all enabled scattering channels (anharmonic + isotope + "
        "boundary + ...). The BTE solver consumes this — Matthiessen's "
        "rule applies under the linearized BTE. Channels a given run does "
        "not model contribute zero."
    ),
)


ISOTOPE_ABUNDANCES = Observable(
    physics_type=PhysicsType.ISOTOPE_ABUNDANCES,
    name="IsotopeAbundances",
    fields=(Field("g", DIMENSIONLESS, indices=("i",)),),
    description=(
        "Per-atom isotopic mass-variance factor g_i = Σ_x f_{ix} "
        "(1 - m_{ix}/m̄_i)² where x runs over isotopes of atomic species i, "
        "f_{ix} is the abundance fraction, m_{ix} is the isotope mass, and "
        "m̄_i is the abundance-weighted average mass. Dimensionless. "
        "Source-tier Observable: either natural-abundance defaults or "
        "user-provided per-species values."
    ),
)

PHONON_DOS = Observable(
    physics_type=PhysicsType.PHONON_DOS,
    name="PhononDOS",
    fields=(Field("g", FREQUENCY, indices=("omega",)),),
    description=(
        "Density of states g(ω) = (1/N_q) Σ_qν δ(ω − ω_qν). A 1-D array "
        "binned in ω. Gauge-invariant: ω_qν are basis-independent and the "
        "sum over (q, ν) is uniformly weighted."
    ),
)

GRUNEISEN = Observable(
    physics_type=PhysicsType.GRUNEISEN,
    name="Gruneisen",
    fields=(Field("gamma_G", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Mode Grüneisen parameter γ_qν = −(V/ω_qν) ∂ω_qν/∂V. Quantifies "
        "anharmonicity-driven volume dependence; computed from FC2 and FC3 "
        "via the standard Maradudin-Fein expression. Dimensionless."
    ),
)

PHASE_SPACE_3PH = Observable(
    physics_type=PhysicsType.PHASE_SPACE_3PH,
    name="PhaseSpace3Phonon",
    fields=(Field("P3", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Three-phonon phase space P3_qν = (1/N) Σ_q'ν'ν'' [δ(ω−ω'−ω'') + "
        "2 δ(ω+ω'−ω'')] available for scattering channels involving mode "
        "(q, ν). Doesn't include |V₃|² — purely the kinematic volume."
    ),
)

MEAN_FREE_DISPLACEMENT_RTA = HiddenState(
    physics_type=PhysicsType.MEAN_FREE_DISPLACEMENT,
    name="MeanFreeDisplacement[bte_solver=rta]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    type_parameters={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),  # terminal — no Observable downstream
    description=(
        "F = v / (2Γ) under the relaxation-time approximation. The 1/Γ "
        "non-linearity is the gauge-breaking step. Approximation HiddenState: "
        "terminal; there is no downstream operation that contracts it into "
        "a gauge-invariant Observable. The LBTE branch (MFD[direct_inverse]) "
        "is the gauge-invariant analogue."
    ),
)

THERMAL_CONDUCTIVITY_RTA = HiddenState(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[bte_solver=rta]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),
    description=(
        "Lattice thermal conductivity from the RTA. The 1/Γ weighting is "
        "non-linear in Γ, so RTA κ inherits Linewidth's gauge-dependence "
        "(unlike the LBTE solution, which preserves gauge-invariance via "
        "off-diagonal collision terms). Terminal approximation HiddenState."
    ),
)


# Wigner and QHGK transport models. Both are terminal κ nodes parameterised
# by `transport_model` (Pattern A). The existing LBTE branch is implicitly
# transport_model=lbte; only the new branches carry the parameter in their
# state names. Wigner decomposes into populations + coherences sub-results
# that combine into the total — each carried as its own sibling state so
# that codes which emit one or the other independently can spec them.

THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[transport_model=wigner_populations]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"transport_model": "wigner_populations"},
    description=(
        "Particle-like (populations) channel of the Wigner κ decomposition "
        "(Simoncelli et al., Nat. Phys. 2019). Numerically close to "
        "κ_LBTE; isolates the diagonal-in-band part of the heat-flux "
        "correlation."
    ),
)

THERMAL_CONDUCTIVITY_WIGNER_COHERENCES = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[transport_model=wigner_coherences]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"transport_model": "wigner_coherences"},
    description=(
        "Wave-like (coherences) channel of the Wigner κ decomposition. "
        "Couples bands at the same q through a Lorentzian-weighted "
        "mode-overlap term; dominates κ in glasses and complex crystals "
        "where mode spacings approach Γ."
    ),
)

THERMAL_CONDUCTIVITY_WIGNER = Observable(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[transport_model=wigner]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"transport_model": "wigner"},
    description=(
        "Unified Wigner κ = κ_populations + κ_coherences. The full "
        "expression interpolates between LBTE (when mode spacings ≫ Γ, "
        "coherences → 0) and a glass-like wave-transport regime "
        "(spacings ≲ Γ). Gauge-invariant Observable."
    ),
)

CUMULATIVE_KAPPA_OMEGA = Observable(
    physics_type=PhysicsType.CUMULATIVE_THERMAL_CONDUCTIVITY,
    name="CumulativeKappa[wrt=omega]",
    fields=(Field("kappa_cum", THERMAL_CONDUCTIVITY, indices=("alpha", "beta", "omega_bin")),),
    type_parameters={"wrt": "omega"},
    description=(
        "Cumulative thermal conductivity vs frequency: κ_cum(ω_c) "
        "= (1/(V N_q)) Σ_{ω_qν ≤ ω_c} c_qν v^α_qν F^β_qν. The distribution "
        "of κ over the phonon-frequency axis; saturates at κ_LBTE for "
        "ω_c → ∞."
    ),
)


CUMULATIVE_KAPPA_MFP = Observable(
    physics_type=PhysicsType.CUMULATIVE_THERMAL_CONDUCTIVITY,
    name="CumulativeKappa[wrt=mfp]",
    fields=(Field("kappa_cum", THERMAL_CONDUCTIVITY, indices=("alpha", "beta", "mfp_bin")),),
    type_parameters={"wrt": "mfp"},
    description=(
        "Cumulative thermal conductivity vs mean free path: κ_cum(Λ_c) "
        "= (1/(V N_q)) Σ_{|F_qν| ≤ Λ_c} c_qν v^α_qν F^β_qν. Heavily used "
        "for nanoscale design — the Λ at which κ_cum is 50% of κ_total "
        "is the median mean free path."
    ),
)


THERMAL_CONDUCTIVITY_QHGK = HiddenState(
    physics_type=PhysicsType.THERMAL_CONDUCTIVITY,
    name="ThermalConductivity[transport_model=qhgk]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    type_parameters={"transport_model": "qhgk"},
    gauge_group="bz_summation_permutation_via_lorentzian",
    kind="approximation",
    gauge_invariant_contractions=(),
    description=(
        "Quasi-harmonic Green-Kubo κ: time-integrated heat-flux "
        "autocorrelation with Lorentzian mode broadening of width Γ. The "
        "Lorentzian-coupled mode overlap inherits Linewidth's "
        "gauge-dependence on the off-diagonal pairings, so per-element "
        "κ_QHGK is treated as a HiddenState until a definitive analysis "
        "of its gauge structure says otherwise. Used primarily for "
        "amorphous systems where the BTE picture breaks down."
    ),
)


NODES: tuple[State, ...] = (
    POTENTIAL,
    TEMPERATURE_STATE,
    FORCE_CONSTANTS_2,
    FORCE_CONSTANTS_3,
    BORN_CHARGES,
    DIELECTRIC_TENSOR,
    BARE_DYNAMICAL_MATRIX,
    DYNAMICAL_MATRIX,
    FREQUENCY_STATE,

    EIGENVECTORS,
    GROUP_VELOCITY,
    HEAT_CAPACITY,
    VOLUMETRIC_HEAT_CAPACITY,
    MOLAR_HEAT_CAPACITY,
    HELMHOLTZ_FREE_ENERGY,
    ENTROPY,
    INTERNAL_ENERGY,
    MOLAR_HELMHOLTZ_FREE_ENERGY,
    MOLAR_ENTROPY,
    MOLAR_INTERNAL_ENERGY,
    ANHARMONIC_LINEWIDTH,
    ISOTOPIC_LINEWIDTH,
    BOUNDARY_LINEWIDTH,
    TOTAL_LINEWIDTH,
    ISOTOPE_ABUNDANCES,
    PHONON_DOS,
    GRUNEISEN,
    PHASE_SPACE_3PH,
    MEAN_FREE_DISPLACEMENT_RTA,
    MEAN_FREE_DISPLACEMENT_DIRECT,
    THERMAL_CONDUCTIVITY_RTA,
    THERMAL_CONDUCTIVITY_DIRECT,
    THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS,
    THERMAL_CONDUCTIVITY_WIGNER_COHERENCES,
    THERMAL_CONDUCTIVITY_WIGNER,
    THERMAL_CONDUCTIVITY_QHGK,
    CUMULATIVE_KAPPA_OMEGA,
    CUMULATIVE_KAPPA_MFP,
)
