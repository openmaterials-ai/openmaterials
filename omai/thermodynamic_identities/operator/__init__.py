"""Thermodynamic-identities operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and its
symbol-dimension bindings as side effects (mirroring the electronic-transport /
mechanics / thermochemistry / quasi-harmonic / molecular packages), so validate_dag
and the dimensional gate see this domain's symbols. Here that side effect is
load-bearing: every edge is an executable closed form the dimensional gate PROVES,
so the four new field-symbol dimension bindings must be live before the gate runs.
"""
from omai.thermodynamic_identities.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.thermodynamic_identities.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.thermodynamic_identities.operator.edges import EDGES
from omai.thermodynamic_identities.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
