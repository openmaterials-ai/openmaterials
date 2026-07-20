# Multiscale distance: design

Date: 2026-07-19. Extends the 2026-07-18 configuration-distance design.

## The generalization

What env-ot established is scale-generic: a system at any scale is a weighted
distribution over carriers, and distance is transport between those
distributions with a scale-appropriate ground metric. Carriers by scale:
local electronic environments (electronic), atomic environments (atomistic,
shipped), phonon modes in (frequency, velocity, lifetime) space
(vibrational), defect and grain populations (mesoscale), configurations
themselves (ensembles and trajectories), values of a field or spectrum
(continuum and properties).

Two structural rules make this multiscale rather than multi-channel:

1. **Nesting.** The ground metric at scale k may itself be a distance from
   scale k-1 (trajectory distance over frames whose ground metric is
   configuration distance). Wasserstein-over-Wasserstein spaces remain
   metric spaces; cost is controlled by flattening each level to cached
   embeddings. The exact-vs-sampled duality recurses: a trajectory is always
   a sample of an ensemble, so trajectory level uses the energy-distance
   estimator by construction.
2. **Contraction.** Coarse-graining loses information, so a well-formed
   coarse metric never exceeds the fine one. Where that holds, coarse
   distances are certified lower bounds and archive search becomes a funnel
   with no false dismissals. Rigorous instance shipped here: the euclidean
   distance between weighted mean vectors lower-bounds Wasserstein-1
   (Kantorovich duality with a linear test function), so latent-lb@1
   certifiably bounds env-ot@1 on symmetry-exact sets. For the sampled
   (energy-distance) regime the analogous bound is not a theorem; the funnel
   takes an explicit margin there and says so.

There is also a scale axis inside a single configuration: a distance profile
d(A, B; r) over interaction radii. The AMD vector's k index is already a
length-scale ladder, and MACE's per-layer features have growing receptive
fields; exposing both turns "how far" into "far at which scale". (Shipped in
the scale-profiles change, separately.)

## What this phase ships

- `spectrum@1`: Wasserstein-1 between 1D mass distributions (DOS, spectra),
  CDF form, mass-normalized.
- `curve@1`: symmetric relative L2 for function-valued curves (kappa vs T);
  deliberately not OT, since a property curve is not a mass to transport.
- `latent-lb@1` plus the `lower_bounds` registry field and `funnel_search`:
  exact env-ot kNN with certified pruning.
- `traj-ot@1` and `keyframes`: trajectory identity and thinning; ground
  metric "mean" (fast, bound-consistent) or "env-ot" (sharp).
- `DistanceSpec.input`: registry entries now declare what their inputs ARE
  ("structure", "spectrum", "curve", "trajectory").

## Deliberately not in this phase

- phonon-ot (mode-space transport): needs kaldo artifact plumbing from MCG.
- Metric-per-map-node and lineage divergence localization: reframes the
  simulation-distance layer, so it gets its own spec and review.
- Material-vs-state quotient (inherent-structure distributions): an encoder
  pipeline flag, scheduled with the encoder benchmark.
