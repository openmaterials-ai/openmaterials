"""Thermochemistry operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and
its symbol-dimension bindings as side effects (mirroring the dft / mechanics /
stability packages), so validate_dag and the dimensional gate see the
thermochemistry symbols.
"""
from omai.thermochemistry.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.thermochemistry.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.thermochemistry.operator.edges import EDGES
from omai.thermochemistry.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
