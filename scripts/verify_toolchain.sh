#!/usr/bin/env bash
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
MODE=full
case "${1:-}" in
  "") ;;
  --toolchain-only) MODE=toolchain ;;
  *) echo "Usage: $0 [--toolchain-only]" >&2; exit 2 ;;
esac

"$PROJECT_ROOT/scripts/make_wrappers.sh" >/dev/null 2>&1 || true
printf '%-18s %-9s %-48s %s\n' TOOL STATUS PATH VERSION
printf '%-18s %-9s %-48s %s\n' ------------------ --------- ------------------------------------------------ ----------------
FAIL=0
show(){ local n="$1" p="$2" v="$3"; if [ -e "$p" ]; then printf '%-18s %-9s %-48s %s\n' "$n" OK "$p" "$v"; else printf '%-18s %-9s %-48s %s\n' "$n" MISSING "$p" '-'; FAIL=1; fi; }

MK=''; for p in "$INSTALLED/mkpsxiso"/*/bin/mkpsxiso; do [ -x "$p" ] && MK="$p" && break; done
DX=''; for p in "$INSTALLED/mkpsxiso"/*/bin/dumpsxiso; do [ -x "$p" ] && DX="$p" && break; done
show mkpsxiso "${MK:-/missing}" "$( [ -n "$MK" ] && "$MK" --help 2>&1 | head -1 )"
show dumpsxiso "${DX:-/missing}" "$( [ -n "$DX" ] && "$DX" --help 2>&1 | head -1 )"

G="$INSTALLED/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless"
GV="$(grep '^application.version' "$INSTALLED/ghidra/ghidra_12.1.3_PUBLIC/Ghidra/application.properties" 2>/dev/null | head -1)"
show Ghidra "$G" "$GV"
J="$INSTALLED/jpsxdec/jpsxdec_v2.1-beta/jpsxdec.jar"; show jPSXdec "$J" '2.1-beta'
D="$INSTALLED/duckstation/squashfs-root/AppRun"; show DuckStation "$D" '0.1-11826-gfe2306b1f'

P="$INSTALLED/pcsx-redux/squashfs-root/AppRun"
PV="$(find "$INSTALLED/pcsx-redux/squashfs-root" -type f -path '*/share/pcsx-redux/resources/version.json' 2>/dev/null | head -1)"
if [ -x "$P" ] && [ -n "$PV" ] && python3 - "$PV" <<'PYPCSX' >/dev/null 2>&1
import json,sys
p=json.load(open(sys.argv[1]))
assert p.get('changeset') == '2a36099dc24c5a746854e3de8359c40e5af21c10'
assert str(p.get('buildId')) == '303'
assert p.get('version') == '2a36099d'
PYPCSX
then
  printf '%-18s %-9s %-48s %s\n' PCSX-Redux OK "$P" '2a36099dc / AppDistrib build 303'
else
  printf '%-18s %-9s %-48s %s\n' PCSX-Redux BROKEN "${P:-/missing}" 'exact embedded changeset/buildId required'
  FAIL=1
fi

X="$INSTALLED/xdelta3/xdelta3"; XV=''
if [ -x "$X" ]; then
  XV="$(python3 - "$X" <<'PYXD'
import subprocess,sys
try:
    p=subprocess.run([sys.argv[1],'-V'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=3)
    out=(p.stdout or '').splitlines()
    if p.returncode==0 and out: print(out[0])
except Exception:
    pass
PYXD
)"
  if [ -n "$XV" ]; then show xdelta3 "$X" "$XV"; else printf '%-18s %-9s %-48s %s\n' xdelta3 BROKEN "$X" '-'; FAIL=1; fi
else show xdelta3 "$X" "$XV"; fi

F="$INSTALLED/fontkit/Continue_Retro_Thai_Game_FontKit/FONTKIT.json"
if [ "$MODE" = toolchain ]; then
  if [ -f "$F" ]; then printf '%-18s %-9s %-48s %s\n' FontKit OK "$F" '1.2.1 user asset'; else printf '%-18s %-9s %-48s %s\n' FontKit OPTIONAL "$F" 'restore before game/font work'; fi
else
  show FontKit "$F" '1.2.1'
fi

UTIL="$TOOLS/src/continue-retro-ps1-utils"
UTIL_OK=1
for u in raw2352.py disc_manifest.py psxexe_info.py sjis_scan.py; do [ -f "$UTIL/$u" ] || UTIL_OK=0; done
if [ "$UTIL_OK" -eq 1 ]; then printf '%-18s %-9s %-48s %s\n' PS1-Utils OK "$UTIL" 'repo utilities'; else printf '%-18s %-9s %-48s %s\n' PS1-Utils MISSING "$UTIL" '-'; FAIL=1; fi

LLVM="$INSTALLED/llvm-17.0.6"
LLVM_OK=1
for p in "$LLVM/bin/clang" "$LLVM/bin/ld.lld" "$LLVM/bin/llvm-objcopy" "$LLVM/bin/llvm-objdump" "$LLVM/lib/clang/17/include"; do [ -e "$p" ] || LLVM_OK=0; done
if [ "$LLVM_OK" -eq 1 ]; then printf '%-18s %-9s %-48s %s\n' LLVM-Portable OK "$LLVM" "$($LLVM/bin/clang --version 2>/dev/null | head -1)"; else printf '%-18s %-9s %-48s %s\n' LLVM-Portable MISSING "$LLVM" '17.0.6 recovery artifact required'; FAIL=1; fi

FF="$(command -v ffmpeg 2>/dev/null || true)"
if [ -n "$FF" ]; then printf '%-18s %-9s %-48s %s\n' FFmpeg OK "$FF" "$($FF -version 2>/dev/null | head -1)"; else printf '%-18s %-9s %-48s %s\n' FFmpeg MISSING '-' '-'; FAIL=1; fi
IM="$(command -v magick 2>/dev/null || command -v convert 2>/dev/null || true)"
if [ -n "$IM" ]; then printf '%-18s %-9s %-48s %s\n' ImageMagick OK "$IM" "$($IM -version 2>/dev/null | head -1)"; else printf '%-18s %-9s %-48s %s\n' ImageMagick MISSING '-' '-'; FAIL=1; fi

mkdir -p "$TOOLS/build"
MIPS_LOG="$TOOLS/build/mips_verify.$$.log"
if [ "$LLVM_OK" -eq 1 ] && "$PROJECT_ROOT/scripts/verify_mips_toolchain.sh" >"$MIPS_LOG" 2>&1; then
  printf '%-18s %-9s %-48s %s\n' PS1-MIPS-Clang OK "$BIN/ps1-mips-cc" 'portable LLVM 17.0.6 MIPS-I target'
else
  printf '%-18s %-9s %-48s %s\n' PS1-MIPS-Clang BROKEN "$BIN/ps1-mips-cc" "$(tr '\n' ' ' <"$MIPS_LOG" 2>/dev/null || true)"
  FAIL=1
fi
rm -f "$MIPS_LOG"

printf '\nSystem dependencies (must not resolve under /tmp or /usr/local):\n'
for c in bash python3 git cmake ninja java unzip; do
  PTH="$(command -v "$c" 2>/dev/null || true)"
  if [ -z "$PTH" ]; then printf '  MISSING %-12s\n' "$c"; FAIL=1
  elif [[ "$PTH" == /tmp/* || "$PTH" == /usr/local/* ]]; then printf '  FORBID  %-12s %s\n' "$c" "$PTH"; FAIL=1
  else printf '  OK      %-12s %s\n' "$c" "$PTH"; fi
done
exit $FAIL
