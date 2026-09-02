#!/usr/bin/env bash
set -euo pipefail
G="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$G/../.." && pwd)"; source "$ROOT/scripts/common.sh"; source "$G/config/game.env"
BD="${CR_BASE_DIR:-$ROOT/PRIVATE/Zoids_2/base}"; BINFILE="$BD/$BASE_BIN_NAME"; CUEFILE="$BD/$BASE_CUE_NAME"
[ -f "$BINFILE" ] || { echo "Missing $BINFILE" >&2; exit 2; }; [ -f "$CUEFILE" ] || { echo "Missing $CUEFILE" >&2; exit 2; }
[ "$(sha256_cmd "$BINFILE"|awk '{print $1}')" = "$BASE_BIN_SHA256" ] || { echo 'Base BIN SHA-256 mismatch' >&2; exit 3; }
[ "$(sha256_cmd "$CUEFILE"|awk '{print $1}')" = "$BASE_CUE_SHA256" ] || { echo 'Base CUE SHA-256 mismatch' >&2; exit 3; }
W="${CR_WORK_DIR:-$ROOT/PRIVATE/Zoids_2/work}"; rm -rf "$W/disc"; mkdir -p "$W/disc"
"$ROOT/tools/bin/dumpsxiso" -x "$W/disc/files" -s "$W/disc/disc.xml" -l "$CUEFILE"
python3 "$ROOT/tools/src/continue-retro-ps1-utils/disc_manifest.py" "$W/disc/disc.xml" -o "$W/disc/lba_map.csv"
python3 - "$G/reference/EXTRACTED_BASE_SHA256.txt" "$W/disc/files" <<'PY'
import hashlib,pathlib,sys
mf=pathlib.Path(sys.argv[1]); base=pathlib.Path(sys.argv[2]); bad=0
for line in mf.read_text().splitlines():
    if not line.strip(): continue
    expected,rel=line.split(None,1); p=base/rel.strip(); h=hashlib.sha256(p.read_bytes()).hexdigest()
    if h!=expected: print('FAIL extracted hash',rel); bad=1
    else: print('OK extracted hash',rel)
raise SystemExit(bad)
PY
echo "Extracted reproducibly: $W/disc"
