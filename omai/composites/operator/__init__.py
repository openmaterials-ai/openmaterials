"""Composites (effective-medium) operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and its
symbol-dimension bindings as side effects (mirroring the thermodynamic-identities /
electronic-transport / mechanics packages), so validate_dag and the dimensional
gate see this domain's symbols. Here that side effect is load-bearing: four of the
five edges are executable closed forms the dimensional gate PROVES, so the new
field-symbol dimension bindings must be live before the gate runs.
"""
from omai.composites.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.composites.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.composites.operator.edges import EDGES
from omai.composites.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
