"""Abstract layer: typed witnesses, symbolic operations, and abstract workflows.

Nothing in this layer carries numerical content. States are claims that an abstract
physics quantity exists, with a provenance recording how the claim was derived.
"""

from omai.abstract.physics_types import PhysicsType

__all__ = ["PhysicsType"]
