r"""mat-surface-adsorption skill (matcalc AdsorptionCalc) adapter specs for the
stability domain.

The AtomisticSkills mat-surface-adsorption skill, driving matcalc 0.5.1's
AdsorptionCalc over an MLIP through the ASE calculator protocol, is the
producer of the AdsorptionEnergy node. This is the "mat-surface-adsorption"
skill rail, NOT a separate "matcalc" rail: per the atomate2 ruling, matcalc is
a driver layer that mints no unit basis of its own, so it lives in these specs'
notes, not as a rail. Anchored in
`scans/matcalc-ase-atomistic-skills.json` (deep review 2026-07-09, the entry
matcalc-adsorption-energy, package-source-verified against the pip-downloaded
matcalc-0.5.1 sdist and re-anchored to the real skill script). AtomisticSkills
(arXiv 2605.24002) drives it via `mat-surface-adsorption`
(`calculate_adsorption.py:58` import, `:83-90` construct, `:101-113`
calc_adslabs).

  operator Space    matcalc / ASE artifact                          units
  ----------------  ----------------------------------------------  -----
  AdsorptionEnergy  AdsorptionCalc.calc_adslabs per-site            eV
                    adsorption_energy = E_adslab - E_slab - E_ads

matcalc is a DRIVER LAYER (the atomate2 ruling applies: it mints no unit
basis, only eVA3ToGPa, a scipy conversion), so it earns no separate rail; the
adsorption energy rides the ASE-calculator eV boundary. The matcalc scheme
(slab / adslab / adsorbate relaxation, site enumeration, FIRE optimizer,
fmax) is the operator discretization, recorded on the OperatorRepresentationSpec
below; the MLIP-checkpoint double-provenance (which model produced the three
energies) lives on the mace / matgl / fairchem Potential specs.
"""

from __future__ import annotations

from omai.representation.adapter import (
    OperatorRepresentationSpec,
    SpaceRepresentationSpec,
)
from omai.stability.operator.edges import compute_adsorption_energy
from omai.stability.operator.nodes import ADSORPTION_ENERGY


MATCALC_ADSORPTION_ENERGY = SpaceRepresentationSpec(
    space=ADSORPTION_ENERGY,
    representation_name="mat-surface-adsorption",
    observable_units={"E_ads": "ev"},
    code_api={
        "E_ads": "matcalc AdsorptionCalc(calc).calc_adslabs(...) per-site adsorption_energy (E_adslab - E_slab - E_adsorbate), eV (_adsorption.py:28-)",
    },
    notes=(
        "Adsorption energy in eV per adsorbate-surface configuration: matcalc "
        "AdsorptionCalc relaxes the clean slab (fixed cell), the isolated "
        "adsorbate (in a box), and each adslab configuration with the SAME ASE "
        "calculator (each via an internal RelaxCalc), then forms the "
        "difference per adsorption site (_adsorption.py:14 imports RelaxCalc). "
        "EXTENSIVE (an energy difference over whole cells), plain eV, NOT the "
        "per-atom currency of FormationEnergy / EnergyAboveHull. The three "
        "energies ride the ASE-calculator boundary (eV per cell), so matcalc "
        "adds NO unit basis of its own here (matcalc.units mints only "
        "eVA3ToGPa, a scipy conversion; the atomate2 ruling applies). The "
        "adsorbate, facet (hkl), and site (ontop / bridge / hollow) ride in "
        "conditions. Committed CO-on-Cu(111) example (mat-surface-adsorption/"
        "examples/CO_on_Cu111/adsorption_results.json): ontop -1.12 eV "
        "(most stable), bridge -0.89, hollow -0.67, MACE checkpoint via "
        "AdsorptionCalc. MLIP-CHECKPOINT DOUBLE-PROVENANCE: which model "
        "produced the three energies is recorded on the mace / matgl / "
        "fairchem Potential specs, matcalc being only the driver."
    ),
)


MATCALC_COMPUTE_ADSORPTION_ENERGY = OperatorRepresentationSpec(
    operator=compute_adsorption_energy,
    representation_name="mat-surface-adsorption",
    discretization_choices={
        "slab_geometry": (
            "AdsorptionCalc min_slab_size / min_vacuum_size and the (hkl) "
            "choice (the committed example: min_slab_size=10.0, "
            "min_vacuum_size=20.0 A); the slab-thickness convergence is the "
            "estimator's discretization"
        ),
        "adsorption_sites": (
            "the site enumeration (ontop / bridge / hollow and height); "
            "distinct sites are distinct configurations, each its own "
            "AdsorptionEnergy instance"
        ),
        "relaxation": (
            "which pieces are relaxed (relax_bulk / relax_slab / "
            "relax_adsorbate, all True in the committed example) and the "
            "optimizer (FIRE default) / fmax (0.05 in the committed example, "
            "matcalc default 0.1); a matcalc-owned discretization"
        ),
    },
    notes=(
        "Realized by matcalc AdsorptionCalc (a driver over the MLIP PES, no "
        "separate rail): the reference_convention scheme "
        "(adslab_minus_slab_minus_adsorbate) is what AdsorptionCalc computes; "
        "the slab / adslab / adsorbate relaxations, site enumeration, "
        "optimizer, and fmax are matcalc-owned discretization choices on this "
        "edge. Provenance must record BOTH the matcalc driver + scheme AND the "
        "MLIP checkpoint (double-provenance): matcalc is the true producer "
        "only via the MLIP PES, exactly as the matcalc/ASE scan notes for the "
        "elastic / EOS / phonon operators. Anchored: mat-surface-adsorption "
        "calculate_adsorption.py:58,83-90,101-113."
    ),
)
