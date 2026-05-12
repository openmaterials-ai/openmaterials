"""Lattice thermal-transport domain.

Layout:
  * operator.py        — the operator DAG: 12 nodes (states) and 11 edges
                         (operations) producing the lattice thermal
                         conductivity from a Born-Oppenheimer potential.
                         Every edge carries a operator formula.
                         Code-agnostic.
  * represented/      — per-code adapter specs declaring how each code's
                         outputs map onto the operator states (units,
                         conventions, discretization choices).
      ├── kaldo.py
      └── phono3py.py
"""
