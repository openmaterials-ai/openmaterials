"""lammps adapter specs for the thermal-transport DAG.

LAMMPS (Large-scale Atomic/Molecular Massively Parallel Simulator,
https://www.lammps.org/) is a classical-MD code that also provides phonon
and thermal-transport functionality via its USER-PHONON package and the
heat-flux / non-equilibrium-MD machinery in standard packages.

This adapter targets LAMMPS-as-its-own-code: the code is driven by a
LAMMPS input script (`lmp -in in.lammps`), reads potentials via
`pair_style` declarations, writes outputs to log files and dump files.

LAMMPS-via-ASE — where LAMMPS is used as an in-Python force backend via
`ase.calculators.lammpslib.LAMMPSlib` — is covered by the separate `ase`
adapter, since that path interacts with LAMMPS through the ASE
protocol rather than through LAMMPS's native scripting interface.

Scope in P1 of phase 2:
  * Potential (`pair_style` declaration + coefficients), via
    `provide_potential`.

Scope added in P2 of phase 2 (MD primitives):
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
  * HNEMD κ — *not exposed* in LAMMPS; the canonical home for HNEMD is
    GPUMD. Recorded in the operator-adapter spec as documentation but
    routes through `compute_hnemd` in the GPUMD adapter instead.

Out of scope:
  * USER-PHONON: dispersion (band.dat), DM via Green's-function
    fluctuation method.
  * Force-constant derivation via the `fix phonon` or external dynaphopy
    workflows.

References:
  * https://docs.lammps.org/pair_style.html — full list of pair_style
    options (tersoff, eam, sw, snap, …).
  * https://docs.lammps.org/Howto_phonon.html — USER-PHONON how-to.
  * https://docs.lammps.org/compute_heat_flux.html — Green-Kubo κ
    pipeline.
  * https://docs.lammps.org/compute_vacf.html — velocity autocorrelation.
  * https://docs.lammps.org/compute_msd.html — mean-squared displacement.
  * https://docs.lammps.org/fix_ave_correlate.html — direct time-correlation.
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
        "adapter instead — same numerical content, different driving "
        "interface."
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
        "controlled by the dump's <every> argument. Wrap/unwrap behavior "
        "is set via `dump_modify` (use `xu yu zu` for unwrapped "
        "coordinates, required for MSD)."
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
        "compute output."
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
        "is user post-processing outside LAMMPS."
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
        "components 1-3 are the αα contributions."
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
        "periodic padding — the operator layer no longer declares a "
        "`correlation_method` scheme."
    ),
)


LAMMPS_COMPUTE_VELOCITY_AUTOCORRELATION = OperatorRepresentationSpec(
    operator=compute_velocity_autocorrelation,
    representation_name="lammps",
    notes=(
        "`compute vacf` is direct-sum. The compute resets at the step it "
        "was created on — for long correlation windows users re-create "
        "the compute periodically or run from a saved velocity dump. The "
        "FFT alternative is numerically equivalent under periodic padding."
    ),
)


LAMMPS_COMPUTE_MSD = OperatorRepresentationSpec(
    operator=compute_msd,
    representation_name="lammps",
    scheme_overrides={"unwrap_pbc": "true"},
    notes=(
        "`compute msd` operates on unwrapped coordinates internally — "
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
        "edge — the contraction is real, just lives outside LAMMPS."
    ),
)


# ---------------------------------------------------------------------------
# MD-based κ paths (phase 2 P3)
# ---------------------------------------------------------------------------

LAMMPS_THERMAL_CONDUCTIVITY_GREEN_KUBO = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_GREEN_KUBO,
    representation_name="lammps",
    code_api={
        "kappa": "post-processed numpy.trapz on dumped J(t)·J(t) tensor (no native kappa.out)"
    },
    notes=(
        "LAMMPS produces the heat-flux autocorrelation through `fix "
        "ave/correlate`, but the time integral to κ is post-processed "
        "(numpy.trapz on the dumped data). LAMMPS does not emit a "
        "kappa-vs-time running average like GPUMD's hac.out. "
        "Conventional input-script pattern: `fix JJ all ave/correlate "
        "Nevery Nrepeat Nfreq c_heatflux[1] c_heatflux[2] c_heatflux[3] "
        "type auto file J0Jt.dat`, then κ = V/(k_B T²) · numpy.trapz(JJ)."
    ),
)


LAMMPS_THERMAL_CONDUCTIVITY_NEMD = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_NEMD,
    representation_name="lammps",
    code_api={
        "kappa": "post-processed: flux / (linear fit of binned T(z))"
    },
    notes=(
        "Müller-Plathe NEMD κ. The input script declares `fix <id> all "
        "thermal/conductivity <Nevery> <axis> <Nbin>`, which swaps "
        "velocities between hottest atom in the cold half and coldest "
        "atom in the hot half on every Nevery steps; the swap rate "
        "produces a deterministic flux. The user dumps T(z) via "
        "`compute ke/atom`+chunked `fix ave/chunk` and fits the linear "
        "regime to extract dT/dz; κ = imposed_flux / |dT/dz|. "
        "Finite-size scaling (κ vs 1/L_z) is required to read bulk κ."
    ),
)


LAMMPS_CONTRACT_KAPPA_GREEN_KUBO = OperatorRepresentationSpec(
    operator=contract_kappa_green_kubo,
    representation_name="lammps",
    parameter_units={"tau_max": "ps", "tau_min": "ps"},
    notes=(
        "Integration is user-driven: dump J(t) (or J(0)J(t)) via `fix "
        "ave/correlate`, then numpy.trapz from tau_min to tau_max with "
        "the V/(k_B T²) prefactor. LAMMPS does not perform the "
        "integration itself."
    ),
)


LAMMPS_CONTRACT_KAPPA_NEMD = OperatorRepresentationSpec(
    operator=contract_kappa_nemd,
    representation_name="lammps",
    scheme_overrides={"nemd_method": "muller_plathe"},
    parameter_units={"imposed_flux": "kcal/(mol*fs)", "imposed_gradient": "K/Angstrom"},
    notes=(
        "Canonical LAMMPS NEMD: `fix thermal/conductivity` (Müller-"
        "Plathe). The `direct_two_reservoir` alternative uses two `fix "
        "nvt` regions with different setpoints; both end up post-"
        "processed identically (linear fit of T(z), divide imposed flux "
        "or measured flux by the gradient)."
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
