"""i-PI adapter specs: the nuclear-quantum-effects layer (Cookbook Slice 1).

i-PI (https://ipi-code.org) is the universal Python force server for advanced
atomistic simulations: path-integral molecular dynamics (PIMD), ring-polymer
contraction, multiple time stepping, GLE / PIGLET thermostats, instanton rate
theory, and replica exchange. It runs a server/driver architecture: i-PI
integrates the (ring-polymer) equations of motion and asks a force provider
(LAMMPS, CP2K, ASE, or a metatomic model) for energies and forces over a socket.

This adapter, from the Atomistic Cookbook audit (scans/cookbook-audit.json, the
i-PI slice), makes i-PI the SIXTH producer of the existing Trajectory node: the
PIMD trajectory is the path-integral producer variant of the classical run_md
Trajectory (the same node, sampled with ring-polymer BEADS instead of a single
classical replica), and the two nuclear-quantum estimators are read off its
beads:

  * QuantumKineticEnergy (new scalar node, ENERGY): the centroid-virial
    estimator of the nuclear quantum kinetic energy, exceeding the classical
    3/2 N k_B T equipartition value and reducing to it in the classical
    (nbeads=1) limit.
  * HeatCapacity[method=pimd] (a method-tagged producer variant of the existing
    HeatCapacity, ENERGY_PER_TEMPERATURE): the PIMD scaled-coordinates
    (double-virial) estimator of C_V, valid for liquids / anharmonic systems
    where the harmonic mode-sum route is not.

Scope of this slice:
  * Temperature (the sampling state point).
  * Trajectory (the PIMD ring-polymer sample; the classical-limit nbeads=1 case).
  * QuantumKineticEnergy (centroid-virial estimator).
  * HeatCapacity[method=pimd] (scaled-coordinates / double-virial estimator).
  * run_md as the PIMD Trajectory producer variant.
  * The two sampling edges (sample_quantum_kinetic_energy,
    sample_quantum_heat_capacity).

Deferred to later slices (reasons carried in the rail notes below): PLUMED +
1-CV PMF (metadynamics / free-energy surface, slice 2), isotope fractionation,
the quantum momentum distributions (the spectrum layer), and the multi-CV free
energy surface (the field-evidence kernel).

Credits (verified 2026-07-11, scans/cookbook-audit.json review table):
  * License: dual GPL-2.0 / MIT (user's choice; repo licenses/LICENSE.md).
  * Citation: Y. Litman, V. Kapil, Y. M. Y. Feldman, et al., i-PI 3.0: a
    flexible and efficient framework for advanced atomistic simulations,
    J. Chem. Phys. 161, 062504 (2024); doi 10.1063/5.0215869.
  * URL: https://ipi-code.org.
Registered in omai/representation/credits.py (CODE_CREDITS), which the
enforcement test (tests/test_code_credits.py) requires for every rail.
"""

from __future__ import annotations

from omai.representation.adapter import OperatorRepresentationSpec, SpaceRepresentationSpec
from omai.thermal_transport.operator.edges import (
    run_md,
    sample_quantum_heat_capacity,
    sample_quantum_kinetic_energy,
)
from omai.thermal_transport.operator.nodes import (
    HEAT_CAPACITY_PIMD,
    QUANTUM_KINETIC_ENERGY,
    TEMPERATURE_STATE,
    TRAJECTORY,
)


IPI_TEMPERATURE = SpaceRepresentationSpec(
    space=TEMPERATURE_STATE,
    representation_name="i-pi",
    observable_units={"temperature": "kelvin"},
    code_api={
        "temperature": "<initialize><cell>/<system> ... ensemble temperature; "
        "output property 'temperature{kelvin}'"
    },
    notes=(
        "i-PI-native Temperature: the ensemble temperature is set in the input "
        "XML (<ensemble><temperature units='kelvin'>) and read back as the "
        "'temperature' output property. For a ring-polymer run it is the "
        "physical temperature T that sets the imaginary-time path length "
        "beta*hbar; the internal ring-polymer spring temperature is nbeads*T and "
        "is not this state point. Kelvin is the standard serving unit; i-PI also "
        "accepts atomic units internally."
    ),
)


IPI_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="i-pi",
    code_api={
        "r": "output <trajectory filename='pos' stride=... > positions{angstrom} (per bead, or the centroid x_centroid)",
        "v": "output <trajectory filename='vel' > velocities{...} (per bead)",
    },
    notes=(
        "i-PI-native Trajectory as the PATH-INTEGRAL producer variant of the "
        "classical run_md Trajectory: the SAME Trajectory node, sampled with "
        "ring-polymer BEADS (P imaginary-time replicas of every atom) rather than "
        "a single classical replica. The number of beads is set by <initialize "
        "nbeads=...> / <beads nbeads=...>; the classical limit is exactly "
        "nbeads=1, at which the PIMD trajectory reduces to the run_md classical "
        "one (i-PI is then a plain MD driver). i-PI is the SERVER: it integrates "
        "the (ring-polymer) equations of motion and requests energies and forces "
        "from a FORCE PROVIDER over a socket. LAMMPS (fix ipi), CP2K, ASE, and "
        "metatomic models are the drivers in the Atomistic Cookbook recipes; the "
        "Potential identity therefore rides on the driver's rail, not on i-PI. "
        "Per-bead positions and velocities are dumped via <trajectory> output "
        "elements; the centroid (the physically meaningful configuration) is "
        "available as the 'x_centroid' trajectory. GLE / PIGLET colored-noise "
        "thermostats (the i-PI signature) accelerate the convergence of the "
        "quantum estimators. Cross-code comparability, as for every Trajectory, "
        "lives in the time-averaged / ensemble-averaged contractions (here the "
        "quantum estimators), never the per-bead snapshot."
    ),
)


IPI_QUANTUM_KINETIC_ENERGY = SpaceRepresentationSpec(
    space=QUANTUM_KINETIC_ENERGY,
    representation_name="i-pi",
    observable_units={"E_K": "ev"},
    code_api={
        "E_K": "output property 'kinetic_cv{electronvolt}' (centroid-virial); "
        "per-atom / tensor via 'kinetic_od', 'kinetic_tens_cv'"
    },
    notes=(
        "i-PI-native nuclear quantum kinetic energy via the centroid-virial "
        "estimator, the 'kinetic_cv' output property: <E_K> = (3/2) N k_B T + "
        "(1/2N) <sum_i (q_i - q_c) . dV/dq_i>, with q_c the ring-polymer bead "
        "centroid. The centroid-virial estimator is preferred over the "
        "thermodynamic estimator because its variance does NOT grow with the "
        "bead count (a load-bearing practical point for converged PIMD). Served "
        "in eV here (i-PI's native output unit is atomic / Hartree; the "
        "'{electronvolt}' output modifier requests eV). The kinetic-energy TENSOR "
        "variant ('kinetic_tens_cv', a 3x3 per-species object) probes the "
        "anisotropy of the quantum effect on bonds; served as the scalar trace "
        "here. Exceeds the classical 3/2 N k_B T equipartition value by the "
        "quantum zero-point contribution, and reduces to it as nbeads -> 1. "
        "Cookbook recipes: path-integrals, heat-capacity."
    ),
)


IPI_HEAT_CAPACITY_PIMD = SpaceRepresentationSpec(
    space=HEAT_CAPACITY_PIMD,
    representation_name="i-pi",
    observable_units={"C_V": "eV_per_K"},
    code_api={
        "C_V": "output property 'scaledcoords' (eps_v, eps_v') post-processed "
        "into C_V, or the i-pi-getacf / heat-capacity example script"
    },
    notes=(
        "i-PI-native constant-volume heat capacity C_V via the PIMD "
        "scaled-coordinates (double-virial) estimator: C_V = k_B beta^2 "
        "(<eps_v^2> - <eps_v>^2 - <eps_v'>), where eps_v and eps_v' are the "
        "virial energy estimator and its temperature derivative accumulated over "
        "the ring-polymer beads (i-PI 'scaledcoords' output; the Atomistic "
        "Cookbook heat-capacity recipe post-processes them into C_V). The "
        "method-tagged HeatCapacity[method=pimd] variant: SAME heat_capacity tag "
        "and ENERGY_PER_TEMPERATURE dimension as the harmonic HeatCapacity, the "
        "quantum FLUCTUATION estimator valid for liquids and strongly anharmonic "
        "systems (the harmonic crystalline mode-sum route is not). Captures the "
        "quantum suppression the harmonic route misses (liquid water ~15 "
        "k_B/molecule). Served as a scalar C_V in eV/K (i-PI native is atomic "
        "units; convertible to k_B/molecule or J/(K mol) for reporting)."
    ),
)


IPI_RUN_MD = OperatorRepresentationSpec(
    operator=run_md,
    representation_name="i-pi",
    scheme_overrides={"integrator": "velocity_verlet"},
    notes=(
        "i-PI drives the (ring-polymer) MD from its input XML: <motion "
        "mode='dynamics'><dynamics mode='nvt|nve|npt'> plus <ensemble> and "
        "<thermostat> (the GLE / PIGLET colored-noise family is i-PI's "
        "signature, alongside Langevin / SVR). The PIMD case is selected by "
        "nbeads>1; nbeads=1 is a classical MD run identical to run_md's "
        "Velocity-Verlet integration. Forces come from the socket-connected "
        "driver (LAMMPS / CP2K / ASE / metatomic), so the Potential identity is "
        "the driver's, not i-PI's. This is the producer of the Trajectory the "
        "two quantum estimators are read from."
    ),
)


IPI_SAMPLE_QUANTUM_KINETIC_ENERGY = OperatorRepresentationSpec(
    operator=sample_quantum_kinetic_energy,
    representation_name="i-pi",
    notes=(
        "i-PI accumulates the centroid-virial kinetic energy on the fly as the "
        "'kinetic_cv' output property during the PIMD run; no post-processing "
        "step is required beyond time-averaging the property column. The "
        "estimator (scheme estimator=centroid_virial) is the bead-count-stable "
        "choice. path-integrals and heat-capacity cookbook recipes."
    ),
)


IPI_SAMPLE_QUANTUM_HEAT_CAPACITY = OperatorRepresentationSpec(
    operator=sample_quantum_heat_capacity,
    representation_name="i-pi",
    notes=(
        "i-PI outputs the scaled-coordinates estimator components ('scaledcoords': "
        "eps_v and eps_v') on the fly; the heat-capacity cookbook recipe combines "
        "them into C_V = k_B beta^2 (<eps_v^2> - <eps_v>^2 - <eps_v'>) in "
        "post-processing (scheme estimator=double_virial). Requires a converged "
        "PIMD run (enough beads and GLE/PIGLET-accelerated sampling) for the "
        "fluctuation variance to converge."
    ),
)
