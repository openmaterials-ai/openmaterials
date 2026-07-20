"""The distance layer's published data: docs/data/distances.json.

The site's Distance tab renders this file; nothing on the page is hardcoded.
Two sections:

- ``registry``: the machine-readable metric registry, read from
  ``omdc.DISTANCES`` itself (ids, versions, descriptions, axioms,
  invariances, cost class, ANN-indexability, the default alias). The table on
  the site IS the registry, so the two can never drift.
- ``zoo``: the quickstart's silicon demonstration (diamond against strained,
  fcc, glass, vacancy) computed fresh on the hist encoder across every
  registered channel. It is ILLUSTRATIVE and labeled so in the payload: the
  structures are constructed, not committed evidence. Deterministic (seeded
  glass, deterministic FPS), so regeneration is byte-stable.
- ``committed``: pairwise default-metric distances between committed
  configuration records, when two or more exist. Today the commons holds one
  configuration, so this section carries the honest count and an empty list;
  it grows by itself as configurations land.

The writer needs the ``distance`` extras (POT and friends); the build wraps
it in the same skipped-when-absent idiom as the lean exports, and the
committed JSON remains the served artifact either way.
"""
from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DOCS = _REPO / "docs"


def _registry():
    import omdc

    rows = []
    for key, spec in omdc.DISTANCES.items():
        rows.append({
            "key": key,
            "id": spec.id,
            "version": spec.version,
            "description": spec.description,
            "metric": bool(spec.metric),
            "ann_indexable": bool(spec.ann_indexable),
            "invariances": sorted(spec.invariances),
            "cost": spec.cost,
            "extra": spec.extra,
            "input": spec.input,
            "lower_bounds": sorted(spec.lower_bounds),
        })
    rows.sort(key=lambda r: r["key"])
    return {"default": omdc.DEFAULT_ALIAS, "distances": rows}


def _zoo():
    import numpy as np
    import omdc
    from pymatgen.core import Lattice, Structure

    diamond = Structure.from_spacegroup("Fd-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    strained = diamond.copy()
    strained.apply_strain(0.01)
    fcc = Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.87), ["Si"], [[0, 0, 0]])
    big = diamond * (3, 3, 3)
    rng = np.random.default_rng(1)
    glass = Structure(
        big.lattice, big.species,
        big.cart_coords + rng.normal(0, 0.5, (len(big), 3)),
        coords_are_cartesian=True)
    vacancy = big.copy()
    vacancy.remove_sites([0])

    zoo = [("strained 1%", strained), ("fcc", fcc), ("glass", glass), ("vacancy", vacancy)]
    # the zoo feeds STRUCTURES; only structure-input channels belong in it
    channels = [s for s in omdc.DISTANCES.values() if s.input == "structure"]
    rows = []
    for name, s in zoo:
        cells = {}
        for spec in channels:
            kwargs = {"metric": spec.id}
            if spec.needs_encoder:
                kwargs["encoder"] = "hist"
            d = omdc.distance(diamond, s, **kwargs)
            cells[spec.id] = None if (isinstance(d, float) and math.isinf(d)) else round(float(d), 6)
        rows.append({"name": name, "distances": cells})
    return {
        "illustrative": True,
        "note": ("constructed silicon cells against Si diamond, hist encoder; "
                 "a demonstration of the channels, not committed evidence"),
        "reference": "Si diamond (a=5.43 A)",
        "encoder": "hist",
        "rows": rows,
    }


def _committed_pairs():
    import omdc
    from pymatgen.core import Structure

    cfg_path = _DOCS / "data" / "configurations.json"
    configs = json.loads(cfg_path.read_text()) if cfg_path.exists() else []
    usable = []
    for c in configs if isinstance(configs, list) else []:
        st = c.get("structure")
        uid = (c.get("canonical") or {}).get("uid")
        if st and uid:
            try:
                usable.append((c.get("name") or uid[:12], uid, Structure.from_dict(st)))
            except Exception:
                continue
    pairs = []
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            d = omdc.distance(usable[i][2], usable[j][2], encoder="hist")
            pairs.append({
                "a": {"name": usable[i][0], "uid": usable[i][1][:12]},
                "b": {"name": usable[j][0], "uid": usable[j][1][:12]},
                "distance": round(float(d), 6),
            })
    return {"configurations": len(usable), "metric": "env-ot@1", "encoder": "hist", "pairs": pairs}


def write_distances(out: Path | None = None):
    out = out or _DOCS / "data" / "distances.json"
    payload = {
        "registry": _registry(),
        "zoo": _zoo(),
        "committed": _committed_pairs(),
    }
    out.write_text(json.dumps(payload))
    return out, {"distances": len(payload["registry"]["distances"]),
                 "zoo_rows": len(payload["zoo"]["rows"]),
                 "committed_pairs": len(payload["committed"]["pairs"])}
