#!/bin/bash
# Build the generated Lean proof layer. lean/ is a standalone lake package
# depending on physlib (leanprover-community/physlib, pinned in lakefile.toml),
# so no external checkout is needed. Regenerate the .lean files first with
# `python -m omai.map_data` (or the individual omai.physlean_export /
# omai.lean_identities / omai.lean_units modules), then run this from anywhere.
#
# Usage: bash lean/check.sh [--no-cache]
#   --no-cache  skip `lake exe cache get` (e.g. CI runners with a warm .lake,
#               or offline machines where the cache was already fetched)
set -e
LEAN_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.elan/bin:$PATH"

cd "$LEAN_DIR"
if [ "$1" != "--no-cache" ]; then
  lake exe cache get
fi
lake build
echo "all Lean files compile against physlib"
