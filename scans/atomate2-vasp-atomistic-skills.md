# atomate2 and VASP as used by AtomisticSkills: scan report

Scan of **atomate2** (the DFT workflow framework) and **VASP** (the DFT engine
underneath it) as the AtomisticSkills (arXiv 2605.24002) DFT stack actually uses
them. Companion catalog: `scans/atomate2-vasp-atomistic-skills.json` (18
entries). Sources: the shared DFT driver `src/utils/dft/atomate2_utils.py`, the
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
| `VaspAmsetMaker` (AMSET) | dense mesh + scattering | sigma_el, Seebeck, kappa_el, mobility | none (new: electronic transport) |
| `FerroelectricMaker` | LCALCPOL Berry phase | spontaneous polarization P_s | none (new: spontaneous_polarization) |
| `FormationEnergyMaker` | charged defect supercells | E_f(defect, q) | none (new: defect_formation_energy, charged/DFT route) |
| `VaspLobsterMaker` | LOBSTER projection | COHP / ICOHP | none (representation-only) |
| `ElectronPhononMaker` | supercell displacements | e-ph coupling (below map floor) | none |
| OUTCAR `Outcar.elastic_modulus` (IBRION=6) | direct elastic | C_ij (kbar) | ElasticConstants (alternate representation) |
| OUTCAR `Outcar.born_charges` / `.dielectric_tensor` | LEPSILON | Z*, eps_inf | BornCharges, DielectricTensor |
| OUTCAR `Outcar.magnetization` | ISPIN=2 | m_i, M_total | none (new: magnetic_moment) |

## Entry counts by status (18 entries)

- **already-mapped: 7** - vasp-total-energy (`TotalEnergy`), vasp-forces
  (`Forces`), vasp-stress-tensor (`Stress`), vasp-structure (`Structure`),
  vasp-elastic-modulus (`ElasticConstants`, alternate representation),
  vasp-born-charges (`BornCharges`), vasp-dielectric-tensor (`DielectricTensor`,
  static eps_inf). VASP is a SECOND representation of every one of these, the
  same physics QE / MLIP already ground.
- **new-node-candidate: 8** - band-gap-and-electronic-dos,
  dielectric-function-spectrum, electronic-transport-coefficients,
  spontaneous-polarization, magnetic-moment-vasp, defect-formation-energy-dft,
  cohp is representation-only (below), vasp-charge-density (DEFERRED, matches the
  map's explicitly deferred ChargeDensity). Note: band_gap, magnetic_moment,
  defect_formation_energy overlap the pymatgen scan's candidates; this scan adds
  the direct-VASP/atomate2 producers.
- **representation-only / framework: 3** - cohp-bonding-vasp-lobster (chemistry
  diagnostic), atomate2-workflow-framework (the operator-representation
  provenance layer, VASP analog of `QE_SOLVE_GROUND_STATE`), and
  vasp-charge-density counted above as deferred-candidate.

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
   `stress * -1.0 * ase.units.GPa`.
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

2. **Stress units: kbar vs GPa, same run.** Raw `pymatgen Vasprun.stress` is
   **kBAR** (VASP native varray, `outputs.py:557-558`); atomate2
   `TaskDoc.output.stress` is **GPa** (atomate2 standardizes,
   `atomate2_utils.py:454`). Factor of 10. `vasp_parser.py:79-81` uses
   `*0.1*ase.units.GPa` (kbar); `atomate2_utils.py:456` uses `*ase.units.GPa`
   (GPa, no 0.1). Declare BOTH `observable_units` on the VASP `Stress`
   representation. `1 kbar = 0.1 GPa` exactly.

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
2. **Stress units**: kbar (raw Vasprun) vs GPa (atomate2 TaskDoc), same run.
   Declare both.
3. **Constant generation**: ase.units.GPa is CODATA-2014 (`160.21766208`), not
   pymatgen's CODATA-2018 (`160.21766339999996`).
4. **Energy variant / smearing**: e_0_energy vs e_fr_energy vs e_wo_entrp;
   per-cell analog of the QE smeared-free-energy trap.
5. **Absolute energy zero**: PAW + XC preset dependent; relative energies only.
6. **atomate2 not importable in base env**: maker names anchored to import sites,
   not atomate2 source. A reviewer with `atomate2-agent` should confirm
   `TaskDoc.output.stress` is GPa and `.energy` is e_0_energy.
7. **Elastic route**: `Outcar.elastic_modulus` (kbar, IBRION=6) is an alternate
   representation of `ElasticConstants` (landing from the pymatgen encode now),
   an EXPECTED_AGREE with the MLIP/matcalc route.
8. **Static vs frequency-dependent dielectric**: `DielectricTensor` (LEPSILON,
   eps_inf) vs `dielectric_function` (LOPTICS, eps(omega)).
9. **Defect DFT vs MLIP**: charged (this scan) vs neutral (pymatgen scan); same
   node, EXPECTED_AGREE at neutral charge only.
