# openmaterials

openmaterials is a versioned map of physics knowledge, built like git: typed
physical quantities (nodes) related by executable formulas (edges), every
element content-hashed, every change logged. The structure comes from codes and
theory: a respected codebase or a published derivation is what adds nodes and
edges. Experiments fill it in: each simulation run or measurement attaches a
value to a node, with its material, conditions, and source. Parsers turn the
world's codes, papers, and data files into both, and an index in the same
repository collects them. The map compounds: every code mapped and every value
attached makes the neighborhood more cross-checked, more reproducible, and more
trustable.

The picture has two tiers, the way git has GitHub. The **openmaterials
protocol** is free and open forever: the map format, the hashing rules, the
versioned change-log, the schemas, the parser contracts. The **openmaterials
app** is a hosted service on top: upload a map and see it rendered instantly, or
store your own custom and private maps. The protocol is the commons; the app is
convenience built on it.

## Protocol and app

The protocol is a standard anyone can implement, self-host, and fork. The
mother map and its index are the shared artifact the community builds through
the protocol; they belong to no one and to everyone.

The app (the website, a separate project) adds the hosted conveniences: paste
and upload a map and have it rendered immediately in rich traversal views, the
way mermaid.live renders a diagram with no setup, and optionally store custom or
private maps. Anything hosted lives entirely app-side; it never touches the
protocol or the commons. The app is free while we build it, and how it is funded
later is out of scope here. The priority is the protocol and the map.

The priority is explicit: first build the community that builds the mother map,
and a rich initial map worth using. The app comes second. Protocol adoption is
what makes the app valuable, the same way git had to matter before GitHub
could.

## Structure and evidence

Two kinds of thing live on the map, and they come from different places. This
is the load-bearing distinction.

**Structure** is nodes and edges. It comes from **sources**: a code (the kaldo,
QE, or LAMMPS codebase) or a theory paper. A source asserts that a quantity
exists and that a formula relates it to other quantities. Codes are the ground
truth we seed from, because a respected code is an executable statement of the
physics; theory papers and, later, new derivations extend the structure.

**Evidence** is values on nodes. It comes from **instances**: one run of a
code, or one measurement. An instance attaches a value to a node, with the
material, the conditions, and a citation. Evidence never creates structure: a
simulation cannot invent a formula, it can only put a number on a node that
already exists.

The two relate through a small type hierarchy. A code is a **representation**: a
named mapping of part of the map onto a concrete tool, with its units, gauge,
and conventions. A single run of that code is an **instance**, and the kappa it
outputs is a **value on the kappa node**. A growth process such as CVD is an
experiment type, also a representation; a specific synthesis and measurement is
an instance; its measured number is a value on a node. So "is ShengBTE a tag?"
resolves cleanly: ShengBTE is a representation, a ShengBTE run is an instance,
and its result is a value on a node.

## The map

The map is a curated reference graph. Today it holds 51 nodes (48 observable
and hidden quantities plus 3 promoted parameters) and 131 edges. Nodes are
typed physical quantities. An edge produces one node from a list of input
nodes, carrying the symbolic formula that relates them (parameter inputs are
marked as inputs rather than derived through a formula).

Identity is structural, not nominal. A derived node's id is the hash of its
operation and its unordered input node ids; a leaf node's id is the hash of its
intrinsic type, units, gauge class, and index signature. Names and symbols are
not part of identity, so your `kappa` and my `k_L` are the same node when they
have the same structure, and a formula written `c v^2 tau` or `tau v^2 c` is one
edge because both store the same operation graph. Genuinely different
decompositions stay separate graphs and are reconciled where they meet, at a
shared observable. The consequence is that two people who contribute the same
physics converge automatically, while a real difference in decomposition
surfaces as a parallel route rather than a false merge.

Three properties propagate, rather than being hand-stamped on every node:

- **Units** live on leaf nodes and propagate through operations; a derived
  node's units are computed, never stored.
- **Gauge** lives on index kinds. Mode and branch indices, and the phase of an
  eigenvector, carry a representation's gauge freedom; a node is **observable**
  once every gauge-carrying index has been contracted away, and **hidden**
  until then. Cross-source values may be compared only at observables.
- **Symmetry** lives on index kinds too. A quantity's intrinsic index symmetry
  (the thermal-conductivity tensor satisfies kappa^{ab} = kappa^{ba}) belongs to
  the node; a material's crystal symmetry (cubic silicon making kappa isotropic)
  acts on the spatial indices at the material and instance level, not on the
  node. Symmetry is what proves that one code reporting kappa_xx and another
  reporting the trace over three are reporting the same observable.

The map is versioned like git, log first. The change-log is the map: an ordered
sequence of operations (add, edit, or deprecate a node; add or remove an edge;
supersede an element), each carrying a date, a reason, and an author. A
materialized current version is always kept in sync, so reading the map is
immediate. The map version hash chains the log, computed as the hash of the
previous version hash combined with the new change record, which makes the
history tamper-evident and path-dependent. Because identity is structural,
editing a foundational leaf re-mints every node above it (a Merkle ripple); the
supersede record ties the old subgraph to the new one, and a value pinned to an
exact element and map version either stays pinned for reproducibility or follows
the supersede chain for currency.

Provenance and confidence ride on every element. A node or edge records the
sources that assert it (which codes and papers) and accumulates the instances
that put values on it. Many independent instances are a confidence signal, but
independence is not the same as multiplicity: two solvers run on the same
interatomic potential are not independent confirmations, so the map keeps the
full provenance (potential, method, code) and lets independence be judged rather
than counting raw repetitions. A claim no instance has reached yet still lives
on the map, simply unconfirmed.

## The parsers

A parser is an assisted on-ramp, one per artifact type. Each proposes
structure, values, or both; the map validates them; a human confirms.

- The code parser imports a codebase as a representation: it maps the code's
  input, output, and intermediate files and key lines onto the nodes and edges
  the code implements (structure), and it lets a run of the code be recorded as
  an instance (values).
- The paper parser turns a paper's formulas into edges (structure) and its
  measured or computed numbers into values on nodes.
- The run parser reads a concrete run and records its inputs (from the input
  file) and its outputs as values on the nodes they belong to.

Proposals must pass the map's types as continuous integration: dimensional
agreement; reachability, so a value lands only on a node that already exists and
a new edge is introduced only by a code or a theory source, never by a bare
experiment; observable discipline, so cross-source equality is asserted only at
observables; completeness, so every input and output of a run is recorded; and
coherence, so one source's contributions form a connected subgraph. All the
difficulty of joining the commons concentrates here, in the parsers, which is
what keeps the store itself simple.

## The index

The index is a subfolder of the map repository, in two clearly separated parts.

The canonical registry is organized by source: `papers/`, `codes/`,
`experiments/`. Each entry holds that source's structure contributions and the
values its instances produced, pinned to a specific element hash at a specific
map version.

The derived lookups are regenerated from the registry and the map, never edited
by hand: symbol to node, value to instances, source to coverage.

One clone gets you the map and the world's evidence together.

## Contracts (for builders)

These are the interfaces the protocol defines. They are described here, not yet
implemented; each becomes its own spec, plan, and build cycle.

**Store operations.** `push(change)` appends a change record (op, target, date,
reason, author) and advances the version hash. `read()` returns the
materialized current map. `read(hash)` returns the map at a given version.
`diff(hashA, hashB)` returns the change records between two versions. Identity
is by content: a derived node id = hash(operation, unordered input node ids); a
leaf node id = hash(type, units, gauge, index signature); an edge id =
hash(output node, operation, input node list); the version hash = hash(previous
version hash + change record).

**Structure contribution (from a source).** A code or a theory paper proposes
new nodes and edges. Inputs to any new edge must resolve to nodes that already
exist or are introduced by the same source in the same contribution, processed
in dependency order. Reviewed before it lands in the canonical map.

**Value record (an instance).** Sketched:

```json
{
  "confirms": "<node id>",
  "value": 0.0, "units": "<units>",
  "material": "<material>", "conditions": "<T, mesh, potential, ...>",
  "source": {
    "kind": "<simulation | measurement>",
    "representation": "<code or experiment-type id>",
    "ref": "<run id or citation>"
  },
  "description": "<human-readable note>"
}
```

`confirms` always points at a node, because a value belongs to a quantity. A
value record never introduces structure; that is a separate, reviewed
contribution.

**Parser contract.** Input: one artifact (a codebase, a paper, a run). Output:
proposed structure and value records. Every proposal must pass validation below
before a human confirms it into the index.

**Index schema.** Registry: `index/papers/`, `index/codes/`,
`index/experiments/`, each entry pinned to (element hash at map version).
Derived files (regenerated, never hand-edited): symbol-to-node,
value-to-instances, source-to-coverage.

**Validation rules.** Dimensional agreement on every edge. Reachability: a value
lands only on an existing node, and a new edge is introduced only by a code or
theory source. Observable discipline: cross-source equality is asserted only at
observables. Completeness: every input and output of a run is recorded.
Coherence: a single source's contributions form a connected subgraph.

## Governance

The protocol is forkable: anyone can self-host a map or fork the mother map.
Landing a contribution in the canonical maintained repository goes through a
reviewer list. Content-addressing handles identity and deduplication on its own;
the reviewers decide what enters the commons.

## Status and build order

Today's map is v1, the genesis version: 48 typed quantities plus 3 promoted
parameters, the symbolic formula on every relational edge, 8 representations
mapped (kaldo 32 variables, phono3py 31, ShengBTE 20, phonopy 17, GPUMD 8,
LAMMPS 8, ASE 1, and the mat-diffusion-analysis skill 2), and real instances
computed through the framework: cross-code silicon thermal conductivity
(Tersoff potential, 8x8x8 mesh, 300 K: kaldo 19.46 RTA and 26.91 direct,
phono3py 16.74 RTA and 24.30 direct, in W/m K) plus an LGPS activation energy
(0.152 eV) from the materials domain. It is live and browsable as an
interactive map.

The contributor on-ramp today is curated pull requests reviewed by the
maintainer list; the silicon values above arrived that way. The parsers are
the eventual automated on-ramp, not the day-one one. Build order from here:
freeze the genesis version hash; build the log-first store; build the index;
then build the first parser, for papers. The app follows once the protocol and a
rich mother map exist.

## See also

- The vision, why this matters: [docs/vision.pdf](docs/vision.pdf).
- The architecture, how the operator and representation layers work:
  [docs/operator_representation_substrate.pdf](docs/operator_representation_substrate.pdf).
- The map, live: [docs/map/](docs/map/) (openmaterials.ai/map).
- The deck, a short walkthrough: [docs/deck/](docs/deck/).
