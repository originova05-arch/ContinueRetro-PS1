#!/usr/bin/env bash
set -euo pipefail
G="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$G/../.." && pwd)"; W="${CR_WORK_DIR:-$ROOT/PRIVATE/Zoids_2/work}"
[ -f "$W/disc/disc.xml" ] || { echo 'Run extract.sh first' >&2; exit 2; }
if [ -f "$G/patches/apply.py" ]; then python3 "$G/patches/apply.py" "$W/disc/files"; else echo 'No stable tracked translation patch payload yet; files left unmodified.'; fi
