# Example lineages

Ten real OpenMaterials lineage files, each shareable, replayable, and grounded
in evidence on the map. Each JSON is a light record whose identity is its lineage:
the X-to-Y path from inputs to a result, with its node, material, hyperparameters,
values, execution metadata, and pointers to heavy data hosted on MaterialsCodeGraph.
No input files, no database: the whole lineage is in the file.

Use them two ways:

- **Open or upload**: the Playground's Lineage tab opens the flagship committed
  example as a full-width plain datasheet, with links to the other nine. Use
  **paste another**, or return to the tools, to drop or paste any of these `.json`
  files into the same view: what it is, every lineage field, what it means on the
  map, provenance, and where the data lives. Dashboards and compute live on
  MaterialsCodeGraph.
- **Share as a link**: `index.json` carries each lineage's gzipped URL fragment; a
  `https://openmaterials.ai/play/#/play?tab=lineage&x=<fragment>` link opens the same
  full-width datasheet with the lineage carried in the URL, no upload needed.

| file | what it shows |
|---|---|
| si-kappa-kaldo-direct | Silicon thermal conductivity, kaldo direct inversion; cross-code agreement with phono3py |
| si-kappa-kaldo-rta | Silicon thermal conductivity, kaldo RTA; the method-comparison story |
| ge-kappa-kaldo | Germanium thermal conductivity, kaldo; cross-code agreement |
| si-diamond-kappa-dfpt | Silicon thermal conductivity from DFPT, the high-fidelity value |
| ptse2-kappa-bte | PtSe2 thermal conductivity, first-principles BTE; theory vs experiment agreement |
| tan-kappa-shengbte | TaN, a high thermal conductivity semiconductor, 3 plus 4 phonon |
| a-si-kappa-qhgk | Amorphous silicon thermal conductivity, QHGK glass transport |
| sige-zt-qhgk | SiGe alloy thermoelectric figure of merit ZT |
| si-elastic-c11-pimd | Silicon elastic constant from PIMD plus TDEP, a mechanical property |
| graphene-kappa-measured | Graphene thermal conductivity, a measurement (Raman optothermal) |

These are curated demonstration lineages. Their hyperparameters and hosted-data URLs are
illustrative of the format; the reported values are grounded in the map's committed evidence.
`si-kappa-kaldo-direct` also pins the committed Si diamond configuration
(`si-diamond-primitive-mp-149`), so its data view resolves the pin and lists the cell's
facts (formula, space group, atoms, lattice), and its Run link carries the pin to
MaterialsCodeGraph.
