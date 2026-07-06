# Skill: extend the operator DAG with a new node or edge

**Goal.** Add a new physical quantity, a new production formula for an existing
quantity, or a new family of variants to the operator-layer DAG, in a way that
respects the framework's commitments (one formula per edge, type discipline on
spaces, no cycles) and does not pollute downstream consumers.

**Prerequisites.**
- The quantity you want to add fits the existing two-layer split: it is
  symbolic / code-independent, not a numerical artefact of one adapter.
- You have read `docs/operator_representation_substrate.tex` § "DAG extension
  rules" (the canonical statement; this skill is the operational form).

## The three patterns

Pick exactly one. They are decision-equivalent and the substrate doc spells
out the formal definitions; this skill is the day-to-day checklist.

### Pattern A — type-level parameter on the space

When the variants change **gauge type** (Observable vs HiddenSpace) and the
parameterised space is **terminal** (or its parameterised consumers are
themselves a closed sub-branch).

Examples in the repo:
- `MeanFreeDisplacement[bte_solver=rta]` (HiddenSpace) vs `[direct_inverse]`
  (Observable). Propagates to `ThermalConductivity[bte_solver=...]` and
  stops.
- `ThermalConductivity[transport_model=lbte|wigner|qhgk]`. All leaves.

**Anti-pattern.** Putting a type parameter on an *intermediate* space. Every
downstream consumer then has to be parameterised in turn, and the entire
downstream sub-DAG inherits the pollution. We rejected this for NAC
specifically because parameterising `DynamicalMatrix[nac=...]` would have
forced `compute_dispersion`, `compute_group_velocity`, `compute_anharmonic_linewidth`,
`solve_bte_rta`, `solve_bte_direct`, and `contract_kappa_*` to all gain the
parameter.

### Pattern B — sibling spaces, converging edge

When several variants represent physically distinct contributions with
**different inputs** that must **combine** before a downstream consumer
uses them.

Examples in the repo:
- `AnharmonicLinewidth`, `IsotopicLinewidth`, `BoundaryLinewidth` →
  `sum_linewidths` → `TotalLinewidth`. `solve_bte_*` consumes only the
  total.
- `HelmholtzFreeEnergy`, `Entropy`, `InternalEnergy`, `HeatCapacity` —
  sibling Observables off `(Frequency, Temperature)`; no converging edge
  because there is no downstream that wants them combined, but the sibling
  structure is the same.

**Why not Pattern A.** The per-channel inputs differ (FC3+e vs
IsotopeAbundances+e vs GroupVelocity), so the channels are not just
parameter variants of one production formula. Sibling spaces make the
different input chains visible in the DAG diagram and let each code's
adapter declare independently which channels it supports.

### Pattern C — shared output node, alternative producing edges

When several formulas produce the **same-typed** output with the **same
gauge classification**, from different inputs. Downstream is unaware of
which path was taken; provenance and adapter specs record it.

Example in the repo:
- `compute_dynamical_matrix(FC2) → BareDynamicalMatrix`, then either
  `apply_nac_correction(BareDM, BornCharges, ε∞) → DynamicalMatrix`
  (polar branch) or `identity_dm(BareDM) → DynamicalMatrix` (non-polar
  branch). `compute_dispersion` consumes only `DynamicalMatrix`.

**The `BareDynamicalMatrix` intermediate is not cosmetic.** A literal
in-place modifier — one space with an edge that both consumes and produces
itself — would create a self-loop, which the DAG validator rejects. The
intermediate names the pre-modification version so the two alternative
edges have a well-defined source and the converging node is a true sink of
both.

## Decision flow

When you have a new quantity / variant to add, walk this in order:

1. **Is it a new physical quantity** (not a variant)? Add a new space node;
   add one or more edges producing it; declare gauge type, dimension,
   conventions, indices.

2. **Is it a variant that changes the gauge type** (Observable ↔
   HiddenSpace)? Pattern A — type-level parameter on the (terminal) space.

3. **Is it a variant with different inputs that physically combine** with
   the existing one? Pattern B — sibling state + a converging edge.

4. **Is it a same-typed variant, different production formula**? Pattern C —
   alternative producing edges into a shared output node, possibly with a
   small upstream intermediate to avoid a cycle.

If none of the above fits cleanly, the variant probably isn't well-modelled
as a graph operation. Reconsider whether it belongs at the operator layer
at all, or whether it's a representation-layer convention.

## Mechanical steps

After choosing a pattern:

1. **Operator layer.**
   - `omai/<domain>/operator/nodes.py`: declare new `Space` instances —
     `ObservableSpace`, or `HiddenSpace` with `kind="scaffolding"` or
     `"approximation"`, a `gauge_group`, and (for scaffolding) the
     `gauge_invariant_contractions`. Pattern A spaces carry the parameter
     in their name and a `labels` dict; Pattern B / C spaces have plain
     names. Declare `fields` with dimensions and index signatures.
   - `omai/<domain>/operator/edges.py`: declare new `Operator` instances.
     Each edge carries a sympy `formula` (use `auxiliary_formulas` when a
     kernel reappears in two edges — see `compute_anharmonic_linewidth` /
     `solve_bte_direct` for the |V₃|² pattern). Declare `schemes` only
     for choices a downstream comparison needs to distinguish.
   - `omai/<domain>/operator/vocabulary.py`: register the sympy
     base-symbol names the new spaces' formulas carry
     (`register_space_symbols`) and any bare constants
     (`register_formula_constants`) into `omai.operator.vocabulary`;
     the unified-validation test fails on unregistered symbols.
   - `omai/<domain>/operator/__init__.py`: re-export.

2. **Adapters.** For every code that produces the new quantity, add a
   `SpaceRepresentationSpec` and (where the operator declares schemes)
   an `OperatorRepresentationSpec` in
   `omai/<domain>/representation/<code>.py`. If a code does not produce
   the quantity, do not write a placeholder spec — its absence is the
   signal.

3. **Tests.** Add a smoke test in `tests/test_operator.py` asserting the
   node and edge identities, the inputs/outputs, and any new schemes. If the new edge has a non-trivial formula, assert that
   `formula.free_symbols` contains the expected ingredients.

4. **Visualization + map data.** `docs/pipeline.html` regenerates from
   `python -m omai.thermal_transport.visualize`, and the unified map data
   (`docs/data/*.json`) from `python -m omai.map_data`. No code changes
   are needed unless you are adding a new pattern that the renderer
   cannot lay out automatically.

5. **Substrate doc.** Update the node / edge counts in
   `docs/operator_representation_substrate.tex` § "The operator DAG" and
   mention the new convention name (if any) in the relevant edge bullet.

## Pitfalls

- **Cycles via in-place modifiers.** Pattern C looks like an "in-place
  refinement" but you must introduce the small intermediate node to keep
  it acyclic.
- **Cascading type parameters.** Pattern A on a non-terminal state. The
  validator does not flag this — discipline is on you.
- **Edge formulas that re-derive an existing kernel.** If a sub-expression
  appears in two edges, factor it into `auxiliary_formulas` on one of them
  and reference it from the other's description. The |V₃|² kernel is
  declared once on `compute_anharmonic_linewidth` and referenced from
  `solve_bte_direct`'s collision matrix.
- **Spaces with no clear gauge type.** Every Space must declare whether it
  is gauge-invariant (ObservableSpace) or gauge-dependent (HiddenSpace).
  HiddenSpaces must declare their `gauge_group` and the cross-code
  contractions that are gauge-invariant.
