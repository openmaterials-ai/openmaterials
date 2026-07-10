"""The molecular domain: molecular quantum chemistry and reaction energetics.

The map's first molecular code slice (AtomisticSkills arXiv 2605.24002: the ORCA
quantum-chemistry skills and the MLIP/chem reaction skills). Three per-molecule
energy nodes (the HOMO-LUMO gap, the NEB reaction barrier, the bond dissociation
energy) on the per-MOLECULE basis, distinct from the periodic per-cell
energetics, plus two rails (orca, openmm) that also cover the pre-existing
TotalEnergy, Forces, Temperature, Pressure, and Trajectory nodes.
"""
