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

## Review verdicts (2026-07-11)

Adversarial deep review of commit `1dbfee8`'s catalog (9 entries). Default to
distrust. Every source anchor was re-opened in the vendored `kaldo/` tree; the
`ModalDiffusivity` unit chain was recomputed from the code (the `dirac_kernel`
delta, the `sij` rescaling, the `omega` convention), not read off the docstring;
the participation-ratio exponent was verified line by line; the three QHGK named
projections were checked against `omai/thermal_transport/operator/edges.py:896-923`
and the `compute_kappa_qhgk` inputs; the Si elastic numbers were traced to their
test assertions; graph state was re-checked against `docs/data/graph.json`.

**Headline: every claim survived. Tally over the 9 entries: 9 CONFIRMED, 0
corrected, 0 rejected. No status flipped. No unit and no physics relationship was
wrong.** Two non-substantive anchor nits are noted inline and did not change any
verdict.

**Snapshot note.** The scan header records `git_head 2834a4e`. At review time HEAD
is `1dbfee8` (this delta scan's own commit); `docs/data/graph.json` is unchanged
between the two (the scan commit touched `scans/` only) and still reads **98 nodes,
242 links, 15 tiers**, matching the snapshot. `Diffusivity`, `ElasticConstants`,
`ThermalExpansion`, `PhononDOS`, `GroupVelocity`, `HeatCapacity`,
`HelmholtzFreeEnergy` are all present; `ParticipationRatio` and `ModalDiffusivity`
are absent, exactly as the `relevant_present` / `relevant_absent` lists claim. (The
snapshot's `records 207` is not derivable from `graph.json`, which carries no
records field; the node/link/tier counts and all present/absent facts hold.)

### The participation-ratio exponent: the trap was avoided (load-bearing)

The brief flagged a specific failure mode: writing `PR = 1/(N sum_i a_i^2)` where
`a_i` is a raw normalized amplitude would give `sum_i a_i^2 = 1` identically. The
scanner did **not** fall into it. `calculate_participation_ratio`
(`harmonic_with_q.py:341-343`) reshapes the eigenvector to `(n_modes, n_atoms, 3)`,
forms `a_i = reduce_sum(e * conj(e), axis=2)` (the **per-atom** amplitude, summed
over the 3 cartesian components, line 341), then `tf.math.square(a_i)` (line 342),
then `reciprocal(reduce_sum(a_i^2, axis=1) * n_atoms)` (line 343). So

```
PR = 1 / (N * sum_i a_i^2),   a_i = sum_cart |e_i|^2
   = 1 / (N * sum_i (sum_cart |e_i|^2)^2)
```

The square is applied to the **cartesian-summed per-atom amplitude**, not to a bare
component, so the sum is not identically 1. This is the Bell/Dean `1/N` ratio, range
`1/N..1`. **Exponent right.** DOI `10.1103/PhysRevB.53.11469` confirmed at
`phonons.py:652`.

### The ModalDiffusivity unit chain: recomputed, it holds (load-bearing)

Working the dimensions from the code rather than the docstring: `omega = 2*pi*freq`
in `rad/ps`; `velocity` is `A/ps` (`phonons.py:685`); `diffusivity_bandwidth` is
`rad/ps`. In `calculate_diffusivity` (`conductivity.py:27-49`):

- `lorentz_delta(delta_omega, sigma) = (1/2pi) sigma / (delta_omega^2 + (sigma/2)^2)`
  has units `ps/rad` (`dirac_kernel.py:25-27`);
- `kernel = pi * lorentz / (omega_n omega_m 4)` has units `ps^3/rad^3`;
- `sij` has units `A*rad/ps^2` (from `velocity_AF = sij / (2pi * 2 * sqrt(omega_n omega_m))`,
  `harmonic_with_q.py:268`, with `velocity` in `A/ps`);
- so `diffusivity = sij_left * kernel * sij_right = (A*rad/ps^2)^2 * ps^3/rad^3 =
  A^2/(ps*rad) = A^2/ps` (radian is dimensionless) `= A^2*THz`.

So the internal per-axis accumulation **is** `A^2/ps`, as claimed. The final
`diffusivity = 1/3 * 1/100 * contract('knaa->kn', diffusivity_with_axis)`
(`conductivity.py:434`): `'knaa->kn'` traces the 3 diagonal cartesian axes, `1/3`
averages them, and `1/100` is **exactly** the `A^2/ps -> mm^2/s` conversion
(`1 A^2/ps = 1e-20 m^2 / 1e-12 s = 1e-8 m^2/s = 1e-2 mm^2/s`). Returned `D_n` in
`mm^2/s` (`conductivity.py:310`). **QHGK-scoped:** `self._diffusivity` is set only
in the `case 'qhgk'` branch (`conductivity.py:248`); `.diffusivity` returns it via
`try/except` and otherwise logs "You need to calculate the conductivity QHGK first."
and returns `None` (`conductivity.py:312-315`).

### The three QHGK named projections: factually right

Checked against `edges.py:896-923` and the `compute_kappa_qhgk` inputs
(`HEAT_CAPACITY, FREQUENCY_STATE, GROUP_VELOCITY, TOTAL_LINEWIDTH, TEMPERATURE_STATE`,
`edges.py:912`): `c_nm`'s diagonal **is** `HeatCapacity` (the `c[q,nu]` factor, line
901); `S_ij`'s diagonal **is** `GroupVelocity` (`calculate_velocity` takes
`Im(diag(rescaled S))`, `harmonic_with_q.py:271`, matching the graph's `GroupVelocity`
formula `v = e-bar.(dD/dq).e / (2 omega)`); the single-mode `Gamma` **is**
`Linewidth[channel=total]` (`TOTAL_LINEWIDTH`, the `(Gamma+Gamma')` width at
`edges.py:902-904`). All three correct. The GroupVelocity double-count trap
(same flux operator, different index depth) is precise.

### The bonus finds: anchors and numbers verified

`calculate_qha` (`quasiharmonic.py:357`) returns `thermal_expansion` (linear
`alpha(T)` in `1/K`, `calculate_thermal_expansion` `np.gradient(a,T)/a` at :264,
docstring `:254`), `free_energies` (meV/atom, docstring `:410`), volumetric via
`3*alpha` in `get_volumetric_thermal_expansion` (`:609`). `elastic_prop`
(`forceconstants.py:278`) returns `C_ijkl` in GPa (`evperang3togpa` at `:393`) via
the FC2 long-wavelength expansion (DOI 10.1002/pssb.200879604, `:294`), **not** a
stress scan. **The Si numbers are real, not invented:** `test_elastic.py` asserts
`cijkl[0,0,0,0]==142.97` (C11, `:19`), `cijkl[0,0,1,1]==75.85` (C12, `:24`),
`cijkl[1,2,1,2]==69.06` (C44, `:29`), `significant=3`, from the `si-crystal/` eskm
fixture.

### The two anchor nits (non-substantive, no verdict change)

- `'participation_ratio': 'formatted'` in `_store_formats` is at `phonons.py:446`,
  not `:447` (off by one). Still a first-class formatted output.
- The `calculate_diffusivity` kernel description writes `sij_right = conj(...)`;
  that conjugation is the **crystal path only** (`conductivity.py:413-414`
  conjugates `sij_right` only when `not _is_amorphous`; the amorphous real-`Gamma`
  path skips it). The core Allen-Feldman kernel formula is correct.

### Orchestrator decisions (node names; the producer-edges call; the tier question)

1. **MINT `ParticipationRatio`** (dimensionless, `(q,nu)`-indexed). HIGH.
   Producer `Eigenvectors -> ParticipationRatio`. Kept apart from every other
   dimensionless node by NAME.
2. **MINT `ModalDiffusivity`** (or `HeatModeDiffusivity` - the name is the open
   question), `mm^2/s`, `L^2 T^-1`, `(q,nu)`-indexed, QHGK/amorphous tier. HIGH.
   FALSE-MERGE GUARDRAIL: same `L^2 T^-1` exponent as the existing mass
   `Diffusivity` node; keep apart by DISTINCT NAME, never merge on dimension.
3. **DO NOT decompose the QHGK/Wigner edge** into `HiddenSpace` nodes for `c_nm`,
   `S_ij`, or the mode-pair lifetime. Record `diffusivity_bandwidth` /
   `diffusivity_shape` / `diffusivity_threshold` as SCHEMES on `compute_kappa_qhgk`.
4. **Producer-edges-now-or-later:** kaldo QHA `-> ThermalExpansion` and kaldo
   `elastic_prop -> ElasticConstants` are cross-engine alternative-producer edges
   into EXISTING nodes (no duplicates). MEDIUM. **Recommend DEFER both** until a
   cross-engine EXPECTED_AGREE test needs the second route; add now only if that
   test is being built. Tolerance must be approximation-level (acoustic-sum-rule /
   long-wavelength for elastic; harmonic-lattice-scan vs phonopy-QHA for
   expansion), not bit-exact.
5. **projected pdos:** a projection SCHEME (`p_atoms`, `direction`) on the
   `PhononDOS` operator, not a distinct node. LOW.
6. **Tier question (open):** put `ParticipationRatio` + `ModalDiffusivity` in the
   existing Harmonic/QHGK tiers, or add a **Localization/Disorder** tier grouping
   the amorphous-branch diagnostics. kaldo does not compute the
   propagon/diffuson/locon cut itself (it exposes PR and `D_n` and leaves the
   threshold to the user), so a classification node is not required by kaldo.
