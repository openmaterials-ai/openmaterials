"""Materials operator DAG: re-exports the domain's NODES and EDGES registries."""
from omai.materials.operator.edges import EDGES
from omai.materials.operator.nodes import NODES

__all__ = ["NODES", "EDGES"]
