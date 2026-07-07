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

## openmaterials.ai

An open, forkable **database for physics**: the schema is the physics itself, a graph of
typed quantities and the formulas relating them, with simulation and measured values appended
as instances. Browse it as an interactive [3D map](https://openmaterials.ai/map/), or read the
[vision](docs/vision.pdf) and the [architecture](docs/operator_representation_substrate.pdf).

For the full product picture (the free protocol and the hosted app), see [PRODUCT.md](PRODUCT.md).

The database is just files in this repo: `docs/data/graph.json` (variables + formulas, generated
from the operator layer), `docs/data/catalog.json` (per-node grounding: symbol, dimension,
description), `docs/data/codes.json` (per-code variable coverage), and `docs/data/instances/`
(one file per value). Rebuild the generated files with:

```bash
CUDA_VISIBLE_DEVICES="" PYTHONPATH=. python -m omai.map_data
```

To append a value, add a JSON file under `docs/data/instances/` and open a pull request.

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
python -m omai.thermal_transport.visualize   # writes docs/pipeline.html
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
                     #   shengbte, qe, ase, lammps, gpumd)
    visualize.py     # emits docs/pipeline.html
  materials/         # second domain, grown from AtomisticSkills: diffusion
                     #   subgraph, skills_catalog.json, ENCODING.md procedure
  map_data.py        # unified multi-domain export -> docs/data/*.json
examples/            # runnable tours; start with quickstart.py
experiments/         # full cross-code material studies (silicon, germanium, NaCl)
tests/               # pytest suite
docs/                # design docs + the openmaterials.ai site (map, learn, deck)
```

## Design

The architecture is documented in `docs/operator_representation_substrate.pdf`
(LaTeX source alongside it). Read the Principles and the two-worlds section
first.
