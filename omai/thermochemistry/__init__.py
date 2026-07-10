"""The thermochemistry domain: assessed phase thermodynamics from CALPHAD.

Phase thermodynamics from assessed Gibbs-energy databases (the pycalphad scan,
AtomisticSkills arXiv 2605.24002): the macroscopic CALPHAD side of stability,
finite-temperature and assessed, distinct from the 0 K DFT hull. Six
ObservableSpaces (AssessedDatabase, MolarGibbsEnergy, MolarEnthalpy,
ChemicalPotential, PhaseFraction, TransitionTemperature) with five implicit
edges, all driven by a Gibbs minimization over a frozen human-assessed TDB.

The Molar* false-merge guardrail is the domain's load-bearing identity
decision: CALPHAD's molar quantities share the ENERGY_PER_MOLE exponent vector
with the phonon-side Molar* nodes but are a Gibbs (constant P) energy per mole
of ATOMS from an assessed model, not a Helmholtz (constant V) energy per mole
of PRIMITIVE CELLS from a phonon-gas sum. The molar_gibbs_energy /
molar_enthalpy quantity tags (fresh, never molar_helmholtz_free_energy) keep
the two sides distinct in identity; the basis lives in the descriptions and
representation notes.

The assessed-entropy slice (LANDED, physics-review recommendation, 2026-07-10):
CalphadMolarEntropy S_m (the constant-P assessed molar entropy per mole of
atoms, SER-referenced, tag calphad_molar_entropy) is now a node, produced
implicitly by compute_calphad_entropy (SM = -dG_m/dT) and consumed by the
EXECUTABLE contract_gibbs_hts edge G_m = H_m - T S_m, the second producer of
MolarGibbsEnergy (Pattern C, must agree with solve_equilibrium's direct GM).
The dimensional gate PROVES the identity (T S_m = ENERGY_PER_MOLE). The map's
existing phonon-side MolarEntropy (constant-V, per-cell) stays a distinct
cousin, kept apart by the calphad_molar_entropy vs molar_entropy tags.

Deferred candidates still open from the pycalphad scan, each with why:

  * CALPHAD-side MolarHeatCapacity C_P,m as a separate source/basis/ensemble-
    labeled node: the constant-P assessed heat capacity SM's T-derivative
    partner. Deferred until a skill reads it (the calphad-agent skills consume
    NP/Phase, not C_P,m); the phonon-side MolarHeatCapacity /
    HeatCapacityConstantP are the constant-V / per-cell cousins and must NOT be
    reused for the CALPHAD constant-P per-atom quantity.
  * Activity a_i = exp((mu_i - mu_i_ref)/RT): dimensionless, per component,
    reachable from ChemicalPotential via a ReferenceState. No calphad-agent
    skill reads it (they consume NP/Phase and the binplot boundaries), so it
    is deferred until a skill uses it.
  * SiteFraction Y: the sublattice-occupancy internal DOF of the
    compound-energy formalism, a representation-only coordinate of a phase's
    Gibbs energy (which sublattice model), not a physical observable, like the
    pymatgen scan's Voigt-packing / symmetry representation verdicts.
  * The phase-diagram products and the full liquidus / solidus / solvus loci
    T(x) and NP(T): array / spectrum instances (like si-frequency-qe.json),
    which need the spectrum layer. The scalar invariant points ARE scalars
    (TransitionTemperature carries them); the full loci are deferred to the
    spectrum layer.
  * QHA computed-side molar Gibbs energy (a phonon G(T) from the harmonic /
    quasi-harmonic route): needs the basis reconciliation between the phonon
    per-cell Helmholtz world and the CALPHAD per-atom Gibbs world, deliberately
    not this slice.
"""
