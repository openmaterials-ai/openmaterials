# openmaterials

openmaterials is a versioned map of physics knowledge, built like git: typed
physical quantities connected by executable formulas, every element
content-hashed, every change logged. Experiments confirm the map: each
simulation or measurement is a tag, attached to the node or edge it confirms,
carrying its value, material, conditions, and source. Parsers turn the world's
papers, codes, and data files into those tags; an index, living in the same
repository, collects them. The map compounds: each experiment it absorbs makes
every neighboring result more cross-checked, more reproducible, and more
trustable.

The picture has two tiers, the way git has GitHub. The **openmaterials
protocol** is free and open forever: the map format, the hashing rules, the
versioned change-log, the tag schema, the index layout, and the parser
contracts. The **openmaterials app** is a hosted service on top: upload a map
and see it rendered instantly, or store your own custom and private maps. The
protocol is the commons; the app is convenience built on it.

## Protocol and app

The protocol is a standard anyone can implement, self-host, and fork. The
mother map and its index are the shared artifact the community builds through
the protocol; they belong to no one and to everyone.

The app (the website, a separate project) adds the hosted conveniences: sign up
for an API key, store custom or private maps in our storage, or paste and
upload a map and have it rendered immediately in rich traversal views, the way
mermaid.live renders a diagram with no setup. Private and custom maps and any
future entitlements live entirely app-side; they never touch the protocol or
the commons. Pricing is metered per token, free for students, and initially
free for everyone.

The priority is explicit: first build the community that builds the mother map,
and a rich initial map worth using. The app comes second. Protocol adoption is
what makes the app valuable, the same way git had to matter before GitHub
could.

## The map

The map is a curated reference graph. Nodes are typed physical quantities, each
carrying its units, index signature, and gauge class (observable, hidden, or
parameter). Edges are symbolic formulas: an operation that produces one node
from a list of input nodes. Today the map holds 49 nodes (46 observable and
hidden quantities plus 3 promoted parameters) and 128 edges, with a formula on
every edge.

Identity comes from content, not from names. A node's id is the hash of its
intrinsic definition only: symbol, type, units, indices, gauge. An edge's id is
the hash of its output node, its operation, and its list of input nodes. The
consequence is that two people who independently contribute the same physics
land on the same object automatically, while a genuine disagreement produces a
different hash and surfaces as an alternative edge, never a silent false merge.

The map is versioned like git, log first. The change-log is the map: an ordered
sequence of operations (add, edit, or deprecate a node; add or remove an edge;
supersede an element), each carrying a date, a reason, and an author. A
materialized current version is always kept in sync, so reading the map is
immediate. The map version hash chains the log, computed as the hash of the
previous version hash combined with the new change record, which makes the
history tamper-evident and path-dependent. Edits supersede rather than rewrite,
and removals leave tombstones, so a tag pinned to an exact element and map
version stays reproducible, and can choose to follow the supersede chain
forward when it wants currency instead.

Knowledge earns confidence through experiments. Every node and edge starts as a
claim and accumulates tags: experiments, simulated or real, that confirm it,
each carrying its value, conditions, and source. When many independent
experiments land on the same element, that multiplicity is the confidence
signal, and the map can render it as edge weight. A claim no experiment has
reached yet is still on the map, just unconfirmed.

## The parsers

A parser is an assisted on-ramp, one per artifact type. Each proposes tags, the
map validates them, and a human confirms.

- The code parser maps a codebase onto the map: its input, output, and
  intermediate files and key lines onto nodes and edges, so the code's
  input/output contract becomes explicit and a run of it can be recorded as an
  experiment.
- The paper parser turns a paper's formulas into edges and its measured or
  computed numbers into tags, each with its material, conditions, and source.
- The I/O-file parser reads a concrete run and records its outputs as
  experiments confirming the edges they bear on.

Proposals must pass the map's types as continuous integration: dimensional
agreement; reachability, so a claimed transformation has to exist as a real
path; observable and hidden discipline, so cross-source equality is asserted
only at observables; completeness, so every input and output of a run is
tagged; and coherence, so one source's tags form a connected subgraph. All the
difficulty of joining the commons concentrates here, in the parsers, which is
what keeps the store itself simple.

## The index

The index is a subfolder of the map repository, in two clearly separated parts.

The canonical registry of experiments is organized by source: `papers/`,
`codes/`, `experiments/`. Each entry holds that source's tags, pinned to a
specific element hash at a specific map version.

The derived lookups are regenerated from the registry and the map, never edited
by hand: symbol to node, value to experiments, source to coverage.

One clone gets you the map and the world's experiments together.

## The tag (an experiment)

A tag is an experiment: a simulation run or a real-world measurement that
confirms a node or an edge. It is the unit of evidence, and the unit by which
the map grows. A tag's record is:

- the element it confirms: the node or edge the experiment bears on, referenced
  by id;
- the result: a value with units, the material, and the conditions
  (temperature, mesh, potential, and so on);
- the source: who produced it, simulated or measured, with a citation or run
  reference;
- a description: a human-readable note.

An experiment confirms what already exists by simply landing on it; many
independent tags on one element are what turn a claim into trusted knowledge.
And an experiment that bears on structure the map does not yet have introduces
that structure as it lands: a measured quantity with no node, or a computed
result whose formula is not yet an edge, brings the new node or edge in with
it. The experiment is primary; the new structure is its byproduct, with human
review as the gate. Any introduced edge is still content-hashed from its output
node, operation, and inputs, so an experiment that introduces an edge already
present elsewhere converges onto it rather than duplicating it, and the inputs
to that formula must resolve to nodes that already exist.

## The app

The app is a separate, hosted project layered on the protocol. It offers an API
key for access; storage for your own custom or private maps in our storage
(S3); and instant upload-and-visualize, where you paste or upload a map and it
renders immediately in rich, well-designed traversal views, the mermaid.live
pattern applied to physics. Pricing is metered per token, free for students,
and initially free for everyone. None of this changes the protocol or the
commons; it is convenience on top.

## Contracts (for builders)

These are the interfaces the protocol defines. They are described here, not yet
implemented; each becomes its own spec, plan, and build cycle.

**Store operations.** `push(change)` appends a change record (op, target, date,
reason, author) and advances the version hash. `read()` returns the
materialized current map. `read(hash)` returns the map at a given version.
`diff(hashA, hashB)` returns the change records between two versions. Identity
is by content: node id = hash(symbol, type, units, indices, gauge); edge id =
hash(output node, operation, input node list); version hash = hash(previous
version hash + change record).

**Tag record (an experiment).** Sketched:

```json
{
  "confirms": "<node id | edge id>",
  "result": {
    "value": 0.0, "units": "<units>",
    "material": "<material>", "conditions": "<T, mesh, potential, ...>"
  },
  "source": { "kind": "<simulation | measurement>", "ref": "<citation or run id>" },
  "description": "<human-readable note>",
  "introduces": {
    "node": "<new node definition, optional>",
    "edge": { "output": "<node id>", "op": "<operation>", "inputs": ["<node id>", "..."] }
  }
}
```

The `confirms` field points at the existing element the experiment bears on. The
optional `introduces` block carries any new node or edge the experiment brings
in with it; an introduced edge is content-hashed and converges onto an
identical one if it already exists.

**Parser contract.** Input: one artifact (a codebase, a paper, an I/O run).
Output: a list of proposed tags. Every proposal must pass validation (below)
before a human confirms it into the index.

**Index schema.** Registry: `index/papers/`, `index/codes/`,
`index/experiments/`, each entry pinned to (element hash at map version).
Derived files (regenerated, never hand-edited): symbol-to-node,
value-to-instances, source-to-coverage.

**Validation rules.** Dimensional agreement on every edge. Reachability: a
claimed transformation must exist as a real path in the map. Observable and
hidden discipline: cross-source equality is asserted only at observables.
Completeness: every input and output of a run is tagged. Coherence: a single
source's tags form a connected subgraph.

## Status and build order

Today's map is v1, the genesis version: 46 typed quantities plus 3 promoted
parameters, a symbolic formula on every edge, 7 codes mapped (kaldo 32
variables, phono3py 31, ShengBTE 20, phonopy 17, GPUMD 8, LAMMPS 8, ASE 1), and
real cross-code silicon thermal-conductivity experiments computed through the
framework (Tersoff potential, 8x8x8 mesh, 300 K: kaldo 19.46 RTA and 26.91
direct, phono3py 16.74 RTA and 24.30 direct, in W/m·K). It is live and
browsable as an interactive map.

Build order from here: freeze the genesis version hash; build the log-first
store; build the index; then build the first parser, for papers. The app
follows once the protocol and a rich mother map exist.

## See also

- The vision, why this matters: [docs/vision.pdf](docs/vision.pdf).
- The architecture, how the operator and representation layers work:
  [docs/operator_representation_substrate.pdf](docs/operator_representation_substrate.pdf).
- The map, live: [docs/map/](docs/map/) (openmaterials.ai/map).
- The deck, a short walkthrough: [docs/deck/](docs/deck/).
