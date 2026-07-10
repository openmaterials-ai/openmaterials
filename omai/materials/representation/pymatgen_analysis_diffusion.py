r"""pymatgen-analysis-diffusion adapter specs for the materials domain.

pymatgen-analysis-diffusion 2025.11.15 as used by the AtomisticSkills
mat-diffusion-analysis / mat-md-probability-density skills, anchored in
`scans/config-thermo-atomistic-skills.json` (deep review 2026-07-09; all 17
entries confirmed; units read from the pip-downloaded wheel
pymatgen_analysis_diffusion-2025.11.15-py3-none-any.whl). The package is NOT
importable in the miniconda base env; the base-agent conda env pins
`pymatgen-analysis-diffusion` with no version, so anchors are wheel-source
references, not a live import.

  operator Space                         diffusion artifact                                 units
  -------------------------------------  -------------------------------------------------  ------
  Diffusivity                            DiffusionAnalyzer.diffusivity (analyzer.py:55)      cm^2/s
  MeanSquaredDisplacement                DiffusionAnalyzer.msd vs dt (analyzer.py:920+)      A^2
  ActivationEnergy                       fit_arrhenius (analyzer.py:877-897)                 eV
  ElectricalConductivity[carrier=ionic]  DiffusionAnalyzer.conductivity /                    mS/cm
                                         get_extrapolated_conductivity (analyzer.py:338,846)

Convention traps this module pins (all review-verified):

  * The Nernst-Einstein conductivity is served in mS/cm; 1 S/m = 10 mS/cm, so
    the ms_per_cm -> s_per_m registration factor is x0.1 (the canonical S/m
    carries to_operator 1.0). get_conversion_factor (analyzer.py:846-869):
    sigma[mS/cm] = convf * D[cm^2/s], convf = 1000 * n/(vol_cm3 * N_A) * z^2 *
    (N_A*e)^2 / (R*T); self.conductivity = self.diffusivity * conv_factor
    (analyzer.py:338).
  * sigma uses the TRACER diffusivity (Haven ratio 1); the collective charge
    diffusivity would give chg_conductivity instead (analyzer.py:340). z is the
    oxidation state, else the valence-electron count (analyzer.py:864).
  * Diffusivity is cm^2/s (1 cm^2/s = 1e16 A^2/s, NOT A^2/ps and NOT SI m^2/s);
    MSD is A^2 vs dt in fs. Constants: F = N_A*e = 96485.33212331 C/mol
    (SI-exact); R = 8.31446261815324 J/mol/K (= N_A * k_B, CODATA);
    k_B = 8.617333262145e-5 eV/K.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.nodes import (
    ACTIVATION_ENERGY,
    DIFFUSIVITY_STATE,
    ELECTRICAL_CONDUCTIVITY_IONIC,
)
from omai.thermal_transport.operator.nodes import MEAN_SQUARED_DISPLACEMENT

PYMATGEN_DIFFUSION_DIFFUSIVITY = SpaceRepresentationSpec(
    space=DIFFUSIVITY_STATE,
    representation_name="pymatgen-analysis-diffusion",
    observable_units={"D": "cm^2/s"},
    code_api={"D": "DiffusionAnalyzer.diffusivity / get_extrapolated_diffusivity (analyzer.py:55,226)"},
    notes=(
        "Self-diffusion coefficient D from the Einstein slope of the MSD, "
        "cm^2/s (analyzer.py:55; get_diffusivity_from_msd converts A^2/fs to "
        "cm^2/s by a factor of 10). The already-mapped Diffusivity node; the "
        "wheel-verified cm^2/s is unchanged from the mat-diffusion-analysis "
        "rail. 1 cm^2/s = 1e16 A^2/s."
    ),
)

PYMATGEN_DIFFUSION_MSD = SpaceRepresentationSpec(
    space=MEAN_SQUARED_DISPLACEMENT,
    representation_name="pymatgen-analysis-diffusion",
    observable_units={"M": "A^2"},
    code_api={"M": "DiffusionAnalyzer.msd vs .dt (analyzer.py:920+)"},
    notes=(
        "Mean squared displacement MSD(t), A^2 against dt in fs "
        "(get_diffusivity_from_msd 'msd units: A^2', 'dt units: fs'; the "
        "mean-square charge displacement mscd is the same A^2 at "
        "analyzer.py:96,118,276). The already-mapped MeanSquaredDisplacement "
        "node (the pymatgen representation carries it in A^2 vs fs). The Haven "
        "ratio (diffusivity/chg_diffusivity, dimensionless) and the charge "
        "diffusivity (cm^2/s, collective vs tracer) at analyzer.py:134,446 are "
        "unmapped low-priority candidates the two skill scripts do not print."
    ),
)

PYMATGEN_DIFFUSION_ACTIVATION = SpaceRepresentationSpec(
    space=ACTIVATION_ENERGY,
    representation_name="pymatgen-analysis-diffusion",
    observable_units={"E_a": "ev"},
    code_api={"E_a": "fit_arrhenius (analyzer.py:877-897)"},
    notes=(
        "Arrhenius activation energy E_a (eV) from D = c exp(-Ea/kT), "
        "k_B = 8.617333262e-5 eV/K (analyzer.py:877-897); the pre-exponential "
        "D0 (cm^2/s) is a fit companion, not its own node. The already-mapped "
        "ActivationEnergy node."
    ),
)

PYMATGEN_DIFFUSION_IONIC_CONDUCTIVITY = SpaceRepresentationSpec(
    space=ELECTRICAL_CONDUCTIVITY_IONIC,
    representation_name="pymatgen-analysis-diffusion",
    observable_units={"sigma": "ms_per_cm"},
    code_api={"sigma": "DiffusionAnalyzer.conductivity / get_extrapolated_conductivity (analyzer.py:338,846-869)"},
    notes=(
        "Ionic (electrical) conductivity from Nernst-Einstein, served in "
        "mS/cm: get_conversion_factor (analyzer.py:846-869) sigma[mS/cm] = "
        "convf * D[cm^2/s], convf = 1000 * n/(vol_cm3 * N_A) * z^2 * "
        "(N_A*e)^2/(R*T); self.conductivity = self.diffusivity * conv_factor "
        "(analyzer.py:338). 1 S/m = 10 mS/cm, so ms_per_cm carries to_operator "
        "0.1 to the canonical s_per_m. Uses the TRACER diffusivity (Haven "
        "ratio 1); z is the oxidation state, else the valence-electron count. "
        "The skill reports sigma_RT at 300 K in mS/cm "
        "(calculate_activation_energy.py:236,241). Companion of Diffusivity "
        "(differ only by conv_factor); the conductivity_components a/b/c are a "
        "tensor packing the node serves as a scalar."
    ),
)
