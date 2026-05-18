"""Smoke tests for phase-2 P2 MD primitives.

P2 introduces 5 new operator-layer states (Trajectory, HeatCurrent,
HeatCurrentACF, VelocityAutocorrelation, MeanSquaredDisplacement) and
6 new edges (run_md, compute_heat_current, autocorrelate_heat_current,
compute_velocity_autocorrelation, compute_msd, fourier_to_dos).

Adapter coverage extends `lammps` and `gpumd` for the five new states
and all six edges. These tests verify each state/edge identity, the
sympy formulas carry the right output indices, the algorithmic
conventions are declared per spec, and each new adapter spec points at
the correct operator-layer object.
"""

from __future__ import annotations

import sympy as sp

from omai.operator.dimensions import (
    ENERGY_TIMES_LENGTH_PER_TIME,
    LENGTH,
    LENGTH_PER_TIME,
    LENGTH_SQUARED,
)
from omai.operator.state import HiddenState, Observable
from omai.operator.validate import validate_dag
from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator import EDGES, NODES
from omai.thermal_transport.operator.edges import (
    autocorrelate_heat_current,
    compute_heat_current,
    compute_msd,
    compute_velocity_autocorrelation,
    fourier_to_dos,
    run_md,
)
from omai.thermal_transport.operator.nodes import (
    HEAT_CURRENT,
    HEAT_CURRENT_ACF,
    MEAN_SQUARED_DISPLACEMENT,
    PHONON_DOS,
    POTENTIAL,
    TEMPERATURE_STATE,
    TRAJECTORY,
    VELOCITY_AUTOCORRELATION,
)


# ---------------------------------------------------------------------------
# State identity & kind
# ---------------------------------------------------------------------------


def test_trajectory_is_hidden_state_with_r_and_v():
    assert isinstance(TRAJECTORY, HiddenState)
    assert TRAJECTORY.name == "Trajectory"
    field_names = {f.name for f in TRAJECTORY.fields}
    assert field_names == {"r", "v"}
    r = next(f for f in TRAJECTORY.fields if f.name == "r")
    v = next(f for f in TRAJECTORY.fields if f.name == "v")
    assert r.dimension is LENGTH
    assert v.dimension is LENGTH_PER_TIME
    assert r.indices == ("i", "alpha", "t")
    assert v.indices == ("i", "alpha", "t")


def test_heat_current_is_hidden_state_with_J():
    assert isinstance(HEAT_CURRENT, HiddenState)
    assert HEAT_CURRENT.name == "HeatCurrent"
    (J,) = HEAT_CURRENT.fields
    assert J.name == "J"
    assert J.dimension is ENERGY_TIMES_LENGTH_PER_TIME
    assert J.indices == ("alpha", "t")


def test_heat_current_acf_is_observable():
    assert isinstance(HEAT_CURRENT_ACF, Observable)
    (Jcorr,) = HEAT_CURRENT_ACF.fields
    assert Jcorr.name == "Jcorr"
    assert Jcorr.indices == ("alpha", "beta", "tau")


def test_vaf_is_observable():
    assert isinstance(VELOCITY_AUTOCORRELATION, Observable)
    (Cv,) = VELOCITY_AUTOCORRELATION.fields
    assert Cv.name == "Cv"
    assert Cv.indices == ("tau",)


def test_msd_is_observable_with_length_squared():
    assert isinstance(MEAN_SQUARED_DISPLACEMENT, Observable)
    (M,) = MEAN_SQUARED_DISPLACEMENT.fields
    assert M.name == "M"
    assert M.dimension is LENGTH_SQUARED
    assert M.indices == ("tau",)


def test_trajectory_scaffolding_contractions_match_observables():
    """Trajectory is scaffolding-kind; its declared contractions must be
    Observables in the node set."""
    assert TRAJECTORY.kind == "scaffolding"
    obs_names = {n.name for n in NODES if isinstance(n, Observable)}
    for contraction in TRAJECTORY.gauge_invariant_contractions:
        assert contraction in obs_names


# ---------------------------------------------------------------------------
# Edge identity, inputs/outputs, and sympy formulas
# ---------------------------------------------------------------------------


def test_run_md_inputs_outputs():
    assert run_md.name == "run_md"
    assert set(run_md.inputs) == {POTENTIAL, TEMPERATURE_STATE}
    assert run_md.outputs == (TRAJECTORY,)
    assert run_md.formula is not None
    assert isinstance(run_md.formula, sp.Eq)
    # LHS rank must match Trajectory.r's index count (3: i, alpha, t).
    assert len(run_md.formula.lhs.indices) == 3


def test_run_md_declares_md_conventions():
    convs = run_md.algorithmic_conventions
    assert "ensemble" in convs
    assert "thermostat" in convs
    assert "integrator" in convs


def test_compute_heat_current_inputs_outputs():
    assert compute_heat_current.name == "compute_heat_current"
    assert set(compute_heat_current.inputs) == {TRAJECTORY}
    assert compute_heat_current.outputs == (HEAT_CURRENT,)
    assert isinstance(compute_heat_current.formula, sp.Eq)
    assert len(compute_heat_current.formula.lhs.indices) == 2  # (alpha, t)
    assert "definition" in compute_heat_current.algorithmic_conventions


def test_autocorrelate_heat_current_inputs_outputs():
    assert autocorrelate_heat_current.name == "autocorrelate_heat_current"
    assert set(autocorrelate_heat_current.inputs) == {HEAT_CURRENT}
    assert autocorrelate_heat_current.outputs == (HEAT_CURRENT_ACF,)
    assert isinstance(autocorrelate_heat_current.formula, sp.Eq)
    assert len(autocorrelate_heat_current.formula.lhs.indices) == 3
    assert "correlation_method" in autocorrelate_heat_current.algorithmic_conventions


def test_compute_velocity_autocorrelation_inputs_outputs():
    assert compute_velocity_autocorrelation.name == "compute_velocity_autocorrelation"
    assert set(compute_velocity_autocorrelation.inputs) == {TRAJECTORY}
    assert compute_velocity_autocorrelation.outputs == (VELOCITY_AUTOCORRELATION,)
    assert isinstance(compute_velocity_autocorrelation.formula, sp.Eq)


def test_compute_msd_inputs_outputs():
    assert compute_msd.name == "compute_msd"
    assert set(compute_msd.inputs) == {TRAJECTORY}
    assert compute_msd.outputs == (MEAN_SQUARED_DISPLACEMENT,)
    assert "unwrap_pbc" in compute_msd.algorithmic_conventions


def test_fourier_to_dos_is_pattern_c_alternative_producer_of_dos():
    """fourier_to_dos and compute_dos both produce PhononDOS — Pattern C."""
    assert fourier_to_dos.outputs == (PHONON_DOS,)
    producers = [e for e in EDGES if PHONON_DOS in e.outputs]
    assert len(producers) >= 2  # compute_dos + fourier_to_dos


# ---------------------------------------------------------------------------
# DAG-level sanity
# ---------------------------------------------------------------------------


def test_dag_validates_clean_with_md_edges():
    errors = validate_dag(NODES, EDGES)
    assert errors == [], "\n".join(errors)


# ---------------------------------------------------------------------------
# LAMMPS adapter coverage
# ---------------------------------------------------------------------------


def test_lammps_covers_all_five_md_states():
    from omai.thermal_transport.representation.lammps import (
        LAMMPS_HEAT_CURRENT,
        LAMMPS_HEAT_CURRENT_ACF,
        LAMMPS_MEAN_SQUARED_DISPLACEMENT,
        LAMMPS_TRAJECTORY,
        LAMMPS_VELOCITY_AUTOCORRELATION,
    )

    pairs = [
        (LAMMPS_TRAJECTORY, TRAJECTORY),
        (LAMMPS_HEAT_CURRENT, HEAT_CURRENT),
        (LAMMPS_HEAT_CURRENT_ACF, HEAT_CURRENT_ACF),
        (LAMMPS_VELOCITY_AUTOCORRELATION, VELOCITY_AUTOCORRELATION),
        (LAMMPS_MEAN_SQUARED_DISPLACEMENT, MEAN_SQUARED_DISPLACEMENT),
    ]
    for spec, state in pairs:
        assert isinstance(spec, StateAdapterSpec)
        assert spec.adapter_name == "lammps"
        assert spec.state is state
        assert spec.code_api, f"{spec.state.name}: empty code_api"


def test_lammps_covers_all_six_md_edges():
    from omai.thermal_transport.representation.lammps import (
        LAMMPS_AUTOCORRELATE_HEAT_CURRENT,
        LAMMPS_COMPUTE_HEAT_CURRENT,
        LAMMPS_COMPUTE_MSD,
        LAMMPS_COMPUTE_VELOCITY_AUTOCORRELATION,
        LAMMPS_FOURIER_TO_DOS,
        LAMMPS_RUN_MD,
    )

    pairs = [
        (LAMMPS_RUN_MD, run_md),
        (LAMMPS_COMPUTE_HEAT_CURRENT, compute_heat_current),
        (LAMMPS_AUTOCORRELATE_HEAT_CURRENT, autocorrelate_heat_current),
        (LAMMPS_COMPUTE_VELOCITY_AUTOCORRELATION, compute_velocity_autocorrelation),
        (LAMMPS_COMPUTE_MSD, compute_msd),
        (LAMMPS_FOURIER_TO_DOS, fourier_to_dos),
    ]
    for spec, op in pairs:
        assert isinstance(spec, OperationAdapterSpec)
        assert spec.adapter_name == "lammps"
        assert spec.operation is op


# ---------------------------------------------------------------------------
# GPUMD adapter coverage
# ---------------------------------------------------------------------------


def test_gpumd_covers_all_five_md_states():
    from omai.thermal_transport.representation.gpumd import (
        GPUMD_HEAT_CURRENT,
        GPUMD_HEAT_CURRENT_ACF,
        GPUMD_MEAN_SQUARED_DISPLACEMENT,
        GPUMD_TRAJECTORY,
        GPUMD_VELOCITY_AUTOCORRELATION,
    )

    pairs = [
        (GPUMD_TRAJECTORY, TRAJECTORY),
        (GPUMD_HEAT_CURRENT, HEAT_CURRENT),
        (GPUMD_HEAT_CURRENT_ACF, HEAT_CURRENT_ACF),
        (GPUMD_VELOCITY_AUTOCORRELATION, VELOCITY_AUTOCORRELATION),
        (GPUMD_MEAN_SQUARED_DISPLACEMENT, MEAN_SQUARED_DISPLACEMENT),
    ]
    for spec, state in pairs:
        assert isinstance(spec, StateAdapterSpec)
        assert spec.adapter_name == "gpumd"
        assert spec.state is state
        assert spec.code_api, f"{spec.state.name}: empty code_api"


def test_gpumd_covers_all_six_md_edges():
    from omai.thermal_transport.representation.gpumd import (
        GPUMD_AUTOCORRELATE_HEAT_CURRENT,
        GPUMD_COMPUTE_HEAT_CURRENT,
        GPUMD_COMPUTE_MSD,
        GPUMD_COMPUTE_VELOCITY_AUTOCORRELATION,
        GPUMD_FOURIER_TO_DOS,
        GPUMD_RUN_MD,
    )

    pairs = [
        (GPUMD_RUN_MD, run_md),
        (GPUMD_COMPUTE_HEAT_CURRENT, compute_heat_current),
        (GPUMD_AUTOCORRELATE_HEAT_CURRENT, autocorrelate_heat_current),
        (GPUMD_COMPUTE_VELOCITY_AUTOCORRELATION, compute_velocity_autocorrelation),
        (GPUMD_COMPUTE_MSD, compute_msd),
        (GPUMD_FOURIER_TO_DOS, fourier_to_dos),
    ]
    for spec, op in pairs:
        assert isinstance(spec, OperationAdapterSpec)
        assert spec.adapter_name == "gpumd"
        assert spec.operation is op
