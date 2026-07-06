# Code-scan catalogs

Read-only scans of external codes, in the schema described in
`docs/superpowers/specs/2026-07-06-map-kernel-design.md` (an extension of
`omai/materials/skills_catalog.json` with source anchors and maps_to
fields). A catalog is the reviewed input for encoding a code onto the map;
it never mutates the map by itself.

| Catalog | Source | Status |
|---|---|---|
| `qe-phonon.json` / `.md` | Quantum ESPRESSO 7.5 (vendored `q-e/`), phonon slice: pw.x, ph.x, q2r.x, matdyn.x | Existing-node groundings encoded as `omai/thermal_transport/representation/qe.py` (2026-07-06). The 7 new-node candidates (total energy, forces, stress, charge density, wavefunctions, positions, dvscf) wait for the map kernel. |
| `lammps-thermal.json` / `.md` | LAMMPS 30 Mar 2026 (vendored `lammps/`), thermal/MD slice | Existing-node corrections and the Temperature spec encoded into `representation/lammps.py` (2026-07-06). The new-node candidates (per-atom stress and energies, reservoir-energy family, RDF, Pressure, ElasticConstants) wait for the map kernel; the Diffusivity workflow entry waits for the materials-domain encode. |

Every entry carries `source_anchors` (file:line in the scanned tree), the
code-native units exactly as emitted, and the convention traps in
`conventions`. The `.md` reports summarize each scan's top findings.
