"""Lattice thermal-transport domain.

Layout:
  * symbolic.py        — the abstract DAG: 12 nodes (states) and 11 edges
                         (operations) producing the lattice thermal
                         conductivity from a Born-Oppenheimer potential.
                         Every edge carries a symbolic formula.
                         Code-agnostic.
  * materialized/      — per-code adapter specs declaring how each code's
                         outputs map onto the symbolic states (units,
                         conventions, discretization choices).
      ├── kaldo.py
      └── phono3py.py
"""
