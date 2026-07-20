"""Per-field channel distances, each bounded to [0, 1] and deterministic."""
from __future__ import annotations

import re

# comp@1 units squashed to [0, 1]: Si vs C is 10 Pettifor units, a full
# cross-block swap is more; 25 is the versioned saturation scale.
MATERIAL_SCALE = 25.0

_WORD = re.compile(r"[^A-Za-z0-9.]+")
_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


def _parse_material(material: str | None) -> dict | None:
    """The same strict rule as the site mirror: a capitalized word must
    tokenize fully into element symbols (a-Si gives Si, SWCNT refuses)."""
    from pymatgen.core import Element

    if not material:
        return None
    comp: dict[str, float] = {}
    found = False
    for word in filter(None, _WORD.split(str(material))):
        if not word[0].isupper():
            continue
        consumed = 0
        local: dict[str, float] = {}
        for m in _TOKEN.finditer(word):
            if m.start() != consumed:
                break
            # D and T are pymatgen isotope aliases, never formula symbols in
            # material names; admitting them would parse SWCNT as S+W+C+N+T.
            if m.group(1) in ("D", "T"):
                break
            try:
                Element(m.group(1))
            except ValueError:
                break
            local[m.group(1)] = local.get(m.group(1), 0.0) + (float(m.group(2)) if m.group(2) else 1.0)
            consumed = m.end()
        if consumed != len(word):
            return None
        for el, amt in local.items():
            comp[el] = comp.get(el, 0.0) + amt
            found = True
    return comp if found else None


def material_distance(a: str | None, b: str | None) -> float:
    if a is None and b is None:
        return 0.0
    if a is None or b is None:
        return 1.0
    if str(a).strip().lower() == str(b).strip().lower():
        return 0.0
    ca, cb = _parse_material(a), _parse_material(b)
    if ca is None or cb is None:
        return 1.0
    from omdc.metrics.comp import elmd

    return min(elmd(ca, cb) / MATERIAL_SCALE, 1.0)


def _pair(x, y) -> float:
    num_x = isinstance(x, (int, float)) and not isinstance(x, bool)
    num_y = isinstance(y, (int, float)) and not isinstance(y, bool)
    if num_x and num_y:
        scale = (abs(x) + abs(y)) / 2.0 or 1.0
        return min(abs(x - y) / scale, 1.0)
    return 0.0 if x == y else 1.0


def mapping_distance(a: dict | None, b: dict | None) -> float:
    a, b = a or {}, b or {}
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    total = 0.0
    for k in keys:
        if k in a and k in b:
            total += _pair(a[k], b[k])
        else:
            total += 1.0
    return total / len(keys)


def categorical(a, b) -> float:
    if a is None and b is None:
        return 0.0
    return 0.0 if a == b else 1.0
