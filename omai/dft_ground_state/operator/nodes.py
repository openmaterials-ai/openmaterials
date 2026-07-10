"""Operator nodes of the DFT ground-state domain.

The first-principles ground state a DFT engine computes for a Structure under a
chosen Potential: the total energy, the per-atom forces, and the cell stress.
All three are ObservableSpaces (gauge-invariant, cross-code-comparable after
unit conversion); Structure enters here from the shared primitives (it keeps
its Sources tier as an input, joining Potential).

Node table:

  Node           quantity tag     dimension                  indices        notes
  -------------  ---------------  -------------------------  -------------  -----
  Structure      structure        opaque                     ()             shared input
  TotalEnergy    total_energy     ENERGY                     ()             extensive, per cell
  Forces         force            FORCE (M L T^-2)           (i, alpha)     per-atom Cartesian
  Stress         stress           ENERGY_PER_LENGTH_CUBED    (alpha, beta)  cell-averaged Cauchy
  MagneticMoment magnetic_moment  MAGNETIC_MOMENT (L^2 I)    (i,)           per-site, mu_B
  BandGap        band_gap         ENERGY                     ()             KS eigenvalue gap, eV

Deferred v1 candidates (from the QE scan's seven new-node set), each with why:

  * ChargeDensity: an observable in principle (Hohenberg-Kohn), but needs a
    real-space grid index kind and a density dimension, and nothing downstream
    consumes it yet. Add when a workflow reads it.
  * Wavefunctions: a HiddenSpace with U(N) gauge freedom; the right showcase
    for gauge discipline in a later slice, not needed for energy/forces/stress.
  * dvscf (the self-consistent potential response): EPW territory, with the
    normalization left open in the scan; defer until the EPW chain lands.

Deferred candidates from the atomate2/VASP scan (arXiv 2605.24002), each with
why (BandGap being the ONE node that scan lands here):

  * charged defect formation energy (FormationEnergyMaker): a new node that
    depends on elemental chemical potentials, the charge state, the Fermi
    reference, and Freysoldt/Kumagai finite-size corrections. It needs the
    chemical-potential machinery the map does not yet carry; defer to a
    dedicated defect slice. (The stability domain's neutral MLIP formation
    energy is a different, per-atom quantity.)
  * frequency-dependent dielectric function eps(omega) and Raman / XRD
    intensities (OpticsMaker LOPTICS): function-valued spectra over a photon
    energy / scattering axis. They need a spectrum-valued space type the map
    does not yet have; defer until that type lands. Distinct from the static
    clamped-ion DielectricTensor already on the map.
  * the electronic transport trio (electrical conductivity, Seebeck
    coefficient, electronic thermal conductivity; VaspAmsetMaker): a new
    thermoelectrics domain hanging off a Boltzmann-transport scattering model.
    Queued for the amset parse. The electronic kappa is physically distinct
    from the map's lattice ThermalConductivity.
  * spontaneous polarization P_s (FerroelectricMaker, LCALCPOL Berry phase):
    defined only modulo a polarization quantum resolved by branch continuity
    along a distortion path, a genuine lattice-gauge structure. It deserves
    its own slice as the gauge-quantum showcase, not a hurried add here.

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

from omai.operator.dimensions import (
    ENERGY,
    ENERGY_PER_LENGTH_CUBED,
    FORCE,
    MAGNETIC_MOMENT,
)
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

MAGNETIC_MOMENT_STATE = ObservableSpace(
    name="MagneticMoment",
    fields=(Field("m", MAGNETIC_MOMENT, indices=("i",)),),
    tier="Ground state",
    description=(
        "Per-site magnetic moment m_i of the spin-polarized ground state, in "
        "Bohr magnetons: the projection of the spin density onto site i that "
        "a spin-polarized SCF reports next to the energy, forces, and "
        "stress (VASP MAGMOM/magnetization, QE site moments; MP serves the "
        "cell total as total_magnetization). Dimension MAGNETIC_MOMENT "
        "(L^2 I, the map's first magnetic use of the current axis); the "
        "collinear FM/AFM/FiM/NM ordering classification is a downstream "
        "label over these moments (pymatgen Ordering), not part of the node."
    ),
)

BAND_GAP = ObservableSpace(
    name="BandGap",
    fields=(Field("E_gap", ENERGY, indices=()),),
    tier="Ground state",
    description=(
        "Electronic band gap E_gap of the ground state: the Kohn-Sham "
        "eigenvalue gap between the valence-band maximum and the "
        "conduction-band minimum a band-structure run reports (zero for a "
        "metal), a single scalar in eV alongside the energy, forces, and "
        "stress. It is the KS gap, NOT the fundamental (quasiparticle) gap: "
        "the two differ by the derivative discontinuity, and semilocal "
        "functionals underestimate the gap, so the value is strongly "
        "exchange-correlation-functional dependent and rides with the "
        "Potential provenance. The direct/indirect character and the Fermi "
        "level are downstream labels over the same band structure, not part "
        "of this scalar node."
    ),
)

NODES: tuple[Space, ...] = (
    STRUCTURE,
    TOTAL_ENERGY,
    FORCES,
    STRESS,
    MAGNETIC_MOMENT_STATE,
    BAND_GAP,
)
