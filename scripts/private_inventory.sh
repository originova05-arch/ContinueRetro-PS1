#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
OUT="${1:-$PROJECT_ROOT/PRIVATE/PRIVATE_SHA256SUMS.txt}"; TMP="$OUT.tmp"; mkdir -p "$(dirname "$OUT")"; cd "$PROJECT_ROOT"
find PRIVATE -type f ! -name PRIVATE_SHA256SUMS.txt -print0 | sort -z | while IFS= read -r -d '' f; do sha256_cmd "$f"; done > "$TMP"
mv "$TMP" "$OUT"; echo "Updated $OUT (private; Git-ignored)"
