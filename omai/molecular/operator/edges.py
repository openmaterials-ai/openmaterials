r"""Operators (edges) of the molecular domain.

Four edges, all implicit (is_executable_in_sympy_override=False): each an opaque
applied function of its inputs with the molecular method recorded as a scheme,
exactly like the electronic-transport, thermochemistry, and quasi-harmonic edges.

  compute_homo_lumo_gap        : (Structure, Potential) -> HOMOLUMOGap
  compute_reaction_barrier     : (TotalEnergy, Structure) -> ReactionBarrier[construction=neb_mep]
  compute_bond_dissociation    : (TotalEnergy, Structure) -> BondDissociationEnergy
  compute_molecular_frequencies: (Structure, Potential) -> MolecularFrequency

Connectivity. The four nodes plus four edges form ONE weakly connected component
through the pre-existing Structure / TotalEnergy / Potential source nodes:
compute_homo_lumo_gap and compute_molecular_frequencies consume Structure +
Potential (a molecular SCF / Hessian runs a structure under a chosen
functional/basis, the Potential-provenance analog); compute_reaction_barrier and
compute_bond_dissociation both consume TotalEnergy + Structure (a barrier and a
BDE are total-energy differences over molecular configurations). All inputs are
pre-existing store nodes, so the additions touch the store and are weakly
connected; every edge shares Structure.

Symbols. The output field symbols (E_{gap}^{mol}, E_{barrier}, E_{BDE}, and the
indexed nu_mol) are new and collision-checked; the input arguments \mathcal{S}
(Structure), V (Potential), E_{tot} (TotalEnergy) are existing registered symbols
reused as opaque-function arguments. The opaque solver functions (\Delta_{HL},
\Delta_{NEB}, \Delta_{BDE}, \nu^{H}) are applied functions, invisible to the
free-symbol check, so they need no vocabulary entries.
"""
from __future__ import annotations

import sympy as sp

from omai.operator.operator import Operator
from omai.molecular.operator.nodes import (
    BOND_DISSOCIATION_ENERGY,
    HOMO_LUMO_GAP,
    MOLECULAR_FREQUENCY,
    REACTION_BARRIER,
)
from omai.dft_ground_state.operator.nodes import TOTAL_ENERGY
from omai.materials.operator.shared_primitives import STRUCTURE
from omai.thermal_transport.operator.nodes import POTENTIAL


# ---------------------------------------------------------------------------
# Symbols used by the formulas below.
# ---------------------------------------------------------------------------

# Output field symbols (new, registered in this domain's vocabulary).
_E_gap_mol = sp.Symbol(r"E_{gap}^{mol}")
_E_barrier = sp.Symbol(r"E_{barrier}")
_E_BDE = sp.Symbol(r"E_{BDE}")
_nu_mol = sp.IndexedBase("nu_mol")     # MolecularFrequency (indexed by mode m)
_m = sp.Symbol("m", integer=True)      # molecular normal-mode index
# Input arguments (existing registered symbols).
_S_struct = sp.Symbol(r"\mathcal{S}")  # Structure
_V_pot = sp.Symbol("V")                # Potential
_E_tot = sp.Symbol("E_{tot}")          # TotalEnergy
# Opaque solver functions (applied functions, not free symbols).
_gap_fn = sp.Function(r"\Delta_{HL}")
_neb_fn = sp.Function(r"\Delta_{NEB}")
_bde_fn = sp.Function(r"\Delta_{BDE}")
_hess_fn = sp.Function(r"\nu^{H}")     # mass-weighted-Hessian normal modes


# ---------------------------------------------------------------------------
# Operators.
# ---------------------------------------------------------------------------

compute_homo_lumo_gap = Operator(
    name="compute_homo_lumo_gap",
    inputs=(STRUCTURE, POTENTIAL),
    outputs=(HOMO_LUMO_GAP,),
    schemes={"method": "scf_orbital_gap"},
    formula=sp.Eq(_E_gap_mol, _gap_fn(_S_struct, _V_pot)),
    is_executable_in_sympy_override=False,
    description=(
        "Molecular HOMO-LUMO gap E_gap = Delta_HL[Structure, Potential]: the "
        "eV difference of the two discrete frontier KS molecular orbitals of a "
        "converged SCF, ORCA's homo_lumo_gap_eV (parse_orca_output.py:86-93). "
        "Delta_HL is opaque over the molecular Structure and the chosen "
        "functional / basis (the Potential-provenance analog, the def2-SVP "
        "default and the wB97M-V hyphenated-functional hack ride the scheme). "
        "The scheme records the scf_orbital_gap method. A COUSIN of the periodic "
        "band-gap producer, never equated (a molecule has no bands). Implicit (a "
        "molecular SCF, an opaque quantum-chemistry solve), so not "
        "sympy-executable."
    ),
)

compute_reaction_barrier = Operator(
    name="compute_reaction_barrier",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(REACTION_BARRIER,),
    schemes={"method": "ci_neb"},
    formula=sp.Eq(_E_barrier, _neb_fn(_E_tot, _S_struct)),
    is_executable_in_sympy_override=False,
    description=(
        "Reaction barrier E_barrier = Delta_NEB[E_tot, Structure] for the "
        "neb_mep construction: the peak-minus-reactant energy along the "
        "climbing-image nudged-elastic-band minimum-energy path, chem-neb-barrier "
        "via ase.mep NEBTools.get_barrier()[0] (calculate_barrier.py:126-127), "
        "results['barrier_eV']. Delta_NEB is opaque over the per-image "
        "TotalEnergy family (the E along the band) and the Structure endpoints; "
        "eV, MLIP. The scheme records the ci_neb method (idpp interpolation, 7 "
        "images, the MLIP checkpoint the discretization). This is the ONE "
        "construction minted this slice; the sella static-TS "
        "(construction=static_ts_mlip) and ORCA static-TS "
        "(construction=static_ts_dft) routes join the SAME reaction_barrier "
        "family later, distinct nodes only by the construction label, no re-mint. "
        "Distinct from the Arrhenius-slope ActivationEnergy. Implicit (a NEB "
        "path optimization), so not sympy-executable."
    ),
)

compute_bond_dissociation = Operator(
    name="compute_bond_dissociation",
    inputs=(TOTAL_ENERGY, STRUCTURE),
    outputs=(BOND_DISSOCIATION_ENERGY,),
    schemes={"method": "homolytic_fragment_difference"},
    formula=sp.Eq(_E_BDE, _bde_fn(_E_tot, _S_struct)),
    is_executable_in_sympy_override=False,
    description=(
        "Bond dissociation energy E_BDE = Delta_BDE[E_tot, Structure]: the "
        "relaxed fragment total-energy difference E(A.) + E(B.) - E(A-B) of "
        "homolytic cleavage, chem-bond-dissociation (calculate_bde.py:8, "
        "bde_eV:486; rdkit fragments the bond, the MLIP supplies the energies). "
        "Delta_BDE is opaque over the intact-molecule and fragment TotalEnergy "
        "values and the molecular Structure; eV native (kcal/mol the chemist's "
        "convention, the script's 23.0605 factor truncated). The scheme records "
        "the homolytic_fragment_difference method (heterolytic charged-fragment "
        "cleavage is the sibling method, an instance condition). A labeled "
        "sibling of the solid-state reaction-energy producer, on the per-molecule "
        "basis. Implicit (relaxed-fragment MLIP energy differences with open-shell "
        "radicals), so not sympy-executable."
    ),
)

compute_molecular_frequencies = Operator(
    name="compute_molecular_frequencies",
    inputs=(STRUCTURE, POTENTIAL),
    outputs=(MOLECULAR_FREQUENCY,),
    schemes={"method": "hessian_normal_modes"},
    formula=sp.Eq(_nu_mol[_m], _hess_fn(_S_struct, _V_pot)),
    is_executable_in_sympy_override=False,
    description=(
        "Molecular normal-mode frequencies nu_mol,m = nu^{H}[Structure, "
        "Potential]: the 3N-6 (or 3N-5) discrete vibrational frequencies from "
        "diagonalizing the mass-weighted Hessian of the molecular potential at "
        "a stationary structure, cm^-1 native. nu^{H} is opaque over the "
        "molecular Structure and the chosen functional / basis (the "
        "Potential-provenance analog; the Hessian is the second derivative of "
        "that energy surface); the method scheme records the "
        "hessian_normal_modes construction. Imaginary modes serialize NEGATIVE "
        "(a negative Hessian eigenvalue), and n_imaginary (their count) is the "
        "saddle-order diagnostic (0 for a minimum, 1 for a transition state). "
        "Indexed by mode m (the registered `mode` kind), NOT the periodic "
        "phonon (q, nu) axis. Unblocks the RRHO molecular-thermochemistry "
        "bundle (the modes drive the partition function). Implicit (a Hessian "
        "diagonalization, an opaque quantum-chemistry / MLIP solve), so not "
        "sympy-executable."
    ),
)

EDGES: tuple[Operator, ...] = (
    compute_homo_lumo_gap,
    compute_reaction_barrier,
    compute_bond_dissociation,
    compute_molecular_frequencies,
)
