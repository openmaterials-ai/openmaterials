r"""pymatgen adapter specs for the DFT ground-state domain.

pymatgen 2025.6.14 as used by the AtomisticSkills mat-* skills, anchored in
`scans/pymatgen-atomistic-skills.json` (review 2026-07-09). pymatgen is the
structure/analysis workhorse of that software: it OWNS the crystal-structure
object every skill passes around, and it REPRESENTS the energies and stresses
an MLIP or DFT engine computes (it never computes them itself):

  operator Space   pymatgen artifact                                 units
  ---------------  ------------------------------------------------  --------
  Structure        pymatgen.core.Structure (lattice+species+coords)  angstrom
  TotalEnergy      entries.ComputedEntry.energy (per cell)           eV
  Stress           stresses fed to ElasticTensor.from_independent_   eV/A^3
                   strains (produced by the ASE/MLIP calculator)
  MagneticMoment   site moments parsed from calculator output;       mu_B
                   analysis.magnetism Ordering classification

Convention traps this module pins down (all review-verified):

  * ComputedEntry.energy is PER CELL (maps to TotalEnergy directly), but
    .energy_per_atom / formation_energy_per_atom / e_above_hull are PER ATOM
    and map to the DISTINCT FormationEnergy / EnergyAboveHull nodes of the
    stability domain, never to TotalEnergy: naive equating is wrong by the
    atom count (the scan's highest-risk trap).
  * VASP stress arrives in kbar with the opposite sign; pymatgen's
    from_independent_strains(vasp=True) fixes it via c_ij *= -0.1
    (elastic.py:519). The MLIP path feeds eV/A^3 and must not take it.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.edges import compute_magnetic_moments
from omai.dft_ground_state.operator.nodes import (
    MAGNETIC_MOMENT_STATE,
    STRESS,
    STRUCTURE,
    TOTAL_ENERGY,
)


PYMATGEN_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="pymatgen",
    code_api={
        "structure": "pymatgen.core.Structure (from_file / from_str; AseAtomsAdaptor bridge)",
    },
    notes=(
        "THE realization of the Structure node across the mat-* skills: "
        "lattice vectors + species + fractional positions, angstrom "
        "throughout (structure.py:1006 IStructure, :4137 Structure). "
        "pymatgen.io.ase.AseAtomsAdaptor is the bridge that lets ASE-native "
        "MLIP calculators act on it, the single most-called pymatgen API in "
        "the MD-based skills. Opaque at the operator layer: an artifact, "
        "not a numeric unit."
    ),
)


PYMATGEN_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="pymatgen",
    observable_units={"E_tot": "ev"},
    code_api={
        "E_tot": "pymatgen.entries.computed_entries.ComputedEntry.energy (per cell), eV",
    },
    notes=(
        "The per-cell total energy as pymatgen represents it "
        "(ComputedEntry / ComputedStructureEntry .energy, eV), fed by an "
        "MLIP calculator or read from VASP/QE output: pymatgen represents "
        "the energy, it does not compute it. PER-ATOM TRAP (review-settled): "
        ".energy_per_atom, formation_energy_per_atom, and e_above_hull are "
        "eV/ATOM currencies of the phase-diagram machinery and map to the "
        "stability domain's FormationEnergy / EnergyAboveHull nodes, NOT to "
        "this per-cell node; equating them is wrong by the atom count."
    ),
)


PYMATGEN_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="pymatgen",
    observable_units={"sigma": "eV_per_A3"},
    code_api={
        "sigma": "stresses consumed by ElasticTensor.from_independent_strains (ASE/MLIP Voigt, eV/A^3)",
    },
    notes=(
        "pymatgen REPRESENTS/CONSUMES the stress (in the elasticity fit); "
        "the MLIP or DFT engine produces it. On the AtomisticSkills MLIP "
        "path the ASE calculator delivers the Voigt 6-vector in eV/A^3, fed "
        "directly to from_independent_strains. VASP TRAP: VASP stress is "
        "kbar with the opposite sign, corrected by the vasp=True branch's "
        "c_ij *= -0.1 (elastic.py:519); taking that branch on eV/A^3 MLIP "
        "stresses flips sign and scale."
    ),
)


PYMATGEN_MAGNETIC_MOMENT = SpaceRepresentationSpec(
    space=MAGNETIC_MOMENT_STATE,
    representation_name="pymatgen",
    observable_units={"m": "mu_B"},
    code_api={
        "m": "site moments parsed from calculator output; pymatgen.analysis.magnetism Ordering / CollinearMagneticStructureAnalyzer, mu_B",
    },
    notes=(
        "Per-site moments in Bohr magnetons as the mat-magnetic-density "
        "skill parses them from spin-polarized DFT output "
        "(parse_magnetic_moments.py; MP serves the cell total as "
        "total_magnetization, mu_B per cell). pymatgen's role is "
        "representation and classification: analysis.magnetism.Ordering / "
        "CollinearMagneticStructureAnalyzer assign the FM/AFM/FiM/NM label "
        "over these moments; the moments themselves are calculator output."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how the skills realize the moment solve)
# ---------------------------------------------------------------------------

PYMATGEN_COMPUTE_MAGNETIC_MOMENTS = OperatorRepresentationSpec(
    operator=compute_magnetic_moments,
    representation_name="pymatgen",
    discretization_choices={
        "site_projection": (
            "how the spin density is assigned to sites (VASP RWIGS "
            "integration spheres by default); changes the split between "
            "site moments and interstitial magnetization, not the physics"
        ),
        "initial_moments": (
            "the MAGMOM-style starting guess (MPStaticSet defaults in the "
            "skill); a poor guess can converge to a different magnetic "
            "solution, recorded in instance conditions"
        ),
    },
    notes=(
        "The mat-magnetic-density flow realizes compute_magnetic_moments as "
        "a spin-polarized static DFT run (VASP via MPStaticSet in the "
        "committed Fe example) whose per-site moments pymatgen parses and "
        "classifies (Ordering). The Potential input's provenance is the "
        "XC functional + pseudopotentials + U corrections, exactly as for "
        "solve_ground_state."
    ),
)
