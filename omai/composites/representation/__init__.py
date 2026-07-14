"""Per-code adapter specs for the composites (effective-medium) domain.

Each submodule holds the SpaceRepresentationSpec instances for one code,
constructed against the shared operator DAG in `omai.composites.operator` so
cross-code agreement is checked at the operator level (per Principle 7):

  * `materialscodegraph`: the closed-form Nan-EMT / Hasselman-Johnson composite
    thermal-conductivity tool (mcg/tools/composite/emt.py, ported verbatim to the
    frontend), serving the random and aligned effective conductivities and the
    depolarization factors in SI units.
"""
