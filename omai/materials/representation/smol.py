r"""smol adapter specs for the materials domain.

smol 0.5.7 (statistical mechanics on lattices: cluster expansion + lattice
Monte Carlo) as used by the AtomisticSkills ml-cluster-expansion / mat-disorder
/ mat-grand-canonical-mc skills, anchored in
`scans/config-thermo-atomistic-skills.json` (deep review 2026-07-09; all 17
entries confirmed; read from the pip-downloaded sdist smol-0.5.7.tar.gz). smol
is NOT importable in the miniconda base env; the smol-agent conda env pins
`smol` with no version, so anchors are sdist-source references, not a live
import.

  operator Space          smol artifact                                        units
  ----------------------  ---------------------------------------------------  ------
  ConfigurationalEnergy   ClusterExpansion.predict /                           eV
                          ExpansionProcessor.compute_property (expansion.py:288)
  Potential               ClusterExpansion (cofe/expansion.py:159; the ECI     (model)
                          checkpoint, a Potential-representation analog)

The cluster-expansion checkpoint IS a Potential-representation analog. A
ClusterExpansion is a ClusterSubspace (the orbit/cluster basis) plus a
coefficient vector coefs (cofe/expansion.py:159); the ECI are
coefs / function_total_multiplicities (:172-183). Predicting an energy is
np.dot(self.coefs, corrs) (:288), exactly how an MLIP evaluates a checkpoint on
a structure. It is serialized to cluster_expansion.json (ClusterExpansion.load /
.save) and re-loaded to drive Monte Carlo, the way an MLIP checkpoint drives MD.
It is fitted to DFT / MLIP-labelled ordered structures via LassoCV /
Sparse-Group-Lasso (fitting is EXTERNAL: sklearn / sparselm, smol carries no
solver), targeting LOOCV < 10 meV/atom. So the smol rail maps the CE onto the
map's existing opaque Potential node, an MLIP-checkpoint sibling, and its
PROVENANCE is the checkpoint schema {ce_file, cutoffs, fit_method (ls / lasso /
ridge / sgl), LOOCV eV/prim, training-energy convention (total vs formation)}.

The energy basis triple (a unit trap the ConfigurationalEnergy node records in
its conditions, not its dimension): extensive per supercell (default
processor.compute_property / predict), per primitive cell (predict
normalized=True, CV-RMSE reported in eV/prim), per atom (eV/atom, what the
grand-canonical-MC skill divides to report). The CE energies are on a FIXED
lattice, FIXED cell (relax_cell=False), reference-shifted by the training set.

Deferred (representation-only, not minted here): the semigrand chemical potential
(per-atom eV, the sibling of the now-live per-mole J/mol ChemicalPotential node
via the Faraday factor 96485.33212331; the representation layer would own the
eV/atom x per-mole normalization if a chempot spec were added), the dimensionless
equilibrium MC composition x (companion of the thermochemistry PhaseFraction),
and the T-x / T-mu phase diagrams (matplotlib plot products, like the CALPHAD
binplot).
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.materials.operator.nodes import CONFIGURATIONAL_ENERGY
from omai.thermal_transport.operator.nodes import POTENTIAL

SMOL_CONFIGURATIONAL_ENERGY = SpaceRepresentationSpec(
    space=CONFIGURATIONAL_ENERGY,
    representation_name="smol",
    observable_units={"E_cfg": "ev"},
    code_api={"E_cfg": "ClusterExpansion.predict / ExpansionProcessor.compute_property (cofe/expansion.py:259-288)"},
    notes=(
        "Configurational energy predicted by a cluster expansion: "
        "predict = np.dot(self.coefs, corrs) (cofe/expansion.py:288), eV. "
        "Three bases coexist (a trap recorded on the instance, not the "
        "dimension): extensive per supercell (default "
        "processor.compute_property, the feature vector is 'correlation vector "
        "x system size', moca/processor/expansion.py:162-180), per primitive "
        "cell (predict normalized=True, expansion.py:259-267; CV-RMSE in "
        "eV/prim, iterative_ce_training.py:393), per atom (eV/atom, the "
        "grand-canonical-MC skill divides by site count, run_gcmc_sweep.py:153). "
        "Fixed lattice, fixed cell (relax_cell=False), reference-shifted by the "
        "training set (a total or a formation energy). Distinct from a "
        "relaxed-structure DFT/MLIP TotalEnergy and a per-atom FormationEnergy."
    ),
)

SMOL_CLUSTER_EXPANSION_POTENTIAL = SpaceRepresentationSpec(
    space=POTENTIAL,
    representation_name="smol",
    code_api={"V": "ClusterExpansion (cofe/expansion.py:159 coefs; :172-183 ECI); load/save cluster_expansion.json"},
    notes=(
        "The trained cluster expansion as a Potential-representation analog: a "
        "ClusterSubspace (orbit/cluster basis) plus a coefficient vector coefs "
        "(cofe/expansion.py:159), the ECI = coefs / function_total_"
        "multiplicities (:172-183). It is the configurational-energetics analog "
        "of an MLIP checkpoint (map's opaque Potential node): fitted to DFT / "
        "MLIP-labelled ordered structures via EXTERNAL solvers (sklearn LassoCV, "
        "sparselm Sparse-Group-Lasso; smol carries no solver), serialized to "
        "cluster_expansion.json and re-loaded to drive Monte Carlo, targeting "
        "LOOCV < 10 meV/atom. Opaque node (no unit): a model. Its PROVENANCE is "
        "the checkpoint schema {ce_file, cutoffs, fit_method (ls / lasso / ridge "
        "/ sgl), LOOCV eV/prim, training-energy convention (total vs "
        "formation)}, the CE analog of the MLIP checkpoint and the CALPHAD "
        "assessed database."
    ),
)
