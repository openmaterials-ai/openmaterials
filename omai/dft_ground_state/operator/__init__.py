"""DFT ground-state operator DAG: re-exports the domain's NODES and EDGES.

Importing this package registers the domain's formula-symbol vocabulary and its
symbol-dimension bindings as side effects (mirroring the materials package), so
validate_dag and the dimensional gate see the ground-state symbols.
"""
from omai.dft_ground_state.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.dft_ground_state.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.dft_ground_state.operator.edges import EDGES
from omai.dft_ground_state.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
