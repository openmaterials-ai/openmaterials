# map: the openmaterials protocol artifact

This directory is the versioned map itself: a log-first, content-addressed
graph of typed physical quantities (nodes) related by executable formulas
(edges). It is the protocol artifact anyone can fork, a peer of `omai/` and
`docs/` rather than a view inside them. The Python operator layer authors it;
the source of truth is the data here.

Every change is one record in `log.jsonl`, one canonical-JSON line each, with
the shape `{seq, op, payload, author, date, reason, prev, version}`. The op is
one of `add_node`, `add_edge`, `edit_meta`, `deprecate`, `supersede`, `equate`.
A payload carries everything needed to rebuild the map without importing any
Python module: the full identity dict that was hashed, and for edges the
formula as a sympy srepr string plus display latex.

Contributions enter through the gated `Store.propose` (which validates an
ordered contribution against the six gates before any record lands) or through
`python -m omai.sync` (which diffs the Python operator layer against
`current/` and proposes change records for review).

The `version` field chains the log: `version = sha256(prev + canonical(record
without version))`, where `prev` is the previous record's version and the
genesis record's prev is 64 zeros. This makes the history tamper-evident and
path-dependent; `Store.verify()` recomputes every link, checks the chain and
the dense seq, and reports any dangling reference.

`current/nodes.json` and `current/edges.json` are the materialized current
view, regenerated from a full replay on every push and never hand-edited. They
are a reviewable mirror keyed by uid; `verify()` compares them structurally
against the replay, so a stale or truncated file is caught rather than trusted.

`GENESIS` holds the frozen genesis version hash,
`e6e8044e92039696417b53b220b0f3f10559a286b0eaabbe7ea4167ff510f6cd`, produced by
the deterministic migration on the genesis date 2026-07-07 (51 nodes, 49 edges).
The migration reads no clock and no randomness, so the hash is reproducible from
the code alone; a repo-state test asserts the committed artifact still matches a
fresh `run_genesis`, the drift alarm between the Python layer and the frozen
store.
