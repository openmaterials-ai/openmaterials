# Substrate doc restructure: design

**Date**: 2026-05-29
**Target**: `docs/operator_representation_substrate.tex` (+ rebuilt PDF). Not touching `dag.html`.
**Goal**: restructure the canonical architecture reference to read like a paper. Motivation-forward, deduplicated, every substantive piece preserved. Project-specific content consolidated, not scattered.

## Decisions (settled in brainstorming)

1. **Purpose**: paper-styled reference. Keep the formal model, the demonstration, and the project specifics (implementation layout, status, deferred decisions); consolidate the specifics into one "Status, scope & roadmap" section near the end.
2. **AI motivation framing**: build to it. Open with the concrete pain, state the thesis, then reveal grounded AI agents (a finite, typed, physically meaningful action space instead of text tokens) as the culminating payoff. The claim "the semantic layer is the key to the future of AI" lands as the culmination, not a buried bullet.
3. **Vocabulary**: replace "atom / atomic unit" with **building block** everywhere (collides with literal atoms in a materials doc; "primitive" collides with "primitive cell", so avoid it too).
4. **Style**: no em dashes anywhere (use commas, colons, parentheses, or split the sentence). Concise prose: tighten, cut padding, no restating.
5. **No phase labels in the body**: do not sprinkle "Phase 1 / Phase 2 / Phase N / Sprint" through the text. The body (§1 to §6) describes what the framework does in the present tense; where something is not yet modeled it says so plainly (for example "the upstream from Potential to ForceConstants is declared but not modeled") without a phase tag. All forward-looking and deferred content lives in one end section, "Next steps".

## Target structure

- **Abstract**: tighten; one forward sentence on the verification and AI payoff. State the Potential-upstream as not-modeled plainly (no phase tag); roadmap goes to Next steps.
- **§1 Introduction** (build-to-it arc): 1.1 the problem (input files are syntactic not semantic; the two questions they cannot answer; brief MCG retrospective). 1.2 the thesis (the building block is the typed operation between physics states). 1.3 why it matters, in increasing reach: cross-code reconciliation now, derived error bounds and formal verification near-term, grounded AI agents as the culmination.
- **§2 The semantic layer: two worlds, one bridge** (core idea, stated once): 2.1 operator world / numeric world / representation-functor bridge. 2.2 witness-as-state, condensed. 2.3 the chain in motion (operator, represent, compare).
- **§3 Driving principles**: the 13 commitments, placed after the core idea so they read as consequences, each with a one-line rationale, grouped into clusters (separation; identity and provenance; errors; Lean-compatibility). Principles fully covered elsewhere become brief pointers.
- **§4 Formal model** (deduped): state; operation (parameterized identity); workflow; DAG extension rules (Patterns A/B/C); discretization; representation (unit times normalization); star topology; gauge discipline (HiddenSpace + GaugeAction); representation functor. Unit-free stated once here. Errors: note only that the type system reserves slots for approximation error (on operations) and discretization error (on representations); the composition algebra is not implemented, so it is described in Next steps, not presented here as a capability.
- **§5 The runtime: executing and validating the DAG** (new home for material now marooned in Formal Definitions): `compare` (five-status); the validation engine (compute / compose / cross-check); dimensional reconciliation (the SI-scale monomial bridge).
- **§6 Demonstration: lattice thermal transport** (results, largely intact): the 46/47 DAG, nodes, edges, the tikz figure, the seven adapters (two tiers), the silicon verification table, cross-paradigm kappa. Present tense, no phase tags.
- **§7 Implementation & current status**: the package layout (`omai.operator`, `omai.representation`, `omai.thermal_transport`) and what the framework does today, stated factually in the present tense. No phase labels.
- **§8 Next steps** (the single home for everything forward-looking): the deferred and planned work, consolidated. Error-composition algebra; when and whether to project into Lean; provenance equivalence; the MD-kappa worked examples still to wire; and the broader directions (Lean verification, theory-experiment integration, grounded AI agents). This is the only place phase/roadmap content appears.
- **§9 Conclusion**: tight restatement. The typed operation is the right building block; the semantic substrate is what makes reconciliation, verification, and grounded AI possible.
- **Appendix A: Lean-compatibility disciplines**: the three disciplines (closed unions for physics types, no physics invariants encoded in Python types, operation parameters always recorded in output metadata) that keep the operator layer transliterable to Lean. Moved out of the main flow into an appendix; the question of when and whether to project to Lean stays in §8.

## Dedup moves

- Two-worlds separation: stated once in §2.1. Abstract and Principles point to it.
- Unit-free: stated once in §4. Principles points to it.
- Lean: the three disciplines live in Appendix A; "when and whether to project into Lean" lives in §8 Next steps; the `compose_path` / T3-evolve note folds into §5. Not three scattered places.
- Errors: the "designed-for" principle stays a one-liner in §3; all error-composition detail (currently in a "total error" subsection and inline "(Phase 2 capability)" tags) moves to §8 Next steps. The body does not present error composition as something the framework does today.
- Witness-as-state: about 50 lines now, condense to the proposition / witness / representation triple.
- Validation engine and dimensional reconciliation: relocate out of Formal Definitions into §5.

## Preserve (no content loss)

The formal model, the gauge discipline (HiddenSpace fields, GaugeAction, the U(1)-phase machine-verified example, crystal-symmetry-as-declaration), the DAG-extension Patterns A/B/C, the full thermal-transport demonstration (46/47 DAG, tikz figure, seven adapters with the not-exposed cross-routing, silicon verification table with the 1/(4 pi) decomposition, cross-paradigm kappa), the validation engine, dimensional reconciliation, the Lean disciplines, all deferred-decision content.

## Execution note

A prose rewrite of one cohesive document needs a single authoring pass (deduping and section flow require the whole doc in one context), not parallel subagents. Execute inline, single-pass, then rebuild the PDF (two pdflatex runs) and verify no substantive content was dropped.

## Success criteria

- The .tex follows the target structure; motivation is forward and builds to the AI payoff.
- No em dashes anywhere in the document.
- No "Phase 1 / Phase 2 / Phase N / Sprint" labels in the body (§1 to §7); all forward-looking content sits in §8 Next steps.
- "building block" replaces "atom / atomic unit"; no remaining "the atom is..." phrasing.
- The five dedup moves are done; each formerly-repeated point appears once with pointers elsewhere.
- All preserved content is present.
- PDF rebuilds clean (two passes, exit 0).
- Counts stay 46/47; the seven adapters remain listed.
