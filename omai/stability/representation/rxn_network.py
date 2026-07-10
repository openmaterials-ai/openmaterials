r"""rxn_network (reaction-network) adapter specs for the stability domain.

reaction-network 8.3.0 as used by the AtomisticSkills mat-reaction-network
skill, anchored in `scans/config-thermo-atomistic-skills.json` (deep review
2026-07-09; all 17 entries confirmed; read from the pip-downloaded wheel
reaction_network-8.3.0-py3-none-any.whl). The package is NOT importable in the
miniconda base env; the base-agent conda env pins `reaction-network` with no
version, so anchors are wheel-source references, not a live import.

  operator Space   rxn_network artifact                                  units
  ---------------  ---------------------------------------------------  ------
  ReactionEnergy   ComputedReaction.energy / .energy_per_atom            eV (total)
                   (reactions/computed.py:104-145)                       or eV/atom

Convention traps this module pins (all review-verified):

  * ReactionEnergy has a DUAL normalization: ComputedReaction.energy is TOTAL
    eV for the as-balanced reaction (coefficient-dependent, reactions/base.py:
    37-38 "The energy of this reaction in total eV"); energy_per_atom =
    energy / num_atoms eV/atom (computed.py:117-122), num_atoms summing the
    product-side atoms x coefficients (per reaction-atom). The skills print
    eV/atom (enumerate_reactions.py:163-164; find_pathways.py:241).
  * The reactions are built from GibbsComputedEntry formation energies: the
    Bartel-SISSO descriptor dGf(T) - dHf(298 K) (entries/gibbs.py:27-118),
    valid 300-2000 K, MAD ~50 meV/atom (uncertainty = 0.05 * num_atoms,
    gibbs.py:97), MP-derived. This dGf(T) is a finite-temperature COUSIN of
    the map's FormationEnergy, NEVER naively equated to the 0 K / 298 K DFT
    FormationEnergy: same dimension and per-atom basis, different physics
    (finite-T SISSO Gibbs vs 0 K DFT). Solids only (gases via
    NISTReferenceEntry).
  * The pathway cost is DIMENSIONLESS, not a mapped observable: Softplus =
    log(1 + (273/T) exp(sum(param*weight))) (costs/functions.py:15-77) squashes
    the eV/atom driving force through a log into a unitless graph-algorithm
    score; the reaction network, the k shortest paths, and the balancing
    multiplicities are likewise combinatorial artifacts, not observables.
"""

from __future__ import annotations

from omai.representation.adapter import SpaceRepresentationSpec
from omai.stability.operator.nodes import REACTION_ENERGY

RXN_NETWORK_REACTION_ENERGY = SpaceRepresentationSpec(
    space=REACTION_ENERGY,
    representation_name="rxn-network",
    observable_units={"dE_rxn": "ev"},
    code_api={"dE_rxn": "ComputedReaction.energy (total eV) / .energy_per_atom (eV/atom) (reactions/computed.py:104-145)"},
    notes=(
        "Reaction energy of a balanced solid-state reaction. Dual "
        "normalization: total eV (as-balanced, coefficient-dependent, "
        "reactions/base.py:37-38) and eV/atom (energy / num_atoms, "
        "computed.py:117-122, per reaction-atom); the skills print eV/atom. "
        "Combined by ComputedReaction from a reduced-composition entry set "
        "weighted by the balancing coefficients. The reactions are built from "
        "GibbsComputedEntry finite-T SISSO Gibbs formation energies dGf(T) "
        "(entries/gibbs.py:27-118, 300-2000 K, ~50 meV/atom MAD, MP-derived): a "
        "COUSIN of FormationEnergy, never naively equated to the 0 K / 298 K "
        "DFT FormationEnergy the producing edge consumes. The MP provenance "
        "(thermo_type / functional), the SISSO temperature, and the "
        "0.05*num_atoms descriptor uncertainty are instance conditions. The "
        "Softplus pathway cost is dimensionless (a graph-algorithm score), not "
        "a mapped observable."
    ),
)
