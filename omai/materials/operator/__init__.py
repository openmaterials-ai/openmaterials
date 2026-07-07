"""Materials operator DAG: re-exports the domain's NODES and EDGES registries."""
from omai.materials.operator import vocabulary as _vocabulary  # registers formula symbols
from omai.materials.operator import dimensions_registry as _dimensions_registry  # registers symbol dimensions
from omai.materials.operator.edges import EDGES
from omai.materials.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
