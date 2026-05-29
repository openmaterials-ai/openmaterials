"""Redundancy cross-check: compute a target several ways, compare under typing.

The DAG is over-determined — more routes to a quantity than quantities.
``cross_check`` runs each route via ``compute`` and pairwise-compares the
results with ``compare_representations``. Verdicts honor the target's gauge
typing: routes to an ObservableSpace must agree (divergence is a bug);
routes to a HiddenSpace are NOT_COMPARABLE per-element (divergence is
predicted, not flagged).
"""
from __future__ import annotations

from dataclasses import dataclass

from omai.operator.space import Space
from omai.representation.compare import compare_representations
from omai.representation.executor import ComputeResult, Source, compute


@dataclass(frozen=True)
class Route:
    label: str
    result: ComputeResult


@dataclass(frozen=True)
class PairVerdict:
    label_a: str
    label_b: str
    status: str
    max_relative_residual: float


@dataclass(frozen=True)
class ValidationReport:
    target: str
    routes: tuple[Route, ...]
    pairwise: tuple[PairVerdict, ...]

    def ok(self) -> bool:
        """True unless any pair is an actual anomaly (UNEXPECTED_*)."""
        return all(
            p.status not in ("UNEXPECTED_DISAGREE", "UNEXPECTED_AGREE")
            for p in self.pairwise
        )

    def render(self) -> str:
        lines = [f"ValidationReport[{self.target}]  ({len(self.routes)} routes)"]
        for p in self.pairwise:
            lines.append(
                f"  {p.label_a:<12s} vs {p.label_b:<12s} : {p.status:<20s} "
                f"max_rel={p.max_relative_residual:.3e}"
            )
        lines.append(f"  ok = {self.ok()}")
        return "\n".join(lines)


def cross_check(
    target: Space,
    routes: dict[str, dict[str, Source]],
    *,
    rtol: float = 1e-6,
    atol: float = 0.0,
    constants: dict[str, float] | None = None,
) -> ValidationReport:
    """Compute ``target`` via each route's source set; pairwise-compare.

    Each route is a label -> sources dict (different codes per leaf gives
    cross-code redundancy). Verdicts come from compare_representations,
    which derives expected-agreement from the target's ObservableSpace/
    HiddenSpace typing.
    """
    computed: list[Route] = [
        Route(label=label, result=compute(target, srcs, constants=constants))
        for label, srcs in routes.items()
    ]
    pairwise: list[PairVerdict] = []
    for i in range(len(computed)):
        for j in range(i + 1, len(computed)):
            a, b = computed[i], computed[j]
            cmp = compare_representations(
                a.result.representation, b.result.representation,
                rtol=rtol, atol=atol,
            )
            pairwise.append(PairVerdict(
                label_a=a.label, label_b=b.label,
                status=cmp.status,
                max_relative_residual=cmp.max_relative_residual,
            ))
    return ValidationReport(
        target=target.name, routes=tuple(computed), pairwise=tuple(pairwise),
    )
