r"""LAMMPS adapter specs for the mechanics domain.

Two spaces and one operator, grounded in the vendored LAMMPS tree via the scan
catalog `scans/lammps-thermal.json` (LAMMPS 30 Mar 2026):

  operator Space      LAMMPS artifact                                   program
  ------------------  -----------------------------------------------  --------------------
  ElasticConstants    examples/ELASTIC log 'Elastic Constant CXYall =  in.elastic workflow
                      ... GPa' block (Voigt 6x6, symmetrized)
  Pressure            thermo Press / compute pressure scalar = trace/3 compute pressure

  operator            LAMMPS realization                                program
  ------------------  -----------------------------------------------  --------------------
  compute_elastic_    examples/ELASTIC finite-strain stress fitting    in.elastic + init.mod
  constants           (+/- box strain, re-minimize, -d(sigma)/d(strain))  + displace.mod

Convention traps this module pins down:

  * LAMMPS ELASTIC prints the Voigt 6x6 stiffness matrix C_ij in GPa (metal
    units, via cfac = 1.0e-4 bar -> GPa in init.mod). The map node is the full
    rank-4 tensor; the Voigt packing is recorded here as the code's layout.
  * The elastic workflow's stress-difference formula carries a MINUS sign
    (in.elastic:75, d_i = -(p_i1 - p_i0)/(strain)*cfac): LAMMPS's pressure
    tensor is positive-compression, exactly the store's stress convention, so
    this is the SAME minus the operator formula C = -d(sigma)/d(strain)
    carries (it restores positive C11 for stable crystals).
  * compute pressure returns the POSITIVE-compression (physics) pressure
    P = trace/3, the exact NEGATIVE of the per-atom stress*volume the heat-flux
    pipeline uses. This is the same sign the store's Stress node records, so
    contract_pressure's P = +trace/3 is consistent.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.mechanics.operator.edges import compute_elastic_constants, contract_density
from omai.mechanics.operator.nodes import (
    ELASTIC_CONSTANTS,
    MASS_DENSITY_STATE,
    PRESSURE,
)


LAMMPS_ELASTIC_CONSTANTS = SpaceRepresentationSpec(
    space=ELASTIC_CONSTANTS,
    representation_name="lammps",
    observable_units={"C": "GPa"},
    code_api={
        "C": "examples/ELASTIC log 'Elastic Constant CXYall = ... GPa' block (in.elastic)",
    },
    notes=(
        "The zero-temperature elastic stiffness tensor by central finite "
        "difference of the virial stress under +/- box strain with energy "
        "minimization (relaxed-ion C_ij, T=0 statics, NOT the finite-T "
        "stress-fluctuation method). LAMMPS emits the Voigt 6x6 matrix C_ij "
        "(scan anchor lammps/examples/ELASTIC/in.elastic:88-157), symmetrized "
        "as 0.5*(Cij + Cji) at in.elastic:124; the map node is the full rank-4 "
        "tensor, of which this is the standard packing. Metal units: cfac = "
        "1.0e-4 converts bar to GPa (lammps/examples/ELASTIC/init.mod:23), so "
        "the printed numbers are GPa; real / lj units need a different cfac in "
        "init.mod. The Voigt strain directions 1..6 map to change_box "
        "x/y/z/yz/xz/xy deformations. The Si Stillinger-Weber example "
        "cross-checks Cowley 1988: C11=151.4, C12=76.4, C44=56.4 GPa."
    ),
)


LAMMPS_PRESSURE = SpaceRepresentationSpec(
    space=PRESSURE,
    representation_name="lammps",
    observable_units={"P": "GPa"},
    code_api={
        "P": "thermo 'Press' / compute pressure scalar (auto-created thermo_press)",
    },
    notes=(
        "Global pressure P = (dof kB T + sum_diag virial)/(d V) * nktv2p, the "
        "scalar being the tensor trace/d (scan anchor "
        "lammps/src/compute_pressure.cpp:253; thermo 'press' keyword at "
        "thermo.cpp:1972). SIGN: LAMMPS's compute pressure is the "
        "positive-under-compression physics pressure, the exact NEGATIVE of "
        "the per-atom stress*volume (compute stress/atom) that grounds the "
        "heat-flux virial (P = -sum(S_i)/(d V), "
        "lammps/src/compute_stress_atom.cpp:328). That matches the store's "
        "Stress sign convention (positive diagonal = compressive), so "
        "contract_pressure's P = +trace(sigma)/3 is consistent with this "
        "output. Native unit is bar in metal (nktv2p), quoted here in GPa "
        "(1 GPa = 1e4 bar); the ELASTIC workflow reads the reference stresses "
        "pxx0..pxy0 from exactly this compute "
        "(lammps/examples/ELASTIC/in.elastic:53-64)."
    ),
)


LAMMPS_MASS_DENSITY = SpaceRepresentationSpec(
    space=MASS_DENSITY_STATE,
    representation_name="lammps",
    observable_units={"rho": "gram_per_cm3"},
    code_api={
        "rho": "thermo 'density' column (thermo_style custom ... density)",
    },
    notes=(
        "The MD thermo 'density' column = total cell mass / cell volume, printed "
        "in g/cm^3 under UNIT STYLE metal (the style of all three mat-lammps-md "
        "examples: eV, bar, K, ps, g/cm^3). mat-lammps-md tracks it across a melt "
        "/ quench / hold to read glass densification "
        "(examples/mace/in.na2si3o7_quench_mace:23) and across the Cu phase "
        "transition (examples/matgl/in.cu_phase_transition_matgl:25); the fairchem "
        "adsorption-relax example (in.relax_adsorption_fairchem:22) omits the "
        "density column, so the g/cm^3 claim is scoped to the mace + matgl runs. "
        "In lj units 'density' is reduced (number density * sigma^-3), so the "
        "g/cm^3 unit is metal-specific. Native metal thermo, not a separate "
        "compute."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how the ELASTIC workflow fits the tensor)
# ---------------------------------------------------------------------------

LAMMPS_COMPUTE_ELASTIC_CONSTANTS = OperatorRepresentationSpec(
    operator=compute_elastic_constants,
    representation_name="lammps",
    discretization_choices={
        "strain_magnitude": (
            "the applied engineering strain 'up' (init.mod, e.g. 1e-6); "
            "convergence is checked by insensitivity of C_ij to up"
        ),
        "deformation_averaging": (
            "each Voigt direction is deformed NEGATIVE then POSITIVE by up, "
            "each followed by a minimize, and the two stress differences are "
            "averaged: C_ij = -(P_i(+up) - P_i(-up))/(2 up) * cfac "
            "(lammps/examples/ELASTIC/displace.mod:26, in.elastic:75)"
        ),
        "ion_relaxation": (
            "atoms are re-minimized after each box deformation (change_box "
            "remap units box + minimize), giving the relaxed-ion constants; "
            "the outer box minimization style / tolerances live in init.mod"
        ),
        "cfac": (
            "unit-style stress-to-GPa factor in init.mod (metal 1.0e-4 bar->GPa, "
            "real 1.01325e-4 atm->GPa); porting unit styles means editing it"
        ),
    },
    notes=(
        "The examples/ELASTIC input-script workflow (in.elastic + init.mod + "
        "potential.mod + displace.mod), not a dedicated compute. It realizes "
        "compute_elastic_constants literally: a finite-difference estimate of "
        "the operator formula C = -d(sigma)/d(strain) at T=0, the script's "
        "own d_i = -(p_i1 - p_i0)/strain carrying exactly the operator's "
        "minus (lammps/examples/ELASTIC/in.elastic:75), since LAMMPS's "
        "pressure tensor has the same positive-compression sign as the "
        "store's stress. The strain magnitude and the up/down averaging are "
        "discretization choices of the estimator; they change how accurately "
        "-d(sigma)/d(strain) is resolved, not what the elastic tensor is."
    ),
)


LAMMPS_CONTRACT_DENSITY = OperatorRepresentationSpec(
    operator=contract_density,
    representation_name="lammps",
    notes=(
        "The metal-unit 'density' thermo keyword: LAMMPS computes mass / volume "
        "of the current box each thermo step and prints it in g/cm^3, the "
        "realization of contract_density (rho = total cell mass / cell volume). "
        "Native to the thermo output, no compute or fix required."
    ),
)
