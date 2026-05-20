"""gpumd adapter specs for the thermal-transport DAG.

GPUMD (Graphics Processing Units Molecular Dynamics,
https://github.com/brucefan1983/GPUMD) is a CUDA-accelerated classical-MD
code optimised for thermal-transport workflows. It ships dedicated drivers
for the homogeneous non-equilibrium MD method (HNEMD), Green-Kubo via the
heat-current autocorrelation function (HAC), and the spectral
decomposition of κ. Its native potential format is NEP (neuro-evolution
potentials), trained against DFT references; classical pair / tersoff /
EAM forms are also supported.

GPUMD is not driven through ASE — it has its own input format (`run.in`)
and its potentials live in their own files (`nep.txt`, `eam.fs`, …). This
adapter therefore targets the *native* GPUMD interface.

Scope in P1 of phase 2:
  * Potential (NEP / EAM / Tersoff file), via `provide_potential`.

Scope added in P2 of phase 2 (MD primitives):
  * Trajectory (`dump_position`, `dump_velocity`).
  * HeatCurrent (`compute heat_current` — virial-form J(t)).
  * HeatCurrentACF (`compute_hac` writes hac.out directly).
  * VelocityAutocorrelation (`compute_dos`, which writes mvac.out and
    derives the DOS in one step).
  * MeanSquaredDisplacement (`compute_msd`).
  * All six MD-driver operations.

Scope added in P3 of phase 2 (MD-based κ paths):
  * Green-Kubo κ via `compute_hac` — GPUMD writes the integrated κ
    running average to `hac.out` alongside the autocorrelation itself.
  * HNEMD κ via `compute_hnemd` — GPUMD's signature method. Writes
    `kappa.out` (running κ_xx, κ_yy, κ_zz under the homogeneous driving
    force F_e).
  * NEMD κ — *not exposed* in GPUMD directly. Users either fall back to
    LAMMPS (`fix thermal/conductivity`) or use HNEMD as the GPUMD-native
    alternative. Documented as not-exposed in the adapter audit.

Out of scope:
  * EMD κ via tighter ensemble averaging.
  * Heat-current spectral decomposition (per-frequency κ contributions
    via `compute_shc`).
  * Spectrally-resolved phonon transport (SRP).

References:
  * GPUMD user manual — https://gpumd.org/
  * NEP training / GPUMD inference — Fan et al., J. Chem. Phys. 157,
    114801 (2022).
  * HNEMD methodology — Fan et al., Phys. Rev. B 99, 064308 (2019).
  * Heat-flux ACF (compute_hac) — see GPUMD manual §"Compute thermal
    conductivity using Green-Kubo".
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
    THERMAL_CONDUCTIVITY_HNEMD,
    TRAJECTORY,
    VELOCITY_AUTOCORRELATION,
)


GPUMD_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="gpumd",
    code_api={
        "potential": "nep.txt (default) | EAM/Tersoff/SW potential file referenced from run.in"
    },
    notes=(
        "GPUMD's Potential is declared in `run.in` via the `potential` "
        "keyword pointing at an on-disk file. Default and most common is "
        "NEP (neuro-evolution potential, `nep.txt` written by `nep`'s "
        "training run); EAM, Tersoff, SW are also supported as classical "
        "alternatives. NEP files carry the trained weights and the "
        "elemental-pair cutoffs; the file *is* the Potential."
    ),
)


GPUMD_PROVIDE_POTENTIAL = OperatorRepresentationSpec(
    operator=provide_potential,
    representation_name="gpumd",
    notes=(
        "Provides Potential by referencing an on-disk potential file in "
        "GPUMD's `run.in`. NEP is the canonical GPUMD potential format "
        "(trained against DFT energies + forces + virials via the `nep` "
        "trainer); classical forms read the same way."
    ),
)


# ---------------------------------------------------------------------------
# MD primitives (phase 2 P2)
# ---------------------------------------------------------------------------

GPUMD_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="gpumd",
    code_api={
        "r": "run.in: dump_position <interval>",
        "v": "run.in: dump_velocity <interval>",
    },
    notes=(
        "GPUMD writes positions and velocities through the "
        "`dump_position` and `dump_velocity` keywords in `run.in`. "
        "Output files are `movie.xyz` (positions) and `velocity.out` "
        "(velocities). The PBC behaviour is unwrapped by default, "
        "which is convenient for MSD."
    ),
)


GPUMD_HEAT_CURRENT = SpaceRepresentationSpec(
    space=HEAT_CURRENT,
    representation_name="gpumd",
    code_api={"J": "run.in: compute_hac <step1> <step2> <Nc>  (writes hac.out — J(t) implicit)"},
    notes=(
        "GPUMD computes the heat current on every MD step internally via "
        "the virial decomposition. The instantaneous J(t) is not "
        "user-exposed: it's consumed directly by `compute_hac` (HAC), "
        "`compute_hnemd`, or `compute_shc` (spectral heat current). "
        "Users typically don't dump J(t) — they go straight to the "
        "autocorrelation in `hac.out`."
    ),
)


GPUMD_HEAT_CURRENT_ACF = SpaceRepresentationSpec(
    space=HEAT_CURRENT_ACF,
    representation_name="gpumd",
    code_api={"Jcorr": "run.in: compute_hac <Ns> <Nc> <out_steps>  →  hac.out"},
    notes=(
        "GPUMD's `compute_hac` keyword writes `hac.out` with columns "
        "`t (ps)  jxjx  jyjy  jzjz  jxjy ...`, i.e. the heat-current "
        "autocorrelation as a function of correlation lag. The same "
        "file is what the Green-Kubo κ contraction (P3) reads."
    ),
)


GPUMD_VELOCITY_AUTOCORRELATION = SpaceRepresentationSpec(
    space=VELOCITY_AUTOCORRELATION,
    representation_name="gpumd",
    code_api={"Cv": "run.in: compute_dos <Nc> <Nw> <max_omega>  →  mvac.out + dos.out"},
    notes=(
        "GPUMD bundles VAF + Fourier-to-DOS into one keyword: "
        "`compute_dos` writes both `mvac.out` (the VAF, mass-weighted) "
        "and `dos.out` (the resulting DOS). The same adapter spec "
        "therefore covers both VELOCITY_AUTOCORRELATION and "
        "PHONON_DOS-via-fourier_to_dos. Mass-weighting is automatic."
    ),
)


GPUMD_MEAN_SQUARED_DISPLACEMENT = SpaceRepresentationSpec(
    space=MEAN_SQUARED_DISPLACEMENT,
    representation_name="gpumd",
    code_api={"M": "run.in: compute_msd <Nc> <output_interval>  →  msd.out"},
    notes=(
        "GPUMD's `compute_msd` keyword writes `msd.out` with columns "
        "`t (ps)  MSD_x  MSD_y  MSD_z  MSD_total`. The default uses "
        "unwrapped coordinates."
    ),
)


GPUMD_RUN_MD = OperatorRepresentationSpec(
    operator=run_md,
    representation_name="gpumd",
    notes=(
        "GPUMD production MD is driven by `ensemble <name> <args>` + "
        "`time_step <Δt>` + `run <n_steps>` blocks in `run.in`. "
        "Supported ensembles include `nve`, `nvt_ber`, `nvt_lan`, "
        "`nvt_nhc`, `nvt_bdp`, `npt_ber`, `npt_scr`. Integrator is "
        "Velocity-Verlet (GPUMD doesn't expose alternatives). Multiple "
        "`run` blocks in series let users equilibrate before the "
        "production segment that feeds compute_hac / compute_dos / "
        "compute_msd."
    ),
)


GPUMD_COMPUTE_HEAT_CURRENT = OperatorRepresentationSpec(
    operator=compute_heat_current,
    representation_name="gpumd",
    notes=(
        "Implicit: GPUMD computes J(t) internally on every step and "
        "feeds it directly to `compute_hac` / `compute_hnemd` / "
        "`compute_shc`. Users don't drive this separately — declaring "
        "`compute_hac` activates the heat-current computation."
    ),
)


GPUMD_AUTOCORRELATE_HEAT_CURRENT = OperatorRepresentationSpec(
    operator=autocorrelate_heat_current,
    representation_name="gpumd",
    notes=(
        "`compute_hac` uses the direct-sum form (no FFT pathway in "
        "GPUMD for HAC). The correlation depth Nc is set in the same "
        "keyword. Direct-sum and FFT are numerically equivalent under "
        "periodic padding — the operator layer no longer declares a "
        "`correlation_method` scheme."
    ),
)


GPUMD_COMPUTE_VELOCITY_AUTOCORRELATION = OperatorRepresentationSpec(
    operator=compute_velocity_autocorrelation,
    representation_name="gpumd",
    notes=(
        "`compute_dos` produces the mass-weighted VAF (mvac.out) "
        "alongside the DOS. The two outputs share the same compute, "
        "which is why GPUMD_VELOCITY_AUTOCORRELATION and the "
        "GPUMD_FOURIER_TO_DOS spec below reference the same keyword."
    ),
)


GPUMD_COMPUTE_MSD = OperatorRepresentationSpec(
    operator=compute_msd,
    representation_name="gpumd",
    scheme_overrides={"unwrap_pbc": "true"},
    notes=(
        "GPUMD's `compute_msd` uses unwrapped coordinates by default — "
        "no user-side unwrap step required."
    ),
)


GPUMD_FOURIER_TO_DOS = OperatorRepresentationSpec(
    operator=fourier_to_dos,
    representation_name="gpumd",
    notes=(
        "Folded into `compute_dos` alongside the VAF: GPUMD computes "
        "g(ω) directly from the mass-weighted VAF on a Nw × max_omega "
        "frequency grid and writes `dos.out`. From the operator's "
        "perspective this is one edge invocation, even though GPUMD "
        "performs VAF + FFT in a single internal step."
    ),
)


# ---------------------------------------------------------------------------
# MD-based κ paths (phase 2 P3)
# ---------------------------------------------------------------------------

GPUMD_THERMAL_CONDUCTIVITY_GREEN_KUBO = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_GREEN_KUBO,
    representation_name="gpumd",
    code_api={"kappa": "hac.out  (columns kappa_xx, kappa_yy, kappa_zz vs t)"},
    notes=(
        "GPUMD's `compute_hac` writes the *running* Green-Kubo κ "
        "alongside the autocorrelation: each row of `hac.out` carries "
        "both Jcorr(τ) and the partial integrals κ_xx(τ), κ_yy(τ), "
        "κ_zz(τ) — the integration is done on-the-fly. Users read off "
        "the plateau value as the converged Green-Kubo κ."
    ),
)


GPUMD_THERMAL_CONDUCTIVITY_HNEMD = SpaceRepresentationSpec(
    space=THERMAL_CONDUCTIVITY_HNEMD,
    representation_name="gpumd",
    code_api={"kappa": "kappa.out  (columns kappa_xx, kappa_xy, ..., kappa_zz vs t)"},
    notes=(
        "GPUMD's flagship thermal-transport output: `compute_hnemd "
        "<output_interval> <Fe_x> <Fe_y> <Fe_z>` writes `kappa.out` "
        "with running κ_xx, κ_yy, κ_zz, off-diagonals at the requested "
        "interval. The driving force F_e is supplied in units of 1/length "
        "(reciprocal Å for the NEP convention)."
    ),
)


GPUMD_CONTRACT_KAPPA_GREEN_KUBO = OperatorRepresentationSpec(
    operator=contract_kappa_green_kubo,
    representation_name="gpumd",
    parameter_units={"tau_max": "ps", "tau_min": "ps"},
    notes=(
        "Integration is implicit: GPUMD's `compute_hac` writes the "
        "running κ(τ) = V/(k_B T²) ∫₀^τ Jcorr dτ as it computes the "
        "ACF. τ_max is the correlation depth `Nc` (in time-step units) "
        "× the trajectory time step. The user reads the converged "
        "plateau."
    ),
)


GPUMD_CONTRACT_KAPPA_HNEMD = OperatorRepresentationSpec(
    operator=contract_kappa_hnemd,
    representation_name="gpumd",
    parameter_units={
        "driving_force_magnitude": "1/Angstrom",
        "driving_direction": "dimensionless",
    },
    notes=(
        "GPUMD's `compute_hnemd` keyword applies a homogeneous driving "
        "force F_e to every atom and reports the running κ. F_e must be "
        "small enough that the heat-current response is linear; GPUMD "
        "literature suggests |F_e| ~ 1e-4 to 1e-3 in 1/Å for typical "
        "potentials. The output file `kappa.out` carries the full "
        "κ_αβ tensor."
    ),
)


GPUMD_CONTRACT_KAPPA_NEMD = OperatorRepresentationSpec(
    operator=contract_kappa_nemd,
    representation_name="gpumd",
    notes=(
        "Not exposed by GPUMD. GPUMD's design choice is to favour HNEMD "
        "over direct NEMD — the homogeneous driving force avoids the "
        "boundary thermostats and reservoir artefacts that direct NEMD "
        "introduces. Users wanting direct/Müller-Plathe NEMD on a "
        "GPUMD-trained NEP potential typically port the NEP to LAMMPS "
        "(via the `pair_style nep` interface) and run `fix "
        "thermal/conductivity` there. Documented here for the adapter "
        "audit; the canonical NEMD path is the LAMMPS adapter's "
        "LAMMPS_CONTRACT_KAPPA_NEMD."
    ),
)
