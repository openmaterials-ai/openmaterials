"""The electronic-transport domain: carrier transport from ab-initio scattering.

Electronic transport from the amset scan (AtomisticSkills arXiv 2605.24002):
the electronic-carrier partner of the phonon (lattice) transport already on the
map. Five ObservableSpaces (StaticDielectricTensor plus the four transport
tensors ElectricalConductivity[carrier=electronic], SeebeckCoefficient,
ElectronicThermalConductivity, CarrierMobility) with five implicit edges, all
driven by amset's iterative-BTE Onsager transport over a BoltzTraP2-interpolated
dense band structure with momentum-relaxation-time scattering (ADP + IMP + PIE +
POP), reached through atomate2's VaspAmsetMaker.

Two load-bearing identity decisions:

  * The carrier family. The electronic electrical conductivity shares the EXACT
    ELECTRICAL_CONDUCTIVITY dimension (S/m) and the electrical_conductivity
    quantity tag with the config-thermo ElectricalConductivity[carrier=ionic];
    it joins the one family as ElectricalConductivity[carrier=electronic]
    through the registered carrier LABEL_KEY, a distinct node only by the
    carrier label (the ThermalConductivity[transport_model=...] pattern). Both
    the carrier label and the dimension are already live (the config-thermo
    landing minted them); this domain reuses them.
  * The lattice-vs-electronic kappa firewall. ElectronicThermalConductivity
    reuses the THERMAL_CONDUCTIVITY dimension W/(m K) shared with the nine
    lattice ThermalConductivity[*] nodes but carries its OWN
    electronic_thermal_conductivity quantity tag: the two are the additive
    contributions to the total measured thermal conductivity
    (kappa_total = lattice + electronic), never merged on the shared dimension.

StaticDielectricTensor is a third distinct dielectric quantity (eps_0 = eps_inf
+ ionic), sitting in the Sources tier with the mapped DielectricTensor eps_inf
though computed within this contribution.

Deferred candidates from the amset scan, each with why:

  * DeformationPotential (eV, VBM+CBM) and PiezoelectricConstant (C/m^2) as
    source nodes: amset scattering inputs, but no skill commits their values,
    and the piezoelectric constant is NOT auto-wired by VaspAmsetMaker (PIE is
    off in the default GaAs flow); deferred until a skill reads them.
  * Per-mechanism scattering-rate spectra (1/tau per ADP / IMP / PIE / POP,
    resolved per band and k-point, the Matthiessen sum
    1/tau_total = sum 1/tau_mech): a resolved-spectrum-layer product, deferred
    with the per-mechanism mobility breakdown.
  * The thermoelectric bundle (power factor S^2 sigma, ZT): downstream
    contracts over sigma / S / kappa, deferred until evidence exists (amset
    computes the first three; PF / ZT are downstream).
"""
