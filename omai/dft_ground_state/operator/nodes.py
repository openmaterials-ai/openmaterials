"""Operator nodes of the DFT ground-state domain.

The first-principles ground state a DFT engine computes for a Structure under a
chosen Potential: the total energy, the per-atom forces, and the cell stress.
All three are ObservableSpaces (gauge-invariant, cross-code-comparable after
unit conversion); Structure enters here from the shared primitives (it keeps
its Sources tier as an input, joining Potential).

Node table:

  Node          quantity tag   dimension                  indices        notes
  ------------  -------------  -------------------------  -------------  -----
  Structure     structure      opaque                     ()             shared input
  TotalEnergy   total_energy   ENERGY                     ()             extensive, per cell
  Forces        force          FORCE (M L T^-2)           (i, alpha)     per-atom Cartesian
  Stress        stress         ENERGY_PER_LENGTH_CUBED    (alpha, beta)  cell-averaged Cauchy

Deferred v1 candidates (from the QE scan's seven new-node set), each with why:

  * ChargeDensity: an observable in principle (Hohenberg-Kohn), but needs a
    real-space grid index kind and a density dimension, and nothing downstream
    consumes it yet. Add when a workflow reads it.
  * Wavefunctions: a HiddenSpace with U(N) gauge freedom; the right showcase
    for gauge discipline in a later slice, not needed for energy/forces/stress.
  * dvscf (the self-consistent potential response): EPW territory, with the
    normalization left open in the scan; defer until the EPW chain lands.

Follow-up edges beyond the v1 leaves:

  * Forces -> ForceConstants[order=2] by finite displacements: built
    2026-07-08 as compute_fc2_finite_displacement, a Pattern C alternative
    producer of FC2 alongside the direct potential-derivative route. This
    knits the ground-state tier into the thermal-transport chain.
  * Stress -> equation-of-state (fit E(V) / sigma(V) across strained cells):
    still deferred; a new observable downstream of Stress, waiting for an
    EOS workflow to ground it.
"""
from __future__ import annotations

from omai.operator.dimensions import ENERGY, ENERGY_PER_LENGTH_CUBED, FORCE
from omai.operator.space import Field, ObservableSpace, Space

# Structure enters NODES from the shared primitives (same node the materials
# graph references), staying in the Sources tier as an input.
from omai.materials.operator.shared_primitives import STRUCTURE

TOTAL_ENERGY = ObservableSpace(
    name="TotalEnergy",
    fields=(Field("E_tot", ENERGY, indices=()),),
    tier="Ground state",
    description=(
        "DFT total energy E_tot of the converged Kohn-Sham self-consistent "
        "ground state, for a Structure under a chosen Potential. Extensive: "
        "one scalar per simulation cell, the conditions carrying the cell. "
        "The pw.x '!' stdout line and the XML total_energy element are the QE "
        "artifacts."
    ),
)

FORCES = ObservableSpace(
    name="Forces",
    fields=(Field("F", FORCE, indices=("i", "alpha")),),
    tier="Ground state",
    description=(
        "Per-atom Cartesian force F_{i,alpha} on the nuclei in the ground "
        "state, the Hellmann-Feynman derivative -dE_tot/dR of the total "
        "energy with respect to atomic positions (plus Pulay / core "
        "corrections in a pseudopotential code). Vanishes at a relaxed "
        "equilibrium; the finite-displacement route to force constants "
        "differentiates these."
    ),
)

STRESS = ObservableSpace(
    name="Stress",
    fields=(Field("sigma", ENERGY_PER_LENGTH_CUBED, indices=("alpha", "beta")),),
    tier="Ground state",
    description=(
        "Cell-averaged macroscopic (Cauchy) stress tensor sigma_{alpha,beta} "
        "= -(1/V_cell) dE_tot/d(strain). Same physical dimension as an energy "
        "density (M L^-1 T^-2), typed ENERGY_PER_LENGTH_CUBED. QE prints it in "
        "Ry/bohr^3 and kbar side by side; a positive value is compressive "
        "(pressure convention) rather than tensile."
    ),
)

NODES: tuple[Space, ...] = (STRUCTURE, TOTAL_ENERGY, FORCES, STRESS)
