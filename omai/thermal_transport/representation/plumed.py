"""PLUMED adapter specs: the enhanced-sampling free-energy layer (Cookbook Slice 2).

PLUMED (https://www.plumed.org) is the enhanced-sampling and free-energy plugin
for molecular dynamics: metadynamics, adaptive biasing, a large collective-
variable library (distances, angles, coordination numbers, SOAP-based order
parameters), and the sum_hills reconstruction of a free-energy profile from the
deposited Gaussian bias. It is a bias / analysis LAYER that rides MD engines: it
patches into LAMMPS, GROMACS, and i-PI and computes collective variables and
biases as they run. Honestly it is closer to a driver than to a standalone
engine (it produces no atoms, no forces of its own). It earns a rail, unlike a
pure driver such as matcalc, because it PRODUCES a quantity no engine produces
alone: the bias and, from it, the potential of mean force (the free-energy
profile along a collective variable).

This adapter, from the Atomistic Cookbook audit (scans/cookbook-audit.json, the
PLUMED slice), makes PLUMED the producer of the map's first enhanced-sampling
node:

  * PotentialOfMeanForce (new node, ENERGY): the one-collective-variable free
    energy F(s) = -k_B T ln P(s), reconstructed by sum_hills (metadynamics) or
    WHAM (umbrella sampling). A scalar-valued FUNCTION of one collective
    variable, so it carries a CanonicalAxis: the collective variable is the
    axis. Because collective variables have HETEROGENEOUS units (a distance in
    angstrom, an angle in radians, a coordination number dimensionless), the
    canonical AXIS unit is left OPEN (unit=None) - the first open-axis
    declaration in the spectrum layer, the axis analog of the PhononDOS open
    value_unit. The concrete CV unit rides in each record's axis and conditions.

Scope of this slice:
  * Trajectory (PLUMED rides an MD engine's Trajectory, biasing it along a CV;
    it patches the engine rather than integrating its own equations of motion).
  * PotentialOfMeanForce (sum_hills / reweighting output, kJ/mol native).
  * The sampling edge sample_pmf.

Deferred to later slices (reasons carried in the rail notes below): the multi-CV
free-energy surface (a scalar field over CV-space, the field-evidence kernel);
the collective-variable ZOO as nodes (collective variables are COORDINATES, not
observables, so they are axis descriptors, not evidence nodes); and PLUMED's
committor and rate analyses.

Credits (verified 2026-07-11, scans/cookbook-audit.json review table):
  * License: LGPL-3.0 (repo COPYING.LESSER, GNU LGPL v3).
  * Citation: G. A. Tribello, M. Bonomi, D. Branduardi, C. Camilloni, G. Bussi,
    PLUMED 2: New feathers for an old bird, Comput. Phys. Commun. 185, 604
    (2014); doi 10.1016/j.cpc.2013.09.018.
  * URL: https://www.plumed.org.
For a metadynamics encode PLUMED also asks (via its plumed-nest / CITATIONS
mechanism) that the specific enhanced-sampling method paper be cited alongside
PLUMED 2; that method DOI is left unknown-until-encode, not invented.
Registered in omai/representation/credits.py (CODE_CREDITS), which the
enforcement test (tests/test_code_credits.py) requires for every rail.
"""

from __future__ import annotations

from omai.representation.adapter import (
    CanonicalAxis,
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.thermal_transport.operator.edges import sample_pmf
from omai.thermal_transport.operator.nodes import (
    POTENTIAL_OF_MEAN_FORCE,
    TRAJECTORY,
)


PLUMED_TRAJECTORY = SpaceRepresentationSpec(
    space=TRAJECTORY,
    representation_name="plumed",
    code_api={
        "r": "the host MD engine's trajectory (LAMMPS / GROMACS / i-PI), read by "
        "PLUMED through its patched interface; PLUMED biases the dynamics along "
        "the chosen collective variables rather than dumping its own positions",
    },
    notes=(
        "PLUMED does not integrate its own equations of motion: it PATCHES an MD "
        "engine (LAMMPS `fix plumed`, GROMACS `-plumed`, i-PI's ffplumed "
        "forcefield) and rides the engine's Trajectory, adding a bias force along "
        "the collective variables defined in the PLUMED input. So the Trajectory "
        "here is the host engine's (the Potential / force identity is the "
        "engine's rail, not PLUMED's); PLUMED's contribution is the bias it "
        "deposits and the free energy it reconstructs from it. Closer to a driver "
        "than an engine, but unlike a pure driver it produces a quantity no engine "
        "produces alone (the bias / PMF), which is why it earns a rail. Cookbook "
        "recipes: pi-metad (i-PI + PLUMED), metatomic-plumed."
    ),
)


PLUMED_POTENTIAL_OF_MEAN_FORCE = SpaceRepresentationSpec(
    space=POTENTIAL_OF_MEAN_FORCE,
    representation_name="plumed",
    observable_units={"F": "kJ_per_mol"},
    # Spectrum-layer canonical axis, the FIRST OPEN-AXIS declaration: the PMF is
    # stored as F(s) against a collective-variable axis whose unit is OPEN
    # (unit=None). Collective variables are heterogeneous (a distance in
    # angstrom, an angle in radians, a coordination number dimensionless), so no
    # single axis unit / dimension can be pinned the way PhononDOS pins linear
    # THz: the concrete CV unit rides in each record's axis units and conditions.
    # This is the axis analog of the PhononDOS open value_unit (there the DOS
    # DENSITY normalization was open; here the AXIS unit is open). The value unit
    # (the free-energy ordinate) is likewise left open (value_unit=None): the
    # per-system-vs-per-mole and k_B T-vs-kJ/mol convention rides in conditions.
    canonical_axis=CanonicalAxis(name="cv", unit=None, value_unit=None),
    code_api={
        "F": "PLUMED sum_hills reconstructs F(s) from a metadynamics HILLS file "
        "(kJ/mol against the collective variable); or a reweighted / WHAM "
        "free-energy profile from umbrella sampling",
    },
    notes=(
        "PLUMED-native potential of mean force: the one-collective-variable free "
        "energy F(s) = -k_B T ln P(s). From metadynamics it is `plumed sum_hills` "
        "over the deposited Gaussian HILLS; from umbrella sampling it is a WHAM "
        "reconstruction over the biased windows. Native energy unit kJ/mol "
        "(PLUMED's default; the map's canonical ENERGY form is eV, a 96.485 kJ/mol "
        "per eV conversion away, applied through the kJ_per_mol unit's "
        "to_operator factor). The metadynamics literature often reports F(s) in "
        "k_B T units per system rather than per mole; that convention rides in the "
        "record's conditions, not in the node. The AXIS is the collective "
        "variable, whose unit is heterogeneous and therefore OPEN in the canonical "
        "declaration (the first open-axis spectrum node): a distance CV serves an "
        "angstrom axis, a coordination-number CV a dimensionless axis, and so on. "
        "Only the ONE-CV PMF is encodable under the current spectrum contract; the "
        "multi-CV free-energy surface (a scalar field over CV-space) is deferred "
        "to the field-evidence kernel. Cookbook recipes: pi-metad, "
        "metatomic-plumed."
    ),
)


PLUMED_SAMPLE_PMF = OperatorRepresentationSpec(
    operator=sample_pmf,
    representation_name="plumed",
    notes=(
        "PLUMED drives the enhanced sampling from its input script: METAD deposits "
        "Gaussian hills along the collective variables at a chosen pace and "
        "height (well-tempered or standard), and `plumed sum_hills` reconstructs "
        "F(s) once the run has converged (scheme method=metadynamics_or_umbrella, "
        "cv_count=1). The umbrella-sampling route (RESTRAINT windows + WHAM) is the "
        "same target by a different bias. The reconstruction is an opaque "
        "functional of the biased Trajectory and the Temperature, so the "
        "dimensional gate skips the sample_pmf edge; the PLUMED rail fixes the "
        "output at ENERGY (kJ/mol). Deferred: the collective-variable zoo as nodes "
        "(CVs are coordinates, not observables), the multi-CV free-energy surface "
        "(the field kernel), and PLUMED's committor / rate analyses."
    ),
)
