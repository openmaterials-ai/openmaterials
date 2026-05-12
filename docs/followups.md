# Open follow-ups

Recorded from session discussions. Items here aren't blocking but are
worth doing.

## Visualization layer
- **Legend wording** for the dashed/hidden-leaf convention. Today's
  legend says "Implicit (no spec yet)" for the dashed circles. With the
  leaf-hiding rule live, the legend should also note: *leaf states
  (DAG outputs) are not drawn when the code lacks an adapter spec for
  them; intermediate states stay dashed.* Make the absence-as-signal
  discoverable.

## Representation layer
- **Helpful errors when units are missing.** `to_operator` (and the old
  `inter_representation_factor`) will fail with a raw `KeyError` if either
  adapter spec lacks `observable_units` for the field being queried.
  Catch this and emit a clearer message, e.g. *"adapter X has no unit
  declared for field Y of state Z — cannot canonicalize. Add an
  observable_units entry to its StateAdapterSpec."* Most of the new
  scaffolding specs (Temperature, FC2/FC3, DM, Eigenvectors, MFD,
  PhaseSpace3Phonon, Gruneisen, DOS) intentionally omit units —
  attempting numerical comparison on them today gives an opaque
  failure.

- **OperationAdapterSpec coverage** lags `StateAdapterSpec` coverage.
  We have op-specs for compute_force_constants[2/3], compute_linewidth,
  solve_bte_direct, compute_heat_capacity. Missing op-specs (for any
  code): compute_dispersion, compute_dynamical_matrix,
  compute_group_velocity, provide_potential, provide_temperature,
  solve_bte_rta, contract_kappa_rta, contract_kappa_direct,
  contract_volumetric_heat_capacity, contract_molar_heat_capacity,
  compute_dos, compute_gruneisen, compute_phase_space_3phonon. The
  diagram doesn't yet visualize op-coverage; when it does, these gaps
  will surface. Adding them is mechanical once we decide what
  algorithmic conventions to capture per op.

## Operator layer
- **More `auxiliary_formulas` on Operations.** `solve_bte_direct` uses
  `auxiliary_formulas` to spell out the collision matrix M. The
  parallel structural definition of `|V₃|²` inside `compute_linewidth`
  is inlined in the main formula; pulling it out as an auxiliary
  equation would make the M/Ξ correspondence explicit and tighten the
  cross-code formula-identity check.

- **Tests for the newer DAG nodes.** `test_symbolic.py` only checks
  total node/edge counts. Worth adding smoke tests asserting
  `compute_dos.inputs == (Frequency,)`, `compute_gruneisen.inputs ==
  (FC2, FC3, Frequency, Eigenvectors)`,
  `compute_phase_space_3phonon.inputs == (Frequency,)`, and that the
  outputs land in the right node identities.

## Skill / documentation
- **Skill rule: grep before declaring "out of scope."** Two times in
  one session I prematurely listed a state as missing in a code (kaldo
  Phase Space, kaldo DOS, phonopy Gruneisen) when a grep against the
  source tree would have surfaced a clean API. The skill should
  require a search-before-classify step.

- **Skill rule: leaves vs intermediates.** Adapter ingestion should
  prioritize leaf-state specs (DAG outputs) over intermediate ones,
  because leaves drive the visualization's hide/dash decision and are
  the primary cross-code-comparable observables.
