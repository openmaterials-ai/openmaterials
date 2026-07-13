"""Learned shortcut edges: ML surrogates as declared, non-authoritative paths.

A machine-learned surrogate, seen from the map, is a *shortcut through the
DAG*: an alternative producing edge (Pattern C of the DAG extension rules)
whose claim is not a symbolic formula but "this edge approximates the
composite of a declared path of exact edges, usually while amortizing away
that path's most expensive boundary input." The canonical example is the
third-order wall in thermal transport: the exact path runs

    ForceConstants[order=3] + Frequency + Eigenvectors + Temperature
        --compute_linewidth[channel=anharmonic_3ph]--> Linewidth

and a trained surrogate produces the same Linewidth node from the harmonic
geometry alone, with ``ForceConstants[order=3]`` amortized into weights.

`LearnedOperator` makes that claim first-class and machine-checkable:

  * ``shortcuts`` names the exact edges whose composite the surrogate
    approximates. The claim is *anchored to the map*: the learned edge's
    outputs must be exactly the terminal outputs of that sub-DAG, and its
    inputs must not read anything the sub-DAG produces (or anything
    downstream of it, which would be a cycle).
  * ``amortized_inputs`` (computed) is what the shortcut buys: the path
    boundary inputs the surrogate does not need at inference time.
  * Scheme discipline is inherited, not optional: a surrogate trained on
    labels computed under scheme S is a surrogate *of the path under
    scheme S*. The learned edge must re-declare the scheme entries of the
    path's terminal edge verbatim; a surrogate of a different scheme
    shortcuts a different path.
  * A learned edge is **never authoritative**. It is not sympy-executable
    (``is_executable_in_sympy`` is forced False), it cannot settle
    cross-code agreement at an ObservableSpace, and its values enter the
    map only as evidence tagged with ``model_ref``, comparable against
    the exact path wherever both are available. Truth stays with the
    exact edges and the evidence; the shortcut is priced speed.

Identity and provenance: a learned edge's claim is versioned by
``model_ref`` (a content-addressed reference to the trained artifact) and
``trained_on`` (references to the label sources). Retraining a model is a
new ``model_ref`` and therefore a new claim, even if the topology of the
shortcut is unchanged.

Validation (`validate_learned`) is the objective part of review, in the
spirit of the contribution gates: topology (the shortcut really is a
shortcut of the named path), acyclicity (inputs do not depend on outputs),
scheme inheritance, and provenance presence. Whether the surrogate is any
*good* is not a gate: that is what attaching its predictions as evidence,
next to the exact path's values, makes visible and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from omai.operator.operator import Operator
from omai.operator.space import Space

__all__ = [
    "LearnedOperator",
    "path_boundary",
    "validate_learned",
]


def path_boundary(
    edges: tuple[Operator, ...] | list[Operator],
) -> tuple[frozenset[Space], frozenset[Space]]:
    """Boundary inputs and terminal outputs of a sub-DAG of edges.

    ``boundary`` is every space consumed by some edge of the path but
    produced by none of them (the path's external dependencies).
    ``terminal`` is every space produced by some edge of the path but
    consumed by none of them (what the path delivers downstream).
    """
    produced: set[Space] = set()
    consumed: set[Space] = set()
    for op in edges:
        produced.update(op.outputs)
        consumed.update(op.inputs)
    return frozenset(consumed - produced), frozenset(produced - consumed)


@dataclass(frozen=True)
class LearnedOperator(Operator):
    """An ML surrogate edge that short-circuits a declared path of exact edges.

    Inherits the full `Operator` surface (typed inputs/outputs, schemes,
    parameters). The ``formula`` slot, when set, is a structural ansatz
    (e.g. an analytic carrier the learned part modulates), never an
    executable definition: ``is_executable_in_sympy`` is forced False.
    """

    # Names of the exact edges whose composite this surrogate approximates.
    shortcuts: tuple[str, ...] = ()
    # Content-addressed reference to the trained model artifact. Retraining
    # mints a new model_ref: same topology, new claim.
    model_ref: str = ""
    # References to the label sources the model was trained on (dataset
    # rails, paper refs, campaign hashes). Same citation discipline as
    # evidence: a surrogate that cannot cite its labels does not enter.
    trained_on: tuple[str, ...] = ()
    # Prose statement of the domain of validity (material classes, ranges,
    # held-out benchmarks). Rendered with the edge; not machine-checked.
    validity: str = ""
    # How the surrogate reports per-prediction uncertainty (ensemble
    # variance, conformal interval, ...). Empty means "none", which is a
    # legitimate but visible statement.
    uncertainty: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.shortcuts:
            raise ValueError(
                f"learned operator {self.name!r} must declare the exact-edge "
                "path it shortcuts (non-empty `shortcuts`)"
            )
        if not self.model_ref:
            raise ValueError(
                f"learned operator {self.name!r} must carry a content-addressed "
                "`model_ref`; a surrogate without a versioned artifact is not "
                "a citable claim"
            )
        # A learned edge is never symbolically executable, whatever its
        # ansatz formula looks like.
        object.__setattr__(self, "is_executable_in_sympy_override", False)

    @property
    def is_authoritative(self) -> bool:
        """Learned edges never decide truth at a node."""
        return False

    def amortized_inputs(
        self, edges: tuple[Operator, ...] | list[Operator]
    ) -> frozenset[Space]:
        """The path boundary inputs this surrogate does not read.

        This is what the shortcut amortizes into weights (e.g. the
        third-order force constants). May be empty: a surrogate with the
        full boundary as inputs is a pure-speed emulator, which is legal.
        """
        path = _resolve_path(self, edges)
        boundary, _ = path_boundary(path)
        return boundary - set(self.inputs)


def _resolve_path(
    learned: LearnedOperator,
    edges: tuple[Operator, ...] | list[Operator],
) -> list[Operator]:
    """Resolve `learned.shortcuts` names against `edges`, in declared order."""
    by_name = {op.name: op for op in edges}
    missing = [name for name in learned.shortcuts if name not in by_name]
    if missing:
        raise KeyError(
            f"learned operator {learned.name!r}: unknown shortcut edge(s) "
            f"{missing!r}"
        )
    return [by_name[name] for name in learned.shortcuts]


def _descendants(
    roots: frozenset[Space],
    edges: tuple[Operator, ...] | list[Operator],
) -> set[Space]:
    """Every space reachable downstream of `roots` through `edges`."""
    frontier = set(roots)
    reached: set[Space] = set()
    while frontier:
        space = frontier.pop()
        for op in edges:
            if space in op.inputs:
                for out in op.outputs:
                    if out not in reached:
                        reached.add(out)
                        frontier.add(out)
    return reached


def validate_learned(
    learned_edges: tuple[LearnedOperator, ...] | list[LearnedOperator],
    edges: tuple[Operator, ...] | list[Operator],
    nodes: tuple[Space, ...] | list[Space],
) -> list[str]:
    """Return the learned-edge discipline violations (empty if clean).

    Checks, per learned edge L:

      * L's name does not collide with an exact edge.
      * Every name in L.shortcuts resolves to an exact (non-learned) edge.
      * L.outputs equals the terminal outputs of the shortcut sub-DAG:
        the surrogate claims exactly what the path delivers, no more and
        no less.
      * L.inputs are known nodes, none of them produced by the path, and
        none of them downstream of the path's outputs in the full DAG
        (acyclicity of the shortcut).
      * L re-declares the scheme entries of the path's terminal edges
        verbatim (a surrogate of scheme S is a surrogate of the path
        under scheme S).
      * Provenance: `trained_on` entries are non-empty.

    The gates are the objective part; whether the surrogate is accurate is
    settled by evidence attached next to the exact path's values, never
    here.
    """
    errors: list[str] = []
    node_set = set(nodes)
    exact_names = {op.name for op in edges}

    for learned in learned_edges:
        prefix = f"{learned.name}"

        if learned.name in exact_names:
            errors.append(
                f"{prefix}: name collides with an exact edge; a learned "
                "shortcut is a distinct claim and needs a distinct name"
            )

        try:
            path = _resolve_path(learned, edges)
        except KeyError as err:
            errors.append(f"{prefix}: {err.args[0]}")
            continue

        for path_edge in path:
            if isinstance(path_edge, LearnedOperator):
                errors.append(
                    f"{prefix}: shortcut path may only contain exact edges, "
                    f"found learned edge {path_edge.name!r}"
                )

        boundary, terminal = path_boundary(path)

        if set(learned.outputs) != terminal:
            errors.append(
                f"{prefix}: outputs {sorted(s.name for s in learned.outputs)} "
                f"must equal the shortcut path's terminal outputs "
                f"{sorted(s.name for s in terminal)}"
            )

        produced_by_path = {out for op in path for out in op.outputs}
        downstream = _descendants(frozenset(learned.outputs), edges)
        for inp in learned.inputs:
            if inp not in node_set:
                errors.append(f"{prefix}: input {inp.name!r} is not a map node")
            if inp in produced_by_path:
                errors.append(
                    f"{prefix}: input {inp.name!r} is produced by the shortcut "
                    "path itself; a shortcut may not read what it claims to "
                    "bypass"
                )
            elif inp in downstream:
                errors.append(
                    f"{prefix}: input {inp.name!r} is downstream of the "
                    "shortcut's outputs (cycle)"
                )

        # Scheme inheritance from the terminal edges of the path: the edges
        # that produce the terminal outputs set the convention the surrogate
        # was trained under.
        for op in path:
            if not (set(op.outputs) & terminal):
                continue
            for key, value in op.schemes.items():
                if learned.schemes.get(key) != value:
                    errors.append(
                        f"{prefix}: must re-declare scheme {key!r}={value!r} "
                        f"of terminal path edge {op.name!r} (found "
                        f"{learned.schemes.get(key)!r}); a surrogate trained "
                        "under a different scheme shortcuts a different path"
                    )

        if not learned.trained_on:
            errors.append(
                f"{prefix}: trained_on is empty; a surrogate that cannot "
                "cite its labels does not enter (same citation discipline "
                "as evidence)"
            )
        for ref in learned.trained_on:
            if not ref:
                errors.append(f"{prefix}: empty entry in trained_on")

    return errors
