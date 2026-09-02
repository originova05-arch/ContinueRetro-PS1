#!/usr/bin/env bash
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
echo 'ContinueRetro-PS1 Doctor'; echo "Project: $PROJECT_ROOT"; echo "Host: $(uname -s) $(uname -m)"; echo
"$PROJECT_ROOT/scripts/verify_toolchain.sh"; STATUS=$?; echo
BASE="$PROJECT_ROOT/PRIVATE/Zoids_2/base/Zoids 2 - Heric Kyouwakoku vs. Guylos Teikoku (Japan).bin"; BIOS="$PROJECT_ROOT/PRIVATE/Zoids_2/bios/SCPH5500.BIN"
if [ -f "$BASE" ]; then G="$(sha256_cmd "$BASE"|awk '{print $1}')"; [ "$G" = 4f41fd9dc2e7f2ae2b336f9b79f7ac0311a50a651579a588923ba3976c982ceb ] && echo 'OK      Zoids 2 base image hash' || { echo 'ERROR   Zoids 2 base hash mismatch'; STATUS=1; }; else echo 'MISSING Zoids 2 private base image (not in Git by design)'; STATUS=1; fi
if [ -f "$BIOS" ]; then G="$(sha256_cmd "$BIOS"|awk '{print $1}')"; [ "$G" = 9c0421858e217805f4abe18698afea8d5aa36ff0727eb8484944e00eb5e7eadb ] && echo 'OK      SCPH5500 NTSC-J BIOS private copy' || { echo 'ERROR   BIOS hash differs'; STATUS=1; }; else echo 'MISSING SCPH5500.BIN private BIOS (not in Git by design)'; STATUS=1; fi
if [ -f "$PROJECT_ROOT/SHA256SUMS.txt" ]; then "$PROJECT_ROOT/scripts/verify_manifest.sh" || STATUS=1; else echo 'ACTION  SHA256SUMS.txt missing: run ./scripts/update_manifest.sh'; STATUS=1; fi
[ -x "$INSTALLED/xdelta3/xdelta3" ] || echo 'ACTION  xdelta3 missing: cache xdelta3-3.2.0-linux-x86_64.tar.gz (SHA-256 480295c7...) or rerun bootstrap on a networked machine; pinned source fallback is also configured.'
command -v ffmpeg >/dev/null 2>&1 || echo 'ACTION  ffmpeg missing: bootstrap can install the system package; command reference is docs/reference/ffmpeg-imagemagick.md.'
(command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1) || echo 'ACTION  imagemagick missing: bootstrap can install the system package; command reference is docs/reference/ffmpeg-imagemagick.md.'
"$PROJECT_ROOT/scripts/verify_mips_toolchain.sh" >/dev/null 2>&1 || echo 'ACTION  PS1 MIPS-I compiler path missing/broken: install clang + lld + llvm tools via bootstrap.'
[ -d "$TOOLS/src/duckstation/.git" ] || echo 'INFO    Third-party source refs are locked; full source clones are optional local cache. Use CR_FETCH_SOURCES=1 ./scripts/bootstrap.sh on a networked machine.'
if [ "$STATUS" -eq 0 ]; then echo; echo 'READY: PS1 localization toolchain healthy.'; else echo; echo 'NOT FULLY READY: see MISSING/ACTION lines above.'; fi
exit "$STATUS"
