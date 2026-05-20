"""ase adapter specs for the thermal-transport DAG.

ASE (Atomic Simulation Environment, https://wiki.fysik.dtu.dk/ase/) is not
a thermal-transport code in itself — it is the *calculator-interface
protocol* that kaldo, phonopy, phono3py, and many other Python-driven
materials-science codes use to evaluate forces, energies, and stresses on
a candidate atomic configuration. Concretely, the `ase.Atoms` object
holds an attached `Atoms.calc` whose `get_forces()` / `get_potential_energy()`
methods drive force-field, DFT, or ML-IP backends behind a uniform API.

This adapter exists to make the *shared ASE-calculator anchor* across the
BTE codes first-class in the operator/representation layer. When kaldo,
phonopy, and phono3py all wire their force evaluations through the same
ASE calculator instance (e.g. `LAMMPSlib(pair_style=...)`), the cross-code
κ comparison's "but you used different forces" caveat goes away: the
operator-layer Potential is pinned at the ASE protocol level.

The ASE adapter does NOT supply numerical thermal-transport observables
(frequencies, linewidths, κ) — those belong to the downstream codes. Its
sole responsibility is to declare `provide_potential` in a code-agnostic
way, so any other adapter can cite "ASE Atoms.calc" as its Potential
source.

References:
  * Atoms.calc — https://wiki.fysik.dtu.dk/ase/ase/atoms.html#ase.Atoms.calc
  * Calculator backends — https://wiki.fysik.dtu.dk/ase/ase/calculators/

Concrete backends commonly used in this project's worked examples:
  * `ase.calculators.lammpslib.LAMMPSlib` — LAMMPS classical potentials
    (Tersoff, EAM, ReaxFF, …) driven by an in-Python LAMMPS instance.
  * `gpaw.GPAW` — DFT via GPAW, real-space grid.
  * `ase.calculators.kim.KIM` — OpenKIM portal models (Tersoff, EAM, …
    drawn from the public KIM-API repository).
  * MACE, NequIP, Orb, M3GNet, … — Python-wrapped ML interatomic
    potentials; each ships an `ase.calculators.calculator.Calculator`
    subclass.
"""

from __future__ import annotations

from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator.edges import provide_potential
from omai.thermal_transport.operator.nodes import POTENTIAL


ASE_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="ase",
    code_api={"potential": "ase.Atoms.calc"},
    notes=(
        "The Potential is the ASE calculator object attached to the "
        "ase.Atoms instance via `atoms.calc = SomeCalculator(...)`. "
        "Concrete backends include LAMMPSlib (LAMMPS classical potentials), "
        "GPAW (DFT), KIM (OpenKIM portal models), and ML-IP wrappers "
        "(MACE, NequIP, Orb, M3GNet, …). Force evaluation is uniform: "
        "`atoms.get_forces()` returns (n_atoms, 3) in eV/Å regardless of "
        "the backend. Stress and energy similarly. The ASE protocol is "
        "what kaldo, phonopy, and phono3py all consume when their "
        "Phonons / Phono3py / Phonopy objects are built from an Atoms "
        "instance with `.calc` set."
    ),
)


ASE_PROVIDE_POTENTIAL = OperatorRepresentationSpec(
    operator=provide_potential,
    representation_name="ase",
    notes=(
        "Provides Potential via the ASE calculator protocol. The user "
        "constructs an `ase.Atoms` instance and assigns "
        "`atoms.calc = SomeCalculator(...)`; downstream adapters "
        "(kaldo, phonopy, phono3py) consume this Atoms object directly. "
        "Algorithmic conventions on FC2/FC3 derivation (symmetry_group, "
        "FD displacement magnitude, etc.) remain with the downstream "
        "adapter — ASE is purely the force-evaluation interface."
    ),
)
