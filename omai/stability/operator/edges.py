r"""Operators (edges) of the stability domain.

Four edges, all implicit (is_executable_in_sympy_override=False): energy
differences whose selectors (which reference phases, which competing entries,
which slab, which intercalated pair) are external constructions over the
ground-state TotalEnergy family, encoded as opaque applied functions of the
inputs, with the selection recorded as schemes:

  compute_formation_energy      : (TotalEnergy, Structure)     -> FormationEnergy
  compute_energy_above_hull     : (FormationEnergy, Structure) -> EnergyAboveHull
  compute_surface_energy        : (TotalEnergy, Structure)     -> SurfaceEnergy
  compute_intercalation_voltage : (TotalEnergy, Structure)     -> Voltage

The TotalEnergy input stands for the FAMILY of ground-state energy
evaluations each edge consumes (compound + elemental references; slab + bulk;
intercalated + de-intercalated + metal), the same family-of-values convention
compute_fc2_finite_displacement uses for displaced forces and fit_arrhenius
uses for D(T). Connectivity: all four edges share the Structure vertex (and
three share TotalEnergy), making the contribution one weakly connected
component through the P4 gate, alongside the magnetic-moment edge that also
touches Structure.

Symbols. Every field symbol is new and collision-checked: \Delta H_f,
E_{hull}, \gamma_{surf} (NOT bare \gamma, the generic dummy index), V_{avg}.
The opaque selector functions (E^{form}_{ref}, d^{hull}, E^{slab}, E^{bulk},
E^{full}, E^{empty}, m^{KS}) are applied functions, not free symbols, so they
need no vocabulary entries; their arguments E_{tot} and \mathcal{S} are the
registered ground-state symbols.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.stability.operator.nodes import (
    ENERGY_ABOVE_HULL,
    FORMATION_ENERGY,
    SURFACE_ENERGY,
    VOLTAGE_STATE,
)
from omai.dft_ground_state.operator.nodes import STRUCTURE, TOTAL_ENERGY


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

_dH_f = sp.Symbol(r"\Delta H_f")
_E_hull = sp.Symbol(r"E_{hull}")
_gamma_surf = sp.Symbol(r"\gamma_{surf}")
_V_avg = sp.Symbol(r"V_{avg}")
_E_tot = sp.Symbol("E_{tot}")
_S = sp.Symbol(r"\mathcal{S}")
# Slab / bulk bookkeeping of the surface-energy difference.
_N_slab = sp.Symbol(r"N_{slab}", positive=True)
_A_surf = sp.Symbol(r"A_{surf}", positive=True)
# Working-ion bookkeeping of the Nernst voltage.
_n_ion = sp.Symbol(r"n_{ion}", positive=True)
_mu_ion = sp.Symbol(r"\mu_{ion}")
_q_e = sp.Symbol("q_e", positive=True)
# Opaque selector functions (applied functions, not free symbols).
_E_form_ref = sp.Function(r"E^{form}_{ref}")
_d_hull = sp.Function(r"d^{hull}")
_E_slab = sp.Function(r"E^{slab}")
_E_bulk = sp.Function(r"E^{bulk}")
_E_full = sp.Function(r"E^{full}")
_E_empty = sp.Function(r"E^{empty}")


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

compute_formation_energy = Operator(
    name="compute_formation_energy",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(FORMATION_ENERGY,),
    schemes={"elemental_references": "materials_project"},
    formula=sp.Eq(_dH_f, _E_form_ref(_E_tot, _S)),
    is_executable_in_sympy_override=False,
    description=(
        "Formation energy per atom Delta H_f = E^{form}_{ref}[E_tot, S]: "
        "subtract the composition-weighted elemental reference chemical "
        "potentials from the compound's total energy and divide by the atom "
        "count, (E_tot - sum_a n_a mu_a)/N. The reference chemical "
        "potentials mu_a are an opaque reference function over the "
        "elemental ground states; WHICH reference set is the "
        "elemental_references scheme (Materials Project references, with "
        "their GGA/GGA+U/R2SCAN mixing corrections, in the committed "
        "examples; pymatgen PhaseDiagram.get_form_energy_per_atom). The "
        "TotalEnergy input stands for the family of energies involved "
        "(compound plus each elemental reference). Implicit (an external "
        "lookup-and-subtract over a computed entry set), so not "
        "sympy-executable."
    ),
)

compute_energy_above_hull = Operator(
    name="compute_energy_above_hull",
    inputs=(FORMATION_ENERGY, STRUCTURE),
    outputs=(ENERGY_ABOVE_HULL,),
    schemes={"hull_source": "materials_project"},
    formula=sp.Eq(_E_hull, _d_hull(_dH_f, _S)),
    is_executable_in_sympy_override=False,
    description=(
        "Energy above the convex hull E_hull = d^{hull}[Delta H_f, S]: the "
        "vertical per-atom distance of the composition's formation energy "
        "above the convex hull of ALL competing phases in its chemical "
        "system (pymatgen PhaseDiagram.get_e_above_hull over a ComputedEntry "
        "set; mat-stability multiplies by 1000 to report meV/atom). The "
        "hull is an opaque convex-hull function of the competing entries; "
        "WHERE those entries come from is the hull_source scheme (the "
        "Materials Project database, R2SCAN or GGA+U thermo types, in the "
        "committed examples). Zero exactly for the ground state. Implicit "
        "(a convex-hull construction), so not sympy-executable."
    ),
)

compute_surface_energy = Operator(
    name="compute_surface_energy",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(SURFACE_ENERGY,),
    schemes={"slab_termination": "symmetric"},
    formula=sp.Eq(
        _gamma_surf,
        (_E_slab(_E_tot, _S) - _N_slab * _E_bulk(_E_tot, _S))
        / (2 * _A_surf),
    ),
    is_executable_in_sympy_override=False,
    description=(
        "Surface energy gamma_surf = (E_slab - N_slab E_bulk)/(2 A_surf): "
        "the slab-bulk energy difference per unit area, the factor 2 "
        "because a symmetric slab exposes the facet on BOTH faces (the "
        "slab_termination scheme records that convention; asymmetric "
        "terminations would change what is computed). E^{slab} and E^{bulk} "
        "are opaque selectors over the TotalEnergy family (the slab "
        "supercell built by pymatgen SlabGenerator for the chosen (hkl), "
        "and the bulk reference per formula unit, N_slab counting the bulk "
        "units in the slab); A_surf is the slab's in-plane cell area. "
        "Computed in eV/A^2 and quoted in J/m^2 (factor "
        "16.021766339999996; the skill truncates to 16.0218). Implicit "
        "(slab construction plus relaxations), so not sympy-executable."
    ),
)

compute_intercalation_voltage = Operator(
    name="compute_intercalation_voltage",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(VOLTAGE_STATE,),
    schemes={"working_ion": "Li"},
    formula=sp.Eq(
        _V_avg,
        -(_E_full(_E_tot, _S) - _E_empty(_E_tot, _S) - _n_ion * _mu_ion)
        / (_n_ion * _q_e),
    ),
    is_executable_in_sympy_override=False,
    description=(
        "Average intercalation voltage V_avg = -(E_full - E_empty - "
        "n_ion mu_ion)/(n_ion q_e): the Nernst energy difference of the "
        "intercalated (E^{full}) and de-intercalated (E^{empty}) cells, "
        "minus n_ion atoms of the working-ion metal reservoir (chemical "
        "potential mu_ion per atom), over the transferred charge n_ion q_e "
        "(one electron per ion for Li). With energies in eV the eV/e "
        "quotient is volts exactly, no Faraday factor. E^{full} and "
        "E^{empty} are opaque selectors over the TotalEnergy family (the "
        "de-intercalated cell built by Structure.remove_species in the "
        "skill); the working_ion scheme records which ion and reservoir "
        "(Li vs Li/Li+ in the committed LiFePO4 example). Implicit, so not "
        "sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    compute_formation_energy,
    compute_energy_above_hull,
    compute_surface_energy,
    compute_intercalation_voltage,
)
