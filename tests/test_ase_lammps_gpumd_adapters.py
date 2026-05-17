"""Smoke tests for the three new phase-2-P1 adapter modules.

P1 of phase 2 introduces three new representation adapters:
  * `ase`    — generic ASE-calculator interface
  * `lammps` — LAMMPS-native
  * `gpumd`  — GPUMD-native

Each gets a StateAdapterSpec for POTENTIAL and an OperationAdapterSpec
for provide_potential. These tests verify the adapters import, name
themselves correctly, and point at the right operator-layer state /
edge.
"""

from __future__ import annotations

from omai.representation.adapter import OperationAdapterSpec, StateAdapterSpec
from omai.thermal_transport.operator.edges import provide_potential
from omai.thermal_transport.operator.nodes import POTENTIAL


# -- ase ----------------------------------------------------------------


def test_ase_potential_spec_targets_potential_state():
    from omai.thermal_transport.representation.ase import ASE_POTENTIAL

    assert isinstance(ASE_POTENTIAL, StateAdapterSpec)
    assert ASE_POTENTIAL.adapter_name == "ase"
    assert ASE_POTENTIAL.state is POTENTIAL
    assert "potential" in ASE_POTENTIAL.code_api
    assert "ase.Atoms.calc" in ASE_POTENTIAL.code_api["potential"]


def test_ase_provide_potential_spec_targets_provide_potential_edge():
    from omai.thermal_transport.representation.ase import ASE_PROVIDE_POTENTIAL

    assert isinstance(ASE_PROVIDE_POTENTIAL, OperationAdapterSpec)
    assert ASE_PROVIDE_POTENTIAL.adapter_name == "ase"
    assert ASE_PROVIDE_POTENTIAL.operation is provide_potential


# -- lammps -------------------------------------------------------------


def test_lammps_potential_spec_targets_potential_state():
    from omai.thermal_transport.representation.lammps import LAMMPS_POTENTIAL

    assert isinstance(LAMMPS_POTENTIAL, StateAdapterSpec)
    assert LAMMPS_POTENTIAL.adapter_name == "lammps"
    assert LAMMPS_POTENTIAL.state is POTENTIAL
    assert "pair_style" in LAMMPS_POTENTIAL.code_api["potential"]


def test_lammps_provide_potential_spec_targets_provide_potential_edge():
    from omai.thermal_transport.representation.lammps import LAMMPS_PROVIDE_POTENTIAL

    assert isinstance(LAMMPS_PROVIDE_POTENTIAL, OperationAdapterSpec)
    assert LAMMPS_PROVIDE_POTENTIAL.adapter_name == "lammps"
    assert LAMMPS_PROVIDE_POTENTIAL.operation is provide_potential


# -- gpumd --------------------------------------------------------------


def test_gpumd_potential_spec_targets_potential_state():
    from omai.thermal_transport.representation.gpumd import GPUMD_POTENTIAL

    assert isinstance(GPUMD_POTENTIAL, StateAdapterSpec)
    assert GPUMD_POTENTIAL.adapter_name == "gpumd"
    assert GPUMD_POTENTIAL.state is POTENTIAL
    api = GPUMD_POTENTIAL.code_api["potential"]
    assert "nep" in api.lower() or "potential" in api.lower()


def test_gpumd_provide_potential_spec_targets_provide_potential_edge():
    from omai.thermal_transport.representation.gpumd import GPUMD_PROVIDE_POTENTIAL

    assert isinstance(GPUMD_PROVIDE_POTENTIAL, OperationAdapterSpec)
    assert GPUMD_PROVIDE_POTENTIAL.adapter_name == "gpumd"
    assert GPUMD_PROVIDE_POTENTIAL.operation is provide_potential


# -- cross-adapter --------------------------------------------------------


def test_all_three_new_adapters_use_distinct_names():
    from omai.thermal_transport.representation.ase import ASE_POTENTIAL
    from omai.thermal_transport.representation.gpumd import GPUMD_POTENTIAL
    from omai.thermal_transport.representation.lammps import LAMMPS_POTENTIAL

    names = {ASE_POTENTIAL.adapter_name, LAMMPS_POTENTIAL.adapter_name, GPUMD_POTENTIAL.adapter_name}
    assert names == {"ase", "lammps", "gpumd"}


def test_existing_bte_adapter_potential_notes_cite_ase_adapter():
    """The four existing BTE-adapter Potential / provide_potential specs
    should mention the new `ase` adapter as the canonical source."""
    from omai.thermal_transport.representation.kaldo import (
        KALDO_POTENTIAL,
        KALDO_PROVIDE_POTENTIAL,
    )
    from omai.thermal_transport.representation.phono3py import (
        PHONO3PY_POTENTIAL,
        PHONO3PY_PROVIDE_POTENTIAL,
    )
    from omai.thermal_transport.representation.phonopy import (
        PHONOPY_POTENTIAL,
        PHONOPY_PROVIDE_POTENTIAL,
    )
    from omai.thermal_transport.representation.shengbte import (
        SHENGBTE_PROVIDE_POTENTIAL,
    )

    for spec in (
        KALDO_POTENTIAL,
        KALDO_PROVIDE_POTENTIAL,
        PHONO3PY_POTENTIAL,
        PHONO3PY_PROVIDE_POTENTIAL,
        PHONOPY_POTENTIAL,
        PHONOPY_PROVIDE_POTENTIAL,
        SHENGBTE_PROVIDE_POTENTIAL,
    ):
        assert "ase" in spec.notes.lower(), (
            f"{type(spec).__name__} for {spec.adapter_name} does not cite "
            f"the `ase` adapter in its notes; got:\n{spec.notes}"
        )
