"""Quantum ESPRESSO adapter specs for the DFT ground-state domain.

pw.x is the engine that grounds this domain: one SCF run produces the total
energy, the per-atom forces (tprnfor=.true., automatic in relax runs), and the
cell stress (tstress=.true.). The mapped artifacts, anchored to the vendored
q-e/ tree via the scan catalog `scans/qe-phonon.json` (QE 7.5):

  operator Space   QE artifact                                        program
  ---------------  -------------------------------------------------  -------
  Structure        input cards CELL_PARAMETERS / ATOMIC_POSITIONS /   pw.x
                   ATOMIC_SPECIES (or ibrav + celldm)
  TotalEnergy      stdout '!    total energy = ... Ry';               pw.x
                   XML total_energy (Hartree, etot/e2)
  Forces           stdout 'Forces acting on atoms' block (Ry/au);     pw.x
                   XML forces (Hartree/bohr, forces/e2)
  Stress           stdout 'total   stress' block (Ry/bohr**3 and      pw.x
                   kbar side by side); XML stress (Hartree/bohr^3)

Convention traps this module pins down:

  * stdout is Rydberg atomic units; the data-file-schema.xml divides every
    energy-bearing quantity by e2 = 2, i.e. stores Hartree atomic units
    (etot/e2 at PW/src/pw_restart_new.f90:728, forces/e2 at
    Modules/qexsd_init.f90:1366, stress/e2 at Modules/qexsd_init.f90:1394).
  * 'Ry/au' in the forces header means Ry/bohr.
  * The stress SIGN is the pressure convention (positive diagonal =
    compressive), verified from the vendored source, not assumed; see
    QE_STRESS.notes for the file:line derivation.
  * With smearing, the printed '!' energy is the smeared free-energy variant
    (F = E - TS_smear), flagged in the output near the '!' line.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.dft_ground_state.operator.edges import solve_ground_state
from omai.dft_ground_state.operator.nodes import (
    FORCES,
    STRESS,
    STRUCTURE,
    TOTAL_ENERGY,
)


QE_STRUCTURE = SpaceRepresentationSpec(
    space=STRUCTURE,
    representation_name="qe",
    code_api={
        "structure": "pw.x input cards CELL_PARAMETERS / ATOMIC_POSITIONS / ATOMIC_SPECIES",
    },
    notes=(
        "The crystal structure a pw.x run consumes: the cell either as an "
        "explicit CELL_PARAMETERS card (ibrav=0) or as a Bravais lattice "
        "index ibrav with celldm parameters; species and masses in "
        "ATOMIC_SPECIES; positions in ATOMIC_POSITIONS (alat, bohr, angstrom, "
        "or crystal units, declared on the card). The two cell routes are "
        "equivalent inputs to the same Structure; ibrav != 0 additionally "
        "fixes QE's canonical orientation of the primitive vectors, which "
        "matters when comparing Cartesian tensors (forces, stress) against "
        "another code's frame. Opaque at the operator layer: an artifact, "
        "not a numeric unit."
    ),
)


QE_TOTAL_ENERGY = SpaceRepresentationSpec(
    space=TOTAL_ENERGY,
    representation_name="qe",
    observable_units={"E_tot": "ry"},
    code_api={
        "E_tot": "pw.x stdout '!    total energy = ... Ry'; XML total_energy element",
    },
    notes=(
        "The converged SCF total energy. The '!' marker prefixes the "
        "CONVERGED value (intermediate iterations print unmarked estimates); "
        "the format lives at q-e/PW/src/electrons.f90:1758 (9080 FORMAT, "
        "F17.8, Ry). The data-file-schema.xml stores total_energy divided by "
        "e2 = 2, i.e. Hartree atomic units (qexsd_init_total_energy call at "
        "q-e/PW/src/pw_restart_new.f90:728), a factor-2 trap when parsing "
        "XML instead of stdout. With smearing the printed quantity is the "
        "smeared free energy F = E - TS_smear, flagged in the output."
    ),
)


QE_FORCES = SpaceRepresentationSpec(
    space=FORCES,
    representation_name="qe",
    observable_units={"F": "Ry_per_bohr"},
    code_api={
        "F": "pw.x stdout 'Forces acting on atoms (cartesian axes, Ry/au):' block (tprnfor=.true.)",
    },
    notes=(
        "Per-atom Cartesian forces in Ry/bohr ('Ry/au' means Ry/bohr): "
        "header at q-e/PW/src/forces.f90:345, per-atom 'atom N type M "
        "force =' lines (3F14.8) at q-e/PW/src/forces.f90:527. Printed when "
        "tprnfor=.true. (automatic in relax / md calculations). The XML "
        "stores forces/e2, i.e. Hartree/bohr (q-e/Modules/qexsd_init.f90:"
        "1366). This block is exactly what finite-displacement drivers "
        "(phonopy for FC2, thirdorder.py for FC3) harvest from supercell "
        "runs."
    ),
)


QE_STRESS = SpaceRepresentationSpec(
    space=STRESS,
    representation_name="qe",
    observable_units={"sigma": "kbar"},
    code_api={
        "sigma": "pw.x stdout 'total   stress  (Ry/bohr**3) ... (kbar)  P=' block (tstress=.true.)",
    },
    notes=(
        "Cell stress printed in Ry/bohr^3 and kbar side by side, with the "
        "pressure P = trace/3 in kbar on the header line (9000 format at "
        "q-e/PW/src/stress.f90:264; P computed as (sigma(1,1)+sigma(2,2)+"
        "sigma(3,3))*ry_kbar/3 at q-e/PW/src/stress.f90:228). SIGN "
        "CONVENTION, verified from the vendored source rather than assumed: "
        "QE prints the PRESSURE convention, positive diagonal = compressive. "
        "The variable-cell force is fcell proportional to (stress - press*I) "
        "(q-e/Modules/cell_base.f90:1008-1013, subroutine cell_force), so "
        "equilibrium under a positive external pressure press requires "
        "stress = press*I with POSITIVE diagonal entries; a compressed cell "
        "therefore prints positive sigma and positive P. Equivalently "
        "sigma_QE = -(1/V) dE/d(strain), the negative of the tension-"
        "positive continuum-mechanics Cauchy convention. The XML stores "
        "stress/e2, Hartree atomic units (q-e/Modules/qexsd_init.f90:1394)."
    ),
)


# ---------------------------------------------------------------------------
# Operator-level spec (diagnostic: how pw.x performs the SCF solve)
# ---------------------------------------------------------------------------

QE_SOLVE_GROUND_STATE = OperatorRepresentationSpec(
    operator=solve_ground_state,
    representation_name="qe",
    discretization_choices={
        "ecutwfc": "plane-wave kinetic-energy cutoff for wavefunctions, Ry (ecutrho for the density, default 4x)",
        "k_mesh": "Monkhorst-Pack K_POINTS automatic grid nk1 x nk2 x nk3, optionally shifted",
        "smearing": "occupations: fixed for insulators; smearing (gaussian / mp / mv / fd) with degauss for metals",
        "conv_thr": "SCF self-consistency threshold on the estimated energy error, Ry (electron_maxstep bounds iterations)",
        "pseudopotentials": "UPF files from pseudo_dir per ATOMIC_SPECIES; the XC functional is read from the UPFs unless input_dft overrides",
    },
    notes=(
        "pw.x realizes solve_ground_state as a plane-wave pseudopotential "
        "Kohn-Sham SCF loop. The Potential input's provenance for a QE run "
        "is exactly the pseudopotential set + XC functional + cutoffs "
        "(matching the thermal-domain QE_POTENTIAL note): two runs differing "
        "in any of these realize different Potentials, so instances must "
        "record them in the conditions. The k-mesh, smearing, and conv_thr "
        "are discretization choices of the solve itself: they change how "
        "accurately E_KS is minimized, not what E_KS is."
    ),
)
