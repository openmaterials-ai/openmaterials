# Open follow-ups

The 2026-05-11 batch (visualization legend, helpful `to_operator`
error message, `OperationAdapterSpec` coverage across all four codes,
the four new operator-layer algorithmic conventions — `gv_method`,
`dos_broadening`, `gruneisen_method`, `delta_broadening` — the
auxiliary `|V₃|²` formula on `compute_linewidth`, smoke tests for the
derived-observable DAG nodes, and the two new ingest-skill rules) is
done. Items below are the next ones worth considering.

## Cross-code agreement

- **Render side-by-side formulas in the edge-click panel.** The
  `verify_operator_agreement.py` script proves that the three codes
  reference identical `Operation` objects, which is byte-identical
  sympy. The DAG viewer already has access to the per-edge formula via
  `_operation_to_json`; the next step is to display it. Today the panel
  shows op-spec metadata; adding `formula_latex` and `auxiliary_latex`
  (already in the JSON) as MathJax-rendered blocks would make the
  "operator promise" visible.

## Domain expansion

- **A second domain to stress-test the split.** Electronic-structure
  (band structure, DOS, Fermi surface) or molecular-dynamics
  (autocorrelation-based κ, MSD) would put pressure on the convention
  vocabulary — the question isn't whether the framework's gauge
  structure holds (it should), but whether the convention names we've
  built up for thermal transport translate or need extension.

## Representation layer

- **The empirical FC3 0.1 factor** in `experiments/silicon_shengbte/convert.py`
  is still unexplained. Trace it through phono3py's internal Φ³ storage
  vs ShengBTE's per-displacement scaling. A clean explanation either
  (a) adds a new convention value to the FC3 state or (b) reveals a
  units bug somewhere; either way the empirical fudge factor should go.
