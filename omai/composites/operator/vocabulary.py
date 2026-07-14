r"""Formula symbol vocabulary of the composites (effective-medium) domain.

Registered into the core registry (`omai.operator.vocabulary`) when
`omai.composites.operator` is imported. Union semantics per space. Every symbol
the four proven closed forms and the depolarization Piecewise reference is a NEW
field / geometry symbol this domain owns (no existing input node is consumed
except the neutral ThermalConductivity, whose \kappa is already registered by
thermal_transport), so all are declared here on their producing / owning node.

  * ThermalConductivity[role=matrix] carries the matrix conductivity k_m.
  * ThermalConductivity[role=filler] carries the filler tensor k_f (its diagonal
    k_f[1,1] = k11, k_f[3,3] = k33) plus the particle dimensions d_1, d_3 and the
    aspect ratio p = d3/d1 that the mixing / depolarization formulas read.
  * InterfaceConductance carries the interface conductance G_{int}.
  * FillerVolumeFraction carries the volume fraction f_{vol}.
  * DepolarizationFactor carries the two factors L_{11}, L_{33} and the aspect p.
  * the effective-kappa nodes carry the composite conductivity \kappa_c; the
    Hasselman-Johnson producer additionally reads the sphere radius a_{rad}.
    The random node also carries the Nan-notation intermediates its producing
    formula's auxiliary equations define (kc_{11}, kc_{33}, \beta_{11},
    \beta_{33}: the interface-corrected filler conductivities and the
    Bruggeman-Nan terms of Nan 1997), and the aligned node its transverse
    companion \kappa_c^{al11}, exactly as MolarVolume carries the V_{cell} its
    producing formula reads (formula-adjacent symbols live on the owning space).
"""
from __future__ import annotations

from omai.operator.vocabulary import register_space_symbols

register_space_symbols({
    "ThermalConductivity[role=matrix]": {"k_m"},
    "ThermalConductivity[role=filler]": {"k_f", "d_1", "d_3", "p", "a_{rad}"},
    "InterfaceConductance": {"G_{int}"},
    "FillerVolumeFraction": {"f_{vol}"},
    "DepolarizationFactor": {"L_{11}", "L_{33}", "p"},
    "ThermalConductivity[effective_medium=nan,orientation=random]": {
        r"\kappa_c", "kc_{11}", "kc_{33}", r"\beta_{11}", r"\beta_{33}"},
    "ThermalConductivity[effective_medium=nan,orientation=aligned]": {
        r"\kappa_c", r"\kappa_c^{al11}"},
})
