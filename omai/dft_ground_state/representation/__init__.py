"""Representation adapters for the DFT ground-state domain.

The QE representation (energy, forces, stress, structure) lands in Task 3.
build_codes discovers SpaceRepresentationSpec / OperatorRepresentationSpec
objects by iterating this package's modules, so re-exports from qe.py are wired
in here.
"""
