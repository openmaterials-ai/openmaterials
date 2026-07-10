r"""pycalphad adapter specs for the thermochemistry domain.

pycalphad 0.11.2 as used by the AtomisticSkills mat-calphad-* skills
(mat-calphad-phase-diagram, mat-calphad-property-diagram), anchored in
`scans/pycalphad-atomistic-skills.json` (deep review 2026-07-09; all 13
entries confirmed; unit declarations read from the pip-downloaded wheel
pycalphad-0.11.2-cp312-cp312-macosx_11_0_arm64.whl, unzipped to
/tmp/pcsrc/wheel). pycalphad is NOT importable in the miniconda base env and
the calphad-agent conda env is not created on this machine, so anchors are
wheel-source line references, not a live import; core_env.yaml pins pycalphad
with no version, so a live install could differ (open question).

  operator Space         pycalphad artifact                             units
  ---------------------  ---------------------------------------------  ------
  AssessedDatabase       Database(tdb) (io/database.py)                 (model)
  MolarGibbsEnergy       equilibrium(...).GM (property_framework)       J/mol
  MolarEnthalpy          equilibrium/calculate(..., output='HM')        J/mol
  ChemicalPotential      equilibrium(...).MU (variables.py:830-836)     J/mol
  PhaseFraction          equilibrium(...).NP (variables.py:488-505)     fraction
  TransitionTemperature  binplot(...) boundary loci (compat_api.py)     K
  CalphadMolarEntropy    equilibrium/calculate(..., output='SM')        J/(mol K)

Convention traps this module pins down (all review-verified):

  * BASIS: pycalphad's molar energies (GM/HM/MU) are per mole of ATOMS
    (the skills set v.N:1, system-moles normalization; units.py:14 defines
    atom = mol/N_A and molar_weight is in g/mol-atom at units.py:67), at
    constant pressure (v.P:101325 Pa), SER reference. This is NOT the map's
    phonon Molar* basis (per mole of primitive cells, constant volume,
    Helmholtz) and NOT per formula unit (pycalphad G = formulaenergy). Three
    different "moles".
  * J/mol vs eV/atom: factor 96485.33212331 (= e * N_A, SI-exact = the Faraday
    constant). A cross-code compare of a CALPHAD molar energy against a DFT
    per-atom energy passes through this factor AND a reference-state bridge.
  * R = 8.3145 hardcoded (variables.py:939), a 5-sig-fig round-up of CODATA
    8.31446261815324; relative error 4.496e-06 = 0.00045% high, negligible at
    assessment precision (the assessed parameters and the -R T sum x ln x
    ideal-mixing term it multiplies carry far larger uncertainty).
  * TDB PROVENANCE is the checkpoint analog: which TDB file and which
    published assessment (alzn_mey.tdb: NIMS 2009, S. an Mey, Z. Metallkd. 84
    (1993) 451-455) plus (comps, phases, v.N, v.P, v.T, v.X) are the
    conditions every value must record.
  * binplot returns a matplotlib Axes, not a data table: the transition
    temperatures are drawn, so extracting the boundary loci for instances
    needs the Workspace / mapping API, not the plot.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.thermochemistry.operator.edges import (
    compute_calphad_entropy,
    compute_chemical_potentials,
    compute_molar_enthalpy,
    compute_phase_fractions,
    compute_transition_temperature,
    solve_equilibrium,
)
from omai.thermochemistry.operator.nodes import (
    ASSESSED_DATABASE,
    CALPHAD_MOLAR_ENTROPY,
    CHEMICAL_POTENTIAL,
    MOLAR_ENTHALPY,
    MOLAR_GIBBS_ENERGY,
    PHASE_FRACTION,
    TRANSITION_TEMPERATURE,
)


# ---------------------------------------------------------------------------
# Space-level specs (the six nodes)
# ---------------------------------------------------------------------------

PYCALPHAD_ASSESSED_DATABASE = SpaceRepresentationSpec(
    space=ASSESSED_DATABASE,
    representation_name="pycalphad",
    code_api={
        "D_tdb": "pycalphad.Database(tdb) (io/database.py; io/tdb.py TDB format hook); dbf.phases / dbf.elements / dbf.symbols",
    },
    notes=(
        "The assessed model artifact: pycalphad.Database(path) loads the "
        "SGTE-convention Gibbs functions from a TDB (GHSER* lattice-stability "
        "polynomials a + b T + c T ln T + sum d_n T^n + e T^-1 in J per mole "
        "of atoms, Redlich-Kister excess parameters, magnetic / Einstein "
        "terms). Opaque node (no unit): a model, the CALPHAD analog of the "
        "MLIP checkpoint and the QE pseudopotential. Its PROVENANCE is the "
        "checkpoint schema: {tdb_file, assessment_citation} plus the solve "
        "conditions {comps, phases, v.N, v.P, v.T, v.X}. The committed "
        "example alzn_mey.tdb (mat-calphad-phase-diagram/examples/Al-Zn/) is "
        "NIMS 2009, parameters from S. an Mey, Z. Metallkd. 84 (1993) "
        "451-455. Elements are implicitly uppercase and the vacancy species "
        "VA must be explicit in comps or the sublattice models break "
        "(plot_phase_diagram.py:48,53-54)."
    ),
)

PYCALPHAD_MOLAR_GIBBS_ENERGY = SpaceRepresentationSpec(
    space=MOLAR_GIBBS_ENERGY,
    representation_name="pycalphad",
    observable_units={"G_m": "J_per_mol"},
    code_api={
        "G_m": "pycalphad.equilibrium(dbf, comps, phases, conds).GM, J/mol per mole of atoms; also calculate(..., output='GM')",
    },
    notes=(
        "Molar Gibbs energy GM, the free energy the minimization returns: "
        "property_framework/units.py:29-31 GM_implementation_units = "
        "GM_display_units = 'J / mol', display name 'Gibbs Energy'; "
        "model.py:484 energy = GM = self.ast. PER MOLE OF ATOMS: each energy "
        "contribution is divided by _site_ratio_normalization (model.py:931/"
        "957/979/..., verified atoms-per-formula-unit at :627-638) as it "
        "enters ast, while G = formulaenergy = ast * _site_ratio_"
        "normalization (:485) is the per-formula-unit form. J/mol maps to "
        "ENERGY_PER_MOLE (canonical J_per_mol, to_operator 1.0; CALPHAD-native "
        "basis). NOTE the eV/atom cross-basis: 1 eV/atom = 96485.33212331 "
        "J/mol (= e * N_A, SI-exact = Faraday); this is a basis conversion, "
        "NOT a unit of ENERGY_PER_MOLE (eV/atom has N=0), so it stays in these "
        "notes, not the unit registry. Distinct from the phonon "
        "MolarHelmholtzFreeEnergy (constant V, per mole of cells, kJ/mol; "
        "factor 1000 plus the atoms-vs-cells basis when bridging)."
    ),
)

PYCALPHAD_MOLAR_ENTHALPY = SpaceRepresentationSpec(
    space=MOLAR_ENTHALPY,
    representation_name="pycalphad",
    observable_units={"H_m": "J_per_mol"},
    code_api={
        "H_m": "pycalphad.equilibrium/calculate(..., output='HM').HM, J/mol per mole of atoms",
    },
    notes=(
        "Molar enthalpy HM = GM - T dGM/dT (the Legendre relation): "
        "units.py:35-39 HM_implementation_units = GM_implementation_units = "
        "'J / mol', display name 'Enthalpy'; model.py:487 enthalpy = HM. Per "
        "mole of atoms, constant P, SER reference, canonical J_per_mol. The "
        "enthalpy of formation (HM referenced to SER) is the CALPHAD analog "
        "of the stability FormationEnergy, but SER-referenced and in "
        "J/mol-atoms not eV/atom (factor 96485.33212331); the mixing enthalpy "
        "HM_MIX (model.py:492) is the CALPHAD heat of mixing. Not read "
        "directly by the two calphad-agent skills (they consume NP/Phase); a "
        "standard equilibrium / calculate output, cataloged for the domain's "
        "enthalpy channel."
    ),
)

PYCALPHAD_CHEMICAL_POTENTIAL = SpaceRepresentationSpec(
    space=CHEMICAL_POTENTIAL,
    representation_name="pycalphad",
    observable_units={"mu": "J_per_mol"},
    code_api={
        "mu": "pycalphad.equilibrium(...).MU (variables.py:830-836, v.MU), J/mol, one per component",
    },
    notes=(
        "Chemical potentials MU, a base equilibrium output: variables.py:"
        "830-836 class ChemicalPotential(StateVariable), implementation_units "
        "= display_units = 'J / mol', display_name 'Chemical Potential "
        "{species}'; aliased v.MU at :937; equilibrium.py:81 "
        "chemical_potentials = properties.MU[index]. Per mole of atoms, "
        "canonical J_per_mol, indexed by component (the `c` axis, one MU per "
        "non-vacancy component). It is the common-tangent hyperplane of the "
        "minimization (the mass-balance Lagrange multipliers; "
        "CONDITIONS_REQUIRING_HESSIANS includes ChemicalPotential, "
        "variables.py:941). An OUTPUT of the equilibrium, distinct from the "
        "elemental-reference mu_i the stability domain supplies as inputs."
    ),
)

PYCALPHAD_PHASE_FRACTION = SpaceRepresentationSpec(
    space=PHASE_FRACTION,
    representation_name="pycalphad",
    observable_units={"NP": "dimensionless"},
    code_api={
        "NP": "pycalphad.equilibrium(...).NP (variables.py:488-505, v.NP), fraction, per stable phase; paired with eq.Phase",
    },
    notes=(
        "Phase fractions NP, THE headline output of the property-diagram "
        "skill: variables.py:488-505 class PhaseFraction(StateVariable), "
        "implementation_units = display_units = 'fraction', varname "
        "'NP_<phase>', result += compset.NP; aliased v.NP at :938. "
        "Dimensionless (canonical `dimensionless` unit), indexed by phase "
        "(the `p` axis). Under v.N:1 it is the mole fraction of each "
        "coexisting phase (the lever rule). plot_phase_fractions.py:73-92 "
        "reads eq.NP.values indexed [0,0,temp,0,idx], filters >1e-3, plots vs "
        "T; :96 ylabel 'Phase Fraction'. A phase-fraction-vs-T curve is a "
        "spectrum instance (like si-frequency-qe.json), not a single scalar."
    ),
)

PYCALPHAD_TRANSITION_TEMPERATURE = SpaceRepresentationSpec(
    space=TRANSITION_TEMPERATURE,
    representation_name="pycalphad",
    observable_units={"T_trans": "kelvin"},
    code_api={
        "T_trans": "pycalphad.binplot(dbf, comps, phases, conds) boundary loci (compat_api.py:6-42), K; drawn, not returned as scalars",
    },
    notes=(
        "Transition temperatures: the liquidus / solidus / solvus boundaries "
        "and invariant points binplot draws by sweeping equilibrium over the "
        "(T, X) grid (mat-calphad-phase-diagram/scripts/plot_phase_diagram.py:"
        "62-67 conds v.T (t_start, t_stop, t_step), v.X(el2) (0,1,0.02); :76 "
        "binplot; :80-81 axes 'Mole Fraction' / 'Temperature (K)'). "
        "TemperatureType implementation_units = 'kelvin' (variables.py:"
        "901-904); canonical `kelvin`. The Al-Zn example cites liquidus "
        "~933 K (Al) -> ~692 K (Zn) and a eutectoid ~550 K. TRAP: binplot "
        "returns a matplotlib Axes, not a data table, so the boundary loci "
        "are drawn, not returned as labeled scalars; extracting them for "
        "instances needs the Workspace / mapping API. The full loci T(x) are "
        "a spectrum-layer product; invariant points are scalars."
    ),
)


PYCALPHAD_CALPHAD_MOLAR_ENTROPY = SpaceRepresentationSpec(
    space=CALPHAD_MOLAR_ENTROPY,
    representation_name="pycalphad",
    observable_units={"S_m": "J_per_K_per_mol"},
    code_api={
        "S_m": "pycalphad.equilibrium/calculate(..., output='SM').SM, J/(mol K) per mole of atoms; SM = -dGM/dT",
    },
    notes=(
        "Molar entropy SM = -dGM/dT (the constant-P Gibbs temperature "
        "derivative): units.py SM_implementation_units = 'J / K / mol', "
        "display name 'Entropy'; model.py entropy = SM. PER MOLE OF ATOMS, "
        "constant P, SER reference; canonical J_per_K_per_mol. J/(K mol) maps "
        "to ENERGY_PER_TEMPERATURE_PER_MOLE (1,2,-2,-1,-1,0,0). It is the "
        "entropy factor of the executable Gibbs identity G_m = H_m - T S_m "
        "(contract_gibbs_hts), the second producer of MolarGibbsEnergy; the "
        "three energy-side quantities (G_m, H_m, S_m) are all on the SAME "
        "per-mole-of-atoms constant-P SER basis, so the identity is "
        "basis-honest. EXPLICITLY DISTINCT from the phonopy MolarEntropy "
        "(constant-V per-mole-of-cells vibrational entropy, kJ/mol per K "
        "phonopy convention): same J/(K mol) exponent vector, different "
        "ensemble and basis, kept apart by the calphad_molar_entropy tag. Not "
        "read directly by the two calphad-agent skills (they consume "
        "NP/Phase); a standard equilibrium / calculate output, cataloged for "
        "the domain's entropy channel and the Gibbs-identity cross-check."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how pycalphad realizes the edges)
# ---------------------------------------------------------------------------

PYCALPHAD_SOLVE_EQUILIBRIUM = OperatorRepresentationSpec(
    operator=solve_equilibrium,
    representation_name="pycalphad",
    discretization_choices={
        "conditions": (
            "the fixed state (v.N:1 per mole of atoms, v.P:101325 Pa, the "
            "v.T grid, the v.X composition) supplied to equilibrium; v.N:1 "
            "pins the per-mole-of-atoms basis and v.P the constant pressure"
        ),
        "gas_constant": (
            "pycalphad hardcodes v.R = 8.3145 J/mol/K (variables.py:939), a "
            "round-up of CODATA 8.31446261815324; relative error 4.496e-06, "
            "negligible at assessment precision; it multiplies every "
            "ideal-mixing -R T sum x ln x and Einstein term"
        ),
    },
    notes=(
        "Realized by pycalphad.equilibrium(dbf, comps, phases, conds): the "
        "global Gibbs minimization over the assessed database's sublattice "
        "site fractions at fixed (N, P, T, X), returning GM. The method "
        "scheme is gibbs_minimization; the composition and pressure are "
        "conditions of the solve."
    ),
)

PYCALPHAD_COMPUTE_MOLAR_ENTHALPY = OperatorRepresentationSpec(
    operator=compute_molar_enthalpy,
    representation_name="pycalphad",
    discretization_choices={
        "output_channel": (
            "HM is requested as an output of equilibrium / calculate "
            "(output='HM'); it is the Legendre derivative GM - T dGM/dT "
            "evaluated through the same assessed Model (model.py:487)"
        ),
    },
    notes=(
        "Realized by pycalphad's Model enthalpy channel: HM = GM - "
        "T dGM/dT, requested as a named output of equilibrium / calculate. "
        "The method scheme is legendre_derivative."
    ),
)

PYCALPHAD_COMPUTE_CALPHAD_ENTROPY = OperatorRepresentationSpec(
    operator=compute_calphad_entropy,
    representation_name="pycalphad",
    discretization_choices={
        "output_channel": (
            "SM is requested as an output of equilibrium / calculate "
            "(output='SM'); it is the constant-P temperature derivative "
            "SM = -dGM/dT evaluated through the same assessed Model"
        ),
    },
    notes=(
        "Realized by pycalphad's Model entropy channel: SM = -dGM/dT, "
        "requested as a named output of equilibrium / calculate. The method "
        "scheme is gibbs_temperature_derivative. Feeds the executable Gibbs "
        "identity contract_gibbs_hts (G_m = H_m - T S_m): pycalphad's own "
        "GM = HM - T SM (model.py) is exactly the identity the map now wires "
        "as a second, sympy-executable producer of MolarGibbsEnergy, so the "
        "direct GM and the H - T S route are the redundant cross-check."
    ),
)

PYCALPHAD_COMPUTE_CHEMICAL_POTENTIALS = OperatorRepresentationSpec(
    operator=compute_chemical_potentials,
    representation_name="pycalphad",
    discretization_choices={
        "reference": (
            "MU is returned in the absolute SER-referenced J/mol of the "
            "assessed database; a chosen ReferenceState "
            "(metaproperties.py:232) would shift the reference plane "
            "(the mechanism activity is built on), not used by the skills"
        ),
    },
    notes=(
        "Realized as a base output of pycalphad.equilibrium: MU is the "
        "common-tangent hyperplane (the mass-balance Lagrange multipliers), "
        "read per component index (equilibrium.py:81). The method scheme is "
        "partial_molar_derivative."
    ),
)

PYCALPHAD_COMPUTE_PHASE_FRACTIONS = OperatorRepresentationSpec(
    operator=compute_phase_fractions,
    representation_name="pycalphad",
    discretization_choices={
        "phase_threshold": (
            "the property-diagram skill filters NP > 1e-3 before plotting "
            "(plot_phase_fractions.py:73-92), the numerical cutoff for a "
            "phase counting as present in the assemblage"
        ),
        "phase_set": (
            "which phases from the TDB are passed to equilibrium "
            "(phases = list(dbf.phases.keys()) in the skill); an omitted "
            "phase cannot appear in the assemblage"
        ),
    },
    notes=(
        "Realized by pycalphad.equilibrium(...).NP paired with eq.Phase: the "
        "per-phase molar amount of the equilibrium assemblage, plotted vs T "
        "by mat-calphad-property-diagram. The method scheme is lever_rule."
    ),
)

PYCALPHAD_COMPUTE_TRANSITION_TEMPERATURE = OperatorRepresentationSpec(
    operator=compute_transition_temperature,
    representation_name="pycalphad",
    discretization_choices={
        "t_grid": (
            "the temperature resolution of the binplot / phase-fraction "
            "sweep (t_step, e.g. 10 K in the Al-Zn example); the boundary "
            "loci are resolved only to this grid"
        ),
        "extraction": (
            "binplot returns a matplotlib Axes (compat_api.py:6-42), not a "
            "data table, so a transition temperature is read from the drawn "
            "boundary; a labeled scalar needs the Workspace / mapping API"
        ),
    },
    notes=(
        "Realized by pycalphad.binplot sweeping equilibrium over the (T, X) "
        "grid to draw the liquidus / solidus / solvus boundaries and "
        "invariant points; the transition temperatures are the boundary "
        "loci. The method scheme is boundary_locus. Only the binary route is "
        "implemented by the skill (ternplot exists at compat_api.py:65 but "
        "SKILL.md notes ternary isotherms are not yet implemented)."
    ),
)
