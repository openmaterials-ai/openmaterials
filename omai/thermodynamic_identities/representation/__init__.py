"""Per-code adapter specs for the thermodynamic-identities domain: none.

This domain encodes identities that COMBINE the map's existing formulas, not new
measurements, so no code emits its nodes directly (a code that reports ZT or a
power factor does so through the underlying transport tensors, whose rails already
attach to the ElectricalConductivity / Seebeck / thermal-conductivity nodes this
domain contracts). build_codes discovers SpaceRepresentationSpec objects here;
there are none, which is correct and intentional. The package exists so the Domain
descriptor has a representation_package to point at, symmetric with every other
domain.
"""
