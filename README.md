# openmaterials-ai

A typed substrate for computational materials science. Workflows are directed
acyclic graphs of typed physics *spaces* connected by *operators* that carry
symbolic (sympy) formulas. Each external code (kaldo, phono3py, phonopy,
ShengBTE, LAMMPS, GPUMD) is a *representation*: a per-code mapping of its
numerical output onto the shared operator layer.

Because every quantity is typed and every edge carries its formula, the
framework reconciles results across codes mechanically, runs calculations
itself, and validates them. The longer aim is a semantic action space for AI
agents that reason over typed physics rather than text tokens.

## Install

```bash
pip install -e ".[dev]"   # Python 3.11+
```

## Try it

A self-contained tour that needs no external codes:

```bash
python examples/quickstart.py
```

It builds the operator DAG, derives molar heat capacity from a phonon
frequency array, and cross-checks two inputs at a gauge-invariant observable.

## Run the tests

```bash
pytest
```

## View the DAG

Regenerate the interactive single-file visualization (operator layer plus the
per-code columns):

```bash
python -m omai.thermal_transport.visualize   # writes docs/dag.html
```

## Layout

```
omai/
  operator/          # operator layer: Spaces, Operators, sympy formulas,
                     #   gauge discipline, validate_dag
  representation/    # the bridge: units, normalizations, per-code specs,
                     #   compare, and the execute/compose/cross-check runtime
  thermal_transport/
    operator/        # the lattice-thermal-transport DAG (Spaces + Operators)
    representation/  # per-code adapters (kaldo, phono3py, phonopy,
                     #   shengbte, ase, lammps, gpumd)
    visualize.py     # emits docs/dag.html
examples/            # runnable tours; start with quickstart.py
experiments/         # full cross-code material studies (silicon, germanium, NaCl)
tests/               # pytest suite
docs/                # design doc + dag.html
```

## Design

The architecture is documented in `docs/operator_representation_substrate.pdf`
(LaTeX source alongside it). Read the Principles and the two-worlds section
first.
