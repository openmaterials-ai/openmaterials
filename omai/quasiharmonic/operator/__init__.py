"""Quasi-harmonic operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and its
symbol-dimension bindings as side effects (mirroring the electronic-transport /
mechanics / thermochemistry packages), so validate_dag and the dimensional gate
see the quasi-harmonic symbols.
"""
from omai.quasiharmonic.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.quasiharmonic.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.quasiharmonic.operator.edges import EDGES
from omai.quasiharmonic.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
