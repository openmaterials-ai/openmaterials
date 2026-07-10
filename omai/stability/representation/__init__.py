"""Per-code adapter specs for the stability domain.

Each submodule holds the SpaceRepresentationSpec / OperatorRepresentationSpec
instances for one code, constructed against the shared operator DAG in
`omai.stability.operator` so cross-code agreement is checked at the operator
level (per Principle 7):

  * `pymatgen`: the phase-diagram machinery (formation energy, hull
    distance, eV/atom), the SlabGenerator surface-energy flow (J/m^2), and
    the intercalation-voltage Nernst difference (volts), as the
    AtomisticSkills mat-* skills drive them.
  * `mat_surface_adsorption`: the mat-surface-adsorption skill (matcalc
    AdsorptionCalc adsorption-energy producer, eV); anchored in the
    matcalc/ASE scan. matcalc is the driver over the MLIP PES, recorded in
    notes (no separate matcalc rail, the atomate2 ruling).
"""
