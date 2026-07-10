r"""Operator nodes of the stability domain.

Phase stability and electrochemistry: four ObservableSpaces, all scalar
energy-difference observables built over the ground-state TotalEnergy and the
Structure it belongs to.

Node table:

  Node             quantity tag       dimension                  indices
  ---------------  -----------------  -------------------------  -------
  FormationEnergy  formation_energy   ENERGY                     ()
  EnergyAboveHull  energy_above_hull  ENERGY                     ()
  SurfaceEnergy    surface_energy     ENERGY_PER_LENGTH_SQUARED  ()
  Voltage          voltage            VOLTAGE (M L^2 T^-3 I^-1)  ()
  AdsorptionEnergy adsorption_energy  ENERGY                     ()

AdsorptionEnergy (added 2026-07-10 from the matcalc/ASE scan) is surface
energetics kin to SurfaceEnergy: a scalar ENERGY per adsorbate-surface
configuration (eV, extensive, NOT per-atom, so plain ENERGY like the per-cell
energy differences it is built from). The configuration (adsorbate, facet,
adsorption site) rides in the instance conditions and the producing edge's
scheme, not in the node's index signature, exactly as the facet does for
SurfaceEnergy. Driven by mat-surface-adsorption via matcalc AdsorptionCalc.

Per-atom discipline. FormationEnergy and EnergyAboveHull are INTENSIVE
per-atom quantities (eV/atom, the phase-diagram currency), distinct nodes from
the extensive per-cell TotalEnergy: the per-atom normalization is declared
here in the descriptions and in the representation units (ev_per_atom), NOT in
the dimension, which is plain ENERGY. This resolves the scan's highest-risk
trap (pymatgen's energy_per_atom family never maps to the per-cell node).

SurfaceEnergy shares the M T^-2 exponents with ForceConstants[order=2]
(energy per area vs force per length): same dimension, physically distinct
quantities, kept apart by the quantity tag that enters node identity. It is a
scalar per facet; the Miller index (hkl) of the facet lives in the instance
conditions and representation notes, not in the node's index signature (no
registered hkl index kind, deliberately).

Voltage is the map's first use of the electric-current axis (the volt,
M L^2 T^-3 I^-1); eV per elementary charge = 1 V exactly, so the eV energy
differences of the Nernst form are already volts.
"""
from __future__ import annotations

from omai.operator.dimensions import (
    ENERGY,
    ENERGY_PER_LENGTH_SQUARED,
    VOLTAGE,
)
from omai.operator.space import Field, ObservableSpace, Space

FORMATION_ENERGY = ObservableSpace(
    name="FormationEnergy",
    fields=(Field("dH_f", ENERGY, indices=()),),
    tier="Stability",
    description=(
        "Formation energy per atom Delta H_f: the energy of the compound "
        "relative to the composition-weighted elemental reference phases, "
        "divided by the atom count. INTENSIVE, in eV/atom (the per-atom "
        "normalization is this quantity's definition, not a unit variant of "
        "the per-cell TotalEnergy; the formation energy also subtracts the "
        "elemental references, so it is a genuinely distinct quantity). "
        "Negative for compounds stable against decomposition into the "
        "elements; the elemental reference set is the producing edge's "
        "scheme (Materials Project references in the committed examples)."
    ),
)

ENERGY_ABOVE_HULL = ObservableSpace(
    name="EnergyAboveHull",
    fields=(Field("E_hull", ENERGY, indices=()),),
    tier="Stability",
    description=(
        "Energy above the convex hull E_hull: the per-atom distance of a "
        "composition's formation energy above the hull of all competing "
        "phases in its chemical system. INTENSIVE, in eV/atom (reported "
        "meV/atom by mat-stability, a factor 1000); exactly zero for the "
        "thermodynamic ground state, positive for metastable phases. Its "
        "provenance is a SET of competing-phase energies (the hull), "
        "recorded by the producing edge's hull_source scheme; the single "
        "most-used output across the stability skills."
    ),
)

SURFACE_ENERGY = ObservableSpace(
    name="SurfaceEnergy",
    fields=(Field("gamma", ENERGY_PER_LENGTH_SQUARED, indices=()),),
    tier="Stability",
    description=(
        "Surface energy gamma of a crystal facet: the excess energy per "
        "unit area of creating the surface, gamma = (E_slab - N E_bulk)/"
        "(2A) for a symmetric slab exposing the facet on both faces. Scalar "
        "per facet: the Miller index (hkl) is carried by conditions and "
        "representations, not by the node's index signature. Dimension "
        "M T^-2 (energy per area), the same exponents as the force "
        "constants (force per length) but a distinct quantity kept apart "
        "by tag; canonical eV/A^2, conventionally quoted in J/m^2 "
        "(1 eV/A^2 = 16.021766339999996 J/m^2). The Wulff construction "
        "aggregates per-facet gammas into a morphology downstream."
    ),
)

VOLTAGE_STATE = ObservableSpace(
    name="Voltage",
    fields=(Field("V_avg", VOLTAGE, indices=()),),
    tier="Stability",
    description=(
        "Average intercalation (open-circuit) voltage V_avg of an electrode "
        "against the working-ion metal: the Nernst energy difference of the "
        "intercalated and de-intercalated cells (minus the metal reservoir) "
        "over the transferred charge, V = -(E_full - E_empty - n mu_metal)/"
        "(n e). The map's first current-axis quantity (volts, M L^2 T^-3 "
        "I^-1); since the energies are eV and the charge is n elementary "
        "charges, eV/e = 1 V exactly and no Faraday factor appears. The "
        "working ion (Li in the committed example) is the producing edge's "
        "scheme."
    ),
)

ADSORPTION_ENERGY = ObservableSpace(
    name="AdsorptionEnergy",
    fields=(Field("E_ads", ENERGY, indices=()),),
    tier="Stability",
    description=(
        "Adsorption energy E_ads of an adsorbate on a crystal surface, the "
        "energy difference E_ads = E_adslab - E_slab - E_adsorbate of the "
        "relaxed adsorbate-on-slab configuration against the isolated clean "
        "slab and the isolated adsorbate. Scalar per adsorbate-surface "
        "configuration in eV; negative for favourable (bound) adsorption. "
        "EXTENSIVE (an energy difference over whole cells), plain ENERGY, NOT "
        "the per-atom currency of FormationEnergy and EnergyAboveHull: it is "
        "surface energetics kin to SurfaceEnergy, the same M L^2 T^-2 as the "
        "TotalEnergy differences it is built from. The adsorbate, the facet "
        "(hkl), and the adsorption site (ontop / bridge / hollow) are carried "
        "by conditions and the producing edge's scheme, not by the node's "
        "index signature (no per-site index kind, deliberately: distinct "
        "sites are distinct configurations, distinct instances)."
    ),
)

NODES: tuple[Space, ...] = (
    FORMATION_ENERGY,
    ENERGY_ABOVE_HULL,
    SURFACE_ENERGY,
    VOLTAGE_STATE,
    ADSORPTION_ENERGY,
)
