"""The semantic layer: fuzzy language in, checkable identity out.

The map speaks symbolic language (typed nodes, sympy edges, proven
dimensions). LLMs and the literature speak semantic language
("phonon-dispersion-calculation", "quasi-harmonic-approximation"). This
module is the bridge: every map element carries its cloud of surface labels
(docs/data/semantics.json, uid-pinned, regenerated with the map), and
resolve(label) turns any fuzzy phrase into ranked, typed identities.

Resolution is DETERMINISTIC in v1: normalization, exact-alias hits, token
containment. No embeddings: an auditable semantic layer beats a plausible
one, and ranking ties with embeddings can arrive later without changing
the contract. Labels are metadata, never identity: adding an alias touches
no store record.

The curated ALIASES seed is reviewed like vocabulary. Its first entries are
the RA2 method-map labels visible in Giuseppe's screenshots (the 16k-paper
skill vocabulary Bohan's tooling emits); full RA2 alignment lands as
index/semantics/ra2.json when the corpus file arrives (spec 2026-07-12).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parent.parent / "docs"

# ---------------------------------------------------------------------------
# Curated aliases: surface label -> map element id (node or edge).
# Reviewed like vocabulary; kebab-case entries follow the RA2 convention.
# A label may map to SEVERAL ids (a family); resolve returns all, ranked.
# ---------------------------------------------------------------------------
ALIASES: dict[str, tuple[str, ...]] = {
    # RA2 screenshot seed (2026-07-12)
    "phonon-thermal-conductivity": (
        "ThermalConductivity[bte_solver=rta]",
        "ThermalConductivity[bte_solver=direct_inverse]",
        "ThermalConductivity[transport_model=qhgk]",
        "ThermalConductivity[transport_model=wigner]",
    ),
    "phonon-dispersion-calculation": ("Frequency", "compute_dispersion"),
    "quasi-harmonic-approximation": (
        "QHAGibbsEnergy", "ThermalExpansion", "compute_qha_gibbs",
        "compute_thermal_expansion", "compute_bulk_modulus_qha",
    ),
    "md-transport-coefficient-estimation": (
        "ThermalConductivity[transport_model=green_kubo]", "Diffusivity",
        "contract_kappa[transport_model=green_kubo]", "contract_diffusivity",
    ),
    "periodic-dft-electronic-structure-calculation": (
        "TotalEnergy", "solve_ground_state",
    ),
    "structure-relaxation": ("Structure", "solve_ground_state"),
    "elastic-constant-calculation": ("ElasticConstants", "compute_elastic_constants"),
    "crystal-polarization-calculation": ("BornCharges",),
    "force-field-parameterization": ("Potential",),
    "electronic-density-of-states": ("ElectronicDOS", "compute_electronic_dos"),
    "phonon-density-of-states": ("PhononDOS", "compute_dos"),
    "free-energy-surface": ("PotentialOfMeanForce", "sample_pmf"),
    "path-integral-molecular-dynamics": (
        "QuantumKineticEnergy", "HeatCapacity[method=pimd]",
        "sample_quantum_kinetic_energy", "sample_quantum_heat_capacity",
    ),
    # Honest NO-HOME markers live in the alignment files, not here: an alias
    # must point at something that exists (the gate below enforces it).
}

_STOP = frozenset({"calculation", "estimation", "computation", "analysis",
                   "the", "a", "an", "of", "and"})


def normalize(label: str) -> str:
    """kebab/snake/camel/space forms collapse to one spaced lowercase form."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(label))
    s = s.replace("-", " ").replace("_", " ").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(label: str) -> frozenset[str]:
    return frozenset(t for t in normalize(label).split() if t not in _STOP)


def _auto_labels(el: dict) -> list[str]:
    """Surface forms derivable from the element itself."""
    out = [el["id"], normalize(el["id"])]
    if el.get("tag"):
        out.append(el["tag"].replace("_", " "))
    if el.get("symbol"):
        out.append(str(el["symbol"]))
    return sorted({x for x in out if x})


def build_semantics(graph: dict) -> list[dict]:
    """The uid-pinned label cloud for every node and edge on the map."""
    curated: dict[str, list[str]] = {}
    known_ids = {n["id"] for n in graph["nodes"]}
    known_ids.update(l["op"] for l in graph["links"] if l.get("op"))
    for label, targets in ALIASES.items():
        for t in targets:
            if t not in known_ids:
                raise ValueError(
                    f"curated alias {label!r} points at {t!r}, which is not "
                    f"on the map: aliases must resolve to real elements")
            curated.setdefault(t, []).append(label)

    entries = []
    for n in graph["nodes"]:
        entries.append({
            "id": n["id"], "uid": n.get("uid"), "kind": "node",
            "labels": _auto_labels(n),
            "curated": sorted(curated.get(n["id"], [])),
        })
    seen_ops = set()
    for l in graph["links"]:
        op = l.get("op")
        if not op or op in seen_ops:
            continue
        seen_ops.add(op)
        entries.append({
            "id": op, "uid": l.get("op_uid"), "kind": "edge",
            "labels": sorted({op, normalize(op)}),
            "curated": sorted(curated.get(op, [])),
        })
    return entries


def resolve(label: str, semantics: list[dict], limit: int = 8) -> list[dict]:
    """Fuzzy label -> ranked typed identities. Deterministic.

    Scoring: exact curated alias 1.0; exact auto label 0.9; all query
    tokens contained in an element's token set 0.6 + coverage bonus;
    empty result means NO-HOME (an honest coverage gap, not an error).
    """
    q = normalize(label)
    qt = _tokens(label)
    hits = []
    for e in entries_iter(semantics):
        score, why = 0.0, None
        if q in (normalize(c) for c in e["curated"]):
            score, why = 1.0, "curated alias"
        elif q in (normalize(a) for a in e["labels"]):
            score, why = 0.9, "exact label"
        elif qt and qt <= _tokens(" ".join(e["labels"]) + " " + e["id"]):
            cov = len(qt) / max(1, len(_tokens(e["id"])))
            score, why = 0.6 + min(0.2, 0.2 * cov), "token containment"
        if score:
            hits.append({"id": e["id"], "uid": e["uid"], "kind": e["kind"],
                         "score": round(score, 3), "why": why})
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits[:limit]


def entries_iter(semantics):
    return semantics


def write_semantics(graph: dict, out: Path | None = None) -> Path:
    out = out or (_DOCS / "data" / "semantics.json")
    entries = build_semantics(graph)
    out.write_text(json.dumps(entries, indent=0, sort_keys=True))
    return out


if __name__ == "__main__":  # pragma: no cover - CLI: rebuild + demo resolve
    import sys
    graph = json.loads((_DOCS / "data" / "graph.json").read_text())
    path = write_semantics(graph)
    sem = json.loads(path.read_text())
    print(f"{len(sem)} elements -> {path}")
    for q in (sys.argv[1:] or ["phonon-thermal-conductivity"]):
        print(f"\nresolve({q!r}):")
        for h in resolve(q, sem, limit=5):
            print(f"  {h['score']:.2f} {h['kind']:5} {h['id']}  ({h['why']})")
