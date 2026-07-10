# atomate2 and VASP as used by AtomisticSkills: scan report

Scan of **atomate2** (the DFT workflow framework) and **VASP** (the DFT engine
underneath it) as the AtomisticSkills (arXiv 2605.24002) DFT stack actually uses
them. Companion catalog: `scans/atomate2-vasp-atomistic-skills.json` (16
entries; the "18" in the original draft was a miscount, corrected in review
2026-07-09). Sources: the shared DFT driver `src/utils/dft/atomate2_utils.py`, the
raw parser `src/utils/dft/vasp_parser.py`, the INCAR generator
`src/utils/dft/vasp_writer.py`, the MCP layer `src/mcp_server/atomate2_server.py`,
and the `mat-dft-*` skills (`mat-dft-vasp`, `mat-dft-lobster`,
`mat-dft-electronic-transport`, `mat-dft-electron-phonon`,
`mat-dft-ferroelectric`, `mat-defect-energy-dft`, `mat-dielectric-response`,
`mat-electronic-structure`, `mat-magnetic-density`). `pymatgen.io.vasp` (the
actual VASP output parser) was read directly from the miniconda base env
(`pymatgen/io/vasp/outputs.py`, pymatgen 2025.6.14). atomate2 is not importable
in base, so the maker names are anchored to the AtomisticSkills import sites.

## What atomate2 and VASP ARE in this software

- **atomate2 is the DFT workflow framework.** It builds jobflow DAGs of VASP
  jobs from a pymatgen `Structure` (`Maker.make(struct) -> Flow`), submits them
  locally (`run_locally`) or remotely (jobflow-remote to Perlmutter), stores
  `TaskDocument`s in MongoDB, and parses VASP outputs (`VaspDrone` /
  `get_vasp_task_document -> TaskDoc`) into energy / forces / stress / structure.
  It is the VASP analog of the map's `QE_SOLVE_GROUND_STATE` operator
  representation: the provenance and discretization layer. Makers seen in the
  code: `StaticMaker`, `RelaxMaker`, `MP*` and `MatPes*` static/relax makers,
  `BandStructureMaker`, `OpticsMaker`, `VaspLobsterMaker`, `FerroelectricMaker`,
  `ElectronPhononMaker`, `VaspAmsetMaker`, `FormationEnergyMaker`.

- **VASP is the DFT engine and a REPRESENTATION of the map's operator nodes.** It
  grounds the same `TotalEnergy` / `Forces` / `Stress` / `Structure` that QE
  already grounds, plus `ElasticConstants`, `BornCharges`, `DielectricTensor`
  (already on the map), plus a set of electronic observables QE does not
  currently expose (band gap, electronic DOS, dielectric spectrum, magnetic
  moments, polarization, electronic transport).

AtomisticSkills reaches VASP **only through atomate2** in practice (the
`mat-dft-vasp` manual path is explicitly deprecated in favor of the atomate2 MCP
tool); the raw `pymatgen` `Vasprun`/`Outcar` parsers are a secondary path.

## Which atomate2 workflow produces which mapped quantity

| atomate2 maker | VASP flags | quantities | map node(s) |
|---|---|---|---|
| `StaticMaker` / `RelaxMaker` (+ MP/MatPES variants) | IBRION=-1 / 2, ISIF=3, tstress | TotalEnergy, Forces, Stress, Structure | TotalEnergy, Forces, Stress, Structure (already mapped) |
| `BandStructureMaker` (line/uniform/both) | NSCF | band gap, E_fermi, band structure, DOS | none (new: band_gap) |
| `OpticsMaker` | LOPTICS | eps(omega), Re/Im, absorption | none (new: dielectric_function); static eps_inf via LEPSILON -> DielectricTensor |
| (all maker names above VERIFIED against atomate2 0.1.4 + emmet-core 0.87.1 wheels, 2026-07-09) | | | |
| `VaspAmsetMaker` (AMSET) | dense mesh + scattering | sigma_el, Seebeck, kappa_el, mobility | none (new: electronic transport) |
| `FerroelectricMaker` | LCALCPOL Berry phase | spontaneous polarization P_s | none (new: spontaneous_polarization) |
| `FormationEnergyMaker` | charged defect supercells | E_f(defect, q) | none (new: defect_formation_energy, charged/DFT route) |
| `VaspLobsterMaker` | LOBSTER projection | COHP / ICOHP | none (representation-only) |
| `ElectronPhononMaker` | supercell displacements | e-ph coupling (below map floor) | none |
| OUTCAR `Outcar.elastic_modulus` (IBRION=6) | direct elastic | C_ij (kbar) | ElasticConstants (alternate representation) |
| OUTCAR `Outcar.born_charges` / `.dielectric_tensor` | LEPSILON | Z*, eps_inf | BornCharges, DielectricTensor |
| OUTCAR `Outcar.magnetization` | ISPIN=2 | m_i, M_total | none (new: magnetic_moment) |

## Entry counts by status (16 entries)

(Review 2026-07-09: the JSON has **16** entry objects, not 18; the "18 (7/8/3)"
was a scanner miscount, the same kind the pymatgen scan hit. Corrected to **7
already-mapped / 7 new-node-candidate / 2 representation-only**. Trust the JSON
`status` fields.)

- **already-mapped: 7** - vasp-total-energy (`TotalEnergy`), vasp-forces
  (`Forces`), vasp-stress-tensor (`Stress`), vasp-structure (`Structure`),
  vasp-elastic-modulus (`ElasticConstants`, alternate representation),
  vasp-born-charges (`BornCharges`), vasp-dielectric-tensor (`DielectricTensor`,
  static eps_inf). VASP is a SECOND representation of every one of these, the
  same physics QE / MLIP already ground.
- **new-node-candidate: 7** - band-gap-and-electronic-dos,
  dielectric-function-spectrum, electronic-transport-coefficients,
  spontaneous-polarization, magnetic-moment-vasp, defect-formation-energy-dft,
  and vasp-charge-density (DEFERRED, matches the map's explicitly deferred
  ChargeDensity). Note: band_gap, magnetic_moment, defect_formation_energy
  overlap the pymatgen scan's candidates; this scan adds the direct-VASP/atomate2
  producers.
- **representation-only: 2** - cohp-bonding-vasp-lobster (chemistry
  diagnostic) and atomate2-workflow-framework (the operator-representation
  provenance layer, VASP analog of `QE_SOLVE_GROUND_STATE`).

The 7 already-mapped VASP representations sit exactly on top of the DFT
ground-state slice the QE adapter established (`TotalEnergy`, `Forces`, `Stress`,
`Structure`) plus three thermal-domain nodes (`ElasticConstants` landing from
the pymatgen encode now, `BornCharges`, `DielectricTensor`).

## The VASP stress sign, relative to the map's store convention (headline)

The map's `Stress` node stores `sigma` in the **QE store convention**:
`sigma_store = -(1/V) dE/d(strain)`, **pressure convention, positive diagonal =
compressive** (`omai/dft_ground_state/representation/qe.py:116-131`, verified
from vendored QE source: the variable-cell force `fcell ~ (stress - press*I)`, so
a compressed cell prints positive sigma and positive P).

**Finding: VASP prints stress in the SAME compression-positive convention as the
map store.** VASP -> map-store therefore needs **no sign flip**. The three
AtomisticSkills conversion sites confirm this and reveal an internal
inconsistency:

1. `atomate2_utils.py:451-458` (TaskDoc route): comment *"Atomate2 standardizes
   stress to GPa. We convert to eV/A^3. VASP uses compressive positive
   convention, while ASE uses tensile positive. Multiply by -1."* Code:
   `stress * -1.0 * ase.units.GPa`. **The "standardizes to GPa" comment is
   wrong** (`TaskDoc.output.stress` is kbar), so this line is 10x too large; see
   trap #2.
2. `atomate2_utils.py:718-726` (MongoDB route): comment *"VASP stress is in kB.
   1 kB = 0.1 GPa. ... VASP compressive positive, ASE tensile positive, multiply
   by -1."* Code: `stress * -0.1 * ase.units.GPa`.
3. `vasp_parser.py:74-81` (raw `Vasprun` route): comment *"VASP stress is in kB.
   Convert to eV/A^3. 1 kB = 0.1 GPa."* Code:
   `np.array(vasprun.stress[-1]) * 0.1 * ase.units.GPa` -- **no `-1`**.

The two atomate2 paths flip to ASE tension-positive; the raw path does **not**,
leaving it in VASP/compression-positive, which is **map-store-consistent**. So
the three paths disagree in sign; the sign that matches the map's `Stress` store
is the un-flipped (compression-positive) one. Encode the VASP `Stress`
representation as **compression-positive** (same as QE), and note the ASE re-sign
AtomisticSkills applies downstream.

## Unit convention traps found

1. **Stress sign disagreement across AtomisticSkills paths** (headline above):
   two atomate2 paths flip to ASE tension-positive (`-1`), the raw `Vasprun`
   path does not. Map store = QE = compression-positive = the un-flipped path.

2. **Stress units: kbar from BOTH routes (CORRECTED 2026-07-09).** Raw
   `pymatgen Vasprun.stress` is **kBAR** (VASP native varray,
   `outputs.py:557-558`); atomate2 `TaskDoc.output.stress` is **ALSO kBAR**, NOT
   GPa. The `TaskDoc` is `emmet.core.tasks.TaskDoc`; its `OutputDoc.stress` field
   is documented **"units of kB"** (`emmet-core 0.87.1 tasks.py:110-111`) and
   `OutputDoc.from_vasp_calc_doc` copies the raw pymatgen ionic-step stress with
   no conversion (`tasks.py:158-181`). The AtomisticSkills comment
   *"Atomate2 standardizes stress to GPa"* (`atomate2_utils.py:454`) is **false**,
   and its code `stress * -1.0 * ase.units.GPa` (`:456`) is therefore **10x too
   large** (it should be `* -0.1 * ase.units.GPa`). The MongoDB route `:726`
   (`* -0.1`) and the raw route `vasp_parser.py:81` (`* 0.1`) get the magnitude
   right. Declare a SINGLE `observable_units {sigma: kbar}` on the VASP `Stress`
   representation. `1 kbar = 0.1 GPa` exactly. This 10x is an AtomisticSkills
   source defect to report upstream; the map stores kbar so it is not an encode
   issue.

3. **Constant generation: ASE CODATA-2014.** `ase.units.GPa` in the base env is
   `0.006241509125883258` eV/A^3, i.e. CODATA-2014 (`_e = 1.6021766208e-19`;
   `1/ase.units.GPa = 160.21766208`). This matches the MLIP-scan benchmark
   constant and DIFFERS from the pymatgen-scan elasticity constant
   `160.21766339999996` (CODATA-2018/scipy). ~1e-8 relative, physically
   negligible, but the same in-repo constant-generation mismatch to record.

4. **Energy variant / smearing.** VASP has three total-energy variants
   (`e_fr_energy` = smeared free energy F = E - TS_smear, `e_wo_entrp`,
   `e_0_energy` = sigma->0 extrapolation; `outputs.py:6213-6215`). pymatgen
   `Vasprun.final_energy` returns `e_0_energy`. This is the per-cell analog of
   the QE `!` smeared-free-energy trap (`qe.py:82-84`). Cross-code EXPECTED_AGREE
   must compare the SAME variant.

5. **Absolute energy zero.** VASP PAW + XC-functional (the omat / mp / matpes-pbe
   / matpes-r2scan / mp-r2scan preset) sets the total-energy zero; VASP and QE
   agree only on RELATIVE energies. The preset is required `Potential`
   provenance.

6. **Elastic modulus in kbar.** `Outcar.elastic_modulus` parses the VASP header
   `TOTAL ELASTIC MODULI (kBar)` (`outputs.py:2824`). kbar -> GPa via `*0.1`.
   Distinct from the mapped matcalc route (eV/A^3 * 160.2176634). Note pymatgen's
   `from_independent_strains(vasp=True)` applies `c_ij *= -0.1` for the
   stress-FIT route (kbar + sign); the OUTCAR direct-modulus route needs only
   `*0.1` (the modulus is a curvature, no sign flip on the modulus itself).

7. **Static vs frequency-dependent dielectric.** The map's `DielectricTensor` is
   the static clamped-ion `eps_inf` (omega->infinity, LEPSILON). VASP LOPTICS /
   `OpticsMaker` gives the frequency-dependent `eps(omega)` spectrum, a distinct
   observable (new-node-candidate `dielectric_function`). `eps_inf` is the
   omega->infinity limit of the spectrum's real part.

## Top encode candidates, ranked

1. **band_gap (E_gap, eV)** - the single most-used VASP electronic observable
   (mat-electronic-structure, mat-dft-electronic-transport, mat-db-mp). Produced
   by `BandStructureMaker`; `bs.get_band_gap()['energy']`, `is_metal`,
   `is_gap_direct`, `efermi`. Same candidate as the pymatgen scan; VASP/atomate2
   is a direct DFT producer alongside MP retrieval. Opens the electronic domain.
2. **defect_formation_energy (charged, DFT route)** - `FormationEnergyMaker`
   (Freysoldt/Kumagai finite-size corrections, Fermi-level & charge-state
   dependence). Richer than the pymatgen scan's neutral MLIP formula; same node,
   EXPECTED_AGREE at neutral only.
3. **magnetic_moment (m_i, M_total, mu_B)** - `Outcar.magnetization` /
   `.total_magnetization`. Direct VASP producer for the pymatgen scan's
   magnetism candidate; VASP is the DFT ground truth for the MLIP CHGNet magmom
   head.
4. **electronic transport (sigma_el S/m, Seebeck V/K, kappa_el W/m/K)** -
   `VaspAmsetMaker`. New thermoelectrics domain; `kappa_el` is the ELECTRONIC
   contribution, distinct from the map's lattice `ThermalConductivity`.
5. **dielectric_function eps(omega)** - `OpticsMaker` (LOPTICS). Optical spectrum
   distinct from the static `DielectricTensor`; independent-particle scheme
   (omits BSE/excitonic).
6. **spontaneous_polarization P_s (C/m^2)** - `FerroelectricMaker` (LCALCPOL
   Berry phase). The polarization QUANTUM / branch ambiguity is a natural
   lattice-gauge showcase for the map's gauge machinery.

Lower priority: COHP (chemistry diagnostic, representation-only); charge_density
(matches the map's explicitly deferred `ChargeDensity` node, needs a real-space
grid index kind).

## Open questions (full list in JSON `open_questions`)

1. **Stress sign** (headline): VASP is compression-positive = the map store; no
   flip to map-store. AtomisticSkills's atomate2 paths flip to ASE
   (tension-positive); its raw path does not. Encode the VASP `Stress`
   representation as compression-positive.
2. **Stress units** (CORRECTED): kbar from BOTH routes. atomate2
   `TaskDoc.output.stress` is kbar (emmet `OutputDoc.stress` "units of kB"), not
   GPa. AtomisticSkills `atomate2_utils.py:456` is 10x too large as a result.
3. **Constant generation**: ase.units.GPa is CODATA-2014 (`160.21766208`), not
   pymatgen's CODATA-2018 (`160.21766339999996`).
4. **Energy variant / smearing**: e_0_energy vs e_fr_energy vs e_wo_entrp;
   per-cell analog of the QE smeared-free-energy trap.
5. **Absolute energy zero**: PAW + XC preset dependent; relative energies only.
6. **atomate2 maker names VERIFIED (2026-07-09)**: atomate2 0.1.4 and emmet-core
   0.87.1 downloaded (`pip download --no-deps`) and read from the wheels. All
   claimed maker classes exist at the claimed paths; no invented API.
   `TaskDoc.output.stress` is **kbar** (not GPa) and `.energy` is **e_0_energy**
   (confirmed via emmet `OutputDoc` and pymatgen `final_energy`).
7. **Elastic route**: `Outcar.elastic_modulus` (kbar, IBRION=6) is an alternate
   representation of `ElasticConstants` (landing from the pymatgen encode now),
   an EXPECTED_AGREE with the MLIP/matcalc route.
8. **Static vs frequency-dependent dielectric**: `DielectricTensor` (LEPSILON,
   eps_inf) vs `dielectric_function` (LOPTICS, eps(omega)).
9. **Defect DFT vs MLIP**: charged (this scan) vs neutral (pymatgen scan); same
   node, EXPECTED_AGREE at neutral charge only.

## Review verdicts (2026-07-09)

Adversarial deep review of commit `de90bf7`'s catalog. The three load-bearing
AtomisticSkills stress paths were opened line-by-line; `pymatgen.io.vasp.outputs`
was read directly from the base env (pymatgen 2025.6.14); `ase.units.GPa` was
recomputed live; `atomate2` (0.1.4) and `emmet-core` (0.87.1) were downloaded
with `pip download --no-deps --dest /tmp/a2src` and every claimed maker class /
output schema field was read from the wheels; every already-mapped node was
checked against `docs/data/graph.json` (59 nodes) and against the in-flight
pymatgen encode set.

### The stress sign chain (verified end to end)

**VASP print -> each AtomisticSkills path -> map store.**

- **VASP print**: compression-positive, `sigma_VASP = -(1/V) dE/d(strain)`.
  Documentation-of-record (independent of the AtomisticSkills comments):
  pymatgen `ElasticTensor.from_independent_strains` applies
  `c_ij *= -0.1  # Convert units/sign convention of vasp stress tensor`
  (`analysis/elasticity/elastic.py:518-519`). On a stress-fit route where the
  physical stiffness is `C = +d(sigma_tension)/d(strain)`, the `-1` is consistent
  only if VASP stress is compression-positive. (The `0.1` there is kbar->GPa.)
- **Map store**: also compression-positive, `sigma_store = -(1/V) dE/d(strain)`,
  positive diagonal = compressive (`omai/dft_ground_state/representation/qe.py:116-131`,
  from vendored QE `Modules/cell_base.f90`: `fcell ~ (stress - press*I)`).
- **Path (a) raw Vasprun** (`vasp_parser.py:79-81`): `* 0.1 * ase.units.GPa`, no
  `-1`. Stays compression-positive. **Map-store-consistent in sign; correct in
  magnitude** (kbar -> eV/A^3).
- **Path (b) TaskDoc extract_results** (`atomate2_utils.py:456`):
  `* -1.0 * ase.units.GPa`. Flips to ASE tension-positive AND is 10x too large
  (treats kbar as GPa). Wrong in magnitude; ASE-signed (map-store-INconsistent
  in sign).
- **Path (c) MongoDB** (`atomate2_utils.py:726`): `* -0.1 * ase.units.GPa`.
  Flips to ASE; correct in magnitude. ASE-signed.

**Conclusion: VASP -> map store needs NO sign flip** (both compression-positive).
Encode the VASP `Stress` representation as `{sigma: kbar}`, compression-positive,
and note that AtomisticSkills re-signs to ASE in its two atomate2 paths (and, in
path b, is 10x too large). This confirms the scanner's central sign finding; it
corrects the scanner's units claim.

### Corrections that changed physics (not typos)

- **vasp-stress-tensor: CORRECTED (units).** The scanner claimed
  `atomate2 TaskDoc.output.stress` is **GPa** ("Atomate2 standardizes stress to
  GPa", following the AtomisticSkills code comment at `atomate2_utils.py:454`).
  It is **kBAR**. `TaskDoc` is `emmet.core.tasks.TaskDoc`; `OutputDoc.stress` is
  documented "The stress on the cell in units of kB." (`emmet-core 0.87.1
  tasks.py:110-111`), populated by copying the raw pymatgen ionic-step stress
  with no conversion (`tasks.py:158-181`). Downstream consequence:
  `atomate2_utils.py:456` (`* -1.0 * ase.units.GPa`, treating the value as GPa)
  is **10x too large**; it should be `* -0.1`. The catalog now declares a single
  `{sigma: kbar}` and flags the 10x as an AtomisticSkills source defect (report
  upstream; not a map-encode issue). Sign finding unchanged.

### Per-entry verdicts

- **vasp-total-energy: CONFIRMED.** `Vasprun.final_energy` returns `e_0_energy`
  (energy(sigma->0)) with the electronic-diff bugfix reconstruction
  (`outputs.py:700-714`), confirmed by direct read. Outcar TOTEN variants at
  `:6213-6215` (`free energy    TOTEN`->e_fr_energy, `energy without entropy`->
  e_wo_entrp, `energy(sigma->0)`->e_0_energy). emmet `OutputDoc.energy` is "eV".
  So the map's VASP `TotalEnergy` should declare **e_0_energy** (the sigma->0
  extrapolation), the per-cell analog of the QE `!` smeared-free-energy note.
  Dimension {M:1,L:2,T:-2} = energy, correct. Node `TotalEnergy` present in
  graph.json. NOTE: `vasp_parser.py:89` builds `energy_history` from
  `e_wo_entrp`, a third variant, but that history is not the mapped observable.
- **vasp-forces: CONFIRMED.** `varray name='forces'` (`outputs.py:555-556`);
  emmet `OutputDoc.forces` "units of eV/A". `Vasprun.forces[-1]` = final ionic
  step (`vasp_parser.py:69`). Ry/bohr->eV/A factor 25.71104309541616 recomputed
  (13.605693122994 / 0.529177210903). Dimension {M:1,L:1,T:-2} = force. Node
  present.
- **vasp-stress-tensor: CORRECTED (units, see above); sign CONFIRMED.** Node
  present. Dimension {M:1,L:-1,T:-2} = pressure, correct.
- **vasp-structure: CONFIRMED.** Opaque Structure container, angstrom; node
  present. Anchors hold.
- **vasp-elastic-modulus: CONFIRMED.** `Outcar.elastic_modulus` parses
  `TOTAL ELASTIC MODULI (kBar)` (`outputs.py:2824`, header regex verified); kbar
  -> GPa via `*0.1`. `from_independent_strains(vasp=True)` `*=-0.1` for the
  stress-FIT route (`elastic.py:519`) is a DIFFERENT path (correctly noted). The
  `atomate2.vasp.flows.elastic.ElasticMaker` claim VERIFIED present in the wheel
  (`class ElasticMaker(BaseElasticMaker)`). ElasticConstants present in
  graph.json (as `ElasticConstants`). Alternate-representation verdict holds.
- **vasp-born-charges: CONFIRMED.** `Outcar.born` "BORN EFFECTIVE CHARGES"
  section (`outputs.py:3209-3257`); dimensionless (units of e). BornCharges
  present in graph.json. Same node QE grounds.
- **vasp-dielectric-tensor: CONFIRMED.** Static clamped-ion eps_inf (LEPSILON) ->
  `DielectricTensor` (present in graph.json), cleanly separated from the
  frequency-dependent eps(omega) spectrum (see next). Dimensionless.
- **band-gap-and-electronic-dos: CONFIRMED as new-node-candidate.**
  `BSVasprun.get_band_structure().get_band_gap()`, `is_metal`, `efermi` anchors
  verified in `plot_band_structure.py:69-78`. `BandStructureMaker` VERIFIED in
  the wheel (`vasp.flows.core`). No electronic-structure node on the map;
  high-value candidate. Overlaps the pymatgen scan's band-gap candidate.
- **dielectric-function-spectrum: CONFIRMED as new-node-candidate.**
  `OpticsMaker` (LOPTICS) VERIFIED in the wheel (`vasp.flows.core`);
  `ensure_frequency_dependent_calculation` guard verified
  (`plot_dielectric.py:170-186`). CLEANLY DISTINCT from the static
  `DielectricTensor` node (eps_inf = omega->infinity limit); distinction check
  passes.
- **electronic-transport-coefficients: CONFIRMED as new-node-candidate.**
  `VaspAmsetMaker` VERIFIED in the wheel (`vasp.flows.amset`); import anchor
  verified (`mat-dft-electronic-transport/generate_inputs.py:14`). AMSET
  `kappa_el` is the ELECTRONIC contribution, CLEANLY separate from the map's
  lattice `ThermalConductivity[...]` family (present in graph.json as
  configured nodes); distinction check passes.
- **spontaneous-polarization: CONFIRMED as new-node-candidate.**
  `FerroelectricMaker` VERIFIED in the wheel (`vasp.flows.ferroelectric`);
  LCALCPOL Berry-phase branch-mapping anchor verified
  (`mat-dft-ferroelectric/generate_inputs.py:14,61-63`). Dimension
  {L:-2,T:1,I:1} = C/m^2, correct.
- **magnetic-moment-vasp: CONFIRMED as new-node-candidate.**
  `Outcar.magnetization` / `.total_magnetization` anchors verified
  (`vasp_parser.py:121-122`); `parse_magnetic_moments.py` present. mu_B. Overlaps
  the pymatgen scan's magnetic-moment candidate and the in-flight encode set's
  MagneticMoment (not yet in graph.json) -- may land as MagneticMoment.
- **defect-formation-energy-dft: CONFIRMED as new-node-candidate.**
  `FormationEnergyMaker` VERIFIED in the wheel (`vasp.flows.defect`). Import
  anchor is in `mat-defect-energy-dft/SKILL.md:67` (the build_diagram.py:67 line
  is the E_f formula comment, both cited). Charged/DFT route, EXPECTED_AGREE with
  the pymatgen neutral MLIP route at neutral charge only. eV.
- **cohp-bonding-vasp-lobster: CONFIRMED representation-only.**
  `VaspLobsterMaker` VERIFIED in the wheel (`vasp.flows.lobster`). Chemistry
  diagnostic, out of the thermal/mechanical DAG scope.
- **atomate2-workflow-framework: CONFIRMED representation-only.** All maker
  classes in `get_flow_maker` VERIFIED in the wheel. The VASP analog of
  `QE_SOLVE_GROUND_STATE`; encode as an `OperatorRepresentationSpec` on
  `solve_ground_state`.
- **vasp-charge-density: CONFIRMED as deferred candidate.** Matches the map's
  explicitly deferred `ChargeDensity` (`nodes.py:19-22`). `Chgcar`/`Locpot`/
  `Wavecar` are pymatgen parsers; not consumed as a mapped observable. Stays
  deferred.

### UNVERIFIED

None. The scanner's two "confirm with atomate2-agent env" items (TaskDoc stress
units, energy variant) were resolved by downloading the atomate2 + emmet-core
wheels: stress is kbar (corrected), energy is e_0_energy (confirmed). CAVEAT: the
downloaded atomate2 is 0.1.4, older than the (unversioned) AtomisticSkills
`atomate2-agent` pin; maker names are stable across versions but a re-run against
the pinned build is advisable if any maker is renamed upstream.

### Decisions for the orchestrator (not for the reviewer)

1. **VASP `Stress` representation: encode as `{sigma: kbar}`,
   compression-positive, NO sign flip to the map store.** This is the confirmed
   sign chain. Record that AtomisticSkills re-signs to ASE (tension-positive) in
   its two atomate2 paths and that path (b) `atomate2_utils.py:456` is
   additionally 10x too large (kbar mislabeled GPa). The 10x is an AtomisticSkills
   source defect worth reporting upstream; it does not affect the map's stored
   representation.
2. **VASP `TotalEnergy`: declare the e_0_energy (sigma->0) variant** as the
   mapped observable, the per-cell analog of the QE smeared-free-energy note. A
   cross-code EXPECTED_AGREE with QE must compare the same variant AND account
   for the different absolute energy zero (PAW/pseudopotential + XC dependent).
3. **Constant generation**: `ase.units.GPa` is CODATA-2014
   (`1/ase.units.GPa = 160.21766208`, verified live), differing from the
   pymatgen elasticity constant `160.21766339999996` (CODATA-2018) at ~1e-8.
   Record on the VASP `Stress` representation; physically negligible.
4. **Which new-node-candidate domains to ingest**: band_gap, magnetic_moment,
   defect_formation_energy overlap the pymatgen scan's candidates (and
   MagneticMoment / defect are in the in-flight encode set, not yet in
   graph.json); electronic transport, dielectric spectrum, and spontaneous
   polarization open new domains. Ranking in "Top encode candidates".
5. **atomate2 version pin**: the AtomisticSkills `atomate2-agent` env has no
   explicit atomate2 pin in `core_env.yaml`. Pin it before an encode relies on a
   specific maker's output schema (the emmet `OutputDoc` "units of kB" contract
   should also be pinned, since a future emmet could restandardize).
