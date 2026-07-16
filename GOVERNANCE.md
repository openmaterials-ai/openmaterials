# Governance

openmaterials.ai is one project in three parts, with three owners. This
document states the structure, the boundary rule, and the graduation path,
so the project can be held to them.

## The three parts

1. **The map**: the versioned graph of physical quantities, formulas, code
   representations, and the evidence attached to them (`map/`, `docs/data/`,
   `index/`), together with the protocol that governs changes (content
   identity, the append-only store, the contribution gates) and its kernel
   reference implementation. This is the commons. It is stewarded by
   **OpenMaterials-AI**, an open initiative currently structured as a
   foundation in formation (see below), and licensed for open reuse
   (data: CC BY 4.0; kernel code: Apache 2.0).
2. **The interfaces**: the site, the map views, the tracer, the learn
   pipeline, and the bibliography tooling. Built and maintained by
   **Da Vinci Labs**.
3. **The improvement engine**: the AI systems that read papers and
   codebases, propose additions, and stress-test the map. Da Vinci Labs
   R&D, open where it touches the commons.

## The boundary rule

The commons owns the ledger and its laws; companies own tools and products
built on top. Anything that decides what is true on the map (the store, the
gates, the identity rules, the genesis hash) belongs to the initiative and
changes only through the gated contribution process. Anything that makes
the map more useful or faster to grow is open territory for anyone,
including commercial actors.

## How changes happen

Every change to the map is a content-addressed record appended to
`map/log.jsonl`, validated by the gates (identity, dimensional consistency,
connectivity, deduplication) and reviewed by a maintainer. Evidence (values
from simulations, measurements, or parsed papers) never edits the map; it
attaches to nodes with material, conditions, uncertainty, and verbatim
provenance. Contributions that cannot cite their source do not enter.

## Decision making, today and later

Today the project has two scientific authors (Giuseppe Barbalinardo and
Davide Donadio) and maintainer-led review: honest BDFL-with-gates. The
stated intent, in order:

1. Now: public governance (this file), open licenses, the gates as the
   objective part of review.
2. As external contributors arrive: a small technical steering group drawn
   from contributing groups; fiscal sponsorship through an established
   nonprofit rather than a standalone legal entity.
3. If and when the community warrants it: a foundation proper, holding the
   map data, the protocol, and the openmaterials.ai name.

The openmaterials.ai name and the map belong to the initiative through
each of these stages, not to any company, including Da Vinci Labs.

## Licensing

* Map data (`map/`, `docs/data/`, `index/`): **CC BY 4.0** (LICENSE-DATA).
  Reuse freely, cite the map version you used.
* Code (`omai/`, tests, site source): **Apache 2.0** (LICENSE).
* Every mapped code's own citation and license is recorded in its rail
  (`docs/data/codes.json`); crediting upstream science is a gate, not a
  courtesy.

## Data ownership and fairness

The map runs on other people's science: simulations someone paid compute
for, measurements someone ran a lab for, codes someone maintains, papers
someone wrote. The rules below keep that exchange fair. They are
commitments of the initiative, not courtesies.

* **Contributed values stay their owner's.** Appending evidence to the
  map transfers nothing. Whatever rights exist in a contributed record
  (for a measured fact, often none; for a curated dataset, sometimes
  many) remain with the contributor or the original rights holder. By
  contributing, you grant the initiative a worldwide, non-exclusive,
  royalty-free license to redistribute the record under CC BY 4.0, and
  you keep everything else. There is no copyright assignment and no
  contributor license agreement: the license in is the license out.
* **Raw artifacts never enter the store.** The map holds derived values
  with conditions, uncertainty, and provenance. It never ingests the
  underlying trajectories, wavefunctions, force sets, lab records, or
  datasets. Those remain wholly the owner's, under the owner's own
  terms, reachable through the provenance reference and nowhere else.
* **Identity in the commons, bulk on the platform.** A lineage is the shareable
  run record defined in `omai/lineages.py`; provenance is a quantity instance's
  source reference; derivation is a node's upstream graph in the map. The record
  is light and lineage-identified: its identity comes from its `lineage` field
  (a map node when known, else a template with its hyperparameters and setup
  values), and heavy artifacts are optional, pointer-only
  (`{path, role, url?, sha256?}`), never embedded and never hashed into
  identity. The format (the data structure) is the open-source,
  host-agnostic part; the heavy bytes live on the platform
  (MaterialsCodeGraph) as the cheap host, or any object store under the
  owner's own terms, referenced by pointer alone. Because location is
  outside the identity, moving bytes, renaming a bucket, or adding a
  mirror never changes the record's identity or orphans a value that cites
  it. This is the operational form of the rule above: the open format
  keeps the lineage and its identity, the platform keeps the bytes.
* **Attribution flows both ways.** Downstream, reuse of map data must
  credit the map version and, through its provenance, the original
  sources: that is what the BY in CC BY 4.0 means. Upstream, every
  mapped code's citation and license is recorded in its rail, every
  parsed paper is cited with verbatim quotes and page anchors, and a
  contribution that cannot cite its source does not enter.
* **Good open licenses are respected where we meet them.** Values enter
  with citation; quotes stay short, verbatim, and page-anchored; codes
  are described and credited, never vendored. Material whose license
  does not permit this kind of inclusion does not enter. A rights
  holder who believes something entered in error can open an issue: the
  record is removed from the current view of the map, and the
  append-only log records the retraction.
