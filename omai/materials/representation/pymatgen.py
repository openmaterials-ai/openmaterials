r"""pymatgen adapter specs for the materials (diffusion) domain.

pymatgen 2025.6.14 plus the pymatgen-analysis-diffusion add-on (a separate
pip distribution imported under the pymatgen.analysis.* namespace; the scan
review verified its unit claims against the 2025.11.15 wheel), as
mat-diffusion-analysis drives them over MLIP MD trajectories. Anchored in
`scans/pymatgen-atomistic-skills.json`:

  operator Space           pymatgen artifact                        units
  -----------------------  ---------------------------------------  -------
  Diffusivity              DiffusionAnalyzer.diffusivity            cm^2/s
  ActivationEnergy         fit_arrhenius over D(T); in-skill fit    eV
  MeanSquaredDisplacement  DiffusionAnalyzer.msd (.dt time axis)    A^2 (fs)

Convention traps this module pins down (review-verified):

  * DiffusionAnalyzer.diffusivity is cm^2/s (analyzer.py:55, wheel-verified),
    NOT A^2/ps and NOT SI m^2/s; 1 cm^2/s = 1e16 A^2/s.
  * .msd is Angstrom^2 and .dt is in the time_step's unit (fs; the skill
    divides by 1000 for ps).
  * The MSD is multi-time-origin averaged, unlike LAMMPS compute msd
    (single origin): an estimator difference, not a unit difference.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.nodes import ACTIVATION_ENERGY, DIFFUSIVITY_STATE
from omai.materials.operator.shared_primitives import MEAN_SQUARED_DISPLACEMENT


PYMATGEN_DIFFUSIVITY = SpaceRepresentationSpec(
    space=DIFFUSIVITY_STATE,
    representation_name="pymatgen",
    observable_units={"D": "cm^2/s"},
    code_api={
        "D": "pymatgen.analysis.diffusion.analyzer.DiffusionAnalyzer.diffusivity, cm^2/s (add-on distribution)",
    },
    notes=(
        "Einstein-relation self-diffusivity from an MD trajectory "
        "(DiffusionAnalyzer.from_structures over AseAtomsAdaptor frames). "
        "UNIT TRAP (wheel-verified 2025.11.15, analyzer.py:55): cm^2/s, not "
        "A^2/ps, not m^2/s; 1 cm^2/s = 1e16 A^2/s. Lives in the separate "
        "pymatgen-analysis-diffusion distribution, not base pymatgen."
    ),
)


PYMATGEN_ACTIVATION_ENERGY = SpaceRepresentationSpec(
    space=ACTIVATION_ENERGY,
    representation_name="pymatgen",
    observable_units={"E_a": "ev"},
    code_api={
        "E_a": "pymatgen.analysis.diffusion.analyzer fit_arrhenius / get_arrhenius_plot over D(T), eV",
    },
    notes=(
        "Arrhenius activation energy from the temperature dependence of the "
        "diffusivity (slope of ln D vs 1/T times k_B = 8.617333262e-5 eV/K, "
        "CODATA-confirmed in the skill's own fit). Provenance is a SET of "
        "Diffusivity(T) values, the same family-of-values convention as the "
        "map's fit_arrhenius edge."
    ),
)


PYMATGEN_MEAN_SQUARED_DISPLACEMENT = SpaceRepresentationSpec(
    space=MEAN_SQUARED_DISPLACEMENT,
    representation_name="pymatgen",
    observable_units={"M": "A^2"},
    code_api={
        "M": "pymatgen DiffusionAnalyzer.msd (A^2) against .dt (fs; skill divides by 1000 for ps)",
    },
    notes=(
        "Mean squared displacement of the mobile species in Angstrom^2 "
        "(wheel-verified: analyzer.py:112,297,378), the Einstein-relation "
        "integrand. Multi-time-origin averaged, unlike LAMMPS compute msd's "
        "single origin: an estimator distinction the scan flags, not a unit "
        "conversion. The time axis .dt is in the input time_step's unit "
        "(fs in the skill)."
    ),
)
