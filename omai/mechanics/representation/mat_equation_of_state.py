r"""mat-equation-of-state skill (matcalc EOS) adapter specs for the mechanics
domain.

The AtomisticSkills mat-equation-of-state skill, driving matcalc 0.5.1's
EOSCalc over an MLIP through the ASE calculator protocol, is the
Birch-Murnaghan E(V) producer of the BulkModulus node along the Pattern C
alternative route compute_bulk_modulus_eos. This is the "mat-equation-of-state"
skill rail, NOT a separate "matcalc" rail: per the atomate2 ruling, matcalc is
a driver layer that mints no unit basis of its own, so it lives in these specs'
notes, not as a rail. Anchored in
`scans/matcalc-ase-atomistic-skills.json` (deep review 2026-07-09, the entry
matcalc-eos-bulk-modulus, package-source-verified against the pip-downloaded
matcalc-0.5.1 sdist and re-anchored to the real skill script). AtomisticSkills
(arXiv 2605.24002) drives it via `mat-equation-of-state`
(`calculate_eos.py:50` import, `:62-67` construct, `:77` reads
`bulk_modulus_bm` in GPa directly).

  operator Space  matcalc / ASE artifact                             units
  --------------  -------------------------------------------------  -----
  BulkModulus     EOSCalc bulk_modulus_bm (pymatgen BM b0_GPa)        GPa
                  from a Birch-Murnaghan fit over an n_points volume
                  scan (default 11)

This is a SECOND estimator of the SAME BulkModulus node, distinct from the
mat-elasticity ElasticityCalc bulk_modulus_vrh (elastic-tensor VRH route):
the EOS-curvature K vs the elastic-average K, same node tag, two physics
routes (the two-bulk-moduli trap). matcalc is a DRIVER LAYER (the atomate2
ruling: it mints no unit basis of its own), so it earns no separate rail; the
volume-scan grid is the operator discretization on the edge, and the
MLIP-checkpoint double-provenance lives on the mace / matgl / fairchem
Potential specs.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.mechanics.operator.edges import compute_bulk_modulus_eos
from omai.mechanics.operator.nodes import BULK_MODULUS


MATCALC_EOS_BULK_MODULUS = SpaceRepresentationSpec(
    space=BULK_MODULUS,
    representation_name="mat-equation-of-state",
    observable_units={"K": "GPa"},
    code_api={
        "K": "matcalc EOSCalc(calc).calc(struct)['bulk_modulus_bm'] (pymatgen BirchMurnaghan b0_GPa), GPa (_eos.py:164)",
    },
    notes=(
        "The bulk modulus from the Birch-Murnaghan equation of state: matcalc "
        "EOSCalc runs its own symmetric volumetric strain scan (n_points=11 "
        "over +/-max_abs_strain, apply_strain per point, fixed-VOLUME "
        "relaxation at each point via RelaxCalc with constant_volume=True), "
        "collects (V, E), then hands them to pymatgen BirchMurnaghan; the bulk "
        "modulus is bm.b0_GPa (_eos.py:164), already in GPa (the skill reads "
        "it directly, no conversion). This is a GENUINELY DIFFERENT ESTIMATOR "
        "of the SAME BulkModulus than the mat-elasticity ElasticityCalc "
        "bulk_modulus_vrh (elastic-tensor VRH route): EOS curvature vs elastic "
        "average, one node tag, two physics routes (the two-bulk-moduli trap). "
        "matcalc adds NO unit basis of its own (the atomate2 ruling); the "
        "b0_GPa lands on pymatgen's CODATA-2018 side of the in-repo constant "
        "split. Committed Si example (mat-equation-of-state/examples/Si/"
        "eos_results.json): 96.42681590768773 GPa, n_points=7, "
        "max_abs_strain=0.08, MACE-OMAT-0-small. MLIP-CHECKPOINT "
        "DOUBLE-PROVENANCE lives on the mace / matgl / fairchem Potential specs."
    ),
)


MATCALC_COMPUTE_BULK_MODULUS_EOS = OperatorRepresentationSpec(
    operator=compute_bulk_modulus_eos,
    representation_name="mat-equation-of-state",
    scheme_overrides={"n_points": "11"},
    discretization_choices={
        "volume_scan_grid": (
            "EOSCalc max_abs_strain (default 0.1) and n_points (default 11); "
            "the symmetric volume grid the E(V) fit runs over is the "
            "estimator's discretization (the committed Si example used "
            "n_points=7, max_abs_strain=0.08)"
        ),
        "eos_model": (
            "the equation-of-state model handed the (V, E) points; matcalc "
            "hands them to pymatgen BirchMurnaghan (the method=birch_murnaghan "
            "scheme)"
        ),
        "relaxation": (
            "fixed-VOLUME relaxation at each scanned volume "
            "(constant_volume=True, allow_shape_change relaxes the cell shape "
            "at fixed volume), optimizer FIRE, fmax 0.1"
        ),
    },
    notes=(
        "Realized by matcalc EOSCalc (a driver over the MLIP PES, no separate "
        "rail): the method=birch_murnaghan scheme is the EOS model, and the "
        "volume-scan grid (n_points, max_abs_strain) is the matcalc-owned "
        "discretization on this edge. Pattern C alternative producer of "
        "BulkModulus, parallel to contract_bulk_modulus (the elastic-tensor "
        "VRH route). Provenance must record BOTH the matcalc driver + scheme "
        "AND the MLIP checkpoint (double-provenance). Anchored: "
        "mat-equation-of-state calculate_eos.py:50,62-67,77."
    ),
)
