# Examples

Runnable tours of the framework.

## `quickstart.py`

Self-contained: needs only `omai`, numpy, and sympy (no external physics
codes, no data files). It shows the three things the framework does:

1. declares a typed operator DAG of physics quantities,
2. runs a calculation over it (derives molar heat capacity from a phonon
   frequency array via the validation engine's `compute`),
3. cross-checks two independent inputs at a gauge-invariant Observable.

```bash
python examples/quickstart.py
```

## Full cross-code material runs

`experiments/` holds the larger, code-backed studies (silicon, germanium,
NaCl) that drive kaldo, phonopy, phono3py, ShengBTE, and LAMMPS and verify
the operator layer's predictions against real output. Those need the
respective codes installed and write to `runs/` (git-ignored). Start with
`experiments/silicon_tersoff/spec_demo.py` and `run_validation.py`.
