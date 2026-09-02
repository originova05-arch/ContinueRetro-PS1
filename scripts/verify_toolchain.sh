#!/usr/bin/env bash
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
"$PROJECT_ROOT/scripts/make_wrappers.sh" >/dev/null 2>&1 || true
printf '%-18s %-9s %-48s %s\n' TOOL STATUS PATH VERSION
printf '%-18s %-9s %-48s %s\n' ------------------ --------- ------------------------------------------------ ----------------
FAIL=0
show(){ local n="$1" p="$2" v="$3"; if [ -e "$p" ]; then printf '%-18s %-9s %-48s %s\n' "$n" OK "$p" "$v"; else printf '%-18s %-9s %-48s %s\n' "$n" MISSING "$p" '-'; FAIL=1; fi; }
MK=''; for p in "$INSTALLED/mkpsxiso"/*/bin/mkpsxiso; do [ -x "$p" ] && MK="$p" && break; done
DX=''; for p in "$INSTALLED/mkpsxiso"/*/bin/dumpsxiso; do [ -x "$p" ] && DX="$p" && break; done
show mkpsxiso "${MK:-/missing}" "$( [ -n "$MK" ] && "$MK" --help 2>&1 | head -1 )"
show dumpsxiso "${DX:-/missing}" "$( [ -n "$DX" ] && "$DX" --help 2>&1 | head -1 )"
G="$INSTALLED/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless"; GV="$(grep '^application.version' "$INSTALLED/ghidra/ghidra_12.1.3_PUBLIC/Ghidra/application.properties" 2>/dev/null | head -1)"; show Ghidra "$G" "$GV"
J="$INSTALLED/jpsxdec/jpsxdec_v2.1-beta/jpsxdec.jar"; show jPSXdec "$J" '2.1-beta'
D="$INSTALLED/duckstation/squashfs-root/AppRun"; show DuckStation "$D" '0.1-11826-gfe2306b1f'
P="$INSTALLED/pcsx-redux/squashfs-root/AppRun"; show PCSX-Redux "$P" '2a36099dc'
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
F="$INSTALLED/fontkit/Continue_Retro_Thai_Game_FontKit/FONTKIT.json"; show FontKit "$F" '1.2.1'
FF="$(command -v ffmpeg 2>/dev/null || true)"
if [ -n "$FF" ]; then printf '%-18s %-9s %-48s %s\n' FFmpeg OK "$FF" "$($FF -version 2>/dev/null | head -1)"; else printf '%-18s %-9s %-48s %s\n' FFmpeg MISSING '-' '-'; FAIL=1; fi
IM="$(command -v magick 2>/dev/null || command -v convert 2>/dev/null || true)"
if [ -n "$IM" ]; then printf '%-18s %-9s %-48s %s\n' ImageMagick OK "$IM" "$($IM -version 2>/dev/null | head -1)"; else printf '%-18s %-9s %-48s %s\n' ImageMagick MISSING '-' '-'; FAIL=1; fi
if "$PROJECT_ROOT/scripts/verify_mips_toolchain.sh" >/tmp/cr_mips_verify.$$ 2>&1; then printf '%-18s %-9s %-48s %s\n' PS1-MIPS-Clang OK "$BIN/ps1-mips-cc" "$(command -v clang | xargs -r basename) MIPS-I target"; else printf '%-18s %-9s %-48s %s\n' PS1-MIPS-Clang BROKEN "$BIN/ps1-mips-cc" "$(tr '\n' ' ' </tmp/cr_mips_verify.$$ 2>/dev/null || true)"; FAIL=1; fi; rm -f /tmp/cr_mips_verify.$$
printf '\nSystem dependencies:\n'
for c in bash python3 git cmake ninja java unzip clang ld.lld llvm-objcopy llvm-objdump; do if command -v "$c" >/dev/null 2>&1; then printf '  OK      %-12s %s\n' "$c" "$(command -v "$c")"; else printf '  MISSING %-12s\n' "$c"; FAIL=1; fi; done
exit $FAIL
