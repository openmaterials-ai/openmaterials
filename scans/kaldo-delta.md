# kaldo DELTA: the QHGK/amorphous branch and beyond

A **delta / gap analysis** (not a fresh survey) of kaldo's public API against the
**32-node kaldo rail** in `docs/data/codes.json`. Triggered by a live finding:
parsing the QHGK paper (Isaeva et al. 2019) surfaced modal diffusivity,
participation ratio, generalized specific heat `c_nm`, mode-pair lifetimes, and
generalized velocity matrix elements as unmappable, and kaldo computes at least
the first two directly. Companion catalog: `scans/kaldo-delta.json` (9 entries).

Source (read-only, ground truth): the vendored `kaldo/` clone. Key files:
`kaldo/kaldo/phonons.py`, `conductivity.py`,
`observables/harmonic_with_q.py`, `observables/harmonic_with_q_temp.py`,
`forceconstants.py`, `quasiharmonic.py`. Every claim is anchored to a real
`file:line`.

**Graph snapshot at my end:** `docs/data/graph.json` = **98 nodes**, records 207,
242 links, 15 tiers, git HEAD `2834a4e`. Load-bearing nodes already present:
`Diffusivity` (tier **Diffusion**, `D = slope_MSD/(2d)`, from `MeanSquaredDisplacement`
- the mass self-diffusion coefficient, **the false-merge guardrail**),
`ElasticConstants` (tier Mechanics, `C = -d sigma/d eps`, from `Stress`+`Structure`),
`ThermalExpansion` (tier Quasi-harmonic, `alpha_V = alpha^qha(G_qha)`, from
`QHAGibbsEnergy`), `PhononDOS` (total only), plus the harmonic/BTE/kappa slice.

## What kaldo computes beyond its rail

kaldo is exercised as a single anharmonic-lattice-dynamics engine. Sweeping its
public API turns up **two genuinely new nodes**, **three QHGK/Wigner internals**
that should stay folded, and **two quantities that already have nodes but reached
by non-kaldo producers**:

| finding | kaldo API | class | verdict |
|---|---|---|---|
| ParticipationRatio | `Phonons.participation_ratio` | **new-candidate** | **mint a node** (dimensionless, 1/N) |
| ModalDiffusivity D_n | `Conductivity.diffusivity` | **new-candidate** | **mint a node** (mm^2/s; false-merge guardrail vs `Diffusivity`) |
| generalized c_nm | `Phonons.heat_capacity_2d` | internal / scheme | leave folded in QHGK+Wigner edges |
| S_ij flux operator | `_sij_x/_y/_z` | internal | leave folded (diagonal = GroupVelocity) |
| mode-pair width Gamma_n+Gamma_m | `diffusivity_bandwidth` | scheme | leave folded (single-mode = Linewidth[total]) |
| kaldo QHA alpha(T) | `quasiharmonic.calculate_qha` | cross-engine | alt producer edge -> `ThermalExpansion` |
| elastic tensor C_ijkl (GPa) | `forceconstants.elastic_prop` | cross-engine | alt producer edge -> `ElasticConstants` |
| projected pdos | `Phonons.pdos` | minor / scheme | projection scheme on `PhononDOS` |

## The two new nodes (headline)

### ParticipationRatio (dimensionless, per-mode localization)

`Phonons.participation_ratio` (`phonons.py:648`) is a **first-class formatted
output** (`_store_formats` at `phonons.py:447`). The math
(`calculate_participation_ratio`, `harmonic_with_q.py:335-344`): reshape the
eigenvector to `(n_modes, n_atoms, 3)`, form the per-atom amplitude
`a_i = sum_cart |e_i|^2`, then

```
PR = 1 / (N_atoms * sum_i a_i^2)
```

the standard **1/N** Bell/Dean localization ratio (range `1/N` to `1`), matching
the kaldo docstring's cited DOI `10.1103/PhysRevB.53.11469` (`phonons.py:652`).
This is the harmonic-side localization diagnostic of the QHGK/amorphous regime
(is a mode extended/propagating or localized/diffuson). **VERDICT: mint a new
node** `ParticipationRatio`, `(q,nu)`-indexed, dimensionless; kept apart from
every other dimensionless node by NAME (name-based identity,
`omai/operator/space.py`). Producer: `Eigenvectors -> ParticipationRatio`. HIGH
priority.

### ModalDiffusivity D_n (mm^2/s) and the FALSE-MERGE guardrail

`Conductivity.diffusivity` (`conductivity.py:303`) is the Allen-Feldman / QHGK
**per-mode heat-mode diffusivity**, the mode-resolved decomposition of
`kappa_QHGK`. The kernel (`calculate_diffusivity`, `conductivity.py:27-49`):

```
D_n^{ab} = S^a_left * [ pi * Lorentz(omega_n - omega_m, 2(Gamma_n+Gamma_m)) / (4 omega_n omega_m) ] * S^b_right
D_n      = (1/3) * (1/100) * trace_a( D_n^{aa} )                         # conductivity.py:434
```

**Units: mm^2/s** (docstring `conductivity.py:310`), CONFIRMED by the code: the
internal per-axis accumulation is `A^2*THz` (= `A^2/ps`), and the `1/100` factor
is exactly the `A^2/ps -> mm^2/s` conversion (`1 A^2/ps = 1e-8 m^2/s = 1e-2
mm^2/s`) after the `1/3` cartesian-trace average. Tested at
`test_diffusivity.py:34`.

**The guardrail (the point the brief flagged):** `D_n` has dimension
`L^2 T^-1` - **identical** to the existing `Diffusivity` node
(`D = slope_MSD/(2d)`, tier Diffusion, from `MeanSquaredDisplacement`). They are
**completely different physics** and must **never** be merged on dimension:

- existing `Diffusivity` = a **scalar** macroscopic Einstein **mass**-transport
  coefficient of diffusing atoms (tier Diffusion);
- kaldo `D_n` = a **per-mode `(q,nu)`-indexed heat-mode** diffusivity from the
  Allen-Feldman/QHGK flux-operator overlap (tier QHGK/amorphous).

A dimension-keyed merge would silently claim a phonon-mode heat diffusivity
equals an atomic mass-diffusion coefficient. **VERDICT: mint a distinct-named
node** (recommend `ModalDiffusivity` / `HeatModeDiffusivity`), kept apart by
NAME, with `{basis: per_mode, physics: allen_feldman_qhgk_heat, indices: (q,nu)}`
in its description prose. Its sum-over-modes relationship to `kappa_QHGK` is an
honest contraction edge. HIGH priority - it is the object the QHGK paper is about.

## The QHGK decomposition question: leave it folded

The brief asked whether decomposing the QHGK edge into `HiddenSpace` scaffolding
nodes for `c_nm`, `S_ij`, and the mode-pair lifetime earns its keep.
**RECOMMEND (do not decide): no.** Evidence:

1. **The edge already carries all three.** The QHGK formula
   (`edges.py:896-923`) and the Wigner-coherence formula (`edges.py:825-836`)
   spell out, in `sympy`, the `c[q,nu]` weight, the off-diagonal velocity
   `v^alpha_qnu * v^beta_qnup`, and the `(Gamma_n+Gamma_m)` Lorentzian width. A
   source comment (`edges.py:820`) already ties `c_nm` to
   `harmonic_with_q_temp.py:77-81`. The physics is documented at the edge, not
   lost.
2. **Each internal's physically-named projection is already a node.** `c_nm`'s
   diagonal (`n=m`) IS `HeatCapacity`; `S_ij`'s diagonal IS `GroupVelocity`
   (`harmonic_with_q.py:255-271` literally derives velocity as
   `Im(diag(rescaled S)))`); the single-mode `Gamma` IS `Linewidth[channel=total]`.
   A scaffolding node would be a near-duplicate distinguished only by a second
   mode index.
3. **No external consumer.** The only readers of `heat_capacity_2d`, `_sij_*`,
   and `diffusivity_bandwidth` are the QHGK/Wigner kappa assembly
   (`conductivity.py:393,399`).

The one point **against**: `heat_capacity_2d` IS a first-class formatted-storable
`Phonons` attribute (`harmonic_with_q_temp.py:15`), so a purist decomposition is
defensible. Net: with no consumer outside the kappa assembly it does not earn its
keep. **Leave folded; revisit only if such a consumer appears.**

### Wigner branch: same internals, already correctly scoped

The Wigner branch shares the QHGK internals exactly (the Simoncelli
frequency-weighted `c_nm` at `edges.py:828-830`, the off-diagonal velocity at
`:830`, the `(Gamma_n+Gamma_m)` Lorentzian at `:831-833`). It is already split
into the three **physically meaningful, separately published** channels -
`wigner_populations` (particle/LBTE), `wigner_coherences` (wave/off-diagonal),
`wigner` (sum) - which is the right granularity (Simoncelli, Marzari, Mauri,
Nat. Phys. 15, 809). Its coherence internals get the **same** recommendation as
QHGK: leave folded in the coherence-channel formula. No further Wigner nodes.

## Two quantities that already have nodes, via new kaldo producers

- **kaldo has a full QHA module.** `quasiharmonic.calculate_qha`
  (`quasiharmonic.py:357`) returns `thermal_expansion` (linear `alpha(T)` in
  `1/K`, `:255`; volumetric via `3*alpha`, `:609`), `lattice_constants` `a(T)`,
  `free_energies` (meV/atom, `:410`), and the `F(lattice,T)` surface (`:536`,
  minimized over lattice per T). The graph **already** has `ThermalExpansion`
  (tier Quasi-harmonic) but produced only via the phonopy `QHAGibbsEnergy` route.
  kaldo reaches the same `alpha(T)` by a **direct free-energy lattice scan** -
  an **alternative producer / cross-engine EXPECTED_AGREE** edge, not a new node.
  The lattice scan (`n_lattice_points`, `lattice_range`, `symmetry in
  {cubic,tetra,ortho,general}`) is a discretization **scheme**.

- **kaldo computes the elastic tensor from FC2.** `forceconstants.elastic_prop()`
  (`forceconstants.py:278`) returns `C_ijkl` (3,3,3,3) in **GPa**
  (`test_elastic.py`: C11=142.97, C12=75.85, C44=69.06 GPa for Si) via the
  long-wavelength expansion of the dynamical matrix, **not** a stress-strain
  scan. The graph **already** has `ElasticConstants` (tier Mechanics) produced
  from `Stress`+`Structure`. kaldo is a third **alternative producer**
  (`ForceConstants[order=2] -> ElasticConstants`), cross-engine EXPECTED_AGREE to
  the acoustic-sum-rule approximation, not bit-exact.

## Coverage confirmed (the harmonic/BTE/kappa slice)

`Frequency` (linear THz), `GroupVelocity` (A*THz), `HeatCapacity` (J/K per mode),
`HelmholtzFreeEnergy` (eV/mode; `zero_point_harmonic_energy` is its T=0 limit,
`phonons.py:862`, not a separate node), the `Linewidth` channels (angular_THz),
`PhaseSpace3Phonon`, `Eigenvectors`, the BTE `ThermalConductivity`/`mean_free_path`
variants, the three Wigner kappa variants, and `ThermalConductivity[transport_model=qhgk]`
itself all match source. `population`, `sparse_phase/sparse_potential`,
`_ps_gamma_and_gamma_tensor`, `_generalized_diffusivity`, `flux` are internal
scaffolding, correctly absent from the rail.

## Units and conventions (from kaldo source)

1. **ModalDiffusivity: mm^2/s** (`conductivity.py:310` docstring; `:434` the
   `1/3 * 1/100` trace-average + `A^2/ps -> mm^2/s` conversion). Internal per-axis
   accumulation is `A^2*THz` (`A^2/ps`).
2. **ParticipationRatio: dimensionless, 1/N** (`PR` in `[1/N, 1]`;
   `harmonic_with_q.py:343`).
3. **generalized c_nm: J/K** (`harmonic_with_q_temp.py:54-56`); quantum
   `c_nm = hbar w_n w_m/T*(n_n-n_m)/(w_m-w_n)`, classical `k_B`, degenerate
   `(c_n+c_m)/2`.
4. **diffusivity_bandwidth: rad/ps** (`conductivity.py:75`); default `= bandwidth/2`
   (`:376`); kernel `sigma = 2(db_n+db_m)` (`:31`).
5. **elastic_prop: GPa** (`forceconstants.py:280,393`).
6. **kaldo QHA:** `thermal_expansion` `1/K` (linear), `free_energies` meV/atom,
   `lattice_constants` Angstrom.

## Traps

- **FALSE-MERGE (headline):** kaldo ModalDiffusivity (mm^2/s heat-mode) shares
  the `L^2 T^-1` exponent vector with the existing mass `Diffusivity` node
  (`slope_MSD/(2d)`, Diffusion). Different physics; keep apart by NAME.
- **`.diffusivity` is QHGK-scoped:** `Conductivity.diffusivity` returns
  `self._diffusivity`, set ONLY in the `method=='qhgk'` branch
  (`conductivity.py:248,312-315`). After an rta/inverse run it logs and returns
  `None`.
- **GroupVelocity is the diagonal of the QHGK flux operator** (`harmonic_with_q.py:255-271`)
  - same object, different index depth; do not double-count.
- **`ThermalExpansion` and `ElasticConstants` already exist** via non-kaldo
  producers; add producer edges, do not mint duplicates.
- **`free_energy`/`zero_point_harmonic_energy`** are both the `HelmholtzFreeEnergy`
  node; ZPE is the T=0 limit.
- **The QHGK/Wigner Lorentzian uses `(Gamma_n+Gamma_m)^2`** (the mode-PAIR width,
  `edges.py:903-904`), not a single lifetime.

## Open questions

1. ModalDiffusivity node name: `ModalDiffusivity` vs `HeatModeDiffusivity` vs
   `ModeDiffusivity`? (Must be distinct from `Diffusivity`.)
2. Tier for the two new nodes: reuse Harmonic/QHGK, or add a
   Localization/Disorder tier grouping the amorphous-branch diagnostics
   (participation ratio, modal diffusivity, propagon/diffuson/locon)?
3. A downstream propagon/diffuson/locon classification node (thresholded on PR
   and D_n), or a representation on the two nodes? (kaldo exposes PR and D_n and
   leaves the cut to the user.)
4. kaldo QHA -> `ThermalExpansion`: encode the alternative producer now, or defer
   to a cross-engine agree test? (Node exists; only the edge is missing.)
5. kaldo `elastic_prop` -> `ElasticConstants`: alternative FC2 producer now, or
   defer? (Agreement is only to the acoustic-sum-rule approximation, not
   bit-exact.)
6. projected pdos: a projection scheme on `PhononDOS` (`p_atoms`, `direction`) or
   a distinct `ProjectedPhononDOS` node? (Recommend scheme.)
7. c_nm / S_ij / mode-pair-lifetime: recommendation is leave-folded, but the
   orchestrator decides. Revisit if any consumer outside the kappa assembly reads
   `heat_capacity_2d` or the flux operator.

**Nothing blocked the scan.** All targeted kaldo modules (`phonons.py`,
`conductivity.py`, `observables/harmonic_with_q*.py`, `forceconstants.py`,
`quasiharmonic.py`) and the `test_diffusivity.py` / `test_elastic.py` reference
values were present in the vendored tree; every unit was confirmed against
source.
