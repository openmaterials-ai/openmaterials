"""Per-code adapter specs for the composites (effective-medium) domain.

Each submodule holds the SpaceRepresentationSpec instances for one code,
constructed against the shared operator DAG in `omai.composites.operator` so
cross-code agreement is checked at the operator level (per Principle 7).

The composite effective-medium formulas (Nan-EMT, with the Hasselman-Johnson
spherical-limit cross-check) live in the operator layer itself: the map's own
closed-form edges are the reference implementation, so no external code rail
is registered for them. Committed composite evidence keeps its provenance in
each instance's source ref.
"""
