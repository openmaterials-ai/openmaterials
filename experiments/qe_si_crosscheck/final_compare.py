#!/usr/bin/env python
"""Final comparison: check A (ph.x direct vs matdyn) and check B (matdyn DFPT vs phonopy FD)."""
import numpy as np

# matdyn interpolated (from si.freq), cm^-1, asr='simple'
matdyn = {
    "Gamma": [-0.0000, -0.0000, 0.0000, 513.6242, 513.6242, 513.6242],
    "X":     [137.6733, 137.6733, 409.0031, 409.0031, 461.9577, 461.9577],
    "L":     [105.6555, 105.6555, 371.7840, 414.0318, 489.9460, 489.9460],
}
# phonopy FD ASR-symmetrized, cm^-1
phon = {
    "Gamma": [0.0, 0.0, 0.0, 513.229, 513.229, 513.229],
    "X":     [136.048, 136.048, 408.469, 408.469, 461.53, 461.53],
    "L":     [103.562, 103.562, 371.189, 413.346, 489.536, 489.536],
}
# ph.x DIRECT Gamma (si.dyn1), cm^-1  (raw DFPT, no ASR)
phx_gamma = [3.727868, 3.727868, 3.727868, 513.637717, 513.637717, 513.637717]

print("===== CHECK A: ph.x direct vs matdyn interpolated at Gamma (cm^-1) =====")
md = sorted(matdyn["Gamma"]); px = sorted(phx_gamma)
print("%4s %12s %10s %9s" % ("mode", "ph.x-direct", "matdyn", "|delta|"))
maxo = 0.0
for i, (a, b) in enumerate(zip(px, md), 1):
    d = abs(a - b)
    print("%4d %12.4f %10.4f %9.4f" % (i, a, b, d))
    if i >= 4:
        maxo = max(maxo, d)
print("Max |delta| optical (ASR-insensitive): %.4f cm^-1" % maxo)
print("Acoustic: ph.x raw %.3f (no ASR) vs matdyn %.4f (asr=simple)." % (px[0], md[0]))

print()
print("===== CHECK B: matdyn (DFPT) vs phonopy (FD) at Gamma/X/L (cm^-1) =====")
allmax = 0.0
rows = []
for q in ["Gamma", "X", "L"]:
    a = sorted(matdyn[q]); b = sorted(phon[q])
    for i, (x, y) in enumerate(zip(a, b), 1):
        d = abs(x - y); allmax = max(allmax, d)
        rows.append((q, i, x, y, d))
        print("%6s m%d: matdyn=%9.3f phonopy=%9.3f |d|=%6.3f" % (q, i, x, y, d))
print("MAX |delta| over all q,modes = %.3f cm^-1" % allmax)
