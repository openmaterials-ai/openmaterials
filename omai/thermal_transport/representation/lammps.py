"""lammps adapter specs for the thermal-transport DAG.

LAMMPS (Large-scale Atomic/Molecular Massively Parallel Simulator,
https://www.lammps.org/) is a classical-MD code that also provides phonon
and thermal-transport functionality via its USER-PHONON package and the
heat-flux / non-equilibrium-MD machinery in standard packages.

This adapter targets LAMMPS-as-its-own-code: the code is driven by a
LAMMPS input script (`lmp -in in.lammps`), reads potentials via
`pair_style` declarations, writes outputs to log files and dump files.

LAMMPS-via-ASE; where LAMMPS is used as an in-Python force backend via
`ase.calculators.lammpslib.LAMMPSlib`; is covered by the separate `ase`
adapter, since that path interacts with LAMMPS through the ASE
protocol rather than through LAMMPS's native scripting interface.

Scope in P1 of phase 2:
  * Potential (`pair_style` declaration + coefficients), via
    `provide_potential`.

Scope added in P2 of phase 2 (MD primitives):
  * Temperature (`compute temp` / `thermo_style temp`, region and
    chunked-profile variants).
  * Trajectory (positions + velocities sampled from `run`).
  * HeatCurrent (`compute heat/flux`).
  * HeatCurrentACF (`fix ave/correlate` over heat-flux components).
  * VelocityAutocorrelation (`compute vacf` + `fix ave/time`).
  * MeanSquaredDisplacement (`compute msd`).
  * All six MD-driver operations.

Scope added in P3 of phase 2 (MD-based κ paths):
  * Green-Kubo κ (`fix ave/correlate` integrated post-hoc, or numpy.trapz
    on the dumped J(t)·J(t) tensor).
  * Direct / Müller-Plathe NEMD κ (`fix thermal/conductivity` swap
    method, or two-reservoir hot/cold thermostats).
  * HNEMD κ; *not exposed* in LAMMPS; the canonical home for HNEMD is
    GPUMD. Recorded in the operator-adapter spec as documentation but
    routes through `compute_hnemd` in the GPUMD adapter instead.

Out of scope:
  * USER-PHONON: dispersion (band.dat), DM via Green's-function
    fluctuation method.
  * Force-constant derivation via the `fix phonon` or external dynaphopy
    workflows.

References:
  * https://docs.lammps.org/pair_style.html; full list of pair_style
    options (tersoff, eam, sw, snap, …).
  * https://docs.lammps.org/Howto_phonon.html; USER-PHONON how-to.
  * https://docs.lammps.org/compute_heat_flux.html; Green-Kubo κ
    pipeline.
  * https://docs.lammps.org/compute_vacf.html; velocity autocorrelation.
  * https://docs.lammps.org/compute_msd.html; mean-squared displacement.
  * https://docs.lammps.org/fix_ave_correlate.html; direct time-correlation.
"""

from __future__ import annotations

from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator.edges import (
    autocorrelate_heat_current,
    compute_heat_current,
    compute_msd,
    compute_velocity_autocorrelation,
    contract_kappa_green_kubo,
    contract_kappa_hnemd,
    contract_kappa_nemd,
    fourier_to_dos,
    provide_potential,
    run_md,
)
from omai.thermal_transport.operator.nodes import (
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    MEAN_SQUARED_DISPLACEMENT,
    POTENTIAL,
    TEMPERATURE_STATE,
    THERMAL_CONDUCTIVITY_GREEN_KUBO,
    THERMAL_CONDUCTIVITY_NEMD,
    TRAJECTORY,
    VELOCITY_AUTOCORRELATION,
)


LAMMPS_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="lammps",
    code_api={
        "potential": "LAMMPS input script: pair_style <name> + pair_coeff <args>"
    },
    notes=(
        "LAMMPS-native Potential: declared in the input script via "
        "`pair_style <name>` (tersoff, eam, sw, snap, reax, …) and the "
        "matching `pair_coeff` lines (or external potential files like "
        "Si.tersoff, Cu_u3.eam). The Potential is fully specified by the "
        "input script + any referenced parameter files. For LAMMPS-via-ASE "
        "(in-Python force evaluation through `LAMMPSlib`), see the `ase` "
        "adapter instead; same numerical content, different driving "
        "interface. "
        "CROSS-ENGINE EXPECTED_AGREE (mat-lammps-md, arXiv 2605.24002): the "
        "SAME MLIP checkpoint runs both as an ASE calculator (the matcalc / "
        "phonopy path) and as a LAMMPS pair_style, so Potential identity, "
        "TotalEnergy, Forces, and Stress must agree on identical configs to "
        "MLIP-inference precision (NOT bit-exact). Three checkpoints: MACE "
        "puts the model on pair_style (`pair_style mace no_domain_decomposition` "
        "+ `pair_coeff * * <model> Na Si O`, in.na2si3o7_quench_mace:18-19) vs "
        "the ASE MACECalculator; CHGNet and FairChem UMA use a bare "
        "`pair_style mliap` with the python bridge on the PAIR_COEFF line "
        "(`pair_coeff * * mliap python chgnet CHGNet-MPtrj-2023.12.1-2.7M-PES Cu`, "
        "in.cu_phase_transition_matgl:18; `pair_coeff * * mliap python fairchem "
        "uma-s-1p1 Cu C O`, in.relax_adsorption_fairchem:18) vs the matgl "
        "PESCalculator / FAIRChemCalculator. The mliap-python bridge is "
        "source-verified in the vendored clone (src/ML-IAP/mliap_model_python.cpp, "
        "mliap_unified.cpp), so chgnet + fairchem are clone-grounded; "
        "`pair_style mace` / `no_domain_decomposition` is an EXTERNAL LAMMPS "
        "plugin (not in the base clone), verifiable only in the skill input, so "
        "MACE cannot be pinned bit-exactly. Unit trap for the Stress compare: "
        "the ASE side is eV/A^3 while the LAMMPS metal side is bar, so it needs "
        "the metal nktv2p = 1.6021765e6 bar<->eV/A^3 factor (src/update.cpp:197). "
        "Tolerance policy: a per-quantity envelope in compare() keyed on the "
        "checkpoint identity string; do NOT assert bit-exactness across the "
        "no_domain_decomposition vs mliap-python bridges."
    ),
)


LAMMPS_PROVIDE_POTENTIAL = OperatorRepresentationSpec(
    operator=provide_potential,
    representation_name="lammps",
    notes=(
        "Provides Potential via LAMMPS's native scripting interface. The "
        "Potential's identity (pair_style + parameters) is read from the "
        "input script at LAMMPS startup; subsequent force evaluations are "
        "all driven by that initial configuration. Per-run reproducibility "
        "depends on the parameter files referenced (Si.tersoff, etc.) "
        "being version-pinned."
    ),
)


# ---------------------------------------------------------------------------
# MD primitives (phase 2 P2)
# ---------------------------------------------------------------------------

LAMMPS_TEMPERATURE = SpaceRepresentationSpec(
    space=TEMPERATURE_STATE,
    representation_name="lammps",
    observable_units={"temperature": "kelvin"},
    code_api={
        "temperature": "compute temp / thermo_style temp; profiles via compute chunk/atom + fix ave/chunk"
    },
    notes=(
        "LAMMPS-native Temperature as an MD output: the auto-created "
        "`compute temp` (surfaced via `thermo_style custom temp`) gives "
        "the global instantaneous kinetic temperature T = mvv2e Σ m_i "
        "v_i² / ((d N - d - fix_dof) k_B), with the dof = dN - d COM-"
        "subtraction convention (scan anchor: thermo-temp, "
        "compute_temp.cpp:58-68). The kelvin unit holds for the metal "
        "and real unit styles; under `units lj` the output is reduced "
        "(ε/k_B with k_B=1), not kelvin. Region-scoped variant: `compute "
        "temp/region` gives the instantaneous temperature of atoms "
        "currently inside a geometric region; used to read the two-"
        "reservoir ΔT in NEMD κ workflows (scan anchor: temp-region, "
        "compute_temp_region.cpp:131). Spatially indexed variant: the "
        "chunked T(z) profile; `compute chunk/atom bin/1d` + `fix "
        "ave/chunk` over `compute temp/chunk` (or an atom-style KE "
        "proxy); bins the temperature along the transport axis and is "
        "what the NEMD gradient dT/dz is measured from (scan anchor: "
        "temperature-profile-chunks, fix_ave_chunk.cpp:328,836). Per-"
        "chunk DOF conventions (cdof/adof, COM-of-chunk removal) affect "
        "the profile normalization and are a cross-code comparison "
        "hazard at small bin populations."
    ),
)


LAMMPS_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="lammps",
    code_api={
        "r": "dump custom <id> all custom <every> <file> id x y z",
        "v": "dump custom <id> all custom <every> <file> id vx vy vz",
    },
    notes=(
        "LAMMPS-native Trajectory: positions and velocities written by "
        "`dump custom` during the production `run`. Sampling interval is "
        "controlled by the dump's <every> argument. `xu yu zu` are dump "
        "CUSTOM column keywords on the dump command itself (not "
        "`dump_modify` options) requesting unwrapped coordinates, "
        "required for MSD; plain `x y z` are wrapped into the periodic "
        "box (scan anchor: dump-custom-trajectory, dump_custom.cpp:1491, "
        "2655)."
    ),
)


LAMMPS_HEAT_CURRENT = SpaceRepresentationSpec(
    space=HEAT_CURRENT,
    representation_name="lammps",
    code_api={"J": "compute <id> all heat/flux ke pe stress"},
    notes=(
        "LAMMPS-native instantaneous heat current via `compute heat/flux`, "
        "which uses the Hardy/Irving-Kirkwood form. Requires per-atom KE, "
        "PE, and stress computes as inputs (`compute ke/atom`, "
        "`compute pe/atom`, `compute stress/atom NULL virial`). The "
        "vector components Jx, Jy, Jz appear as elements 1-3 of the "
        "compute output. IMPORTANT: the compute's output is J·V, not J; "
        "'normalization by volume is not included' (scan anchor: "
        "heat-flux-vector, compute_heat_flux.cpp:114-117); every "
        "downstream κ = 1/(V k_B T²) ∫⟨(JV)(0)(JV)(t)⟩dt must divide by "
        "V exactly once, and cross-code comparison against intensive-J "
        "codes (e.g. GPUMD) is a guaranteed factor-V mismatch unless this "
        "is done. Per-atom stress chain caveat: the stress-ID input "
        "(`compute stress/atom`) returns S = -(virial+ke) in "
        "pressure·volume units (the negative of the per-atom pressure "
        "tensor, un-divided by any per-atom volume); `heat/flux` applies "
        "`jv -= S·v` then divides by nktv2p, netting +virial·v in "
        "energy·velocity units. The default `stress/atom` includes the "
        "kinetic term, which double-counts kinetic transport against the "
        "convective e_i·v_i term unless the compute is declared as "
        "`stress/atom NULL virial`. For bonded/many-body systems (angle/"
        "dihedral/improper/rigid contributions), plain `stress/atom` "
        "gives an unphysical J; use `compute centroid/stress/atom` (the "
        "9-component asymmetric decomposition) instead; the two "
        "decompositions differ per-atom (a gauge) while summing to the "
        "same global virial. Alternate route to the same space: the "
        "TALLY package's `compute heat/flux/tally` and `compute "
        "heat/flux/virial/tally` compute J·V by direct pairwise tally "
        "during the force loop instead of the per-atom stress "
        "decomposition; exact for pairwise potentials, unavailable for "
        "bonded/kspace/many-body contributions (scan anchor: "
        "heat-flux-tally-variant)."
    ),
)


LAMMPS_HEAT_CURRENT_ACF = SpaceRepresentationSpec(
    space=HEAT_CURRENT_ACF,
    representation_name="lammps",
    code_api={
        "Jcorr": "fix <id> all ave/correlate <Nevery> <Nrepeat> <Nfreq> c_heatflux[1] c_heatflux[2] c_heatflux[3]"
    },
    notes=(
        "LAMMPS-native heat-current autocorrelation via `fix "
        "ave/correlate`. The `type auto` mode produces ⟨J_α(0) J_α(τ)⟩; "
        "for the full αβ tensor, request the cross-correlations "
        "explicitly (`type full`). Output is the direct-O(N²) sum; for "
        "long trajectories users post-process the dumped J(t) with FFT "
        "instead."
    ),
)


LAMMPS_VELOCITY_AUTOCORRELATION = SpaceRepresentationSpec(
    space=VELOCITY_AUTOCORRELATION,
    representation_name="lammps",
    code_api={
        "Cv": "compute <id> all vacf  +  fix <id> all ave/time <Nevery> <Nrepeat> <Nfreq> c_vacf[*]"
    },
    notes=(
        "LAMMPS-native VAF via `compute vacf` (per-atom v(0)·v(t), reset "
        "at the compute's start step) accumulated through `fix ave/time`. "
        "Output is the direct-sum form; the Wiener-Khinchin FFT pathway "
        "is user post-processing outside LAMMPS. ESTIMATOR CAVEAT: "
        "`compute vacf` is a single-time-origin estimator; it "
        "correlates against the velocities stored at the compute's "
        "creation time, with no sliding time-origin average (scan "
        "anchor: vacf, compute_vacf.cpp:56-63), whereas the map's "
        "VelocityAutocorrelation node is defined as a time-origin-"
        "averaged correlation ⟨v(0)·v(τ)⟩. The two agree as estimators "
        "in the long-trajectory limit but are different finite-"
        "trajectory quantities. Averaging over multiple origins requires "
        "either `fix vector` accumulation over periodically re-created "
        "computes, running multiple computes with staggered creation "
        "steps, or post-processing a velocity dump; this is an open "
        "question in the scan, not resolved natively by LAMMPS."
    ),
)


LAMMPS_MEAN_SQUARED_DISPLACEMENT = SpaceRepresentationSpec(
    space=MEAN_SQUARED_DISPLACEMENT,
    representation_name="lammps",
    code_api={
        "M": "compute <id> all msd com yes  +  fix <id> all ave/time <Nevery> <Nrepeat> <Nfreq> c_msd[4]"
    },
    notes=(
        "LAMMPS-native MSD via `compute msd`. The `com yes` flag subtracts "
        "the COM motion (essential to read self-diffusion off the linear "
        "slope). Component 4 of the output is the scalar |Δr|²; "
        "components 1-3 are the αα contributions. ESTIMATOR CAVEAT: "
        "`compute msd` is a single-time-origin estimator; displacements "
        "are measured against the reference configuration stored "
        "(unwrapped) at the compute's creation time, with no sliding "
        "time-origin average (scan anchor: msd, compute_msd.cpp:82-86), "
        "whereas the map's MeanSquaredDisplacement node is defined as a "
        "time-origin-averaged correlation ⟨|r(t+τ)-r(t)|²⟩. The two "
        "agree as estimators of 2dDτ in the diffusive regime but are "
        "different finite-trajectory quantities. Averaging over "
        "multiple origins requires either `fix vector` accumulation over "
        "periodically re-created computes, running multiple computes "
        "with staggered creation steps, or post-processing a position "
        "dump; this is an open question in the scan, not resolved "
        "natively by LAMMPS."
    ),
)


LAMMPS_RUN_MD = OperatorRepresentationSpec(
    operator=run_md,
    representation_name="lammps",
    notes=(
        "LAMMPS production MD: `velocity all create <T> <seed>` to "
        "initialise, `fix <id> all nve` / `fix <id> all nvt temp <T> <T> "
        "<Tdamp>` / `fix <id> all npt ...` for ensemble, optionally `fix "
        "<id> all langevin <T> <T> <Tdamp> <seed>` for thermostat, then "
        "`run <n_steps>`. Velocity-Verlet is the default integrator "
        "(no override needed). The Trajectory is realised by the dump "
        "statements declared in LAMMPS_TRAJECTORY."
    ),
)


LAMMPS_COMPUTE_HEAT_CURRENT = OperatorRepresentationSpec(
    operator=compute_heat_current,
    representation_name="lammps",
    notes=(
        "LAMMPS computes the heat current with `compute heat/flux` "
        "during the production `run`. Requires the per-atom KE, PE, and "
        "stress computes to be declared upstream. Result is written via "
        "`fix ave/time` to a thermo or log file, or correlated directly "
        "via `fix ave/correlate` (see autocorrelate_heat_current)."
    ),
)


LAMMPS_AUTOCORRELATE_HEAT_CURRENT = OperatorRepresentationSpec(
    operator=autocorrelate_heat_current,
    representation_name="lammps",
    notes=(
        "`fix ave/correlate` is the direct-sum, O(N²) variant. For the "
        "FFT/Wiener-Khinchin path users dump J(t) to a file and "
        "post-process with numpy. Both are numerically equivalent under "
        "periodic padding; the operator layer no longer declares a "
        "`correlation_method` scheme."
    ),
)


LAMMPS_COMPUTE_VELOCITY_AUTOCORRELATION = OperatorRepresentationSpec(
    operator=compute_velocity_autocorrelation,
    representation_name="lammps",
    notes=(
        "`compute vacf` is direct-sum. The compute resets at the step it "
        "was created on; for long correlation windows users re-create "
        "the compute periodically or run from a saved velocity dump. The "
        "FFT alternative is numerically equivalent under periodic padding."
    ),
)


LAMMPS_COMPUTE_MSD = OperatorRepresentationSpec(
    operator=compute_msd,
    representation_name="lammps",
    scheme_overrides={"unwrap_pbc": "true"},
    notes=(
        "`compute msd` operates on unwrapped coordinates internally; "
        "the compute tracks atoms across PBC unwrap automatically, so "
        "the user need not dump `xu yu zu` if MSD is the only output."
    ),
)


LAMMPS_FOURIER_TO_DOS = OperatorRepresentationSpec(
    operator=fourier_to_dos,
    representation_name="lammps",
    notes=(
        "Not exposed natively. The user dumps the VAF from `compute "
        "vacf` and FFTs it externally (numpy.fft.rfft + cosine kernel) "
        "to obtain g(ω). Documented here so the adapter audit sees the "
        "edge; the contraction is real, just lives outside LAMMPS."
    ),
)


# ---------------------------------------------------------------------------
# MD-based κ paths (phase 2 P3)
# ---------------------------------------------------------------------------

LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_GREEN_KUBO,
    representation_name="lammps",
    code_api={
        "kappa": "in-script trap() on a fix ave/correlate vector, scaled by a variable (no dedicated kappa.out file)"
    },
    notes=(
        "LAMMPS produces the heat-flux autocorrelation through `fix "
        "ave/correlate`, and the canonical examples/KAPPA/in.heatflux "
        "script computes the running κ natively in-script via the "
        "trap() variable function applied to the fix's f_JJ vector, "
        "scaled by a `scale` equal-style variable (scan anchor: "
        "green-kubo-kappa-workflow, examples/KAPPA/in.heatflux:68-72). "
        "There is still no dedicated κ output file (unlike GPUMD's "
        "hac.out); the running κ appears as thermo custom columns "
        "(v_k11 v_k22 v_k33 v_kappa) in the log. Users who prefer "
        "post-processing may instead dump J(t) and run numpy.trapz "
        "externally with the same V/(k_B T²) prefactor; both routes "
        "are numerically equivalent. Conventional input-script "
        "pattern: `fix JJ all ave/correlate Nevery Nrepeat Nfreq "
        "c_heatflux[1] c_heatflux[2] c_heatflux[3] type auto file "
        "J0Jt.dat`, then κ = V/(k_B T²) · trap(f_JJ) (in-script) or "
        "numpy.trapz(JJ) (post-hoc)."
    ),
)


LAMMPS_THERMAL_CONDUCTIVITY_NEMD = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_NEMD,
    representation_name="lammps",
    code_api={
        "kappa": "post-processed: flux / (linear fit of binned T(z))"
    },
    notes=(
        "Müller-Plathe NEMD κ (default scheme). The input script "
        "declares `fix <id> all thermal/conductivity <Nevery> <axis> "
        "<Nbin>`, which swaps velocities between hottest atom in the "
        "cold half and coldest atom in the hot half on every Nevery "
        "steps; the swap rate produces a deterministic flux. The user "
        "dumps T(z) via `compute ke/atom`+chunked `fix ave/chunk` and "
        "fits the linear regime to extract dT/dz; κ = imposed_flux / "
        "|dT/dz|. Finite-size scaling (κ vs 1/L_z) is required to read "
        "bulk κ. LAMMPS ships three further reservoir-driver schemes "
        "that reach the same space via the same flux/gradient ratio "
        "(scan anchor: nemd-kappa-workflow, examples/KAPPA/README:44-"
        "104): `fix heat` (imposed energy rate via momentum-conserving "
        "rescale), `fix ehex` (enhanced heat exchange, better energy "
        "conservation than `fix heat`), and `fix langevin` with `tally "
        "yes` (stochastic two-reservoir thermostat with a measured "
        "energy tally). All five methods (including Green-Kubo) agree "
        "within ~15% on the Evans 1986 LJ reference state point."
    ),
)


LAMMPS_CONTRACT_KAPPA_GREEN_KUBO = OperatorRepresentationSpec(
    operator=contract_kappa_green_kubo,
    representation_name="lammps",
    parameter_units={"tau_max": "ps", "tau_min": "ps"},
    notes=(
        "The canonical examples/KAPPA/in.heatflux script performs the "
        "integration in-script via the trap() variable function on the "
        "`fix ave/correlate` vector, times a `scale` variable carrying "
        "the V/(k_B T²) prefactor (scan anchor: green-kubo-kappa-"
        "workflow, examples/KAPPA/in.heatflux:68-72); this is not "
        "purely user-side post-processing. Equivalently, users may dump "
        "J(t) (or J(0)J(t)) via `fix ave/correlate` and integrate "
        "externally with numpy.trapz from tau_min to tau_max with the "
        "same prefactor; both routes agree numerically. Neither route "
        "gives tau_min/tau_max plateau control beyond the correlation "
        "length set by Nrepeat."
    ),
)


LAMMPS_CONTRACT_KAPPA_NEMD = OperatorRepresentationSpec(
    operator=contract_kappa_nemd,
    representation_name="lammps",
    scheme_overrides={"nemd_method": "muller_plathe"},
    # parameter_units deliberately undeclared: LAMMPS has no single unit for
    # these parameters; the run's `units` style decides (imposed_flux: metal
    # eV/ps, real kcal/(mol*fs), lj epsilon/tau; imposed_gradient: K/Angstrom
    # for metal/real, reduced for lj). declared_parameter_unit() raising is
    # the honest signal here; declaring one token would repeat the
    # hard-coding this spec used to have.
    notes=(
        "Canonical LAMMPS NEMD: `fix thermal/conductivity` (Müller-"
        "Plathe swap method). LAMMPS ships several reservoir/scheme "
        "variants beyond Müller-Plathe, all cross-checked against each "
        "other in examples/KAPPA (scan anchor: nemd-kappa-workflow, "
        "examples/KAPPA/README:44-104): `fix thermal/conductivity` "
        "(deterministic velocity-swap NEMD), `fix heat` (imposed "
        "energy-addition/subtraction rate via momentum-conserving "
        "velocity rescale), `fix ehex` (enhanced heat exchange, an "
        "improved-energy-conservation variant of `fix heat`), and `fix "
        "langevin` with `tally yes` (stochastic two-reservoir "
        "thermostat with a measured cumulative energy tally). All four "
        "end up post-processed identically once the numerator (imposed "
        "or measured reservoir energy) and denominator (linear fit or "
        "finite difference of the T(z) profile) are known: κ = "
        "flux / (dT/dz). `imposed_flux` and `imposed_gradient` are "
        "unit-style dependent throughout; the canonical examples/KAPPA "
        "scripts are `units lj` (where kB, mvv2e, nktv2p = 1), not real "
        "units; porting the parameter values to metal/real requires "
        "reinserting the appropriate conversion factors (scan anchor: "
        "nemd-kappa-workflow)."
    ),
)


LAMMPS_CONTRACT_KAPPA_HNEMD = OperatorRepresentationSpec(
    operator=contract_kappa_hnemd,
    representation_name="lammps",
    notes=(
        "Not exposed by LAMMPS. The Evans / Fan HNEMD driving force is "
        "not implemented as a native fix; users wanting HNEMD on a "
        "LAMMPS Potential typically port the Potential to GPUMD (NEP "
        "training against LAMMPS-evaluated forces) and run "
        "`compute_hnemd` there instead. Documented here for the adapter "
        "audit; references the GPUMD adapter's GPUMD_CONTRACT_KAPPA_HNEMD."
    ),
)
