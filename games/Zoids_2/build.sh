#!/usr/bin/env bash
set -euo pipefail
G="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$G/../.." && pwd)"; source "$ROOT/scripts/common.sh"
W="${CR_WORK_DIR:-$ROOT/PRIVATE/Zoids_2/work}"; O="${CR_OUTPUT_DIR:-$ROOT/PRIVATE/Zoids_2/output}"; mkdir -p "$O"; XML="$W/disc/disc.xml"
[ -f "$XML" ] || { echo 'Missing extracted disc.xml; run extract.sh first' >&2; exit 2; }
NAME="${CR_BUILD_NAME:-ZOIDS2_THAI_BUILD}"
"$ROOT/tools/bin/mkpsxiso" -y -o "$O/$NAME.bin" -c "$O/$NAME.cue" -lba "$O/lba_build.txt" "$XML"
BIN_SHA="$(sha256_cmd "$O/$NAME.bin"|awk '{print $1}')"; CUE_SHA="$(sha256_cmd "$O/$NAME.cue"|awk '{print $1}')"
KIND='translated-or-test-build'; [ ! -f "$G/patches/apply.py" ] && KIND='unmodified-roundtrip-baseline'
{
  echo "# build_kind=$KIND"; echo "$BIN_SHA  $NAME.bin"; echo "$CUE_SHA  $NAME.cue"
} > "$G/OUTPUT_SHA256.txt"
cat "$G/OUTPUT_SHA256.txt"
