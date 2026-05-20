"""Lattice thermal-transport domain.

Layout:
  * operator.py        — the operator DAG: 12 nodes (Spaces) and 11 edges
                         (Operators) producing the lattice thermal
                         conductivity from a Born-Oppenheimer potential.
                         Every edge carries an operator formula.
                         Code-agnostic.
  * represented/      — per-code adapter specs declaring how each code's
                         outputs map onto the operator Spaces (units,
                         normalizations, schemes, discretization choices).
      ├── kaldo.py
      └── phono3py.py
"""
