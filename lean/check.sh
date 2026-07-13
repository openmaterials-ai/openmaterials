#!/bin/bash
# Compile the generated Lean files against PhysLean. Run on a machine with a
# Lean toolchain and PhysLean built (see lean/README). Regenerate first with
# `python -m omai.map_data`, then run this from the repo root.
#
# Usage: bash lean/check.sh /path/to/PhysLean
set -e
PHYSLEAN="${1:-PhysLean}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.elan/bin:$PATH"

if [ ! -d "$PHYSLEAN/.lake" ]; then
  echo "PhysLean not built at $PHYSLEAN (run 'lake exe cache get && lake build Physlib.Units.Basic' there)"; exit 1
fi

fail=0
for f in OpenMaterials OpenMaterialsIdentities OpenMaterialsUnits; do
  src="$REPO/lean/$f.lean"
  [ -f "$src" ] || { echo "MISSING $src"; fail=1; continue; }
  cp "$src" "$PHYSLEAN/$f.lean"
  echo -n "compiling $f.lean ... "
  if (cd "$PHYSLEAN" && lake env lean "$f.lean" 2>&1 | grep -qiE "error|sorry"); then
    echo "FAIL"; (cd "$PHYSLEAN" && lake env lean "$f.lean" 2>&1 | grep -iE "error|sorry" | head -5); fail=1
  else
    echo "ok"
  fi
  rm -f "$PHYSLEAN/$f.lean"
done
[ "$fail" = 0 ] && echo "all Lean files compile against PhysLean" || { echo "some files failed"; exit 1; }
