# amset (electronic transport) as used by AtomisticSkills: scan report

Scan of **amset 0.5.1** (Ab-initio Scattering and Transport: electronic transport
from first principles) as the AtomisticSkills (arXiv 2605.24002) skill
`mat-dft-electronic-transport` actually uses it. Companion catalog:
`scans/amset-atomistic-skills.json` (7 entries). This is a SCAN: it catalogs, it
does not map code. It seeds a future electronic-transport domain.

amset is **not importable** in the miniconda base env (`No module named 'amset'`);
anchors are read from the pip-downloaded wheel (`pip download --no-deps --dest
/tmp/amsetsrc amset` -> `amset-0.5.1-py3-none-any.whl`, unzipped to
`/tmp/amsetsrc/amset_pkg`) and from the vendored skill tree.

## How AtomisticSkills uses amset (indirect, through atomate2)

The single skill is `mat-dft-electronic-transport`. It reaches amset **only
through atomate2's `VaspAmsetMaker`** (`atomate2.vasp.flows.amset`,
`generate_inputs.py:14`), the same maker the atomate2-vasp scan recorded. The
skill never calls the amset Python API directly: it builds the VASP+AMSET jobflow
DAG (relax -> dense uniform bands -> elastic tensor -> deformation potentials ->
static+dielectric -> AMSET run, `generate_inputs.py:36-50`), jobflow-remote
submits it to Perlmutter, and the amset transport JSON is parsed "natively using
standard amset.plot utilities" (`SKILL.md`). So the amset output contract
(`amset/core/data.py:to_data`) is the ground truth, and `VaspAmsetMaker` is the
provenance layer (the electronic-transport analog of `QE_SOLVE_GROUND_STATE` /
the atomate2 workflow framework the VASP scan already catalogued).

The GaAs example (`examples/GaAs/`) sets `doping=(1e16,1e17,1e18)` cm^-3,
`temperatures=(300.,400.)` K, `use_hse_gap=False`, and quotes 300 K electron
mobility ~8500 and hole ~400 cm^2/Vs, ADP + POP (+ piezoelectric) limited.

## Graph snapshot (freshness at my end)

`docs/data/graph.json` read at **73 nodes** at scan time. **None** of amset's
transport quantities is present (no ElectricalConductivity, Seebeck, Mobility,
ElectronicThermalConductivity, ScatteringRate). Three cross-domain INPUTS amset
needs ARE present: `DielectricTensor`, `BornCharges`, `Frequency` (phonon), plus
`ElasticConstants`. The map's `ThermalConductivity[*]` family is **lattice**
thermal conductivity; amset's `kappa_e` is the **electronic** contribution: same
dimension, different carrier.

**DEEP-REVIEW freshness (2026-07-10)**: at the start of review `map/log.jsonl` was
**144 records** / graph **73 nodes**. **During** review an encode landed records
**145-147** (a stability surface-adsorption node + a mechanics equation-of-state
node), taking the working tree to **147 records / 74 nodes**. None of those are
electronic-transport, so this catalog's core claim (no `ElectricalConductivity` /
`Seebeck` / `Mobility` / `ElectronicThermalConductivity` / `ScatteringRate` node)
**still holds** at 74 nodes. CORRECTION: the lattice `ThermalConductivity[*]`
family has **9 nodes** (2 `bte_solver` + 7 `transport_model`), **not 11** as in the
original scan. `DielectricTensor`, `BornCharges`, `Frequency`, `ElasticConstants`,
`BandGap`, `Voltage` all confirmed present.

## Entry counts by status (7 entries)

- **new-node-candidate: 5** - `amset-electrical-conductivity-electronic`
  (sigma, S/m), `amset-seebeck-coefficient` (S, muV/K),
  `amset-electronic-thermal-conductivity` (kappa_e, W/m/K),
  `amset-carrier-mobility` (mu, cm^2/Vs), plus two scattering INPUTS produced by
  `VaspAmsetMaker`: `amset-deformation-potential` (eV) and
  `amset-piezoelectric-constant` (C/m^2).
- **representation-only: 1** - `amset-scattering-rates` (per-mechanism 1/s
  spectrum feeding the transport tensors, resolved per band/k).
- **already-mapped: 0** - amset produces no quantity the map already carries; its
  cross-domain overlap is on the INPUT side (DielectricTensor, Frequency,
  ElasticConstants, BornCharges), catalogued under `cross_domain_inputs` rather
  than as already-mapped output entries.

## Transport-quantity dimension derivations

Base-axis order `(M, L, T, Th, N, I, J)` (`dimensions.py:26`). All four verified
by hand AND programmatically against the map's own `Dimension` objects.

### Seebeck coefficient S = V/K  (VERIFIED)

Volt (the `VOLTAGE` node) = `M L^2 T^-3 I^-1`. Per kelvin adds `Th^-1`.

    S = V/K = (M=1, L=2, T=-3, Th=-1, N=0, I=-1, J=0)

Matches the task-supplied `(1,2,-3,-1,0,-1,0)`. amset serves **muV/K** (source
multiplies raw V/K by 1e6, `transport.py:191`; header `S [uV/K]`, `run.py:583`).

### Carrier mobility mu = cm^2/(V.s)  (VERIFIED, from first principles)

    mu = L^2 / (V . s)
    V . s = (M L^2 T^-3 I^-1)(T) = M L^2 T^-2 I^-1
    mu = L^2 / (M L^2 T^-2 I^-1) = L^2 . M^-1 L^-2 T^2 I = M^-1 T^2 I
    mu = (M=-1, L=0, T=2, Th=0, N=0, I=1, J=0)

So `(M-1, T2, I1)` is correct. The task's alternative guess
`(0,0,1,0,0,1,-1)` is **wrong** (that would be `L T^-1 I J^-1`, not a mobility).
amset serves **cm^2/(V.s)** (`transport.py:133-135`, `run.py:583,617`);
cm^2 -> m^2 is x1e-4.

### Electronic electrical conductivity sigma = S/m  (VERIFIED)

    Siemens = A/V = I / (M L^2 T^-3 I^-1) = M^-1 L^-2 T^3 I^2
    S/m = M^-1 L^-3 T^3 I^2
    sigma = (M=-1, L=-3, T=3, Th=0, N=0, I=2, J=0)

**Identical exponent vector to the config-thermo scan's IonicConductivity**
`(M=-1,L=-3,T=3,I=2)`. amset serves **S/m** (`run.py:583`, `data.py:484`), NOT
S/cm. This is the conductivity-family finding (below).

### Electronic thermal conductivity kappa_e = W/(m.K)  (VERIFIED)

    W/(m.K) = (M L^2 T^-3) / (L K) = M L T^-3 Th^-1
    kappa_e = (M=1, L=1, T=-3, Th=-1, 0, 0, 0)

**Identical to the map's lattice `ThermalConductivity`** (`dimensions.py:115`).
Same dimension, distinct by carrier (below). amset's source itself flags the
unit as unconfirmed: `data.py:483 '# TODO: confirm unit of kappa'`, header unit
`?` (`data.py:484`); W/(m.K) is the BoltzTraP2 `calc_Onsager_coefficients`
convention.

### Scattering rate 1/tau = 1/s = FREQUENCY

`(0,0,-1,0,0,0,0)` (`plot/rates.py:22-26`). Per-mechanism, added by Matthiessen
(`1/tau_total = sum_mech 1/tau_mech`, `transport.py:101,163`).

## The transport-tensor grid (spectrum-layer answer)

Every transport quantity is a function of **(doping, temperature)**, stored as a
full `(n_doping, n_temperature, 3, 3)` tensor (`data.py` np.zeros
`n_t_size + (3,3)`; `to_data()` writes the upper triangle xx,xy,xz,yy,yz,zz per
`(n,t)` row, `data.py:464-489`). They are **full arrays, not scalars**. Scalar
reduction (`tensor_average`, isotropic trace/3) is a reporting convenience only
(`run.py:588-590`); the GaAs single-number mobility is a reduction at one
`(doping, T)`. Ingest the full grid via the representation/discretization layer,
with doping (cm^-3) and T (K) as the grid axes. Doping sign convention: **positive
= p-type, negative = n-type** (`defaults.yaml:8`).

## Scattering mechanisms (per-mechanism rate decomposition)

amset's contribution over bare BoltzTraP2 is the momentum-relaxation-time
scattering that replaces BoltzTraP2's constant relaxation time. Seven mechanism
classes, each with a short name and `required_properties`:

| name | mechanism | kind | required properties |
|---|---|---|---|
| ADP | Acoustic Deformation Potential | elastic | deformation_potential (eV), elastic_constant (GPa) |
| IMP | Ionized Impurity | elastic | defect_charge, static_dielectric, compensation_factor |
| PIE | Piezoelectric | elastic | piezoelectric_constant (C/m^2), elastic_constant, high_frequency_dielectric, free_carrier_screening |
| POP | Polar Optical Phonon | inelastic | pop_frequency (THz), static_dielectric, high_frequency_dielectric, free_carrier_screening |
| CRT / MFP / SRT | constant tau / mean free path / base tau | basic | constant_relaxation_time (s) / mean_free_path (nm) / base_relaxation_time (s) |

`scattering_type: auto` (`defaults.yaml:6`) picks the physical mechanisms from
the supplied materials parameters. `separate_mobility` (default True) gives a
per-mechanism mobility breakdown (`run.py:615-624`), the resolved spectrum for
"which channel limits mobility".

## Cross-domain input finding (the strongest edge candidate)

amset's `compute_electronic_transport` operator is **genuinely cross-domain**:
its scattering inputs come from the phonon, dielectric, and mechanical domains,
several of which the map ALREADY carries.

Already on the map (feed amset UPSTREAM through the phonon/dielectric calc):

- `DielectricTensor` (eps_inf) - amset needs it for POP/PIE/IMP screening. But
  amset ALSO needs the **static** eps_0 (ion-clamped + ionic), which the map does
  not carry separately (`static_dielectric` + `high_frequency_dielectric`,
  `inelastic.py:62-64`). eps_0 is a distinct dielectric quantity (new-node note).
- `Frequency` (phonon) - the effective POP frequency `pop_frequency` (THz,
  `defaults.yaml:41`) is a reduction of the phonon spectrum omega_LO.
- `ElasticConstants` - **REVIEW CORRECTION**: amset takes the **full rank-4**
  elastic tensor, not a longitudinal scalar. `cast_elastic_tensor` (`util.py:115`)
  expands any scalar/6x6-Voigt/3x3x3x3 input to the full `(3,3,3,3)` `C_ijkl`; the
  longitudinal modulus `c_long` is derived per q-direction at run time via the
  Christoffel construction (`get_christoffel_tensors` einsum + `solve_christoffel_
  equation`, `elastic.py:180-183,266-267`). atomate2 `VaspAmsetMaker` wires
  `elastic.output.elastic_tensor.raw` (`vasp/flows/amset.py:290`), the full tensor.
- `BornCharges` - drive omega_LO and the Frohlich POP coupling; feed amset
  upstream through the phonon calc, not as a direct amset argument (provenance).
  **REVIEW CONFIRMED** from atomate2: `VaspAmsetMaker` calls
  `calculate_polar_phonon_frequency(structure, normalmode_frequencies,
  normalmode_eigenvecs, outcar["born"])` (`vasp/flows/amset.py:245-250`) to reduce
  Born charges + normal modes into the single effective `pop_frequency`.

Not yet on the map (produced by `VaspAmsetMaker`, new source-node candidates):

- `deformation_potential` (eV, VBM+CBM) - the strained-band step.
- `piezoelectric_constant` (C/m^2) - the full rank-3 e-tensor (3x6 Voigt ->
  3x3x3, `util.py:146`), contracted with the inverse eps_inf to the h-coefficient
  (`elastic.py:398-406`). Same dimension as SpontaneousPolarization (VASP-scan
  candidate). **REVIEW**: NOT wired by `VaspAmsetMaker` (no `piezo` in
  `flows/amset.py`); PIE is only active if the user supplies it via `amset_settings`.
- the dense uniform **band structure / wavefunction** amset interpolates
  (BoltzTraP2 `fite`/`sphere`, `bandstructure.py:10,53`); the map has `BandGap`
  but not the full bands.

## The conductivity-family proposal (facts + proposal, NOT decided)

**Facts.** Electronic sigma `(M=-1,L=-3,T=3,I=2)` = S/m has the **exact** exponent
vector of the config-thermo scan's IonicConductivity (Nernst-Einstein, mS/cm).
Both are electrical conductivity S/m. They differ only in carrier (band
electrons/holes vs mobile ions), producing operator (Onsager over DFT bands vs
Nernst-Einstein over tracer diffusivity), domain (electronic-transport vs
diffusion), and serving unit (S/m vs mS/cm). PRECEDENT: the map's
`ThermalConductivity` is already a labeled family that keeps same-dimension
route/carrier variants apart via labels (`transport_model=wigner|green_kubo|...`,
`bte_solver=rta|direct_inverse`, `registry.py` LABEL_KEYS).

**Proposal (deferred to orchestrator).** Prefer **ONE quantity tag
`electrical_conductivity` carrying a `carrier` label**:
`ElectricalConductivity[carrier=electronic]` (amset) and
`ElectricalConductivity[carrier=ionic]` (renaming the config-thermo
IonicConductivity). They share the exact dimension AND the physical quantity;
they differ only in which particle carries the charge, which is exactly a label's
job (mirrors `ThermalConductivity[transport_model=...]`). A new `LABEL_KEYS`
entry `carrier: {electronic, ionic}` would be the registry change. Weaker
alternative: keep `IonicConductivity` its own tag and add `ElectricalConductivity`
as a sibling-by-tag (loses the shared-quantity insight, risks a false non-merge).
Either way the serving-unit split (S/m vs mS/cm) must be recorded per
representation.

## The lattice-vs-electronic-kappa distinction (MANDATORY)

amset's `kappa_e` (`electronic_thermal_conductivity`, `data.py:80,419,473`) and
the map's lattice `ThermalConductivity[*]` family share the exact dimension
W/(m.K) `(1,1,-3,-1,0,0,0)`. They are the two ADDITIVE contributions to the total
measured thermal conductivity (`kappa_total = kappa_lattice + kappa_electronic`),
from different carriers, different operators, different domains. Merging them (or
letting them false-merge on shared dimension) is a physics error. Register the
electronic kappa with a carrier label that keeps it distinct:
`ThermalConductivity[carrier=electronic]` (parallel to the conductivity carrier
label; the existing 9 lattice nodes gain `carrier=lattice`) OR a distinct
`ElectronicThermalConductivity` tag. Same structural pattern as the conductivity
family: a carrier label over a shared dimension. amset's own `# TODO: confirm
unit of kappa` (`data.py:483`) means the unit assertion W/(m.K) should carry a
"confirm against BoltzTraP2 bandlib" provenance note.

## Unit convention traps

1. **sigma is S/m, NOT S/cm** (`run.py:583`, `data.py:484`). `1 S/cm = 100 S/m`;
   the sibling IonicConductivity serves mS/cm (`1 mS/cm = 0.1 S/m`). Three
   serving units in the wild for one dimension.
2. **kappa unit unconfirmed by amset** (`data.py:483 '# TODO: confirm unit of
   kappa'`, header `?`). W/(m.K) by BoltzTraP2 convention; flag on the
   representation.
3. **lattice vs electronic kappa** share W/(m.K); MANDATORY distinct by carrier;
   total = sum. Never merge on dimension.
4. **electronic vs ionic conductivity** share `(M=-1,L=-3,T=3,I=2)` = S/m;
   different carrier/domain. Carrier label proposed; do not false-merge or
   false-split.
5. **Seebeck muV/K** (source `*1e6`, `transport.py:191`); sign carries carrier
   type.
6. **Mobility only for non-metals** (`transport.py:47-49`); sigma/seebeck/kappa
   still computed. Per-mechanism breakdown needs `separate_mobility` (default
   True).
7. **Per-mechanism rate decomposition is a Matthiessen sum**
   (`1/tau_total = sum 1/tau_mech`, `transport.py:101,163`). Per-mechanism rates
   and mobilities are the resolved spectrum; the transport tensors are the sum.
   Do not double-count.
8. **Doping sign**: positive = p-type, negative = n-type (`defaults.yaml:8`);
   cm^-3 input, bohr^-3 internal.
9. **Transport tensors are (doping, T, 3, 3)**, not scalars. GaAs single-number
   mobility is a `tensor_average` at one point.
10. **eps_0 vs eps_inf**: amset needs BOTH `static_dielectric` (eps_0) and
    `high_frequency_dielectric` (eps_inf). The map's `DielectricTensor` is
    eps_inf only; eps_0 is a distinct quantity amset requires.
11. **Internal atomic units**: amset works in Hartree atomic units
    (`constants.py`); all serving-unit conversions happen at output. Cross-code
    EXPECTED_AGREE must use the serving units above.
12. **Indirect use**: AtomisticSkills never calls amset's Python API directly; it
    goes through `VaspAmsetMaker` and reads the amset JSON. The `to_data` output
    schema (`data.py:461-491`: doping, T, Fermi_level, then sigma/seebeck/kappa/
    mobility tensors) is the contract.

## Open questions (full list in JSON `open_questions`)

1. **Conductivity family topology**: `ElectricalConductivity[carrier=...]` as one
   labeled family (recommended) vs distinct tags. Would rename the config-thermo
   IonicConductivity; needs a `carrier` LABEL_KEY. DEFERRED.
2. **Electronic kappa identity**: `ThermalConductivity[carrier=electronic]`
   (adds `carrier=lattice` to the 9 existing lattice nodes) vs a distinct
   `ElectronicThermalConductivity` tag.
3. **Seebeck standalone vs thermoelectric bundle** (sigma, S, kappa_e, power
   factor S^2 sigma, ZT). amset computes the first three; PF/ZT are downstream.
   Mint Seebeck now (dimension verified), ZT later.
4. **Scattering rates**: representation-only (per band/k spectrum) confirmed, or
   a top-level `ScatteringRate` node? Recommend representation-only.
5. **compute_electronic_transport edge**: which inputs are edges from existing
   nodes (DielectricTensor, Frequency->pop_frequency, ElasticConstants,
   BornCharges provenance) vs new source nodes (deformation_potential,
   piezoelectric_constant, static eps_0, band structure)?
6. **Static eps_0**: mint a `StaticDielectricTensor` distinct from the electronic
   eps_inf (the VASP scan already split eps_inf from eps(omega); eps_0 is a
   third distinct dielectric quantity).
7. **PiezoelectricConstant** (C/m^2) shares SpontaneousPolarization's dimension;
   one polarization family or distinct?
8. **kappa unit**: confirm W/(m.K) against BoltzTraP2 `bandlib` before
   EXPECTED_AGREE (amset's `# TODO`).
9. **Version pin**: amset 0.5.1 downloaded; the atomate2-agent env is unpinned.
   Pin before an encode relies on the `to_data` schema; the kappa-unit TODO may
   be fixed upstream.

## Review verdicts (2026-07-10)

Adversarial deep-review, default-distrust. Four transport dimensions re-derived
independently in pure Python **and** cross-checked against
`omai.operator.dimensions` (`VOLTAGE`, `THERMAL_CONDUCTIVITY`, `FREQUENCY`).
amset 0.5.1 source re-read (`/tmp/amsetsrc/amset_pkg`); atomate2 0.1.4
`VaspAmsetMaker` re-read (`/tmp/a2src/extracted/.../vasp/flows/amset.py`);
config-thermo `IonicConductivity` dimension re-read; `registry.py` LABEL_KEYS
re-read; `map/log.jsonl` and `graph.json` re-read (144 records / 73 nodes at review
start, 147 / 74 after a concurrent non-transport encode landed 145-147).

**Dimension verdicts (all VERIFIED).**

- Seebeck `(1,2,-3,-1,0,-1,0)` = V/K (from omai `VOLTAGE` minus `Th`). VERIFIED.
- Mobility `(-1,0,2,0,0,1,0)` = L^2/(V.s) = M^-1 T^2 I. VERIFIED.
- Electronic sigma `(-1,-3,3,0,0,2,0)` = S/m. VERIFIED; **identical exponent
  vector to config-thermo `IonicConductivity`** (re-confirmed from that catalog).
- Electronic kappa `(1,1,-3,-1,0,0,0)` = W/(m.K). VERIFIED (= omai
  `THERMAL_CONDUCTIVITY`).

**`to_data` unit findings (verbatim).** `to_data` at `data.py:461`; the comment
`# TODO: confirm unit of kappa` is **line 483** verbatim; **line 484** is
`for prop, unit in [("cond", "S/m"), ("seebeck", "µV/K"), ("kappa", "?")]:`. So the
**serialized** units are sigma = **S/m** (confirmed, NOT S/cm), seebeck = **µV/K**
(micro-sign U+00B5; the ASCII `muV/K` in this catalog is a faithful
transliteration), kappa = **`?`** (unconfirmed by amset itself). Shape
`(n_doping, n_temperature, 3, 3)`, upper triangle written per `(doping,T)` row via
`np.triu_indices(3)` (`data.py:464`): CONFIRMED. `run.py:583` header uses Unicode
glyphs `σ [S/m]`, `S [µV/K]`, `μ [cm²/Vs]`: CONFIRMED.

**Per-entry verdicts.** All 7 entries CONFIRMED (dimensions, serving units,
statuses). Two additions to `amset-piezoelectric-constant`: (1) the input is the
full rank-3 e-tensor contracted to the h-coefficient; (2) it is NOT auto-wired by
`VaspAmsetMaker`.

**Physics-changing corrections.**

1. **Elastic input (was WRONG).** The scan repeatedly called `elastic_constant`
   "a single longitudinal-average scalar, a reduction of the rank-4 tensor". FALSE.
   amset consumes the **full rank-4** `(3,3,3,3)` tensor: `cast_elastic_tensor`
   (`util.py:115`) expands any scalar/Voigt/full input to `(3,3,3,3)`; `c_long`
   is derived **per q-direction at run time** via the Christoffel construction
   (`elastic.py:180-183,266-267`). `VaspAmsetMaker` wires
   `elastic.output.elastic_tensor.raw` (the full tensor, `flows/amset.py:290`). The
   cross-domain edge is the full `ElasticConstants` tensor. Corrected throughout.
2. **Born-charge wiring (sharpened).** `VaspAmsetMaker` reduces Born charges +
   normal modes to the effective `pop_frequency` via
   `calculate_polar_phonon_frequency(..., outcar["born"])` (`flows/amset.py:245-250`).
3. **Piezo not auto-wired (added).** PIE is off in the default GaAs flow unless the
   user supplies `piezoelectric_constant`.
4. **Lattice `ThermalConductivity` count (was WRONG).** 11 -> **9** (2 `bte_solver`
   + 7 `transport_model`).

**Non-physics corrections.** Graph freshness: 144 records / 73 nodes at review
start; a concurrent encode landed 145-147 (surface-adsorption + equation-of-state,
non-transport) -> 147 records / 74 nodes; no transport node landed. `carrier`
LABEL_KEY is collision-free (current keys `{order, bte_solver, transport_model,
channel, wrt}`).

**Orchestrator decisions.**

1. **Mint** the four transport nodes; register the three new dimension constants
   the map lacks (`electrical_conductivity`, `seebeck_coefficient`, `mobility`);
   electronic kappa reuses `THERMAL_CONDUCTIVITY`.
2. **Conductivity family**: recommended one `electrical_conductivity` tag with a
   `carrier` label, renaming config-thermo `IonicConductivity` to
   `ElectricalConductivity[carrier=ionic]`. Identity double-confirmed; `carrier`
   key is clean. DECISION DEFERRED to orchestrator.
3. **Kappa carrier label MANDATORY**: never merge electronic and lattice kappa on
   shared dimension; the 9 lattice nodes gain `carrier=lattice` if the label lands.
4. **Elastic edge** from the FULL `ElasticConstants` tensor node.
5. **Mint `StaticDielectricTensor`** (eps_0 = eps_inf + eps_ionic) distinct from the
   eps_inf `DielectricTensor` (`flows/amset.py:261-266`).
6. **Kappa unit**: record W/(m.K) with a "confirm against BoltzTraP2; amset
   serializes `?`" note before any `EXPECTED_AGREE`.
7. **Pin amset** at encode (0.5.1 here; the kappa `# TODO` may be resolved upstream).

## Source anchors

- **amset 0.5.1** (`/tmp/amsetsrc/amset_pkg`): `amset/core/transport.py:6`
  (BoltzTraP2 `calc_Onsager_coefficients`), `:36-39,186` (sigma/seebeck/kappa),
  `:191` (seebeck *1e6), `:73-137` (mobility, `:133-135` cm^2/Vs conv, `:47-49`
  non-metal guard), `:101,163` (Matthiessen lifetime); `amset/core/data.py:80`
  (electronic_thermal_conductivity field), `:400-410` (set_transport_properties),
  `:412-420` (to_dict keys), `:461-491` (to_data, `:483-484` kappa TODO + units,
  `:467` doping cm->bohr); `amset/core/run.py:583` (headers sigma S/m, S uV/K,
  mu cm^2/Vs), `:615-624` (per-mechanism breakdown), `:576` (doping bohr->cm);
  `amset/defaults.yaml:6,8,36-44,56` (scattering_type, doping sign, input units,
  separate_mobility); `amset/scattering/elastic.py:84-85` (ADP), `:280-281`
  (IMP), `:369-406` (PIE); `amset/scattering/inelastic.py:60-65,91-92` (POP,
  THz->au); `amset/scattering/basic.py:54,85,125` (CRT/MFP/SRT);
  `amset/plot/rates.py:22-26` (rate s^-1); `amset/interpolation/bandstructure.py:10,53`
  and `amset/interpolation/boltztrap.py:4` (BoltzTraP2 interpolation);
  `amset/constants.py:14-44` (Hartree atomic units).
- **AtomisticSkills**: `mat-dft-electronic-transport/SKILL.md:1-40`;
  `scripts/generate_inputs.py:14,36-50` (VaspAmsetMaker, doping/temperatures);
  `examples/GaAs/README.md` (300K mu ~8500/400 cm^2/Vs, ADP+POP).
- **Map side**: `omai/operator/dimensions.py:26` (base axes), `:115`
  (THERMAL_CONDUCTIVITY), `:132` (VOLTAGE, the I-axis); `omai/operator/registry.py`
  (LABEL_KEYS, the ThermalConductivity family pattern); `docs/data/graph.json`
  (73 nodes; DielectricTensor, BornCharges, Frequency, ElasticConstants present;
  no electronic-transport node); `scans/atomate2-vasp-atomistic-skills.md`
  (VaspAmsetMaker, lattice-vs-electronic kappa mandate);
  `scans/config-thermo-atomistic-skills.md` (IonicConductivity dimension,
  the conductivity-family precedent).
