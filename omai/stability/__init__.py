"""The stability domain: FormationEnergy, EnergyAboveHull, SurfaceEnergy,
Voltage, AdsorptionEnergy.

Phase stability and electrochemistry from the pymatgen scan (AtomisticSkills,
arXiv 2605.24002): the per-atom formation energy against elemental references,
its distance to the convex hull, the per-facet surface energy, and the average
intercalation voltage. All four are energy differences over the per-cell
TotalEnergy the ground-state domain already carries; the per-atom quantities
are DISTINCT nodes from TotalEnergy (the scan's highest-risk trap: pymatgen's
energy_per_atom / formation_energy_per_atom / e_above_hull are per-atom
currencies that never map to the per-cell node).

The matcalc/ASE scan (arXiv 2605.24002) added AdsorptionEnergy (2026-07-10):
the surface-energetics kin of SurfaceEnergy, an extensive (per-configuration,
NOT per-atom) energy difference E_adslab - E_slab - E_adsorbate, driven by
mat-surface-adsorption via matcalc AdsorptionCalc.

Deferred with reasons (from the matcalc/ASE scan): the QHA finite-T
thermodynamics domain (Gibbs G(T), thermal expansion alpha(T), Cp(T); driven
by mat-qha-thermal-expansion via matcalc QHACalc) is owed a basis
reconciliation to the thermochemistry domain's second slice before it lands;
the NEB migration barrier (chem-neb-barrier via raw ase.mep, not matcalc
NEBCalc) is queued with the MD / chem family task.

Deferred candidates from the scan's new-node list, each with why:

  * XRD pattern I(2theta) and Raman intensity I(omega): function-valued
    characterization signals; they need a spectrum type (an axis-and-values
    representation with binning semantics) the operator layer does not have
    yet. High value, wrong shape for a scalar-node slice.
  * Defect formation energy E_f: needs the chemical-potential machinery
    (reservoir choices, charge states, Freysoldt corrections) as first-class
    schemes; the committed examples span neutral and charged conventions
    that must not be merged silently.
  * Grain-boundary energy gamma_gb: the surface-energy family's second
    slice (same J/m^2 difference form, GrainBoundaryGenerator import path
    moved across pymatgen versions and needs its own version pin).
  * Bare energy-per-atom: subsumed, deliberately not a node: it is
    TotalEnergy / N_atoms, a normalization of an existing quantity, not a
    distinct physical quantity (unlike the formation energy, which also
    subtracts elemental references).
"""
