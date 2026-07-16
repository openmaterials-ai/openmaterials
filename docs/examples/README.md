# Example recipes

Ten real OpenMaterials recipe files, each a shareable, replayable simulation grounded
in evidence on the map. Each JSON is a light SimulationRecord: the recipe (node, material,
hyperparameters, values), its execution code, and pointers to where the heavy data is hosted
on MaterialsCodeGraph. No input files, no database: the whole recipe is in the file.

Use them two ways:

- **Upload**: open the Playground, Experiment tab, and drop or paste any of these `.json`
  files to see the recipe as a plain data view: what it is, every recipe field, what it
  means on the map, provenance, and where the data lives. Dashboards and compute live on
  MaterialsCodeGraph.
- **Share as a link**: `index.json` carries each recipe's gzipped URL fragment; a
  `https://openmaterials.ai/play/#/play?tab=experiment&x=<fragment>` link opens the same
  data view with the recipe carried in the URL, no upload needed.

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

These are curated demonstration recipes. Their hyperparameters and hosted-data URLs are
illustrative of the format; the reported values are grounded in the map's committed evidence.
