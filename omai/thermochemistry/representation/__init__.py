"""Per-code adapter specs for the thermochemistry domain.

Each submodule holds the SpaceRepresentationSpec / OperatorRepresentationSpec
instances for one code, constructed against the shared operator DAG in
`omai.thermochemistry.operator` so cross-code agreement is checked at the
operator level (per Principle 7):

  * `pycalphad`: the CALPHAD Gibbs-minimization engine (GM molar Gibbs energy,
    HM enthalpy, MU chemical potentials, NP phase fractions, the binplot
    transition temperatures, and the TDB assessed-database artifact) as the
    AtomisticSkills mat-calphad-* skills drive it.
"""
