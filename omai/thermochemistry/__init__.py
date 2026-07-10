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

Deferred candidates from the pycalphad scan, each with why:

  * CALPHAD-side MolarEntropy S_m and MolarHeatCapacity C_P,m as separate
    source/basis/ensemble-labeled nodes, PLUS the executable contract edge
    G = H - T S that ties MolarGibbsEnergy, MolarEnthalpy, and a CALPHAD
    MolarEntropy: the second slice. It needs the S_m node minted first (this
    hook is named explicitly so the next contribution can land the closed-form
    G = H - T S edge over the three nodes); the map's existing MolarEntropy /
    MolarHeatCapacity are the phonon (constant-V, per-cell) cousins and must
    NOT be reused for the CALPHAD (constant-P, per-atom) quantities.
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
