r"""Formula symbol vocabulary of the DFT ground-state domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.dft_ground_state.operator` is imported. Union semantics per space, so
extending Structure's and Potential's symbol sets here does not disturb the
thermal / materials registrations of those shared nodes.

No new bare formula constants: the only global symbol the formulas reference
beyond the per-space sets is V_{cell}, already registered as a generic constant
by the thermal domain.
"""

from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    # The converged SCF total energy the ground-state solve produces.
    "TotalEnergy": {"E_{tot}"},
    # Per-atom force field; F_j(R) is the displaced-configuration force
    # label the finite-displacement FC2 formula differentiates.
    "Forces": {r"F^{at}", "F_j(R)"},
    # Cell stress and the homogeneous strain it differentiates against.
    "Stress": {r"\sigma", r"\varepsilon^{str}"},
    # Structure carries its label \mathcal{S} and the atomic positions R^{at}
    # the forces differentiate against.
    "Structure": {r"\mathcal{S}", r"R^{at}"},
    # The opaque potential appears as the second argument of E_KS(S, V).
    "Potential": {"V"},
    # Per-site magnetic moment (m^{spin}, not bare m: that is the thermal
    # domain's registered atomic mass).
    "MagneticMoment": {r"m^{spin}"},
    # Electronic band gap scalar the band-structure solve reports.
    "BandGap": {"E_{gap}"},
})
