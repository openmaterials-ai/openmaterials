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
  * HeatCurrentACF (`compute_hac` writes hac.out directly — the same
    file Green-Kubo κ is read from in P3).
  * VelocityAutocorrelation (`compute_dos`, which writes mvac.out and
    derives the DOS in one step — the GPUMD pathway folds VAF + Fourier
    into one keyword, so the same adapter spec covers fourier_to_dos
    too).
  * MeanSquaredDisplacement (`compute_msd`).
  * All six MD-driver operations.

Out of scope (will land in P3 of phase 2):
  * `contract_kappa_green_kubo`, `contract_kappa_nemd`,
    `contract_kappa_hnemd` — GPUMD's strongest suit lives here.
  * EMD κ via tighter ensemble averaging.
  * Heat-current spectral decomposition (per-frequency κ contributions).
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

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import (
    autocorrelate_heat_current,
    compute_heat_current,
    compute_msd,
    compute_velocity_autocorrelation,
    fourier_to_dos,
    provide_potential,
    run_md,
)
from omai.thermal_transport.operator.nodes import (
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    MEAN_SQUARED_DISPLACEMENT,
    POTENTIAL,
    TRAJECTORY,
    VELOCITY_AUTOCORRELATION,
)


GPUMD_POTENTIAL = StateAdapterSpec(
    state=POTENTIAL,
    adapter_name="gpumd",
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


GPUMD_PROVIDE_POTENTIAL = OperationAdapterSpec(
    operation=provide_potential,
    adapter_name="gpumd",
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

GPUMD_TRAJECTORY = StateAdapterSpec(
    state=TRAJECTORY,
    adapter_name="gpumd",
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


GPUMD_HEAT_CURRENT = StateAdapterSpec(
    state=HEAT_CURRENT,
    adapter_name="gpumd",
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


GPUMD_HEAT_CURRENT_ACF = StateAdapterSpec(
    state=HEAT_CURRENT_ACF,
    adapter_name="gpumd",
    code_api={"Jcorr": "run.in: compute_hac <Ns> <Nc> <out_steps>  →  hac.out"},
    notes=(
        "GPUMD's `compute_hac` keyword writes `hac.out` with columns "
        "`t (ps)  jxjx  jyjy  jzjz  jxjy ...`, i.e. the heat-current "
        "autocorrelation as a function of correlation lag. The same "
        "file is what the Green-Kubo κ contraction (P3) reads."
    ),
)


GPUMD_VELOCITY_AUTOCORRELATION = StateAdapterSpec(
    state=VELOCITY_AUTOCORRELATION,
    adapter_name="gpumd",
    code_api={"Cv": "run.in: compute_dos <Nc> <Nw> <max_omega>  →  mvac.out + dos.out"},
    notes=(
        "GPUMD bundles VAF + Fourier-to-DOS into one keyword: "
        "`compute_dos` writes both `mvac.out` (the VAF, mass-weighted) "
        "and `dos.out` (the resulting DOS). The same adapter spec "
        "therefore covers both VELOCITY_AUTOCORRELATION and "
        "PHONON_DOS-via-fourier_to_dos. Mass-weighting is automatic."
    ),
)


GPUMD_MEAN_SQUARED_DISPLACEMENT = StateAdapterSpec(
    state=MEAN_SQUARED_DISPLACEMENT,
    adapter_name="gpumd",
    code_api={"M": "run.in: compute_msd <Nc> <output_interval>  →  msd.out"},
    notes=(
        "GPUMD's `compute_msd` keyword writes `msd.out` with columns "
        "`t (ps)  MSD_x  MSD_y  MSD_z  MSD_total`. The default uses "
        "unwrapped coordinates."
    ),
)


GPUMD_RUN_MD = OperationAdapterSpec(
    operation=run_md,
    adapter_name="gpumd",
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


GPUMD_COMPUTE_HEAT_CURRENT = OperationAdapterSpec(
    operation=compute_heat_current,
    adapter_name="gpumd",
    notes=(
        "Implicit: GPUMD computes J(t) internally on every step and "
        "feeds it directly to `compute_hac` / `compute_hnemd` / "
        "`compute_shc`. Users don't drive this separately — declaring "
        "`compute_hac` activates the heat-current computation."
    ),
)


GPUMD_AUTOCORRELATE_HEAT_CURRENT = OperationAdapterSpec(
    operation=autocorrelate_heat_current,
    adapter_name="gpumd",
    algorithmic_convention_overrides={"correlation_method": "direct"},
    notes=(
        "`compute_hac` uses the direct-sum form (no FFT pathway in "
        "GPUMD for HAC). The correlation depth Nc is set in the same "
        "keyword."
    ),
)


GPUMD_COMPUTE_VELOCITY_AUTOCORRELATION = OperationAdapterSpec(
    operation=compute_velocity_autocorrelation,
    adapter_name="gpumd",
    algorithmic_convention_overrides={"correlation_method": "direct"},
    notes=(
        "`compute_dos` produces the mass-weighted VAF (mvac.out) "
        "alongside the DOS. The two outputs share the same compute, "
        "which is why GPUMD_VELOCITY_AUTOCORRELATION and the "
        "GPUMD_FOURIER_TO_DOS spec below reference the same keyword."
    ),
)


GPUMD_COMPUTE_MSD = OperationAdapterSpec(
    operation=compute_msd,
    adapter_name="gpumd",
    algorithmic_convention_overrides={"unwrap_pbc": "true"},
    notes=(
        "GPUMD's `compute_msd` uses unwrapped coordinates by default — "
        "no user-side unwrap step required."
    ),
)


GPUMD_FOURIER_TO_DOS = OperationAdapterSpec(
    operation=fourier_to_dos,
    adapter_name="gpumd",
    notes=(
        "Folded into `compute_dos` alongside the VAF: GPUMD computes "
        "g(ω) directly from the mass-weighted VAF on a Nw × max_omega "
        "frequency grid and writes `dos.out`. From the operator's "
        "perspective this is one edge invocation, even though GPUMD "
        "performs VAF + FFT in a single internal step."
    ),
)
