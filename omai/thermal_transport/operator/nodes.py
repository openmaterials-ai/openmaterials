"""Operator nodes of the lattice thermal-transport DAG.

Split into ObservableSpaces (gauge-invariant, cross-code-comparable) and
HiddenSpaces (gauge-dependent; scaffolding or terminal approximations, not
cross-code-comparable per-element), assembled into the module-level NODES
tuple. The DAG covers the harmonic chain (force constants → dynamical
matrix → frequencies / eigenvectors / group velocities), per-mode
thermodynamics and their volumetric / molar contractions, the polar (NAC)
branch, the anharmonic / isotope / boundary scattering channels, the BTE
solvers, the Wigner and QHGK transport models, cumulative-κ distributions,
and an MD tier (trajectory, heat current, correlation functions) feeding
the Green-Kubo / NEMD / HNEMD κ paths.

Gauge policy in brief: a quantity whose per-element values depend on
eigenvector phase / degenerate-subspace rotation, BZ-summation choice, or
MD ensemble noise is a HiddenSpace declaring its gauge_group and — when it
is scaffolding — the ObservableSpace contractions that capture its
invariant content. MeanFreeDisplacement and ThermalConductivity are
parameterized by the upstream `bte_solver` choice: the RTA variants (like
κ_QHGK) are terminal `approximation` HiddenSpaces because the 1/Γ
non-linearity breaks gauge invariance, while the direct-inverse /
iterative LBTE variants and the MD κ observables are gauge-invariant
ObservableSpaces.
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
    ENERGY_TIMES_LENGTH_PER_TIME,
    FREQUENCY,
    LENGTH,
    LENGTH_PER_TIME,
    LENGTH_SQUARED,
    LENGTH_TIMES_FREQUENCY,
    OPAQUE,
    TEMPERATURE,
    THERMAL_CONDUCTIVITY,
)
from omai.operator.space import Field, HiddenSpace, ObservableSpace, Space


# ---------------------------------------------------------------------------
# ObservableSpaces (gauge-invariant; cross-code agreement required)
# ---------------------------------------------------------------------------

POTENTIAL = ObservableSpace(
    name="Potential",
    fields=(Field("potential", OPAQUE, indices=()),),
    description="Born-Oppenheimer potential of the material; in Phase 1 an opaque label.",
)

TEMPERATURE_STATE = ObservableSpace(
    name="Temperature",
    fields=(Field("temperature", TEMPERATURE, indices=()),),
)

FORCE_CONSTANTS_2 = ObservableSpace(
    name="ForceConstants[order=2]",
    fields=(Field("phi", ENERGY_PER_LENGTH_SQUARED, indices=("i", "j", "R")),),
    labels={"order": 2},
)

FORCE_CONSTANTS_3 = ObservableSpace(
    name="ForceConstants[order=3]",
    fields=(Field("phi", ENERGY_PER_LENGTH_CUBED, indices=("i", "j", "k", "R", "R'")),),
    labels={"order": 3},
)

BORN_CHARGES = ObservableSpace(
    name="BornCharges",
    fields=(Field("Z_star", DIMENSIONLESS, indices=("i", "alpha", "beta")),),
    description=(
        "Per-atom Born effective-charge tensor Z*_{i,αβ}, in units of the "
        "elementary charge e. Source-tier ObservableSpace: read from a BORN "
        "file or DFT linear-response output. Together with the macroscopic "
        "DielectricTensor ε∞ it parameterises the non-analytic correction "
        "(LO-TO splitting) for polar materials."
    ),
)

DIELECTRIC_TENSOR = ObservableSpace(
    name="DielectricTensor",
    fields=(Field("epsilon_infinity", DIMENSIONLESS, indices=("alpha", "beta")),),
    description=(
        "Macroscopic (electronic) dielectric tensor ε∞ at infinite "
        "frequency, dimensionless. Source-tier ObservableSpace. Enters the "
        "non-analytic correction to D(q) at q→0."
    ),
)

BARE_DYNAMICAL_MATRIX = ObservableSpace(
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

DYNAMICAL_MATRIX = ObservableSpace(
    name="DynamicalMatrix",
    fields=(Field("D", FREQUENCY, indices=("i", "j", "q")),),
    description=(
        "D(q) such that D e_qν = ω²_qν e_qν. Produced from BareDynamicalMatrix "
        "by either identity_dm (non-polar) or apply_nac_correction (polar). "
        "Entries are dimensionally frequency² (mass-weighted Hessian); codes "
        "typically store the matrix with eigenvalues that are ω², not ω."
    ),
)

FREQUENCY_STATE = ObservableSpace(
    name="Frequency",
    fields=(Field("omega", FREQUENCY, indices=("q", "nu")),),
)

HEAT_CAPACITY = ObservableSpace(
    name="HeatCapacity",
    fields=(Field("c", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
)

VOLUMETRIC_HEAT_CAPACITY = ObservableSpace(
    name="VolumetricHeatCapacity",
    fields=(Field("C_V_vol", ENERGY_PER_TEMPERATURE_PER_VOLUME, indices=()),),
    description=(
        "Total heat capacity per unit volume at temperature T, "
        "C_V/V = (1/V_cell N_q) Σ_qν c_qν(T). Scalar in (q, ν); a function "
        "of T only. ShengBTE emits this directly as BTE.cv; codes that "
        "emit per-mode HeatCapacity reach it via the contraction edge."
    ),
)

MOLAR_HEAT_CAPACITY = ObservableSpace(
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
# contract before exposing. The per-mode spaces are still declared at the
# operator layer to keep the DAG honest and to give the contracted molar
# variants a well-defined source.

HELMHOLTZ_FREE_ENERGY = ObservableSpace(
    name="HelmholtzFreeEnergy",
    fields=(Field("f", ENERGY, indices=("q", "nu")),),
    description=(
        "Per-mode Helmholtz free energy f_qν(T) = (ℏω/2) + "
        "k_B T ln(1 - exp(-ℏω/k_B T)). The 1/2 is the zero-point part; "
        "the log term carries the temperature dependence."
    ),
)

ENTROPY = ObservableSpace(
    name="Entropy",
    fields=(Field("s", ENERGY_PER_TEMPERATURE, indices=("q", "nu")),),
    description=(
        "Per-mode entropy s_qν(T) = (1/T)·ℏω·n_BE(ω,T) - "
        "k_B ln(1 - exp(-ℏω/k_B T)). Equivalently -∂f/∂T."
    ),
)

INTERNAL_ENERGY = ObservableSpace(
    name="InternalEnergy",
    fields=(Field("e", ENERGY, indices=("q", "nu")),),
    description=(
        "Per-mode internal energy e_qν(T) = ℏω(1/2 + n_BE(ω/T)). "
        "Sums the zero-point energy and the thermal occupation."
    ),
)


# Contracted per-mole-of-primitive-cells variants. Phonopy's harmonic
# thermal_properties output exposes these directly.

MOLAR_HELMHOLTZ_FREE_ENERGY = ObservableSpace(
    name="MolarHelmholtzFreeEnergy",
    fields=(Field("F_mol", ENERGY_PER_MOLE, indices=()),),
    description=(
        "Helmholtz free energy per mole of primitive unit cells at "
        "temperature T, F_mol = (N_A / N_q) Σ_qν f_qν(T). Phonopy emits "
        "this as part of its thermal_properties output (kJ/mol)."
    ),
)

MOLAR_ENTROPY = ObservableSpace(
    name="MolarEntropy",
    fields=(Field("S_mol", ENERGY_PER_TEMPERATURE_PER_MOLE, indices=()),),
    description=(
        "Entropy per mole of primitive unit cells at temperature T, "
        "S_mol = (N_A / N_q) Σ_qν s_qν(T). Phonopy emits this as "
        "thermal_properties['entropy'] in J/(K·mol)."
    ),
)

MOLAR_INTERNAL_ENERGY = ObservableSpace(
    name="MolarInternalEnergy",
    fields=(Field("E_mol", ENERGY_PER_MOLE, indices=()),),
    description=(
        "Internal energy per mole of primitive unit cells at temperature T, "
        "E_mol = (N_A / N_q) Σ_qν e_qν(T). Phonopy emits this as "
        "thermal_properties['internal_energy'] in kJ/mol."
    ),
)

THERMAL_CONDUCTIVITY_DIRECT = ObservableSpace(
    name="ThermalConductivity[bte_solver=direct_inverse]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"bte_solver": "direct_inverse"},
    description=(
        "Lattice thermal conductivity from the direct/iterative LBTE solver. "
        "Gauge-invariant: the collision matrix's off-diagonals preserve "
        "invariance under per-mode Γ redistribution."
    ),
)

MEAN_FREE_DISPLACEMENT_DIRECT = ObservableSpace(
    name="MeanFreeDisplacement[bte_solver=direct_inverse]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    labels={"bte_solver": "direct_inverse"},
    description=(
        "F obtained from the full linearized BTE (direct inversion or "
        "iterative solution). Gauge-invariant by construction."
    ),
)


# ---------------------------------------------------------------------------
# HiddenSpaces (gauge-dependent; not cross-code comparable per-element)
# ---------------------------------------------------------------------------

EIGENVECTORS = HiddenSpace(
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

GROUP_VELOCITY = HiddenSpace(
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

ANHARMONIC_LINEWIDTH = HiddenSpace(
    name="Linewidth[channel=anharmonic_3ph]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    labels={"channel": "anharmonic_3ph"},
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

ISOTOPIC_LINEWIDTH = HiddenSpace(
    name="Linewidth[channel=isotope]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    labels={"channel": "isotope"},
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


BOUNDARY_LINEWIDTH = HiddenSpace(
    name="Linewidth[channel=boundary]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    labels={"channel": "boundary"},
    gauge_group="bz_summation_permutation",
    kind="scaffolding",
    gauge_invariant_contractions=("ThermalConductivity[bte_solver=direct_inverse]",),
    description=(
        "Per-mode boundary scattering rate from the Casimir / Matthiessen "
        "form: Γ_boundary(qν) = |v_qν| / L where L is the boundary length "
        "scale (operator parameter). Gauge-dependent inherits "
        "GroupVelocity's basis dependence at degenerate ω."
    ),
)


TOTAL_LINEWIDTH = HiddenSpace(
    name="Linewidth[channel=total]",
    fields=(Field("Gamma", FREQUENCY, indices=("q", "nu")),),
    labels={"channel": "total"},
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


ISOTOPE_ABUNDANCES = ObservableSpace(
    name="IsotopeAbundances",
    fields=(Field("g", DIMENSIONLESS, indices=("i",)),),
    description=(
        "Per-atom isotopic mass-variance factor g_i = Σ_x f_{ix} "
        "(1 - m_{ix}/m̄_i)² where x runs over isotopes of atomic species i, "
        "f_{ix} is the abundance fraction, m_{ix} is the isotope mass, and "
        "m̄_i is the abundance-weighted average mass. Dimensionless. "
        "Source-tier ObservableSpace: either natural-abundance defaults or "
        "user-provided per-species values."
    ),
)

PHONON_DOS = ObservableSpace(
    name="PhononDOS",
    fields=(Field("g", FREQUENCY, indices=("omega",)),),
    description=(
        "Density of states g(ω) = (1/N_q) Σ_qν δ(ω − ω_qν). A 1-D array "
        "binned in ω. Gauge-invariant: ω_qν are basis-independent and the "
        "sum over (q, ν) is uniformly weighted."
    ),
)

GRUNEISEN = ObservableSpace(
    name="Gruneisen",
    fields=(Field("gamma_G", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Mode Grüneisen parameter γ_qν = −(V/ω_qν) ∂ω_qν/∂V. Quantifies "
        "anharmonicity-driven volume dependence; computed from FC2 and FC3 "
        "via the standard Maradudin-Fein expression. Dimensionless."
    ),
)

PHASE_SPACE_3PH = ObservableSpace(
    name="PhaseSpace3Phonon",
    fields=(Field("P3", DIMENSIONLESS, indices=("q", "nu")),),
    description=(
        "Three-phonon phase space P3_qν = (1/N) Σ_q'ν'ν'' [δ(ω−ω'−ω'') + "
        "2 δ(ω+ω'−ω'')] available for scattering channels involving mode "
        "(q, ν). Doesn't include |V₃|² — purely the kinematic volume."
    ),
)

MEAN_FREE_DISPLACEMENT_RTA = HiddenSpace(
    name="MeanFreeDisplacement[bte_solver=rta]",
    fields=(Field("F", LENGTH, indices=("alpha", "q", "nu")),),
    labels={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),  # terminal — no ObservableSpace downstream
    description=(
        "F = v / (2Γ) under the relaxation-time approximation. The 1/Γ "
        "non-linearity is the gauge-breaking step. Approximation HiddenSpace: "
        "terminal; there is no downstream operator that contracts it into "
        "a gauge-invariant ObservableSpace. The LBTE branch (MFD[direct_inverse]) "
        "is the gauge-invariant analogue."
    ),
)

THERMAL_CONDUCTIVITY_RTA = HiddenSpace(
    name="ThermalConductivity[bte_solver=rta]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"bte_solver": "rta"},
    gauge_group="bz_summation_permutation_via_1_over_Gamma",
    kind="approximation",
    gauge_invariant_contractions=(),
    description=(
        "Lattice thermal conductivity from the RTA. The 1/Γ weighting is "
        "non-linear in Γ, so RTA κ inherits Linewidth's gauge-dependence "
        "(unlike the LBTE solution, which preserves gauge-invariance via "
        "off-diagonal collision terms). Terminal approximation HiddenSpace."
    ),
)


# Wigner and QHGK transport models. Both are terminal κ nodes parameterised
# by `transport_model` (Pattern A). The existing LBTE branch is implicitly
# transport_model=lbte; only the new branches carry the parameter in their
# space names. Wigner decomposes into populations + coherences sub-results
# that combine into the total — each carried as its own sibling space so
# that codes which emit one or the other independently can spec them.

THERMAL_CONDUCTIVITY_WIGNER_POPULATIONS = ObservableSpace(
    name="ThermalConductivity[transport_model=wigner_populations]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "wigner_populations"},
    description=(
        "Particle-like (populations) channel of the Wigner κ decomposition "
        "(Simoncelli et al., Nat. Phys. 2019). Numerically close to "
        "κ_LBTE; isolates the diagonal-in-band part of the heat-flux "
        "correlation."
    ),
)

THERMAL_CONDUCTIVITY_WIGNER_COHERENCES = ObservableSpace(
    name="ThermalConductivity[transport_model=wigner_coherences]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "wigner_coherences"},
    description=(
        "Wave-like (coherences) channel of the Wigner κ decomposition. "
        "Couples bands at the same q through a Lorentzian-weighted "
        "mode-overlap term; dominates κ in glasses and complex crystals "
        "where mode spacings approach Γ."
    ),
)

THERMAL_CONDUCTIVITY_WIGNER = ObservableSpace(
    name="ThermalConductivity[transport_model=wigner]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "wigner"},
    description=(
        "Unified Wigner κ = κ_populations + κ_coherences. The full "
        "expression interpolates between LBTE (when mode spacings ≫ Γ, "
        "coherences → 0) and a glass-like wave-transport regime "
        "(spacings ≲ Γ). Gauge-invariant ObservableSpace."
    ),
)

CUMULATIVE_KAPPA_OMEGA = ObservableSpace(
    name="CumulativeKappa[wrt=omega]",
    fields=(Field("kappa_cum", THERMAL_CONDUCTIVITY, indices=("alpha", "beta", "omega_bin")),),
    labels={"wrt": "omega"},
    description=(
        "Cumulative thermal conductivity vs frequency: κ_cum(ω_c) "
        "= (1/(V N_q)) Σ_{ω_qν ≤ ω_c} c_qν v^α_qν F^β_qν. The distribution "
        "of κ over the phonon-frequency axis; saturates at κ_LBTE for "
        "ω_c → ∞."
    ),
)


CUMULATIVE_KAPPA_MFP = ObservableSpace(
    name="CumulativeKappa[wrt=mfp]",
    fields=(Field("kappa_cum", THERMAL_CONDUCTIVITY, indices=("alpha", "beta", "mfp_bin")),),
    labels={"wrt": "mfp"},
    description=(
        "Cumulative thermal conductivity vs mean free path: κ_cum(Λ_c) "
        "= (1/(V N_q)) Σ_{|F_qν| ≤ Λ_c} c_qν v^α_qν F^β_qν. Heavily used "
        "for nanoscale design — the Λ at which κ_cum is 50% of κ_total "
        "is the median mean free path."
    ),
)


THERMAL_CONDUCTIVITY_QHGK = HiddenSpace(
    name="ThermalConductivity[transport_model=qhgk]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "qhgk"},
    gauge_group="bz_summation_permutation_via_lorentzian",
    kind="approximation",
    gauge_invariant_contractions=(),
    description=(
        "Quasi-harmonic Green-Kubo κ: time-integrated heat-flux "
        "autocorrelation with Lorentzian mode broadening of width Γ. The "
        "Lorentzian-coupled mode overlap inherits Linewidth's "
        "gauge-dependence on the off-diagonal pairings, so per-element "
        "κ_QHGK is treated as a HiddenSpace until a definitive analysis "
        "of its gauge structure says otherwise. Used primarily for "
        "amorphous systems where the BTE picture breaks down."
    ),
)


# ---------------------------------------------------------------------------
# MD primitives (phase 2 P2). The MD tier sits parallel to the BTE chain
# and feeds the MD-based κ paths added in P3 (Green-Kubo, NEMD, HNEMD).
# ---------------------------------------------------------------------------

TRAJECTORY = HiddenSpace(
    name="Trajectory",
    fields=(
        Field("r", LENGTH, indices=("i", "alpha", "t")),
        Field("v", LENGTH_PER_TIME, indices=("i", "alpha", "t")),
    ),
    gauge_group="md_ensemble_noise",
    kind="scaffolding",
    gauge_invariant_contractions=(
        "HeatCurrentACF",
        "VelocityAutocorrelation",
        "MeanSquaredDisplacement",
    ),
    description=(
        "Per-atom positions r(t) and velocities v(t) sampled at each MD "
        "timestep. Gauge-dependent: the realised trajectory depends on the "
        "integrator (Velocity-Verlet vs. leapfrog), the ensemble "
        "(NVE/NVT/NPT), the thermostat (Berendsen / Langevin / Nose-Hoover "
        "/ CSVR / none), and the initial conditions. Cross-code "
        "comparability lives entirely in the time-averaged contractions "
        "below — HeatCurrentACF, VelocityAutocorrelation, and "
        "MeanSquaredDisplacement are the gauge-invariant content."
    ),
)

HEAT_CURRENT = HiddenSpace(
    name="HeatCurrent",
    fields=(Field("J", ENERGY_TIMES_LENGTH_PER_TIME, indices=("alpha", "t")),),
    gauge_group="md_ensemble_noise",
    kind="scaffolding",
    gauge_invariant_contractions=("HeatCurrentACF",),
    description=(
        "Instantaneous heat-current vector J(t) computed from a Trajectory "
        "via the Irving-Kirkwood (or Hardy, or virial) decomposition. "
        "Per-element J_α(t) is a stochastic MD snapshot — gauge-dependent. "
        "The cross-code observable is the time-correlation HeatCurrentACF, "
        "which is what enters Green-Kubo κ."
    ),
)

HEAT_CURRENT_ACF = ObservableSpace(
    name="HeatCurrentACF",
    fields=(Field("Jcorr", OPAQUE, indices=("alpha", "beta", "tau")),),
    description=(
        "Time-correlation tensor ⟨J_α(0) J_β(τ)⟩ of the MD heat current. "
        "Computed by averaging J(t)·J(t+τ) over the production trajectory "
        "and ensemble repeats; gauge-invariant in the τ→∞ limit. "
        "The Green-Kubo κ integrand: κ_αβ ∝ ∫₀^∞ Jcorr_αβ(τ) dτ — "
        "added in P3 as contract_kappa_green_kubo."
    ),
)

VELOCITY_AUTOCORRELATION = ObservableSpace(
    name="VelocityAutocorrelation",
    fields=(Field("Cv", OPAQUE, indices=("tau",)),),
    description=(
        "Velocity autocorrelation function ⟨v(0)·v(τ)⟩ averaged over atoms "
        "and time origins. Gauge-invariant (a time-correlation of "
        "ensemble-averaged quantities). The Fourier transform gives the "
        "phonon density of states via the Wiener-Khinchin theorem — see "
        "the `fourier_to_dos` edge, which makes this a Pattern-C "
        "alternative-producer of PhononDOS alongside compute_dos."
    ),
)

MEAN_SQUARED_DISPLACEMENT = ObservableSpace(
    name="MeanSquaredDisplacement",
    fields=(Field("M", LENGTH_SQUARED, indices=("tau",)),),
    description=(
        "⟨|r(t+τ) − r(t)|²⟩ averaged over atoms and time origins. "
        "PBC-unwrapped trajectories are required for the linear regime "
        "M(τ) = 2·d·D·τ to be meaningful (D = self-diffusion). "
        "Gauge-invariant; orthogonal to κ but a free addition that lets "
        "the framework cover diffusion observables."
    ),
)


# ---------------------------------------------------------------------------
# MD-based κ paths (phase 2 P3). Three more Pattern-A `transport_model`
# variants of ThermalConductivity, closing the cross-paradigm κ map.
# ---------------------------------------------------------------------------

THERMAL_CONDUCTIVITY_GREEN_KUBO = ObservableSpace(
    name="ThermalConductivity[transport_model=green_kubo]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "green_kubo"},
    description=(
        "Classical Green-Kubo κ: time-integrated heat-flux autocorrelation. "
        "κ_αβ = V/(k_B T²) ∫₀^∞ ⟨J_α(0) J_β(τ)⟩ dτ. The ObservableSpace "
        "produced from the HeatCurrentACF gauge-invariant contraction of "
        "the MD Trajectory. Free of the perturbation a NEMD setup "
        "introduces; the equilibrium-MD reference value for κ."
    ),
)


THERMAL_CONDUCTIVITY_NEMD = ObservableSpace(
    name="ThermalConductivity[transport_model=nemd]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "nemd"},
    description=(
        "Non-equilibrium MD κ: steady-state response to an imposed "
        "temperature gradient or imposed heat flux. κ = −⟨J⟩ / (∂T/∂z) "
        "for direct two-reservoir; for Müller-Plathe (imposed flux), the "
        "swap-rate-derived flux divides by the measured gradient. "
        "Finite-size scaling (κ vs 1/L_z) is a separate post-processing "
        "step left out of this space's definition. Gauge-invariant once "
        "the steady state has converged."
    ),
)


THERMAL_CONDUCTIVITY_HNEMD = ObservableSpace(
    name="ThermalConductivity[transport_model=hnemd]",
    fields=(Field("kappa", THERMAL_CONDUCTIVITY, indices=("alpha", "beta")),),
    labels={"transport_model": "hnemd"},
    description=(
        "Homogeneous-NEMD κ (Evans 1982, Fan et al. 2019): a uniform "
        "driving force F_e is applied to every atom, biasing the heat "
        "current; κ_αβ = ⟨J_α⟩ / (T · V · F_e^β) in the linear-response "
        "limit (small F_e). Free of the boundary-thermostat artefacts of "
        "direct NEMD; GPUMD's signature thermal-transport method. "
        "Gauge-invariant in the small-F_e limit."
    ),
)


NODES: tuple[Space, ...] = (
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
    # MD primitives (phase 2 P2)
    TRAJECTORY,
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    VELOCITY_AUTOCORRELATION,
    MEAN_SQUARED_DISPLACEMENT,
    # MD-based κ paths (phase 2 P3)
    THERMAL_CONDUCTIVITY_GREEN_KUBO,
    THERMAL_CONDUCTIVITY_NEMD,
    THERMAL_CONDUCTIVITY_HNEMD,
)
