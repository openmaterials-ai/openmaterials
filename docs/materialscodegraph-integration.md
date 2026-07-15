# MaterialsCodeGraph integration: the recipe card and the executable run

Status: design note, for discussion. This is a plan to look at whole, not an
implementation. Nothing here changes the store, the gates, or any record; it
proposes where a small set of optional, additive seams would sit and defers every
interface and identity decision to the maintainer. Each concrete change already
has (or will have) its own issue; this note is the map they hang on.

## Why this note exists

Three issues on this repo describe one arc, and they read better together than
apart: #23 (an optional `provider` key on a mirror entry), #25 (an optional "Run
on MaterialsCodeGraph" link on the experiment page), and the companion upload
idea. On the MaterialsCodeGraph (MCG) side, materialscodegraph#74 is merged (MCG
emits a SimulationRecord byte-identical to `omai/simulations.py`) and
materialscodegraph#65 is merged (a compute deep link `#/new/<node_id>`). The
pieces exist or are proposed in separate places; this note puts the shared
picture in front of you in one place so you can shape the boundary before any of
it ships.

The framing throughout: openmaterials is the git-native, storage-free experiment
**card**; MaterialsCodeGraph is the executable **Space**. It is the HuggingFace
split, stated plainly, and the point of the note is to keep that split honest so
neither side can cannibalize the other.

## 1. The model

### openmaterials: the git-native, storage-free card

An experiment on this repo is light. `omai/simulations.py` fixes it precisely: a
record's identity is the **recipe** alone (`recipe_id` is the sha256 of the
canonical recipe), and the recipe is the map `node` (with a `node_uid` pin when a
map node is known, else a `template`), the `material`, the `conditions`, the
`params`, the `hyperparameters`, and the setup `values`. Everything else a record
carries (`execution`, `artifacts`, `mirrors`, `results`) rides **outside** the
hash. A record with no artifacts at all is valid and normal (the module docstring
says so: "A record with NO artifacts is valid and normal. Identity comes from the
RECIPE, never from a per-artifact manifest").

This card enters the commons two ways, and the live pages already show both:

- **By git PR.** An experiment is one source's evidence, grouped by its
  provenance ref. `docs/experiment/index.html` fetches `../data/instances.json`,
  groups records by `source.ref` (line 178), and renders each group as a page you
  can share by URL. The ref rides in the fragment: `refFromHash()` reads
  `location.hash.match(/[#?&]ref=([^&]*)/)` (line 159), so
  `experiment/#ref=paper:cnt-2021-barbalinardo` opens the SWCNT card for
  Barbalinardo et al., PRL 127, 025902 (2021): the reported thermal conductivity
  3190 W/(m K) at 300 K, with its verbatim page-anchored quote
  (`docs/data/instances/10-0-swcnt-thermalconductivity-bte-solver-direct-inverse-paper-cnt-2021-barbalinardo.json`,
  cross-indexed at `index/papers/cnt-2021-barbalinardo.json`).

- **By uploading a JSON.** The Playground already renders a record client-side
  with no server: its Experiment tab (`docs/play/index.html`, `renderExperiment`,
  line 487) takes a pasted record, renders the recipe, its values, and any
  artifact pointers, and lights the recipe's node on the canvas when it names a
  live map node. The whole record even rides in the `#x=` fragment via the same
  gzip+base64url scheme `record_to_fragment` uses in Python, so a link is
  self-contained and needs no backend.

Either way the commons holds **zero bytes**. It holds the recipe and its
identity, the reported value with conditions and uncertainty, and verbatim
provenance. It never ingests a trajectory, a force set, or a wavefunction
(GOVERNANCE.md, "Raw artifacts never enter the store").

### MaterialsCodeGraph: the executable Space

MCG is the same recipe wired to an engine and a pod: runnable, and able to host
the heavy artifacts a run produces. materialscodegraph#74 (merged) makes MCG a
conformant host of exactly this format: a node-addressed run emits a
SimulationRecord whose JSON and canonical id are byte-identical to what
`record_simulation` / `canonical_id` produce, served publicly at
`GET /api/shared/:token/record`. A pinned run with zero artifacts is a valid,
complete lightweight record; a run with heavy outputs adds an optional
sha256-addressed mirror layer, with the sha256 computed from the actual bytes and
a mirror url at the run's public artifact route.

### The analogy, plainly

On HuggingFace a model card is free, git-native, and describes a model; a Space
is the card wired to hardware that can run it, and the free card is what drives
people to paid compute. Here the experiment card is free, git-native, and
describes a computation (its recipe and what a source reported); the MCG run is
that recipe wired to an engine that can compute it, and the free card is what
drives people to paid compute. The card is the commons (what is true, its
provenance, its map-version pin); the Space is the product (execution, storage,
billing). GOVERNANCE.md draws the same line: "the commons owns the ledger and its
laws; companies own tools and products built on top."

## 2. The three shareable things, and the flywheel

Three things become URLs, one per side of the boundary plus one that crosses it:

1. **A simulation** lives on MCG: a run, shared by a guest link
   `${APP_BASE_URL}/s/<token>` (the human entry point), with its machine-readable
   record at `GET /api/shared/:token/record`.
2. **A recipe** lives on openmaterials: an experiment card, shared by
   `experiment/#ref=...` (or, for a pasted record, the Playground's `#x=`
   fragment).
3. **A run-from-a-recipe** lives on MCG: the recipe deep-linked into the compute
   wizard, `#/new/<node_id>` prefilled from the card (materialscodegraph#65,
   merged).

Put end to end, these are a flywheel:

```
recipe card (openmaterials)
   -> "Run on MaterialsCodeGraph" (#25, a deep link)
   -> MCG run (#/new/<node_id>, prefilled)
   -> SimulationRecord JSON (materialscodegraph#74, byte-identical)
   -> uploaded back to openmaterials as evidence (the upload ingress)
   -> a new shareable recipe card, itself carrying a Run button
   -> ... (repeat)
```

Each lap adds a computed value to the commons (a new card, entering through the
normal gated contribution path, never as a side effect of a link) and a run to
MCG (paid compute). The free card feeds the paid Space, and the paid Space feeds
the free commons back. That reciprocity is the whole reason to keep the two
identities strong: if either side could rewrite the other's truth, the loop would
stop being trustworthy.

## 3. The three seams

Each seam is optional and additive, tied to an issue, and marked with the side it
ships on. None touches the hashing path.

### (a) "Run on MaterialsCodeGraph" on the experiment page

- **Ships on:** openmaterials (UI only).
- **Issue:** #25.
- **What:** for a card whose node is computable, add one more `a.btn` in
  `renderDetail`'s existing action row (`docs/experiment/index.html`, lines
  276-278, alongside "Copy link" and "View on the map"), deep-linking to MCG
  prefilled from the recipe. The fields are already in scope: each record in the
  group carries `variable` (the node id), `material`, and `conditions` (see the
  instance file cited above), which is exactly what MCG's `#/new/<node_id>`
  expects (materialscodegraph#65). Prefill uses the card's default values when
  they are present; where the recipe is node-only, the link still lands the
  wizard on the define step for that node's kind.
- **Hidden when there is no wired engine.** The link renders only when the node
  is computable, and fails silently otherwise (no link, no harm, the card is
  identical). Issue #25 proposes two ways to decide, both keeping the page
  storage-free: a small static capability list shipped alongside the other
  `docs/data/*.json`, or a soft capability fetch that renders nothing on any
  error (the same defensive pattern the Playground uses, e.g. its
  `.catch(function(){ return []; })` on every optional load,
  `docs/play/index.html` lines 245-247). Which one is a decision for you (open
  question Q3 below).
- **Commons-pure.** It adds no map data, mints no node, attaches no value, and
  touches no record. The recipe fields are read from already-published records to
  build a URL. Evidence still enters only through the gated contribution process.

### (b) Upload-a-JSON ingress

- **Ships on:** openmaterials (UI only).
- **Issue:** the companion upload issue (the ingress half of the same arc #25
  calls out).
- **What:** let someone paste or drop a SimulationRecord and render it in place,
  validated against the light gates, with **no git and no storage**. The
  precedent is the Playground's Experiment tab, which already does the render and
  the `#x=` round-trip client-side (`renderExperiment`, `docs/play/index.html`).
  The validation to surface is the one already written: `validate_light` in
  `omai/simulations.py` (recompute `recipe_id`, reject a stated `id` that
  disagrees, check the node pin when a node is named, shape-check any pointers,
  and stay honest about a node-unresolved record rather than rejecting it). A JS
  mirror of that check on the page, or a documented subset, keeps the ingress
  faithful to the Python contract.
- **It already round-trips with MCG.** Because materialscodegraph#74 emits a
  byte-identical record, a record fetched from `GET /api/shared/:token/record`
  pastes straight in, renders, and (having a `sha256`-addressed mirror when the
  run had heavy outputs) verifies through `verify_simulation`. The ingress needs
  nothing from MCG beyond the record MCG already serves.
- **Commons-pure.** Rendering a pasted record writes nothing and stores nothing;
  it is a client-side view, exactly like the Playground today.

### (c) The reciprocal MCG-run to openmaterials-card link

- **Ships on:** MCG.
- **What:** from an MCG run, a "view this run's card" link back to the
  openmaterials experiment card for its recipe (the egress of seam (a), run in
  reverse). This is noted here for completeness so the loop is symmetric on paper,
  but it ships MCG-side and is out of scope for this repo. A grep of the MCG
  frontend today finds no such back-link yet, so it is genuinely unbuilt, not
  merely undocumented. It is listed so the maintainer can see the whole loop and
  weigh in on what a canonical card URL should be (open question Q1), since both
  the "Run" link and this back-link need one.

### The naming seam: `provider` on mirrors (already open as #23)

- **Ships on:** openmaterials (format), MCG (first populator).
- **Issue:** #23, already filed.
- **What:** one optional free-form `provider` key on a mirror entry
  (`"mirrors": {"trajectory.nc": {"url": "...", "provider": "materialscodegraph"}}`),
  naming who holds the bytes, plus a one-line surfacing in `verify_simulation` (it
  already reads each mirror `loc` for its `url`; echoing `loc.get("provider")`
  onto the report entry closes the provenance loop). This is the naming seam for
  hosted artifacts: openmaterials standardizes the name, MCG fills it in as the
  first resolver, Zenodo or an institutional archive could fill it in as others.
  It is identity-safe by construction (mirrors never reach `recipe_id`), so it is
  the same shape as seam (a): the commons names a capability, the product
  provides it.

## 4. The invariants

These are the properties that keep both repos' identity strong and the boundary
healthy. They are the reason the flywheel is safe to turn.

- **openmaterials holds zero bytes.** Heavy artifacts live on MCG (or Zenodo, or
  any object store under the owner's own terms) and are referenced by `sha256` in
  the `mirrors` layer, outside the hashed claim. This is not a nicety, it is the
  governance rule: "Identity in the commons, bulk on the platform" (GOVERNANCE.md,
  "Data ownership and fairness"). `recipe_id` never receives `artifacts` or
  `mirrors`; `_canonical_recipe` hashes only the recipe. Moving bytes, renaming a
  bucket, or adding a mirror cannot change a record's id or orphan a value that
  cites it.

- **The record MCG serves is byte-identical to what openmaterials mints.** This
  is the load-bearing invariant of the whole integration, and it is already true:
  materialscodegraph#74 proves it with an oracle test that imports the real
  `omai.simulations` and asserts equality (sorted keys, `separators=(",",":")`,
  the `FLOAT_DECIMALS=6` rule, url dropped from identity). `verify_simulation` is
  the check on the openmaterials side: it fetches each mirror and compares the
  sha256 to the manifest, returning a dated report. Verification is a report,
  never a gate (a record whose bytes moved is stale, not wrong).

- **Every cross-link is optional and additive, and degrades gracefully.** The Run
  link renders only for computable nodes and vanishes on any error; the upload
  ingress renders a pasted record with no server; the `provider` key is one
  optional string. A build with no capability list, or with MCG unreachable, is
  the experiment page exactly as it is today. Nothing required changes anywhere.

- **The commons owns identity and the gates; the product owns execution, storage,
  and billing.** Neither can cannibalize the other, because the split is
  structural, not contractual: the recipe (identity) is git-native and free and
  cannot be locked up; the bytes and the compute are the product and are never
  ingested into the commons. GOVERNANCE.md, "The boundary rule": "Anything that
  decides what is true on the map ... belongs to the initiative." A run's link
  points at a product; the product's record points back at the commons; neither
  writes the other's ledger.

## 5. A phased sequence

A suggested order, smallest and most independent first. Each phase is a separate
PR gated on your review; nothing here presumes the sequence, it just proposes one.

- **Phase 0 (done).** MCG emits the byte-identical record (materialscodegraph#74)
  and receives the compute deep link (materialscodegraph#65). The receiving ends
  exist, so the openmaterials-side seams have something real to point at.
- **Phase 1: `provider` on mirrors (#23).** The smallest, purely-additive change:
  document one optional key and add the one-line `verify_simulation` surfacing,
  with a test that a `provider` string round-trips and shows up in the report
  while `canonical_id` stays unchanged. It unblocks nothing else but is the
  cleanest first step and settles the naming pattern the other seams reuse.
- **Phase 2: upload-a-JSON ingress (seam (b)).** Reuses the Playground's existing
  `renderExperiment` and the `validate_light` contract; adds paste/drop and the
  light-gate surfacing. No dependency on the Run link. It makes an MCG-served
  record directly viewable and verifiable in the commons.
- **Phase 3: "Run on MaterialsCodeGraph" (#25).** One `a.btn` in `renderDetail`,
  gated on the capability check chosen in Q3. Depends only on the deep-link target
  (materialscodegraph#65, already merged).
- **Phase 4 (MCG-side, noted not owned): the reciprocal back-link (seam (c)).**
  Ships on MCG once the canonical card URL is decided (Q1). Closes the loop.

## Open questions for the maintainer

These are decisions for you, not assertions. They are the interface and identity
choices this note deliberately does not make.

- **Q1. What is the canonical URL of a live SimulationRecord card?** The Run link
  (seam a) and the reciprocal back-link (seam c) both need a stable, addressable
  card URL, and the current `#ref=` scheme addresses a *paper* ref
  (`paper:<slug>`, grouping instances by `source.ref`), not a single
  recipe-identified record. Options to weigh: keep `#ref=` for paper/source cards
  and address a live record through the Playground's `#x=` fragment (the record
  rides in the URL, no new route); or introduce a record-addressed ref (for
  example an `#x=` on the experiment page, or a `#record=<recipe_id>` that
  resolves a committed `docs/data/simulations/<slug>.json`); or something else.
  This is the one decision the rest hangs on, so it is first.

- **Q2. Does a card ever address an MCG *instance* (a specific run) as opposed to
  a recipe?** A recipe is content-addressed and side-agnostic; a run is an MCG
  object behind a guest token (`/s/<token>`). Should the commons ever link to a
  specific run, or only ever to a recipe (with the run reachable through the
  card's mirrors)? The invariants favor recipe-only from the commons, but the
  call is yours.

- **Q3. Static capability list, or soft capability fetch, for the Run link's
  computability check (#25)?** The static list keeps the page dependency-free and
  lets the commons declare which node kinds have a resolver; the soft fetch is
  always current but adds an optional network call. Both fail silent. Issue #25
  leans static; confirming the choice (and, if static, where the list lives among
  `docs/data/*.json`) is yours.

- **Q4. How faithful should the upload ingress's client-side validation be to
  `validate_light`?** A full JS re-implementation of the light gates, a documented
  subset (recompute the id, check the stated id, shape-check pointers), or render
  first and annotate gaps as the Playground does today? This trades strictness
  against page weight.

- **Q5. Is `provider` free-form, or should the commons keep a short registry of
  known provider strings?** #23 proposes free-form. A tiny registry would make
  `provider` values comparable across records at the cost of a list to maintain.
  Your call on whether that is worth it.

## What this note does not do

It writes no code, changes no gate, mints no node, and touches no record. It is a
shared picture and a set of questions. The interface and identity decisions
(especially Q1) are yours to make; the seams above are drafted to be reshaped
around whatever you decide.
