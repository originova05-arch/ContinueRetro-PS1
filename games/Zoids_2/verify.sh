#!/usr/bin/env bash
set -euo pipefail
G="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$G/../.." && pwd)"; source "$ROOT/scripts/common.sh"; source "$G/config/game.env"
B="$ROOT/PRIVATE/Zoids_2/base/$BASE_BIN_NAME"; [ -f "$B" ] || { echo 'Missing private base BIN' >&2; exit 2; }
[ "$(sha256_cmd "$B"|awk '{print $1}')" = "$BASE_BIN_SHA256" ] || { echo 'FAIL base hash' >&2; exit 3; }
python3 "$ROOT/tools/src/continue-retro-ps1-utils/raw2352.py" info "$B"
W="${CR_WORK_DIR:-$ROOT/PRIVATE/Zoids_2/work}"
if [ -d "$W/disc/files" ]; then
 python3 - "$G/reference/EXTRACTED_BASE_SHA256.txt" "$W/disc/files" <<'PY'
import hashlib,pathlib,sys
bad=0; base=pathlib.Path(sys.argv[2])
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if not line.strip(): continue
    expected,rel=line.split(None,1); p=base/rel.strip(); got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got==expected: print('OK extracted',rel)
    else: print('CHANGED extracted',rel,'sha256='+got)
PY
fi
O="${CR_OUTPUT_DIR:-$ROOT/PRIVATE/Zoids_2/output}"; NAME="${CR_BUILD_NAME:-ZOIDS2_THAI_BUILD}"; OUT="$O/$NAME.bin"
if [ -f "$OUT" ]; then
 python3 "$ROOT/tools/src/continue-retro-ps1-utils/raw2352.py" info "$OUT"
 BS="$(wc -c < "$B" | tr -d ' ')"; OS="$(wc -c < "$OUT" | tr -d ' ')"; [ "$BS" = "$OS" ] && echo 'OK output byte size matches base' || { echo "WARN output size differs: base=$BS output=$OS"; exit 4; }
 if cmp -s "$B" "$OUT"; then echo 'OK output BIN is byte-identical to base (roundtrip baseline)';
 else echo 'INFO output differs from base; sector audit follows'; python3 "$ROOT/tools/src/continue-retro-ps1-utils/raw2352.py" diff-sectors "$B" "$OUT" --limit 200 || true; fi
else echo 'INFO no current output build'; fi
