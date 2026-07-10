"""Molecular operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and its
symbol-dimension bindings as side effects (mirroring the electronic-transport /
mechanics / thermochemistry / quasi-harmonic packages), so validate_dag and the
dimensional gate see the molecular symbols.
"""
from omai.molecular.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.molecular.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.molecular.operator.edges import EDGES
from omai.molecular.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
