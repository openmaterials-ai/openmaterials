r"""pymatgen adapter specs for the stability domain.

pymatgen 2025.6.14 as used by the AtomisticSkills mat-* skills
(mat-stability, mat-phase-diagram, mat-surface-energy,
mat-intercalation-voltage), anchored in `scans/pymatgen-atomistic-skills.json`
(review 2026-07-09, full-precision factors):

  operator Space   pymatgen artifact                                units
  ---------------  -----------------------------------------------  --------
  FormationEnergy  PhaseDiagram.get_form_energy_per_atom /          eV/atom
                   ComputedEntry.formation_energy_per_atom
  EnergyAboveHull  PhaseDiagram.get_e_above_hull (ComputedEntry     eV/atom
                   convex hull); MP field energy_above_hull
  SurfaceEnergy    SlabGenerator slabs + in-skill                   J/m^2
                   (E_slab - N E_bulk)/(2A); WulffShape aggregation
  Voltage          in-skill Nernst difference over Structure         V
                   .remove_species de-intercalation

Convention traps this module pins down (all review-verified):

  * The whole family is PER ATOM (eV/atom; mat-stability reports meV/atom, a
    factor 1000), never the per-cell TotalEnergy: the scan's highest-risk
    trap, resolved by these dedicated nodes.
  * Surface energy is computed in eV/A^2 and converted to J/m^2 by
    16.021766339999996 (CODATA-exact; the skill's constant truncates to
    16.0218 at calculate_surface_energy.py:114). Same M T^-2 exponents as
    the force constants; do not confuse the conversion with the FC2
    Ry/bohr^2 factor 48.58681221205054.
  * Voltage: eV per elementary charge = 1 V exactly; no Faraday factor.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.stability.operator.edges import (
    compute_energy_above_hull,
    compute_formation_energy,
    compute_grain_boundary_energy,
    compute_intercalation_voltage,
    compute_surface_energy,
)
from omai.stability.operator.nodes import (
    ENERGY_ABOVE_HULL,
    FORMATION_ENERGY,
    GRAIN_BOUNDARY_ENERGY,
    SURFACE_ENERGY,
    VOLTAGE_STATE,
)


PYMATGEN_FORMATION_ENERGY = SpaceRepresentationSpec(
    space=FORMATION_ENERGY,
    representation_name="pymatgen",
    observable_units={"dH_f": "ev_per_atom"},
    code_api={
        "dH_f": "pymatgen PhaseDiagram.get_form_energy_per_atom / ComputedEntry.formation_energy_per_atom, eV/atom",
    },
    notes=(
        "Formation energy per atom against the elemental references of the "
        "entry set (phase_diagram.py:562-575 get_form_energy / "
        "get_form_energy_per_atom). PER ATOM: eV/atom, the phase-diagram "
        "currency; never equate with the per-cell ComputedEntry.energy "
        "(wrong by the atom count). The committed Li2O example: "
        "-2.061597913888889 eV/atom, GGA+U, MP references "
        "(examples/Li-O/li_o_phase_diagram/li2o_stability.json)."
    ),
)


PYMATGEN_ENERGY_ABOVE_HULL = SpaceRepresentationSpec(
    space=ENERGY_ABOVE_HULL,
    representation_name="pymatgen",
    observable_units={"E_hull": "ev_per_atom"},
    code_api={
        "E_hull": "pymatgen PhaseDiagram.get_e_above_hull / get_decomp_and_e_above_hull, eV/atom (skills report meV/atom)",
    },
    notes=(
        "Convex-hull distance in eV/atom (phase_diagram.py:716-757 "
        "get_decomp_and_e_above_hull), over a ComputedEntry set of the "
        "chemical system; mat-stability multiplies by 1000 to report "
        "meV/atom (compute_ehull.py:181), a factor to keep explicit. MP "
        "serves the same quantity as the energy_above_hull field. The "
        "committed examples: Li2O 0.0 eV/atom (stable, GGA+U); Li3PS4 0.0 "
        "meV/atom (stable, R2SCAN thermo)."
    ),
)


PYMATGEN_SURFACE_ENERGY = SpaceRepresentationSpec(
    space=SURFACE_ENERGY,
    representation_name="pymatgen",
    observable_units={"gamma": "J_per_m2"},
    code_api={
        "gamma": "pymatgen SlabGenerator slabs; in-skill gamma = (E_slab - N E_bulk)/(2A), J/m^2; WulffShape aggregation",
    },
    notes=(
        "Per-facet surface energy: pymatgen builds the slabs "
        "(core.surface SlabGenerator / generate_all_slabs) and aggregates "
        "the Wulff morphology (analysis.wulff.WulffShape, "
        "weighted_surface_energy); the gamma itself is the in-skill "
        "difference (calculate_surface_energy.py:108-114), computed in "
        "eV/A^2 then converted by the truncated 16.0218 (CODATA-exact "
        "16.021766339999996 = e/(1e-10)^2). The facet (hkl) rides in "
        "conditions. Committed Cu examples: 1.3 (111), 1.45 (100), 1.55 "
        "(110) J/m^2, CHGNet-MatPES-r2SCAN "
        "(examples/FCC_metals/surface_energies.json)."
    ),
)


PYMATGEN_VOLTAGE = SpaceRepresentationSpec(
    space=VOLTAGE_STATE,
    representation_name="pymatgen",
    observable_units={"V_avg": "volt"},
    code_api={
        "V_avg": "in-skill V = -(E_full - E_empty - n mu_metal)/n over pymatgen Structure.remove_species cells, volts",
    },
    notes=(
        "Average intercalation voltage in volts: pymatgen's role is the "
        "de-intercalated Structure construction (remove_species, "
        "remove_atoms.py:18-30) and the energies come from the MLIP; the "
        "quotient eV/e is volts exactly (calculate_voltage.py:39-55). "
        "pymatgen.apps.battery.InsertionElectrode is the library "
        "equivalent, not used by the skill. Committed LiFePO4 example: "
        "3.260441522078377 V vs Li/Li+, MACE-MH-1 matpes_r2scan "
        "(examples/LiFePO4/voltage_results.json)."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level specs (diagnostic: how pymatgen realizes the edges)
# ---------------------------------------------------------------------------

PYMATGEN_COMPUTE_FORMATION_ENERGY = OperatorRepresentationSpec(
    operator=compute_formation_energy,
    representation_name="pymatgen",
    discretization_choices={
        "entry_corrections": (
            "the MP compatibility scheme applied to raw energies before "
            "referencing (GGA/GGA+U mixing or R2SCAN thermo type); changes "
            "the reference chemical potentials, recorded in conditions"
        ),
    },
    notes=(
        "Realized by pymatgen's phase-diagram machinery over a ComputedEntry "
        "set: the elemental_references scheme is the Materials Project "
        "reference set (with its compatibility corrections); "
        "PhaseDiagram.get_form_energy_per_atom performs the "
        "subtract-and-normalize."
    ),
)


PYMATGEN_COMPUTE_ENERGY_ABOVE_HULL = OperatorRepresentationSpec(
    operator=compute_energy_above_hull,
    representation_name="pymatgen",
    discretization_choices={
        "competing_entries": (
            "which entries populate the hull (the full MP chemical system "
            "in the committed examples); an incomplete entry set "
            "underestimates E_hull"
        ),
    },
    notes=(
        "Realized by pymatgen PhaseDiagram (convex hull over the entry set) "
        "and get_e_above_hull; the hull_source scheme records where the "
        "competing entries come from (MP database, thermo type R2SCAN or "
        "GGA_GGA+U in the committed examples)."
    ),
)


PYMATGEN_COMPUTE_SURFACE_ENERGY = OperatorRepresentationSpec(
    operator=compute_surface_energy,
    representation_name="pymatgen",
    discretization_choices={
        "slab_geometry": (
            "SlabGenerator min_slab_size / min_vacuum_size and the (hkl) "
            "choice; convergence of gamma with slab thickness is the "
            "estimator's discretization"
        ),
        "relaxation": (
            "whether slab and bulk are relaxed with the same MLIP settings "
            "(the committed Cu flow relaxes both with "
            "CHGNet-MatPES-r2SCAN)"
        ),
    },
    notes=(
        "Realized by pymatgen SlabGenerator slabs plus the in-skill "
        "difference; the slab_termination scheme (symmetric, both faces "
        "equivalent) is what licenses the 2A denominator. WulffShape "
        "consumes the per-facet gammas downstream."
    ),
)


PYMATGEN_COMPUTE_INTERCALATION_VOLTAGE = OperatorRepresentationSpec(
    operator=compute_intercalation_voltage,
    representation_name="pymatgen",
    discretization_choices={
        "deintercalation": (
            "how the empty cell is built (Structure.remove_species removes "
            "ALL working ions: the average voltage over the full "
            "composition range, not a voltage profile)"
        ),
        "metal_reference": (
            "the working-ion metal reservoir cell whose per-atom energy is "
            "mu_metal (bcc Li in the committed example)"
        ),
    },
    notes=(
        "Realized by the mat-intercalation-voltage flow: pymatgen builds "
        "the de-intercalated Structure, the MLIP supplies the three "
        "energies, and the working_ion scheme records the ion (Li) and the "
        "reference couple (Li/Li+)."
    ),
)


PYMATGEN_GRAIN_BOUNDARY_ENERGY = SpaceRepresentationSpec(
    space=GRAIN_BOUNDARY_ENERGY,
    representation_name="pymatgen",
    observable_units={"gamma_GB": "J_per_m2"},
    code_api={
        "gamma_GB": "pymatgen.analysis.gb.grain.GrainBoundaryGenerator CSL slabs; in-skill gamma_GB = (E_GB - N E_bulk)/(2A), J/m^2",
    },
    notes=(
        "Grain-boundary energy per CSL boundary: pymatgen "
        "GrainBoundaryGenerator builds the coincidence-site-lattice slab "
        "supercells (mat-grain-boundary), an MLIP relaxes them (relax_cell="
        "False), and the gamma_GB is the in-skill slab-bulk difference "
        "(calculate_gb_energy.py, (E_GB - N E_bulk)/(2A)), computed in "
        "eV/A^2 and quoted in J/m^2. The SIBLING of the pymatgen "
        "SurfaceEnergy spec (same construction, same J/m^2 unit); the "
        "boundary configuration (Sigma, tilt angle, rotation axis, GB plane) "
        "rides in conditions. Committed Cu [001]-tilt example "
        "(examples/Cu-001-tilt-TensorNet/gb_energy_results.json): "
        "Sigma5 0.9768, Sigma13 0.7759, Sigma25 0.7196 J/m^2, "
        "TensorNet-MatPES-r2SCAN-v2025.1-PES, Cu mp-30, bulk energy "
        "-10.825556 eV/atom, validated against EAM-Mishin (0.99, 0.92) and "
        "DFT-PBE (~0.74, ~0.72). NOT a fipy phase-field output: the "
        "phase-field / kMC INPUT."
    ),
)


PYMATGEN_COMPUTE_GRAIN_BOUNDARY_ENERGY = OperatorRepresentationSpec(
    operator=compute_grain_boundary_energy,
    representation_name="pymatgen",
    discretization_choices={
        "gb_geometry": (
            "GrainBoundaryGenerator Sigma / rotation axis / GB plane and the "
            "min-slab / vacuum sizes (the committed Cu example: rotation axis "
            "[001], vacuum 0.0, min-slab-size 10 A); convergence of gamma_GB "
            "with slab thickness is the estimator's discretization"
        ),
        "relaxation": (
            "the MLIP relax of the GB slab (relax_cell=False, fmax 0.02 in the "
            "committed example) against the separately relaxed bulk reference "
            "(relax_cell=True, fmax 0.005)"
        ),
    },
    notes=(
        "Realized by pymatgen GrainBoundaryGenerator CSL slabs plus the "
        "in-skill difference over an MLIP relax; the method scheme "
        "(slab_energy_difference) is the same slab-bulk-over-2A construction "
        "compute_surface_energy uses (the factor 2 for the two periodic "
        "boundaries). The MLIP-checkpoint provenance (which model produced "
        "the energies, TensorNet-MatPES-r2SCAN in the committed example) "
        "lives on the Potential specs; mat-grain-boundary is the driving "
        "skill."
    ),
)


# ---------------------------------------------------------------------------
# XRD note (pymatgen rail extension, representation-only; no XRDPattern node)
# ---------------------------------------------------------------------------
#
# The characterization scan (scans/characterization-atomistic-skills.json)
# catalogs pymatgen's XRDCalculator (mat-xrd-calculator) as a FUNCTION-VALUED
# kinematic diffraction pattern I(2theta), DEFERRED to the spectrum layer (no
# XRDPattern node is minted this slice, per orchestrator decision "XRDPattern
# deferral"). Rather than open a new xrd rail for a deferred quantity, the
# XRDCalculator design is recorded here as an extension NOTE on the existing
# pymatgen rail (the calculator IS pymatgen), so no new representation_name and
# no new rail are added:
#
#   * CANONICAL AXIS. Store the pattern on the wavelength-independent d_hkl
#     (Angstrom, d_hkl = 1/g_hkl, xrd.py:259) or Q = 4 pi sin(theta)/lambda
#     (Angstrom^-1); 2theta (degrees) is a DERIVED / served axis that carries
#     the wavelength as a REQUIRED condition (Bragg 2 d sin theta = lambda, so
#     the same plane sits at different 2theta for Cu vs Mo radiation).
#   * WAVELENGTH is a required physical condition, not an internal gauge: it
#     changes 2theta AND the relative intensities (via the LP factor and
#     s = sin theta / lambda). Drawn from the pymatgen WAVELENGTHS vocabulary
#     (CuKa 1.54184 the Ka1/Ka2 WEIGHTED AVERAGE, distinct from CuKa1 1.54056:
#     mixing them shifts 2theta, the headline trap), with a free-float escape
#     for synchrotron wavelengths.
#   * INTENSITIES are kinematic |F_hkl|^2 x Lorentz-polarization, scaled so the
#     max peak is 100, with NO absorption, NO preferred orientation, and NO
#     Debye-Waller by default (a convention flag on any XRD representation).
#   * XRDPattern is DEFERRED to the spectrum layer (the named hook): mint it
#     only when a characterization domain opens; it grounds a Structure
#     representation (the pattern is a purely GEOMETRIC function of the
#     Structure), not a per-material scalar node. Peak positions d_hkl and
#     relative intensities ride as scalar-reduction fingerprint fields, refined
#     lattice params as Structure metadata, refinement weight fractions as a
#     fitted characterization output kept DISTINCT from the equilibrium
#     PhaseFraction node (a CALPHAD Gibbs-minimization output, different
#     provenance).
