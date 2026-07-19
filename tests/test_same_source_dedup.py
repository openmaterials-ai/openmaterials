"""The same-source near-duplicate gate.

Exact duplicates within one source are impossible by construction (same
canonical lineage, same id). This gate closes the phrasing gap: two committed
instances from the SAME in-hash source carrying the same node, material, and
headline value under differently-phrased conditions are near-certainly one
claim written twice, and the commons refuses them at commit time. A paper
genuinely reporting one number under two protocols earns an entry in the
documented allowlist instead.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

_INSTANCES = Path(__file__).resolve().parents[1] / "docs" / "data" / "instances"

# (source, node, material, value) tuples reviewed and accepted as genuinely
# distinct despite matching on the headline fields. Empty today.
ALLOWED = set()


def test_no_same_source_near_duplicates():
    groups = defaultdict(list)
    for f in sorted(_INSTANCES.glob("*.json")):
        rec = json.loads(f.read_text())
        lin = rec.get("lineage") or {}
        src = lin.get("source")
        if not (isinstance(src, str) and ":" in src):
            continue   # no in-hash source, no namespace to dedup within
        mat = lin.get("material")
        mat = mat if isinstance(mat, str) else (mat or {}).get("name")
        val = (lin.get("values") or {}).get("value")
        key = (src, lin.get("node"), mat, val)
        groups[key].append((f.name, rec.get("id")))
    offenders = {k: v for k, v in groups.items()
                 if len(v) > 1 and k not in ALLOWED}
    assert not offenders, (
        "same-source near-duplicates (same source, node, material, value; "
        f"different ids): {offenders}")
