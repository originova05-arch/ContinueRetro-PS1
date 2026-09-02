#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
OUT="$PROJECT_ROOT/SHA256SUMS.txt"; TMP="$OUT.tmp"; cd "$PROJECT_ROOT"
find . -type f ! -path './.git/*' ! -path './PRIVATE/*' ! -path './tools/cache/*' ! -path './tools/installed/*' ! -name SHA256SUMS.txt ! -name '*.tmp' -print0 | sort -z | while IFS= read -r -d '' f; do sha256_cmd "$f"; done > "$TMP"
mv "$TMP" "$OUT"; echo "Updated $OUT"
