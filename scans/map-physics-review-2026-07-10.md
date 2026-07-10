# The whole map, read as a theoretical physicist

Review date 2026-07-10. Scope: the entire published map (91 nodes, 217 links,
60+ formula edges, 14 tiers) as serialized in `docs/data/graph.json`, cross-read
against `omai/*/operator/{nodes,edges}.py`, `omai/operator/{registry,dimensions}.py`,
and the settled scan verdicts. The reviewer verifies and proposes; no map code
was touched. Deliverable is findings plus a ranked, orchestrator-decision list.

Exponent convention throughout: dimensions are seven-tuples over the SI base
axes `(M, L, T, Th, N, I, J)`, exactly as `omai/operator/dimensions.py` writes
them. "Dimensionless" means the all-zero tuple. Every proposed relation below is
dimension-checked by hand in that basis.

Settled doctrine respected (not reopened): the carrier-label family
(`electrical_conductivity` split ionic/electronic by the `carrier` label), the
`electronic_thermal_conductivity` firewall tag, the band_gap / homolumo_gap
cousin ruling, the `reaction_barrier` construction-label family with
cross-construction subtraction forbidden, the per-mole-of-cells vs
per-mole-of-atoms basis separations (phonopy Molar* vs CALPHAD Molar*, QHA
vs CALPHAD Gibbs), and "ionic conductivity is emphatically NOT thermal
conductivity". These are correct and are treated as axioms here.

---

## 1. The bases that decide everything (read this first)

Five heat-capacity-like and volume-like quantities on the map carry *different
bases*, and every thermodynamic-identity candidate lives or dies on which one it
uses. The map's own nodes are:

| node | tag | dimension tuple | basis |
|---|---|---|---|
| `HeatCapacity` (per mode) | heat_capacity | `(1,2,-2,-1,0,0,0)` J/K | per (q,nu) mode |
| `VolumetricHeatCapacity` C_V | volumetric_heat_capacity | `(1,-1,-2,-1,0,0,0)` J/(K m^3) | **per unit volume** |
| `MolarHeatCapacity` C_V | molar_heat_capacity | `(1,2,-2,-1,-1,0,0)` J/(K mol) | **per mole of primitive cells** |
| `HeatCapacityConstantP` C_P | heat_capacity_constant_p | `(1,2,-2,-1,-1,0,0)` J/(K mol) | per mole of phonopy cells, const-P |
| `CellVolume` V_cell | cell_volume | `(0,3,0,0,0,0,0)` m^3 | **volume of ONE primitive cell** |
| `BulkModulus` K | bulk_modulus | `(1,-1,-2,0,0,0,0)` Pa | intensive |
| `ThermalExpansion` alpha | thermal_expansivity | `(0,0,0,-1,0,0,0)` 1/K | intensive |
| `ThermalGruneisen` gamma | thermal_gruneisen | `(0,0,0,0,0,0,0)` | intensive, per T |

The critical fact: the map has **a per-unit-volume C_V, a per-mole-of-cells
C_V, and a single-cell volume, but no molar volume node** (m^3/mol) and no
per-single-cell C_V. That absence is the fault line the Gruneisen and
C_P - C_V candidates fall along.

---

## 2. Formula-unification candidates (the core ask), verified

### 2a. Gruneisen relation gamma = alpha * V * B_T / C_V

Physics: the macroscopic (thermodynamic) Gruneisen parameter obeys
`gamma = alpha * B_T * V / C_V` where V and C_V share a basis (V molar with C_V
molar; V total with C_V total; or the intensive form `gamma = alpha * B_T / C_V^vol`
with the volumetric heat capacity). The map already carries all four factor
species. Dimension check, done by hand:

- Intensive form with the volumetric heat capacity:
  `alpha * B_T / C_V^vol = (0,0,0,-1) . (1,-1,-2,0) . -(1,-1,-2,-1) = (0,0,0,0,0,0,0)`.
  **Exactly dimensionless. VERIFIED.**
- Molar form `alpha * B_T * V_molar / C_V^mol` with V_molar = `(0,3,0,0,-1,0,0)`:
  also exactly dimensionless. VERIFIED.
- Naive form with the map's actual nodes `alpha * V_cell * B_T / C_V^mol`:
  `(0,0,0,-1).(0,3,0,0).(1,-1,-2,0).-(1,2,-2,-1,-1,0,0) = (0,0,0,0,+1,0,0)`.
  **Leaves a residual N^+1 (one uncancelled mole axis). BROKEN by basis.**
- Naive form `alpha * V_cell * B_T / C_V^vol`:
  `(0,0,0,-1).(0,3,0,0).(1,-1,-2,0).-(1,-1,-2,-1) = (0,3,0,0,0,0,0)` = leftover
  L^3 (a volume). **BROKEN: a per-unit-volume C_V already divided out the volume,
  so multiplying by V_cell double-counts it.**

Verdict: the relation is a real thermodynamic identity and is **exactly
satisfiable with existing nodes in exactly ONE combination**:

> **gamma_th = alpha_V * BulkModulus / VolumetricHeatCapacity**   (intensive form, no V node)

Every symbol maps to a node: `alpha_V` = ThermalExpansion `(0,0,0,-1)`,
`BulkModulus` = K `(1,-1,-2,0)`, `VolumetricHeatCapacity` = C_V^vol
`(1,-1,-2,-1)`, output `ThermalGruneisen` = dimensionless. **No CellVolume, no
MolarHeatCapacity**: using either of those breaks the dimension. This is the
encode-ready form (A-list #1).

Basis mismatch named for the orchestrator: **CellVolume (per single cell) times
MolarHeatCapacity (per mole of cells) do NOT close** because they carry
incompatible extensivity (one cell vs one mole of cells); the naive
"alpha V B/C_V" that a textbook writes silently assumes V and C on the same
molar basis. On this map only the volumetric C_V is on a basis that needs no V
factor at all, so it is the clean route.

Note on the *existing* edge: `contract_thermal_gruneisen` today produces
ThermalGruneisen from `(mode Gruneisen, Frequency)` by a heat-capacity-weighted
BZ average (phonopy `gruneisen_temperature`). That is a *different, independent*
producer of the same node (a Pattern-C alternative), not the thermodynamic
identity. The identity above would be a **second executable producer** of
ThermalGruneisen from the QHA/mechanics side, exactly the redundant-route
pattern the map already uses for BulkModulus (three producers) and PhononDOS
(two). The two must agree numerically; that agreement is the physics content.

### 2b. C_P - C_V = T * V * alpha^2 * B_T

Physics: exact thermodynamic identity. Dimension check with molar bases and a
molar volume:
`T . V_molar . alpha^2 . B_T = (0,0,0,1).(0,3,0,0,-1).(0,0,0,-2).(1,-1,-2,0)
= (1,2,-2,-1,-1,0,0)` = ENERGY_PER_TEMPERATURE_PER_MOLE. **Matches C_P and
molar C_V exactly. VERIFIED**, but only with a molar volume.

The map has `HeatCapacityConstantP` C_P (per mole of phonopy cells),
`MolarHeatCapacity` C_V (per mole of primitive cells), `ThermalExpansion` alpha,
`BulkModulus` K, `Temperature` T, but **no molar volume**. With the single-cell
`CellVolume` the identity leaves a residual N axis exactly as in 2a:
`T . V_cell . alpha^2 . B_T = (1,-1,-2,-1,0,0,0)` = the *volumetric* dimension,
off from the molar C_P/C_V by an N (mole) axis and an L^-4. So:

- Fully consistent form exists: `C_P^vol - C_V^vol = T * alpha^2 * B_T` (no V
  needed, both C per unit volume). Dimension:
  `T . alpha^2 . B_T = (0,0,0,1).(0,0,0,-2).(1,-1,-2,0) = (1,-1,-2,-1)` =
  VolumetricHeatCapacity dimension. **VERIFIED, dimensionless-consistent, and
  needs NO volume node.**
- But the map's C_P node is **molar, not volumetric**, and there is no
  volumetric C_P node, and no volumetric-C_V-at-constant-P. So the *executable*
  identity would need either (i) a molar-volume node, or (ii) a volumetric C_P
  sibling. Neither exists today.

Verdict: **B-list / C-list, not A-list.** The physics is exact but the map is
one node short of an honest encoding. Two honest options for the orchestrator:
  - (C) mint a `MolarVolume` node (m^3/mol, `(0,3,0,0,-1,0,0)`) = CellVolume x
    N_A / atoms-per-cell; then `C_P - C_V = T V_m alpha^2 B_T` is executable and
    also unlocks the *molar* Gruneisen route as a cross-check. This is the
    physically cleanest single addition and it is reused by both 2a and 2b.
  - (D-leaning) leave C_P - C_V unencoded as an executable edge; it is already
    stated verbatim in the C_P node's own description as a documented identity.
    The information is present; only the machine-checked edge is missing.

Recommended: treat MolarVolume as the one worth-minting node (see 4C). It is a
promoted-parameter-style contraction of Structure/CellVolume, dimensionally
unambiguous, and it is the single key that makes BOTH textbook identities
(2a molar form and 2b) executable and mutually cross-checking. The intensive
forms (2a volumetric, above) remain the zero-new-node A-list route.

### 2c. Arrhenius: D = D_0 exp(-E_a / (k_B T))

This is **already encoded** as `fit_arrhenius`: `(Diffusivity, Temperature) ->
ActivationEnergy`, and the edge already builds the real sympy Eq
`D(T) = D_0 exp(-E_a/(k_B T))` with `D_0`, `E_a`, `k_B` as bare positive
Symbols, `is_executable_in_sympy_override=False` (it is a regression, not a
closed form). Assessment of the honest encoding:

- The exponent's dimensionlessness is gate-provable:
  `E_a / (k_B T) = (1,2,-2,0) - [(1,2,-2,-1) + (0,0,0,1)] = (0,0,0,0,0,0,0)`.
  **VERIFIED dimensionless.** k_B (ENERGY_PER_TEMPERATURE) times T (TEMPERATURE)
  is exactly ENERGY, matching E_a. A dimensional gate over this edge would pass.
- D_0 (the pre-exponential) has D_0 = D at 1/T -> 0, so D_0 carries the
  DIFFUSIVITY dimension `(0,2,-1,0,0,0,0)` (m^2/s). It is correctly a *scheme /
  fit parameter*, not a node: it is a property of the fitted D(T) curve, not an
  independently-produced observable. Honest verdict: **leave as-is (D-list).**
  The current encoding is already the honest one, a fit with the exponent's
  dimensionlessness provable. If anything is owed, it is only a note in the edge
  scheme that D_0 carries DIFFUSIVITY (documentation, not structure).

### 2d. Nernst-Einstein as an executable edge

Already an *implicit* edge `compute_ionic_conductivity`:
`sigma = (n/V) z^2 e^2 D / (k_B T)`, `method=nernst_einstein`, `haven_ratio=1`.
The number density n/V and the ionic charge z^2 are read off Structure and are
folded into the opaque solver function; they are **not nodes and not surfaced
Symbols**.

Honest verdict: **keep opaque (D-list).** To make it executable in sympy you
would need carrier density n/V (an L^-3 quantity) and carrier charge z (a
dimensionless integer times e) as first-class inputs. Neither is a node, and
neither should be minted just for this: n/V is a per-species count over the
opaque Structure (the same reason FormationEnergy's reference chemical
potentials stay opaque), and z is an integer label. The dimensional honesty is
already discharged in the config-thermo scan (the S/m = `(-1,-3,3,0,0,2,0)`
result is verified twice there). The relation being *implicit* is the correct
encoding: the map does not have the carrier-counting machinery, and inventing a
`CarrierDensity` node solely to close one edge is re-mint cost with no other
consumer. If a future slice adds defect/carrier-concentration nodes (they would
have many consumers), revisit, that is a genuine C-list item, not now.

### 2e. BDE / FormationEnergy / AdsorptionEnergy / ReactionEnergy as one family?

The candidate: collapse `bond_dissociation_energy`, `formation_energy`,
`adsorption_energy`, `reaction_energy` (and arguably `surface_energy`,
`grain_boundary_energy`, `reaction_barrier`) into one `reaction_energy` family
with a type label, since they are all "an energy difference of a balanced set of
species".

Argue from the map's own doctrine:

1. **The physics is true but proves too much.** They ARE all reaction energies
   in the loosest sense, but so is TotalEnergy difference, so is SurfaceEnergy,
   so is Voltage's numerator, so is essentially every ENERGY-typed stability
   node. "It is a reaction energy" is not a *distinguishing* predicate; it is
   the genus, not the species. The map's identity doctrine
   (`registry.py:85-93`) is explicit that pure type-content identity false-merges
   real pairs and the *tag* is what keeps same-typed distinct quantities apart.
   These four share the ENERGY dimension precisely so the tag must do the work.

2. **They fail the label-family test the carrier precedent sets.** The carrier
   family (`carrier=ionic|electronic`) works because the two members are the
   *same quantity* (electrical conductivity, same S/m dimension, same defining
   relation sigma = j/E) differing only in which charge carries the current , 
   an exchangeable axis with a closed value set. Contrast:
   - FormationEnergy is **per atom (intensive, eV/atom)**; its very dimension of
     "energy" hides a per-atom normalization that is definitional, and its
     references are *elemental*.
   - AdsorptionEnergy is **extensive (per whole-cell configuration, eV)**, a
     three-term adslab - slab - adsorbate difference.
   - BondDissociationEnergy is **per molecule** (no lattice, no BZ), a homolytic
     two-fragment difference, kcal/mol native.
   - ReactionEnergy is a **stoichiometric combination of per-atom formation
     energies**, per reaction-atom.
   These are not one quantity on an exchangeable axis; they are different
   normalizations (intensive vs extensive), different reference conventions
   (elemental vs fragment vs slab), and in BDE's case a different *system class*
   (molecule vs crystal). The carrier label swaps a physical carrier; a putative
   `type=formation|adsorption|bde|reaction` label would swap the *definition*.
   That is what a **tag** is for, not a label. The registry already spends four
   separate tags on exactly this and documents each boundary
   (`registry.py:105,109,148,170`).

3. **Re-mint cost is real and one-directional.** Collapsing four tags into one
   family re-hashes four node identities (the id is a content hash over the
   quantity tag). Every serialized instance, every scan `maps_to`, every
   representation adapter keyed on those tags breaks and must be superseded.
   The carrier merge paid that cost because it bought a genuine cross-code
   observable (one conductivity a physicist reads as one number). Merging the
   energy tags buys nothing a physicist wants: you would immediately re-split
   them by label at every use site, because you can never subtract a per-atom
   FormationEnergy from an extensive AdsorptionEnergy. The `reaction_barrier`
   family is the precedent that CUTS AGAINST this: it labels constructions of
   *the same barrier* and FORBIDS cross-construction subtraction, the doctrine
   already refuses to let a label paper over an incompatible basis.

4. **The one real sibling relationship is already recorded.** BDE's own node
   description calls it "a LABELED SIBLING of solid-state ReactionEnergy but on
   the per-MOLECULE basis; kept distinct by bond_dissociation_energy tag", and
   `registry.py:170` says the same. That is the *correct* resolution: acknowledge
   the kinship in prose, keep the tags distinct. It mirrors the band_gap /
   homolumo_gap cousin ruling exactly.

Verdict: **D-list, leave separate.** They are correctly separate tags, not a
labeled family. The physics reason: they share only the genus (an energy), not
the species (normalization, reference, system class). The map's own precedents
,  carrier (merge only true same-quantity), reaction_barrier (label but forbid
cross-subtraction), band_gap/homolumo_gap (cousin, never equated), all point
the same way. One improvement is warranted and it is cosmetic, not structural:
ReactionEnergy could be executable *from* the others (see 2f, the missing
edges), which is the real unification the physics offers, not merging the
nodes, but wiring the relation ReactionEnergy = Sigma c_i (formation energies).

### 2f. Everything else: a full sweep of the 60+ edges

Pairs that are secretly the same physics, missing obvious relations, and
dimensional near-misses, from a complete read of the link list:

- **Wiedemann-Franz L = kappa_e / (sigma T)** connecting
  `ElectronicThermalConductivity`, `ElectricalConductivity[carrier=electronic]`,
  `Temperature`. Dimension of L, by hand:
  `kappa_e / (sigma T) = (1,1,-3,-1) - [(-1,-3,3,0,0,2,0) + (0,0,0,1)]
  = (2,4,-6,-2,0,-2,0)` = V^2/K^2, the Lorenz-number dimension. This is a
  **genuinely new dimension not on the map** (it is VOLTAGE^2 / TEMPERATURE^2).
  So Wiedemann-Franz is NOT a zero-new-machinery edge: encoding it either (a)
  introduces the Lorenz number L as a *scheme constant* with dimension
  `(2,4,-6,-2,0,-2,0)` and makes `kappa_e = L sigma T` an executable check, or
  (b) stays a documented relation. Physics caveat: L = pi^2/3 (k_B/e)^2 is the
  Sommerfeld value only for degenerate elastic scattering; amset's kappa_e is
  computed independently (not via WF), so an executable WF edge would be a
  *consistency test*, not a producer, and it can legitimately be violated
  (bipolar conduction, inelastic scattering). Verdict: **B/C-list**: worth a
  documented non-executable relation now; executable only if a `LorenzNumber`
  scheme-constant dimension is minted. Do NOT wire it as a hard producer of
  kappa_e, that would encode a physics falsehood (WF is approximate).

- **SeebeckCoefficient <-> Voltage.** A physicist reading the map cold sees a
  Seebeck coefficient (V/K) and an intercalation Voltage (V) with no relation,
  which is correct: the Seebeck V is a thermopower (dV/dT under a thermal
  gradient), the intercalation V is an electrochemical open-circuit potential.
  They share the volt but are unrelated physics. **No missing edge. D-list.**
  (Flag only: both correctly carry the current axis; the dimension design is
  sound.)

- **The power factor sigma S^2** (thermoelectric) connects
  `ElectricalConductivity[carrier=electronic]` and `SeebeckCoefficient`.
  Dimension: `sigma S^2 = (-1,-3,3,0,0,2,0) + 2(1,2,-3,-1,0,-1,0)
  = (1,1,-3,-2,0,0,0)` = W/(m K^2), a real derived quantity (power factor).
  This is a clean **executable contraction of two existing nodes into a new
  node** if a `PowerFactor` node is wanted, but it needs a new node and a new
  dimension. **C-list** (future thermoelectric slice; also enables ZT =
  sigma S^2 T / (kappa_lat + kappa_e), which would finally *connect the lattice
  and electronic thermal-conductivity families*, the single most physically
  meaningful missing link on the map). Noting ZT here because it is the one
  relation that would make the thermal-transport and electronic-transport halves
  of the map tell one story to a thermoelectrics colleague.

- **ThermalConductivity total = lattice + electronic.** The
  `electronic_thermal_conductivity` tag description literally states
  `kappa_total = kappa_lattice + kappa_electronic`, but **no edge sums them**.
  Both are THERMAL_CONDUCTIVITY `(1,1,-3,-1)`; the sum is dimensionally trivial
  and physically exact (they are additive parallel heat channels). This is the
  cleanest genuinely-missing edge on the map: a `sum_thermal_conductivity`
  contraction `kappa_total = kappa_lattice + kappa_electronic` mirroring the
  existing `sum_linewidths` (Matthiessen) and `combine_kappa_wigner`. It needs a
  new *node* (`ThermalConductivity[contribution=total]` or similar) but NO new
  dimension and NO new machinery. **A/B-list**: the physics is exact and additive,
  the only cost is one node + one edge, and it discharges a claim the map already
  makes in prose. Caveat: choose the label carefully so it does not collide with
  the lattice `transport_model` family (a `contribution=lattice|electronic|total`
  label, or a dedicated node, per the label-collision discipline in
  `registry.py:250`).

- **Elastic-modulus family internal closure: VERIFIED COMPLETE.** `E_Y =
  9KG/(3K+G)`, `nu = (3K-2G)/(2(3K+G))` are both encoded and both build real
  sympy. Dimension: E_Y is ENERGY_PER_LENGTH_CUBED (correct, a modulus), nu is
  dimensionless (correct). No missing edge; this sub-map is exemplary.

- **BulkModulus has three producers** (`contract_bulk_modulus` from elastic
  tensor, `compute_bulk_modulus_eos` from E(V) curvature, `compute_bulk_modulus_qha`
  from QHA). All three land on the same node and the same dimension. This is the
  redundant-route pattern done right and is the template for the Gruneisen
  second-producer (2a) and any thermal-conductivity-sum edge.

- **PhononDOS has two producers** (`compute_dos` from frequencies,
  `fourier_to_dos` from the velocity autocorrelation). Correct Pattern-C
  redundancy; dimension FREQUENCY on both. No issue.

- **Green-Kubo kappa vs BTE kappa vs Wigner kappa** all land on
  THERMAL_CONDUCTIVITY-typed nodes distinguished by `transport_model`. This is
  the label family working as designed. No merge, no split. Sound.

- **Diffusivity from MSD (Einstein) and Diffusivity's dimension.** `contract_diffusivity`
  builds `D = slope_MSD / (2 d)`; D is DIFFUSIVITY `(0,2,-1)` = m^2/s. MSD is
  LENGTH_SQUARED `(0,2,0)`, its slope is `(0,2,-1)`, over dimensionless 2d.
  **VERIFIED consistent.** No issue.

- **Near-miss watch (correctly firewalled, no action):** ThermalConductivity
  `(1,1,-3,-1)` vs ElectricalConductivity `(-1,-3,3,0,0,2,0)`, share the English
  word only, different axes; the `electronic_thermal_conductivity` tag and the
  dimensions.py comment both firewall this. SurfaceEnergy / GrainBoundaryEnergy
  `(1,0,-2,0)` share exponents with ForceConstants[order=2] (energy per area vs
  force per length are the same M T^-2), three distinct tags keep them apart,
  correctly. Stress / ElasticConstants / BulkModulus / ShearModulus / Pressure /
  YoungsModulus all share ENERGY_PER_LENGTH_CUBED `(1,-1,-2,0)`, six tags, all
  documented, all correct (they are all pressures/moduli; the tag carries the
  distinction). No false merges anywhere; the tag discipline is holding.

---

## 3. Coherence audit

**Dimension vs formula, node by node (spot-check + implicit-relation check):**
No dimensional inconsistency found between any node's declared dimension and the
formula its producing edge builds. The transport chain (D e = omega^2 e ->
omega -> c, F, kappa) is dimensionally clean end to end; the MD chain
(Trajectory -> J -> <JJ> -> kappa_GK) lands on THERMAL_CONDUCTIVITY correctly
via the `V/(k_B T^2)` prefactor. The one place a declared dimension *reuses*
another's exponents by design (VolumetricHeatCapacity shares the tuple with
nothing; ElectronicThermalConductivity shares THERMAL_CONDUCTIVITY with the nine
lattice kappa nodes) is firewalled by tag in every case. Implicit relations
checked for hypothetical consistency: Gruneisen (2a), C_P-C_V (2b),
Nernst-Einstein (2d), Wiedemann-Franz (2f), all dimensionally consistent **in
the correct-basis form**; the only failures are the *wrong-basis* naive forms
(CellVolume x MolarHeatCapacity), which is a basis warning, not a node error.

**Label-family consistency:**
- `carrier` = {ionic, electronic}: both present. Complete.
- `bte_solver` = {rta, direct_inverse}: both present (as MeanFreeDisplacement and
  ThermalConductivity). Complete.
- `transport_model` = {wigner, wigner_populations, wigner_coherences, qhgk,
  green_kubo, nemd, hnemd}: all seven present. Complete.
- `channel` = {anharmonic_3ph, isotope, boundary, total}: all four present.
  Complete.
- `wrt` = {omega, mfp}: both present. Complete.
- `construction` = {neb_mep, static_ts_mlip, static_ts_dft}: only `neb_mep`
  present as a node; the other two are registered-but-unminted (documented as
  "join later, no re-mint"). This is intentional and correct, the family is
  open, the label set is declared, siblings join without re-minting. **No gap.**
- `order` = {2, 3}: both present (ForceConstants). Complete.

No family has a sibling that is silently missing; the only unpopulated label
values (`static_ts_*`) are deliberately deferred with the re-mint-free join
already guaranteed.

**Tier placement sanity:** every node sits in a physically defensible tier.
BulkModulus at layer 7 in Mechanics despite three producers spanning
layers 3-7 is fine (the node is placed at its deepest producer). ActivationEnergy
in the Diffusion tier (materials domain) is correct (it is a diffusivity-slope,
not a PES barrier, the description firewalls it against ReactionBarrier).
StaticDielectricTensor placed in Sources tier though it is *computed* from
DielectricTensor + BornCharges + Frequency is a minor oddity (it has a real
producing edge `compute_static_dielectric`, so it is derived, not a source), but
this is a display-tier choice, not a physics error, and the amset transport nodes
genuinely consume it as an input. Flag for the orchestrator, do not treat as a
bug.

**Description accuracy vs encoded physics:** descriptions are unusually
disciplined, basis guardrail language ("PER MOLE OF THE PHONOPY CELL", "per
unit volume", "INTENSIVE eV/atom", "EXTENSIVE") is present exactly where the
scans mandated it (QHAGibbsEnergy, C_P, MolarHeatCapacity, VolumetricHeatCapacity,
FormationEnergy, AdsorptionEnergy). Two descriptions *state identities that are
not encoded as edges*: HeatCapacityConstantP says "C_P - C_V = alpha^2 B V T"
and ElectronicThermalConductivity says "kappa_total = kappa_lattice +
kappa_electronic". Both are true and both are the missing edges of section 2.
The prose is ahead of the wiring, the review's job is to close that gap.

**Coherence-audit verdict: the map is physically coherent.** No dimensional
error, no false merge, no mis-tiered node, no missing label sibling, every basis
guardrail in place. The gaps are all *additive* (missing edges the prose already
promises), never *corrective*.

---

## 4. Ranked recommendations

### (A) Executable contract edges ready to encode now (sympy + dimensions + existing nodes only)

**A1. Gruneisen thermodynamic identity (second producer of ThermalGruneisen).**
```
gamma_th = ThermalExpansion * BulkModulus / VolumetricHeatCapacity
```
Dimensions: `(0,0,0,-1) . (1,-1,-2,0) . -(1,-1,-2,-1) = (0,0,0,0,0,0,0)` -> dimensionless.
All three inputs are existing nodes; output ThermalGruneisen (dimensionless).
Uses the VOLUMETRIC heat capacity (NOT Molar, NOT CellVolume), this is the
only closing combination. Becomes a Pattern-C alternative producer alongside the
existing heat-capacity-weighted mode-average; the two must agree. Zero new nodes,
zero new dimensions.

**A2. Total thermal conductivity = lattice + electronic.**
```
kappa_total = kappa_lattice + kappa_electronic
```
where kappa_lattice is any of the lattice ThermalConductivity producers (e.g.
`transport_model=wigner`) and kappa_electronic = ElectronicThermalConductivity.
Both THERMAL_CONDUCTIVITY `(1,1,-3,-1)`; the sum is exact and additive
(parallel heat channels). Mirrors the existing `sum_linewidths` Matthiessen edge.
Requires ONE new node for the total (choose a non-colliding label, e.g.
`contribution=total`, or a dedicated `TotalThermalConductivity` tag) but NO new
dimension. Discharges a claim the map already makes in prose. Borderline A/B
because of the one new node; the physics itself is A-grade (trivial, exact).

### (B) Structural changes worth the churn (re-mint / supersede cost stated)

**B1. Wire ReactionEnergy = Sigma c_i (formation energies) as an executable edge.**
The `compute_reaction_energy` edge is currently implicit (opaque combination of
FormationEnergy). Making it a real sympy stoichiometric sum `dE_rxn = Sigma_p c_p
Hf(p) - Sigma_r c_r Hf(r)` surfaces the balancing coefficients as scheme data and
makes the one true unification the energy-family physics offers *executable*
(the relation between the nodes) without merging the nodes. Cost: edit one edge
from opaque to closed-form; no node re-mint. This is the *right* answer to the
"combine the energy formulas" ask, combine the relation, not the identities.

**B2. Document (non-executable) Wiedemann-Franz relation.** Add a documented
relation `kappa_e = L sigma T` (L the Lorenz number, `(2,4,-6,-2,0,-2,0)`, a new
scheme-constant dimension) as a *consistency annotation*, NOT a producer of
kappa_e (WF is approximate; amset computes kappa_e independently). Cost: a scheme
note + one new dimension constant IF made executable; free if left as prose.
Recommend prose-only now. Re-mint cost: none (no node identity changes).

### (C) Future slices (need new nodes / machinery)

**C1. MolarVolume node** `(0,3,0,0,-1,0,0)` m^3/mol = CellVolume x N_A /
atoms-per-cell. Single cleanest addition: makes BOTH the molar Gruneisen form
AND C_P - C_V = T V_m alpha^2 B_T executable and mutually cross-checking. A
promoted-parameter-style contraction of Structure/CellVolume. Low machinery cost,
high physics payoff; the natural next node after this review.

**C2. Thermoelectric slice: PowerFactor = sigma S^2** `(1,1,-3,-2)` W/(m K^2),
then **ZT = sigma S^2 T / (kappa_lattice + kappa_electronic)** (dimensionless).
ZT is the single relation that would connect the lattice and electronic halves
of the map into one thermoelectrics story. Needs two new nodes (PowerFactor, ZT)
and the A2 total-kappa edge. High-value future slice.

**C3. CarrierDensity / defect-concentration nodes** would make Nernst-Einstein
(2d) executable, but only mint them when a slice has many consumers (defect
thermodynamics, doping), never solely to close one edge.

### (D) Leave-alone verdicts (look combinable, are not; physics reason given)

- **D1. BDE / FormationEnergy / AdsorptionEnergy / ReactionEnergy stay four
  tags, not one labeled family.** They share the genus (an energy) not the
  species (intensive per-atom vs extensive per-cell vs per-molecule; elemental
  vs fragment vs slab references). The carrier precedent merges only true
  same-quantity; the reaction_barrier precedent labels but forbids
  cross-subtraction; both cut against merging here. Re-mint cost buys nothing a
  physicist would use. (The kinship is already recorded in prose, correctly.)
- **D2. Nernst-Einstein stays implicit** (2d): no CarrierDensity node to close
  it, and minting one for a single consumer is unjustified re-mint cost.
- **D3. Arrhenius stays a fit** (2c): D_0 is a curve parameter, not an
  observable; the current encoding is already the honest one, exponent
  dimensionlessness provable.
- **D4. SeebeckCoefficient and intercalation Voltage stay unconnected**: they
  share the volt but are unrelated physics (thermopower vs electrochemical
  potential). No missing edge.
- **D5. The six ENERGY_PER_LENGTH_CUBED nodes** (Stress, ElasticConstants,
  Bulk/Shear/Youngs moduli, Pressure) stay six tags: all pressures/moduli, the
  tag carries the distinction, no false merge.
- **D6. C_P - C_V stays undecided pending C1**: exact identity, but the map is
  one node (MolarVolume) short of an honest executable encoding; the intensive
  volumetric form needs a volumetric C_P sibling the map also lacks. Documented
  in prose today; wire it only after C1.

---

## 5. Orchestrator-decision list

1. **Encode A1** (gamma_th = alpha B_T / C_V^volumetric) now? Recommended YES , 
   zero new nodes, exact identity, second producer of an existing node, the
   redundant-route pattern the map already blesses. Decision needed:
   confirm VolumetricHeatCapacity (not Molar) as the C_V input.
2. **Encode A2** (kappa_total = kappa_lattice + kappa_electronic)? Recommended
   YES, discharges a prose claim; needs one non-colliding label/node
   (`contribution=total`?). Decision needed: node-vs-label form and label-key
   collision review against `transport_model`.
3. **Promote B1** (ReactionEnergy edge opaque -> closed-form stoichiometric sum)?
   Recommended YES, this is the real "combine the energy formulas" answer:
   combine the *relation*, keep the tags.
4. **Mint C1 MolarVolume**? Recommended YES as the next node, it is the single
   key to executable 2a-molar and 2b (C_P - C_V), both cross-checking. Decision:
   this session or next slice.
5. **B2 Wiedemann-Franz**: prose-only annotation now, executable only if a
   Lorenz-number dimension is later minted. Decision: annotate or defer.
6. **Confirm D1-D6 leave-alone verdicts** (energy tags stay separate,
   Nernst-Einstein stays implicit, Arrhenius stays a fit, Seebeck/Voltage
   unconnected). Recommended: accept as settled.
7. **Note (not a decision): StaticDielectricTensor tier.** It is derived, not a
   source; the Sources-tier placement is a display choice. Flag for the display
   pass, not a physics ruling.

The three most important recommendations overall: **A1** (the Gruneisen identity,
free and exact, and the headline answer to "combine the formulas that should be
combined"), **A2 + C2** (total thermal conductivity, then ZT, the one thread
that stitches the lattice and electronic transport halves into a single physics
story), and **C1** (MolarVolume, the one node that unlocks two textbook
identities at once and resolves the CellVolume-vs-molar basis fault line this
review found running through the whole QHA/mechanics corner of the map).
